#!/usr/bin/env python3
"""
系统数据层增量更新脚本
使用 DataCollector 和 MultiSourceDataManager 进行数据增量更新

注意: 已统一使用同花顺(THS)作为默认数据源
      AKShare/Tushare 已弃用
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import time
from datetime import datetime, timedelta

import pandas as pd

from data.db_manager import get_db_manager
from data.multi_source import MultiSourceDataManager


class IncrementalUpdater:
    """增量更新器 - 使用系统数据层"""

    def __init__(self, prefer_source: str = 'ths'):
        """
        初始化增量更新器

        Args:
            prefer_source: 优先使用的数据源 ('ths', 'akshare', 'cache')
        """
        self.db = get_db_manager()
        self.data_mgr = MultiSourceDataManager()
        self.prefer_source = prefer_source

        print("📊 增量更新器初始化完成")
        print(f"   优先数据源: {prefer_source}")

    def get_last_update_date(self, symbol: str) -> str | None:
        """获取股票最后更新日期"""
        result = self.db.pg.execute(
            "SELECT MAX(date) as last_date FROM market_data WHERE symbol = %s",
            (symbol,), fetch=True
        )
        if result and result[0]['last_date']:
            return result[0]['last_date'].strftime('%Y-%m-%d')
        return None

    def get_all_symbols(self) -> list[str]:
        """获取所有股票代码"""
        result = self.db.pg.execute(
            "SELECT DISTINCT symbol FROM market_data ORDER BY symbol",
            fetch=True
        )
        return [r['symbol'] for r in result]

    def fetch_incremental_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame | None:
        """
        使用系统数据层获取增量数据

        使用 MultiSourceDataManager (自动 failover)
        """
        try:
            df = self.data_mgr.get_history(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                prefer_source=self.prefer_source
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"   MultiSourceDataManager 失败: {e}")

        return None

    def save_to_db(self, df: pd.DataFrame, symbol: str) -> int:
        """保存数据到数据库"""
        if df is None or df.empty:
            return 0

        # 标准化列名
        column_mapping = {
            '日期': 'date',
            '股票代码': 'symbol',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
        }
        df = df.rename(columns=column_mapping)

        # 确保必要的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                print(f"   ⚠️ 缺少必要列: {col}")
                return 0

        # 添加symbol列
        if 'symbol' not in df.columns:
            df['symbol'] = symbol

        # 标准化日期格式
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        # 保存到数据库
        success_count = 0
        for _, row in df.iterrows():
            try:
                sql = """INSERT INTO market_data (symbol, date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume, amount = EXCLUDED.amount"""

                self.db.pg.execute(sql, (
                    row['symbol'], row['date'], row['open'], row['high'],
                    row['low'], row['close'], row['volume'], row.get('amount', 0)
                ))
                success_count += 1
            except Exception as e:
                print(f"   保存失败: {e}")

        return success_count

    def update_symbol(self, symbol: str, force_full: bool = False) -> dict:
        """
        更新单只股票数据

        Args:
            symbol: 股票代码
            force_full: 是否强制全量更新

        Returns:
            更新结果统计
        """
        print(f"\n🔍 更新 {symbol}...")

        # 确定日期范围
        if force_full:
            start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
        else:
            last_date = self.get_last_update_date(symbol)
            if last_date:
                # 从最后日期的下一天开始
                start = datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)
                start_date = start.strftime('%Y-%m-%d')
            else:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        end_date = datetime.now().strftime('%Y-%m-%d')

        if start_date > end_date:
            print(f"   ✅ 数据已是最新 (最后更新: {last_date})")
            return {'symbol': symbol, 'status': 'up_to_date', 'count': 0}

        print(f"   日期范围: {start_date} ~ {end_date}")

        # 获取数据
        df = self.fetch_incremental_data(symbol, start_date, end_date)

        if df is None or df.empty:
            print("   ❌ 无数据")
            return {'symbol': symbol, 'status': 'no_data', 'count': 0}

        # 保存到数据库
        count = self.save_to_db(df, symbol)
        print(f"   ✅ 成功保存 {count} 条")

        return {'symbol': symbol, 'status': 'success', 'count': count}

    def run_incremental_update(
        self,
        symbols: list[str] | None = None,
        max_stocks: int | None = None,
        rate_limit: float = 0.3
    ) -> dict:
        """
        运行增量更新

        Args:
            symbols: 指定股票列表，None则更新所有
            max_stocks: 最大更新股票数
            rate_limit: 请求间隔(秒)

        Returns:
            更新统计
        """
        print("\n" + "="*60)
        print("🚀 开始增量更新")
        print("="*60)

        # 获取股票列表
        if symbols is None:
            symbols = self.get_all_symbols()
            print(f"📊 数据库共有 {len(symbols)} 只股票")

        if max_stocks:
            symbols = symbols[:max_stocks]
            print(f"📊 本次更新前 {max_stocks} 只")

        # 统计
        stats = {
            'total': len(symbols),
            'success': 0,
            'no_data': 0,
            'up_to_date': 0,
            'failed': 0,
            'total_records': 0
        }

        # 更新每只股票
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] ", end='')

            result = self.update_symbol(symbol)

            if result['status'] == 'success':
                stats['success'] += 1
                stats['total_records'] += result['count']
            elif result['status'] == 'no_data':
                stats['no_data'] += 1
            elif result['status'] == 'up_to_date':
                stats['up_to_date'] += 1
            else:
                stats['failed'] += 1

            # 速率限制
            if rate_limit > 0 and i < len(symbols):
                time.sleep(rate_limit)

        # 总结
        print("\n" + "="*60)
        print("📊 增量更新完成")
        print("="*60)
        print(f"总股票数: {stats['total']}")
        print(f"成功更新: {stats['success']} 只")
        print(f"已是最新: {stats['up_to_date']} 只")
        print(f"无数据: {stats['no_data']} 只")
        print(f"失败: {stats['failed']} 只")
        print(f"新增记录: {stats['total_records']} 条")
        print("="*60)

        return stats


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='系统数据层增量更新')
    parser.add_argument('--source', type=str, default='ths',
                       choices=['ths', 'akshare', 'cache'],
                       help='优先数据源')
    parser.add_argument('--symbols', type=str, nargs='+',
                       help='指定股票代码')
    parser.add_argument('--max', type=int,
                       help='最大更新数量')
    parser.add_argument('--rate-limit', type=float, default=0.3,
                       help='请求间隔(秒)')

    args = parser.parse_args()

    # 创建更新器
    updater = IncrementalUpdater(prefer_source=args.source)

    # 运行更新
    updater.run_incremental_update(
        symbols=args.symbols,
        max_stocks=args.max,
        rate_limit=args.rate_limit
    )


if __name__ == '__main__':
    main()
