"""
并行下载脚本 - 多进程加速
使用进程池并行下载多只股票
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import time
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager
import os

# 必须在导入其他模块前设置环境变量
os.environ['PYTHONPATH'] = str(Path(__file__).parent.parent / 'src')

def get_db_connection():
    """每个进程独立的数据库连接"""
    from data.db_manager import get_db_manager
    return get_db_manager()

def get_fetcher():
    """每个进程独立的fetcher"""
    from data.ths_history_fetcher import ThsHistoryFetcher
    return ThsHistoryFetcher()

def download_single_stock(args):
    """下载单只股票的包装函数"""
    symbol, start_date, end_date = args
    
    try:
        fetcher = get_fetcher()
        db = get_db_connection()
        
        code = f'hs_{symbol}'
        df = fetcher.get_data_by_date_range(code, start_date, end_date)
        
        if df is None or df.empty:
            return {'symbol': symbol, 'status': 'empty', 'records': 0}
        
        # 保存到数据库
        count = 0
        for _, row in df.iterrows():
            try:
                db.pg.insert_market_data(
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
            except Exception as e:
                pass  # 忽略重复键等错误
        
        return {'symbol': symbol, 'status': 'success', 'records': count}
    except Exception as e:
        return {'symbol': symbol, 'status': 'error', 'error': str(e)}

def load_stock_list():
    """加载股票列表"""
    with open('all_industry_stocks.txt', 'r') as f:
        return [line.strip() for line in f if line.strip()]

def get_downloaded_stocks():
    """获取已下载的股票"""
    try:
        db = get_db_connection()
        result = db.pg.execute("SELECT DISTINCT symbol FROM market_data", fetch=True)
        return {r['symbol'] for r in result}
    except:
        return set()

def main():
    print("\n" + "="*80)
    print("📊 并行下载模式 (8进程)")
    print("="*80)
    print(f"开始时间: {datetime.now()}")
    
    # 加载股票列表
    all_stocks = load_stock_list()
    print(f"\n目标列表: {len(all_stocks)} 只")
    
    # 获取已下载
    downloaded = get_downloaded_stocks()
    print(f"已下载: {len(downloaded)} 只")
    
    # 筛选未下载
    pending = [s for s in all_stocks if s not in downloaded]
    print(f"待下载: {len(pending)} 只")
    
    if not pending:
        print("\n✅ 全部完成!")
        return
    
    start_date = '2017-01-01'
    end_date = '2024-12-31'
    
    # 准备任务
    tasks = [(s, start_date, end_date) for s in pending]
    
    # 并行下载 - 8进程
    max_workers = 8
    total_success = 0
    total_fail = 0
    total_records = 0
    
    print(f"\n启动 {max_workers} 个并行进程...")
    print(f"预计时间: ~{len(pending) * 8 / max_workers / 60:.1f}小时\n")
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_single_stock, task): task[0] for task in tasks}
        
        for i, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            try:
                result = future.result()
                status = result['status']
                
                if status == 'success':
                    total_success += 1
                    total_records += result['records']
                    print(f"[{i}/{len(pending)}] {symbol} ✅ {result['records']}条")
                elif status == 'empty':
                    total_fail += 1
                    print(f"[{i}/{len(pending)}] {symbol} ⚠️ 无数据")
                else:
                    total_fail += 1
                    print(f"[{i}/{len(pending)}] {symbol} ❌ {result.get('error', '未知错误')}")
                
                # 每50只暂停一下
                if i % 50 == 0:
                    print(f"\n⏸️ 已处理 {i} 只，暂停 3 秒...\n")
                    time.sleep(3)
                    
            except Exception as e:
                total_fail += 1
                print(f"[{i}/{len(pending)}] {symbol} ❌ 异常: {e}")
    
    # 最终统计
    print("\n" + "="*80)
    print("📊 下载汇总")
    print("="*80)
    print(f"本次成功: {total_success} 只")
    print(f"本次失败: {total_fail} 只")
    print(f"本次记录: {total_records:,} 条")
    
    # 查询最终统计
    try:
        db = get_db_connection()
        result = db.pg.execute(
            "SELECT COUNT(DISTINCT symbol) as stocks, COUNT(*) as total FROM market_data",
            fetch=True
        )
        print(f"\n📈 数据库最终:")
        print(f"  总股票: {result[0]['stocks']} 只")
        print(f"  总记录: {result[0]['total']:,} 条")
    except Exception as e:
        print(f"查询失败: {e}")
    
    print(f"\n结束时间: {datetime.now()}")
    print("="*80)

if __name__ == '__main__':
    main()
