"""
全量产业链股票数据下载 - 断点续传版本
跳过已下载的股票
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import time
from datetime import datetime

from data.db_manager import get_db_manager
from data.ths_history_fetcher import ThsHistoryFetcher


def load_stock_list():
    """加载股票列表"""
    with open('all_industry_stocks.txt') as f:
        stocks = [line.strip() for line in f if line.strip()]
    return stocks

def get_downloaded_stocks(db_manager):
    """获取已下载的股票列表"""
    try:
        result = db_manager.pg.execute(
            "SELECT DISTINCT symbol FROM marketdata",
            fetch=True
        )
        return {r['symbol'] for r in result}
    except Exception:
        return set()

def save_todatabase(db_manager, symbol, df):
    """保存到数据库"""
    if df.empty:
        return 0

    count = 0
    try:
        for _, row in df.iterrows():
            db_manager.pg.insert_marketdata(
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
            count += 1
        return count
    except Exception as e:
        print(f"    保存失败: {e}")
        return 0

def download_stockdata(fetcher, symbol, start_date='2017-01-01', end_date='2024-12-31'):
    """下载单只股票历史数据"""
    try:
        code = f'hs_{symbol}'
        df = fetcher.getdata_by_date_range(code, start_date, end_date)

        if df is None or df.empty:
            return None

        df['symbol'] = symbol
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        print(f"    下载失败: {e}")
        return None

def main():
    print("\n" + "="*80)
    print("📊 产业链全量数据下载 (断点续传)")
    print("="*80)
    print(f"开始时间: {datetime.now()}")

    # 加载股票列表
    stocks = load_stock_list()
    print(f"\n共 {len(stocks)} 只股票在目标列表中")

    # 初始化
    db_manager = get_db_manager()
    fetcher = ThsHistoryFetcher()

    # 获取已下载的股票
    downloaded = get_downloaded_stocks(db_manager)
    print(f"数据库中已有 {len(downloaded)} 只股票")

    # 筛选未下载的股票
    pending_stocks = [s for s in stocks if s not in downloaded]
    print(f"待下载: {len(pending_stocks)} 只")

    if not pending_stocks:
        print("\n✅ 所有股票已下载完成!")
        return

    # 分批配置
    batch_size = 50
    total_batches = (len(pending_stocks) + batch_size - 1) // batch_size

    print(f"分批下载: 每批 {batch_size} 只, 共 {total_batches} 批")

    # 统计
    total_success = 0
    total_fail = 0
    total_records = 0

    start_date = '2017-01-01'
    end_date = '2024-12-31'

    # 按批次下载
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(pending_stocks))
        batch_stocks = pending_stocks[start_idx:end_idx]

        print(f"\n{'='*80}")
        print(f"📦 批次 {batch_idx+1}/{total_batches} ({start_idx+1}-{end_idx}/{len(pending_stocks)})")
        print(f"{'='*80}")

        batch_success = 0
        batch_fail = 0
        batch_records = 0

        for i, symbol in enumerate(batch_stocks, 1):
            overall_idx = len(downloaded) + start_idx + i
            print(f"\n[{overall_idx}/{len(stocks)}] {symbol}", end=" ", flush=True)

            try:
                df = download_stockdata(fetcher, symbol, start_date, end_date)

                if df is not None and not df.empty:
                    records_saved = save_todatabase(db_manager, symbol, df)
                    if records_saved > 0:
                        print(f"✅ 保存 {records_saved} 条记录")
                        batch_success += 1
                        batch_records += records_saved
                    else:
                        print("❌ 保存失败")
                        batch_fail += 1
                else:
                    print("❌ 无数据")
                    batch_fail += 1

            except Exception as e:
                print(f"❌ 错误: {e}")
                batch_fail += 1

            time.sleep(0.3)

        # 批次汇总
        print(f"\n{'-'*80}")
        print(f"批次 {batch_idx+1} 汇总: 成功 {batch_success} | 失败 {batch_fail} | 记录 {batch_records}")

        total_success += batch_success
        total_fail += batch_fail
        total_records += batch_records

        # 每5批暂停
        if (batch_idx + 1) % 5 == 0 and batch_idx < total_batches - 1:
            print(f"\n⏸️ 已处理 {batch_idx+1} 批，暂停 5 秒...")
            time.sleep(5)

    # 最终汇总
    print("\n" + "="*80)
    print("📊 本次下载汇总")
    print("="*80)
    print(f"本次成功: {total_success} 只")
    print(f"本次失败: {total_fail} 只")
    print(f"本次记录: {total_records:,} 条")

    # 查询数据库最终统计
    try:
        result = db_manager.pg.execute(
            "SELECT COUNT(DISTINCT symbol) as stocks, COUNT(*) as total FROM marketdata",
            fetch=True
        )
        if result:
            print("\n📈 数据库最终统计:")
            print(f"  总股票数: {result[0]['stocks']} 只")
            print(f"  总记录数: {result[0]['total']:,} 条")
    except Exception as e:
        print(f"查询失败: {e}")

    print(f"\n结束时间: {datetime.now()}")
    print("="*80)

if __name__ == '__main__':
    main()
