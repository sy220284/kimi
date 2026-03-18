"""
全量产业链股票数据下载 - 514只标的
分批下载，全量历史数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import time
from datetime import datetime
from data.db_manager import get_db_manager
from data.ths_history_fetcher import ThsHistoryFetcher

def load_stock_list():
    """加载股票列表"""
    with open('all_industry_stocks.txt', 'r') as f:
        stocks = [line.strip() for line in f if line.strip()]
    return stocks

def save_to_database(db_manager, symbol, df):
    """保存到数据库"""
    if df.empty:
        return 0
    
    count = 0
    try:
        for _, row in df.iterrows():
            db_manager.pg.insert_market_data(
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

def download_stock_data(fetcher, symbol, start_date='2017-01-01', end_date='2024-12-31'):
    """下载单只股票历史数据"""
    try:
        code = f'hs_{symbol}'
        df = fetcher.get_data_by_date_range(code, start_date, end_date)
        
        if df is None or df.empty:
            return None
        
        df['symbol'] = symbol
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        print(f"    下载失败: {e}")
        return None

def main():
    print("\n" + "="*80)
    print("📊 产业链全量数据下载")
    print("="*80)
    print(f"开始时间: {datetime.now()}")
    
    # 加载股票列表
    stocks = load_stock_list()
    print(f"\n共 {len(stocks)} 只股票待下载")
    
    # 分批配置
    batch_size = 50
    total_batches = (len(stocks) + batch_size - 1) // batch_size
    
    print(f"分批下载: 每批 {batch_size} 只, 共 {total_batches} 批")
    
    # 初始化
    fetcher = ThsHistoryFetcher()
    db_manager = get_db_manager()
    
    # 统计
    total_success = 0
    total_fail = 0
    total_records = 0
    
    start_date = '2017-01-01'
    end_date = '2024-12-31'
    
    # 按批次下载
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(stocks))
        batch_stocks = stocks[start_idx:end_idx]
        
        print(f"\n{'='*80}")
        print(f"📦 批次 {batch_idx+1}/{total_batches} ({start_idx+1}-{end_idx}/{len(stocks)})")
        print(f"{'='*80}")
        
        batch_success = 0
        batch_fail = 0
        batch_records = 0
        
        for i, symbol in enumerate(batch_stocks, start_idx+1):
            print(f"\n[{i}/{len(stocks)}] {symbol}", end=" ", flush=True)
            
            try:
                df = download_stock_data(fetcher, symbol, start_date, end_date)
                
                if df is not None and not df.empty:
                    records_saved = save_to_database(db_manager, symbol, df)
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
            
            time.sleep(0.3)  # 控制请求频率
        
        # 批次汇总
        print(f"\n{'-'*80}")
        print(f"批次 {batch_idx+1} 汇总: 成功 {batch_success} | 失败 {batch_fail} | 记录 {batch_records}")
        
        total_success += batch_success
        total_fail += batch_fail
        total_records += batch_records
        
        # 每5批暂停一下
        if (batch_idx + 1) % 5 == 0 and batch_idx < total_batches - 1:
            print(f"\n⏸️ 已处理 {batch_idx+1} 批，暂停 5 秒...")
            time.sleep(5)
    
    # 最终汇总
    print("\n" + "="*80)
    print("📊 下载汇总")
    print("="*80)
    print(f"总股票数: {len(stocks)}")
    print(f"成功: {total_success} 只")
    print(f"失败: {total_fail} 只")
    print(f"总记录: {total_records:,} 条")
    print(f"成功率: {total_success/len(stocks)*100:.1f}%")
    
    # 查询数据库统计
    try:
        result = db_manager.pg.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT symbol) as stocks FROM market_data",
            fetch=True
        )
        if result:
            print(f"\n数据库统计:")
            print(f"  总记录: {result[0]['total']:,} 条")
            print(f"  股票数: {result[0]['stocks']} 只")
    except Exception as e:
        print(f"查询失败: {e}")
    
    print(f"\n结束时间: {datetime.now()}")
    print("="*80)

if __name__ == '__main__':
    main()
