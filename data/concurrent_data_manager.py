"""
并发版数据库数据管理器 - 支持多线程批量拉取
保留完整状态管理 + 错误处理 + 性能提升
"""
import os
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.db_connector import PostgresConnector, RedisConnector

from .ths_adapter import ThsAdapter


class ConcurrentDatabaseDataManager:
    """
    并发版数据库数据管理器
    
    特性:
    1. 多线程并发拉取 (默认6线程)
    2. 保留完整状态管理 (start/update/end)
    3. 分级错误处理 + 重试机制
    4. 批量入库优化 (execute_values)
    5. 实时进度回调
    """

    def __init__(
        self,
        ths_config: dict | None = None,
        pg_host: str = 'localhost',
        pg_port: int = 5432,
        pg_database: str = 'quant_analysis',
        pg_username: str | None = None,  # 读取 PG_USERNAME 环境变量
        pg_password: str | None = None,  # 读取 PG_PASSWORD 环境变量
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        enable_cache: bool = True,
        cache_ttl: int = 14400,
        max_workers: int | None = None,  # None=自动按设备档位（PerformanceAdaptor）
        rate_limit: float = 0.05         # 每线程间隔(秒)
    ):
        # 自动适配并发数
        if max_workers is None:
            try:
                from utils.performance_adaptor import get_adaptor
                max_workers = get_adaptor().data_fetch_workers
            except Exception:
                max_workers = 3

        # THS API
        self.ths = ThsAdapter(ths_config or {'enabled': True, 'timeout': 30})
        
        # PostgreSQL
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_database = pg_database
        self.pg_username = pg_username
        self.pg_password = pg_password
        self._pg = None  # 延迟连接
        
        # Redis
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        self.redis = None
        if enable_cache:
            try:
                self.redis = RedisConnector(host=redis_host, port=redis_port)
                self.redis.connect()
            except Exception:
                self.redis = None
        
        # 并发配置
        self.max_workers = max_workers
        self.rate_limit = rate_limit
        
        # 统计
        self.stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_records': 0
        }
        self.stats_lock = threading.Lock()
        
        # 进度回调
        self.progress_callback: Callable | None = None

    @property
    def pg(self):
        """延迟连接PostgreSQL"""
        if self._pg is None:
            self._pg = PostgresConnector(
                host=self.pg_host, port=self.pg_port, database=self.pg_database,
                username=self.pg_username, password=self.pg_password
            )
            self._pg.connect()
        return self._pg

    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数 callback(current, total, stats)"""
        self.progress_callback = callback

    def sync_symbols_concurrent(
        self,
        symbols: list[str],
        start_year: int = 2000,
        end_year: int | None = None,
        use_cache: bool = True,
        progress_interval: int = 10
    ) -> dict:
        """
        并发同步多只股票的历史数据
        
        Args:
            symbols: 股票代码列表
            start_year: 开始年份
            end_year: 结束年份(默认今年)
            use_cache: 是否使用本地缓存
            progress_interval: 进度报告间隔(秒)
            
        Returns:
            {'success': int, 'failed': int, 'skipped': int, 'total_records': int}
        """
        if not end_year:
            end_year = datetime.now().year
        
        end_date = f"{end_year}-12-31"
        
        print(f"\n🚀 并发同步 {len(symbols)} 只股票")
        print(f"   线程数: {self.max_workers} | 年份: {start_year}-{end_year}")
        print("-" * 60)
        
        start_time = time.time()
        last_report = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._sync_single,
                    symbol,
                    start_year,
                    end_year,
                    end_date,
                    use_cache
                ): symbol for symbol in symbols
            }
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    result = future.result()
                    
                    # 更新统计
                    if result['status'] == 'success':
                        with self.stats_lock:
                            self.stats['success'] += 1
                            self.stats['total_records'] += result.get('records', 0)
                    elif result['status'] == 'skipped':
                        with self.stats_lock:
                            self.stats['skipped'] += 1
                    else:
                        with self.stats_lock:
                            self.stats['failed'] += 1
                    
                    # 进度报告
                    if time.time() - last_report > progress_interval:
                        self._report_progress(len(symbols), start_time)
                        last_report = time.time()
                        
                except Exception as e:
                    print(f"   ⚠️ {symbol} 异常: {e}")
                    with self.stats_lock:
                        self.stats['failed'] += 1
        
        # 最终报告
        self._report_progress(len(symbols), start_time, final=True)
        
        return dict(self.stats)

    def _sync_single(
        self,
        symbol: str,
        start_year: int,
        end_year: int,
        end_date: str,
        use_cache: bool,
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> dict:
        """同步单只股票（线程安全），含指数退避重试"""
        # 1. 检查数据库是否已有完整数据
        if not use_cache:
            db_data = self._query_database(symbol, f"{start_year}-01-01", end_date)
            if not db_data.empty and len(db_data) > 100:
                return {'symbol': symbol, 'status': 'skipped', 'records': len(db_data)}

        # 2. 每个线程创建独立的THS实例（线程安全）
        ths = ThsAdapter({'enabled': True, 'timeout': 30})

        last_error = None
        for attempt in range(max_retries):
            try:
                # 3. 从THS拉取
                df = ths.get_full_history(symbol, start_year, end_year)

                if df is None or df.empty:
                    return {'symbol': symbol, 'status': 'no_data', 'records': 0}

                # 4. 过滤日期
                df = df[df['date'] <= end_date]

                # 5. 写入数据库（每个线程独立连接）
                self._save_to_database(symbol, df)

                # 6. 限速
                time.sleep(self.rate_limit)

                return {
                    'symbol': symbol,
                    'status': 'success',
                    'records': len(df),
                    'start': df['date'].min(),
                    'end': df['date'].max()
                }

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = base_delay * (2 ** attempt)   # 指数退避：1s, 2s, 4s
                    time.sleep(wait)
                # 否则循环结束，返回 error

        return {'symbol': symbol, 'status': 'error',
                'error': str(last_error), 'records': 0}

    def _query_database(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据库查询（线程安全）"""
        query = """
            SELECT date, open, high, low, close, volume, amount
            FROM market_data
            WHERE symbol = %s AND date BETWEEN %s AND %s
            ORDER BY date
        """
        try:
            # 每个线程使用独立连接
            pg = PostgresConnector(
                host=self.pg_host, port=self.pg_port, database=self.pg_database,
                username=self.pg_username, password=self.pg_password
            )
            pg.connect()
            results = pg.execute(query, (symbol, start_date, end_date), fetch=True)
            pg.disconnect()
            
            if results:
                df = pd.DataFrame(results)
                for col in ['open', 'high', 'low', 'close', 'amount']:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                if 'volume' in df.columns:
                    df['volume'] = df['volume'].astype(int)
                return df
        except Exception as e:
            pass
        
        return pd.DataFrame()

    def _save_to_database(self, symbol: str, df: pd.DataFrame):
        """批量保存到数据库（使用execute_values优化）"""
        if df.empty:
            return
        
        try:
            from psycopg2.extras import execute_values
            
            records = [
                (symbol, row['date'], float(row['open']), float(row['high']),
                 float(row['low']), float(row['close']), int(row['volume']),
                 float(row.get('amount', 0)), 'THS')
                for _, row in df.iterrows()
            ]
            
            # 每个线程使用独立连接
            pg = PostgresConnector(
                host=self.pg_host, port=self.pg_port, database=self.pg_database,
                username=self.pg_username, password=self.pg_password
            )
            pg.connect()
            
            # 使用上下文管理器获取连接
            with pg.get_connection() as conn:
                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        '''INSERT INTO market_data (symbol, date, open, high, low, close, volume, amount, data_source)
                           VALUES %s ON CONFLICT (symbol, date) DO NOTHING''',
                        records
                    )
            
            pg.disconnect()
            
        except Exception as e:
            print(f"   ⚠️ {symbol} 入库失败: {e}")

    def _report_progress(self, total: int, start_time: float, final: bool = False):
        """报告进度"""
        elapsed = time.time() - start_time
        done = self.stats['success'] + self.stats['failed'] + self.stats['skipped']
        rate = done / elapsed * 60 if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        
        status = "✅ 完成" if final else "⏳ 进度"
        print(f"\n{status}: {done}/{total} ({done/total*100:.1f}%) | "
              f"速度: {rate:.1f}只/分钟 | 预计剩余: {eta/60:.1f}分钟 | "
              f"✅{self.stats['success']} ❌{self.stats['failed']} ⏭️{self.stats['skipped']}")
        
        # 回调
        if self.progress_callback:
            self.progress_callback(done, total, dict(self.stats))

    def get_stock_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """单只股票查询（兼容原版接口）"""
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        # 尝试缓存
        if not force_refresh and self.enable_cache and self.redis:
            cache_key = f"stock:{symbol}:{start_date}:{end_date}"
            cached = self.redis.get_cache(cache_key)
            if cached:
                return pd.DataFrame(cached)
        
        # 查询数据库
        db_data = self._query_database(symbol, start_date, end_date)
        if not db_data.empty:
            return db_data
        
        # 从THS获取
        try:
            df = self.ths.get_full_history(symbol)
            if not df.empty:
                df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
                self._save_to_database(symbol, df)
                return df
        except Exception as e:
            print(f"THS获取失败: {e}")
        
        return pd.DataFrame()

    def close(self):
        """关闭连接"""
        if self._pg:
            self._pg.disconnect()
        if self.redis:
            self.redis.disconnect()


