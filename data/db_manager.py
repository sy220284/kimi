"""
数据库优先的数据管理器
默认从数据库读取，缺失时从THS获取并写入数据库
"""
from datetime import datetime, timedelta

import pandas as pd

from utils.db_connector import PostgresConnector, RedisConnector

from .ths_adapter import ThsAdapter


class DatabaseDataManager:
    """
    数据库优先数据管理器

    策略:
    1. 读: 先查数据库 → 无数据则调THS API → 写入数据库 → 返回
    2. 写: THS获取的数据自动持久化到数据库
    3. 缓存: Redis作为二级缓存加速
    """

    def __init__(
        self,
        ths_config: dict | None = None,
        pg_host: str = 'localhost',
        pg_port: int = 5432,
        pg_database: str = 'quant_analysis',
        pg_username: str = 'quant_user',
        pg_password: str = 'quant_password',
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        enable_cache: bool = True,
        cache_ttl: int = 14400  # 4小时
    ):
        # THS API (备用源)
        self.ths = ThsAdapter(ths_config or {'enabled': True, 'timeout': 30})

        # PostgreSQL (主存储)
        self.pg = PostgresConnector(
            host=pg_host, port=pg_port, database=pg_database,
            username=pg_username, password=pg_password
        )
        self.pg.connect()

        # Redis (缓存)
        self.enable_cache = enable_cache
        self.cache_ttl = cache_ttl
        if enable_cache:
            self.redis = RedisConnector(host=redis_host, port=redis_port)
            self.redis.connect()
        else:
            self.redis = None

    def get_stock_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        获取股票数据 (数据库优先)

        Args:
            symbol: 股票代码
            start_date: 开始日期 (默认一年前)
            end_date: 结束日期 (默认今天)
            force_refresh: 强制从API刷新

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount
        """
        # 默认日期范围
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        # 1. 尝试从Redis缓存读取
        if not force_refresh and self.enable_cache:
            cache_key = f"stock:{symbol}:{start_date}:{end_date}"
            cached = self.redis.get_cache(cache_key) if self.redis else None
            if cached:
                return pd.DataFrame(cached)

        # 2. 尝试从PostgreSQL读取
        if not force_refresh:
            db_data = self._query_database(symbol, start_date, end_date)
            if not db_data.empty:
                # 检查数据完整性
                if self._check_data_completeness(db_data, start_date, end_date):
                    # 写入缓存
                    if self.enable_cache and self.redis:
                        cache_key = f"stock:{symbol}:{start_date}:{end_date}"
                        self.redis.set_cache(cache_key, db_data.to_dict('records'), self.cache_ttl)
                    return db_data

        # 3. 从THS API获取 (先用完整历史接口，因为get_daily_kline有日期限制)
        try:
            # 计算年份
            start_year = datetime.strptime(start_date, '%Y-%m-%d').year
            end_year = datetime.strptime(end_date, '%Y-%m-%d').year
            api_data = self.ths.get_full_history(symbol, start_year, end_year)

            # 过滤日期范围
            if not api_data.empty:
                api_data = api_data[(api_data['date'] >= start_date) & (api_data['date'] <= end_date)]
        except Exception as e:
            print(f"THS获取失败: {e}")
            api_data = pd.DataFrame()

        if api_data.empty:
            # API也失败，返回数据库中有的数据
            return self._query_database(symbol, start_date, end_date)

        # 4. 写入数据库
        self._save_to_database(symbol, api_data)

        # 5. 写入缓存
        if self.enable_cache and self.redis:
            cache_key = f"stock:{symbol}:{start_date}:{end_date}"
            self.redis.set_cache(cache_key, api_data.to_dict('records'), self.cache_ttl)

        return api_data

    def _query_database(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据库查询"""
        query = """
            SELECT date, open, high, low, close, volume, amount
            FROM market_data
            WHERE symbol = %s AND date BETWEEN %s AND %s
            ORDER BY date
        """
        try:
            results = self.pg.execute(query, (symbol, start_date, end_date), fetch=True)
            if results:
                df = pd.DataFrame(results)
                # 转换Decimal为float
                for col in ['open', 'high', 'low', 'close', 'amount']:
                    if col in df.columns:
                        df[col] = df[col].astype(float)
                if 'volume' in df.columns:
                    df['volume'] = df['volume'].astype(int)
                return df
        except Exception as e:
            print(f"数据库查询失败: {e}")

        return pd.DataFrame()

    def _save_to_database(self, symbol: str, df: pd.DataFrame):
        """保存到数据库"""
        if df.empty:
            return

        try:
            for _, row in df.iterrows():
                self.pg.insert_market_data(
                    symbol=symbol,
                    date=row['date'],
                    open_price=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']),
                    amount=float(row.get('amount', 0)),
                    source='THS'
                )
        except Exception as e:
            print(f"数据库写入失败: {e}")

    def _check_data_completeness(self, df: pd.DataFrame, start_date: str, end_date: str) -> bool:
        """检查数据完整性 (是否有明显缺失)"""
        if df.empty:
            return False

        # 计算交易日数量 (粗略估计)
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        expected_days = (end - start).days * 0.6  # 假设60%是交易日

        # 实际数据量应该接近预期
        return len(df) >= expected_days * 0.8  # 允许20%缺失

    def get_full_history(
        self,
        symbol: str,
        start_year: int = 2000,
        end_year: int | None = None
    ) -> pd.DataFrame:
        """获取完整历史数据"""
        if not end_year:
            end_year = datetime.now().year

        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"

        return self.get_stock_data(symbol, start_date, end_date)

    def sync_symbol(self, symbol: str, years: int = 5) -> int:
        """
        同步某只股票的历史数据到数据库

        Returns:
            同步的记录数
        """
        end_year = datetime.now().year
        start_year = end_year - years

        print(f"同步 {symbol} {start_year}-{end_year} 数据...")

        df = self.ths.get_full_history(symbol, start_year, end_year)

        if not df.empty:
            self._save_to_database(symbol, df)
            print(f"✅ 同步完成: {len(df)} 条记录")
            return len(df)

        print("❌ 同步失败")
        return 0

    def get_stored_symbols(self) -> list[str]:
        """获取数据库中已存储的股票列表"""
        query = "SELECT DISTINCT symbol FROM market_data ORDER BY symbol"
        try:
            results = self.pg.execute(query, fetch=True)
            return [r['symbol'] for r in results] if results else []
        except Exception:
            return []

    def execute_query(self, query: str, params: tuple | None = None) -> list | None:
        """执行SQL查询"""
        try:
            return self.pg.execute(query, params, fetch=True)
        except Exception as e:
            print(f"查询执行失败: {e}")
            return None

    def get_connection(self):
        """获取数据库连接"""
        try:
            # 使用上下文管理器获取连接
            return self.pg.get_connection()
        except Exception:
            return None

    def close(self):
        """关闭连接"""
        self.pg.disconnect()
        if self.redis:
            self.redis.disconnect()


# 全局实例
_db_manager: DatabaseDataManager | None = None


def get_db_manager() -> DatabaseDataManager:
    """获取全局数据管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseDataManager()
    return _db_manager


def get_stock_data(symbol: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """便捷函数 - 获取股票数据"""
    return get_db_manager().get_stock_data(symbol, start_date, end_date)
