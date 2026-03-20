#!/usr/bin/env python3
"""
补全缺失的自选股数据 - 从上市到2026-03-19的全量前复权数据
"""
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')

from data.ths_adapter import ThsAdapter
import psycopg2
from psycopg2.extras import execute_values

# 配置
CACHE_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/stock_data')
DB_CONFIG = {
    'host': 'localhost', 'port': 5432, 'database': 'quant_analysis',
    'user': 'quant_user', 'password': 'quant_password'
}
END_DATE = '2026-03-19'

# 并发配置
MAX_WORKERS = 6
RATE_LIMIT = 0.05  # 50ms间隔

class SelfSelectFetcher:
    def __init__(self, missing_stocks):
        self.stocks = missing_stocks
        self.stats = {'success': 0, 'failed': 0, 'skipped': 0, 'total_records': 0}
        self.stats_lock = threading.Lock()
        self.start_time = datetime.now()
        
    def _print_progress(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        done = self.stats['success'] + self.stats['failed'] + self.stats['skipped']
        total = len(self.stocks)
        rate = done / elapsed * 60 if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        
        print(f"\n📊 [{datetime.now().strftime('%H:%M:%S')}] "
              f"进度: {done}/{total} ({done/total*100:.1f}%) | "
              f"速度: {rate:.1f}只/分钟 | 预计剩余: {eta/60:.1f}分钟 | "
              f"✅{self.stats['success']} ❌{self.stats['failed']} ⏭️{self.stats['skipped']}")
    
    def fetch_single(self, symbol):
        """单只股票拉取"""
        cache_file = CACHE_DIR / f"{symbol}.json"
        
        # 如果缓存已存在，直接返回成功
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                with self.stats_lock:
                    self.stats['skipped'] += 1
                return {'symbol': symbol, 'status': 'cached', 'records': len(data)}
            except:
                pass  # 缓存损坏，重新拉取
        
        try:
            ths = ThsAdapter({'enabled': True, 'timeout': 30})
            df = ths.get_full_history(symbol)
            
            if df is not None and not df.empty:
                df = df[df['date'] <= END_DATE]
                data = df.to_dict('records')
                
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
                
                with self.stats_lock:
                    self.stats['success'] += 1
                    self.stats['total_records'] += len(df)
                
                return {'symbol': symbol, 'status': 'success', 'records': len(df)}
            else:
                with self.stats_lock:
                    self.stats['failed'] += 1
                return {'symbol': symbol, 'status': 'no_data', 'records': 0}
                
        except Exception as e:
            with self.stats_lock:
                self.stats['failed'] += 1
            return {'symbol': symbol, 'status': 'error', 'error': str(e), 'records': 0}
        finally:
            time.sleep(RATE_LIMIT)
    
    def fetch_all(self):
        """并行拉取所有缺失股票"""
        print(f"\n⚡ 启动并行拉取: {MAX_WORKERS}线程, 目标{len(self.stocks)}只")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        last_print = time.time()
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.fetch_single, s): s for s in self.stocks}
            
            for future in as_completed(futures):
                result = future.result()
                
                # 每15秒打印进度
                if time.time() - last_print > 15:
                    self._print_progress()
                    last_print = time.time()
        
        self._print_progress()
        print(f"\n✅ 拉取完成: 成功{self.stats['success']}只, 失败{self.stats['failed']}只, 跳过{self.stats['skipped']}只")
        return self.stats['success'], self.stats['failed'], self.stats['skipped']
    
    def import_to_db(self):
        """导入到数据库"""
        print("\n💾 导入数据到数据库...")
        
        # 只导入本次拉取的股票
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        total_imported = 0
        failed_symbols = []
        
        for i, symbol in enumerate(self.stocks, 1):
            cache_file = CACHE_DIR / f"{symbol}.json"
            
            if not cache_file.exists():
                continue
            
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                
                if not data:
                    continue
                    
                records = [
                    (d.get('symbol', symbol), d['date'], float(d['open']), 
                     float(d['high']), float(d['low']), float(d['close']),
                     int(d['volume']), float(d.get('amount', 0)), 'THS')
                    for d in data
                ]
                
                execute_values(
                    cursor,
                    '''INSERT INTO market_data (symbol, date, open, high, low, close, volume, amount, data_source)
                       VALUES %s ON CONFLICT (symbol, date) DO NOTHING''',
                    records
                )
                
                total_imported += len(records)
                
                if i % 20 == 0:
                    conn.commit()
                    print(f"   已导入 {i}/{len(self.stocks)} 只, 共{total_imported:,}条")
                    
            except Exception as e:
                failed_symbols.append(symbol)
                print(f"   ⚠️ {symbol} 失败: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"   ✅ 导入完成: 共{total_imported:,}条")
        if failed_symbols:
            print(f"   ⚠️ 失败: {len(failed_symbols)}只")
        return total_imported

def main():
    # 读取缺失的自选股列表
    with open('.cache/mx_missing_stocks.json') as f:
        missing_stocks = json.load(f)
    
    print("="*60)
    print(f"🚀 补全自选股数据 - {len(missing_stocks)}只")
    print(f"📅 目标日期: {END_DATE}")
    print("="*60)
    
    start_time = datetime.now()
    
    fetcher = SelfSelectFetcher(missing_stocks)
    
    # 1. 并行拉取
    success, failed, skipped = fetcher.fetch_all()
    
    # 2. 导入数据库
    imported = fetcher.import_to_db()
    
    # 统计
    duration = datetime.now() - start_time
    print("\n" + "="*60)
    print("✅ 任务完成!")
    print("="*60)
    print(f"⏱️  耗时: {duration}")
    print(f"📈 成功: {success}只")
    print(f"❌ 失败: {failed}只")
    print(f"⏭️  跳过: {skipped}只")
    print(f"📝 总记录: {imported:,}条")

if __name__ == '__main__':
    main()