# ==================== 便捷函数 ====================

def sync_selfselect_concurrent(
    symbols: list[str] | None = None,
    max_workers: int = 6,
    years: int = 30
) -> dict:
    """
    并发同步自选股数据
    
    Args:
        symbols: 股票列表(None则自动获取)
        max_workers: 并发线程数
        years: 拉取年数(默认30年，从上市开始)
        
    Returns:
        同步结果统计
    """
    # 如果没有提供列表，尝试从妙想获取
    if symbols is None:
        try:
            import requests
            resp = requests.post(
                'https://mkapi2.dfcfs.com/finskillshub/api/claw/self-select/get',
                headers={
                    'Content-Type': 'application/json',
                    'apikey': os.environ.get('MX_APIKEY', '')
                },
                timeout=30
            )
            data = resp.json()
            if data.get('code') == 0:
                stocks = data.get('data', {}).get('allResults', {}).get('result', {}).get('dataList', [])
                symbols = [s.get('SECURITY_CODE') for s in stocks]
        except Exception as e:
            print(f"获取自选股失败: {e}")
            return {'error': str(e)}
    
    if not symbols:
        print("没有可同步的股票")
        return {'success': 0, 'failed': 0, 'skipped': 0, 'total_records': 0}
    
    print("=" * 60)
    print("🚀 自选股并发同步")
    print("=" * 60)
    
    end_year = datetime.now().year
    start_year = end_year - years
    
    mgr = ConcurrentDatabaseDataManager(max_workers=max_workers)
    result = mgr.sync_symbols_concurrent(symbols, start_year, end_year)
    mgr.close()
    
    print("\n" + "=" * 60)
    print("✅ 同步完成!")
    print(f"   成功: {result['success']}只")
    print(f"   失败: {result['failed']}只")
    print(f"   跳过: {result['skipped']}只")
    print(f"   总记录: {result['total_records']:,}条")
    print("=" * 60)
    
    return result


# ==================== 测试 ====================

if __name__ == '__main__':
    # 测试并发同步
    test_symbols = ['000001', '000002', '000333', '000858', '600519', '600036']
    
    mgr = ConcurrentDatabaseDataManager(max_workers=3)
    result = mgr.sync_symbols_concurrent(test_symbols, 2020, 2026)
    mgr.close()
    
    print(f"\n测试结果: {result}")
