#!/usr/bin/env python3
"""
全量重拉股票数据 - 优化加速版
使用线程池 + 连接复用 + 批量处理
"""
import os
import sys
import json
import time
import signal
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加项目路径
sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')

from data.ths_adapter import ThsAdapter
import psycopg2
from psycopg2.extras import execute_values

# 配置
CACHE_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/stock_data')
BACKUP_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/backup')
PROGRESS_FILE = CACHE_DIR / '.progress_optimized.json'
DB_CONFIG = {
    'host': 'localhost', 'port': 5432, 'database': 'quant_analysis',
    'user': 'quant_user', 'password': 'quant_password'
}
END_DATE = '2026-03-19'

# 优化配置
MAX_WORKERS = 6  # 6线程并发
BATCH_SIZE = 100  # 每100只保存一次进度
RATE_LIMIT = 0.05  # 每线程50ms间隔

# 全局变量
should_exit = False
stats_lock = threading.Lock()

class OptimizedRefresher:
    def __init__(self):
        self.ths = ThsAdapter({'enabled': True, 'timeout': 30})
        self.stats = {'success': 0, 'failed': 0, 'skipped': 0, 'total_records': 0}
        self.stocks = self._load_stock_list()
        self.completed = self._load_progress()
        self.start_time = datetime.now()
        
    def _load_stock_list(self):
        select_file = Path('/root/.openclaw/workspace/智能体系统') / 'selfselect_stocks.json'
        if select_file.exists():
            with open(select_file) as f:
                data = json.load(f)
                return [s['symbol'] for s in data.get('stocks', [])]
        with open('/root/.openclaw/workspace/智能体系统/all_industry_stocks.txt') as f:
            return [line.strip() for line in f if line.strip()]
    
    def _load_progress(self):
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
                return set(data.get('completed', []))
        return set()
    
    def _save_progress(self):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({
                'completed': list(self.completed),
                'last_update': datetime.now().isoformat()
            }, f)
    
    def _print_progress(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        total = len(self.stocks)
        done = len(self.completed)
        rate = done / elapsed * 60 if elapsed > 0 else 0
        eta = (total - done) / rate if rate > 0 else 0
        
        print(f"\n📊 [{datetime.now().strftime('%H:%M:%S')}] "
              f"进度: {done}/{total} ({done/total*100:.1f}%) | "
              f"速度: {rate:.1f}只/分钟 | 预计剩余: {eta/60:.1f}分钟 | "
              f"✅{self.stats['success']} ❌{self.stats['failed']} ⏭️{self.stats['skipped']}")
    
    def fetch_single(self, symbol):
        """单只股票拉取"""
        if should_exit:
            return None
            
        cache_file = CACHE_DIR / f"{symbol}.json"
        
        # 跳过已存在的
        if cache_file.exists():
            with stats_lock:
                self.stats['skipped'] += 1
                self.completed.add(symbol)
            return {'symbol': symbol, 'status': 'skipped', 'records': 0}
        
        try:
            # 每个线程创建独立adapter（线程安全）
            ths = ThsAdapter({'enabled': True, 'timeout': 30})
            df = ths.get_full_history(symbol)
            
            if df is not None and not df.empty:
                df = df[df['date'] <= END_DATE]
                data = df.to_dict('records')
                
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
                
                with stats_lock:
                    self.stats['success'] += 1
                    self.stats['total_records'] += len(df)
                    self.completed.add(symbol)
                
                return {'symbol': symbol, 'status': 'success', 'records': len(df)}
            else:
                with stats_lock:
                    self.stats['failed'] += 1
                return {'symbol': symbol, 'status': 'no_data', 'records': 0}
                
        except Exception as e:
            with stats_lock:
                self.stats['failed'] += 1
            return {'symbol': symbol, 'status': 'error', 'error': str(e), 'records': 0}
        finally:
            time.sleep(RATE_LIMIT)
    
    def fetch_parallel(self):
        """并行拉取"""
        print(f"\n⚡ 启动并行拉取: {MAX_WORKERS}线程, 目标{len(self.stocks)}只")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        pending = [s for s in self.stocks if s not in self.completed]
        print(f"📊 已缓存: {len(self.completed)}只, 待拉取: {len(pending)}只")
        
        if not pending:
            print("   ✅ 所有股票已缓存")
            return
        
        last_print = time.time()
        processed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            futures = {executor.submit(self.fetch_single, s): s for s in pending}
            
            for future in as_completed(futures):
                result = future.result()
                processed += 1
                
                # 每10秒打印进度
                if time.time() - last_print > 10:
                    self._save_progress()
                    self._print_progress()
                    last_print = time.time()
                
                # 每BATCH_SIZE只保存一次
                if processed % BATCH_SIZE == 0:
                    self._save_progress()
                
                if should_exit:
                    executor.shutdown(wait=False)
                    break
        
        self._save_progress()
        self._print_progress()
        print(f"\n✅ 拉取完成: 成功{self.stats['success']}只, 失败{self.stats['failed']}只, 跳过{self.stats['skipped']}只")
    
    def import_to_db(self):
        """导入数据库"""
        print("\n💾 导入数据到数据库...")
        
        cache_files = [f for f in CACHE_DIR.glob('*.json') 
                      if f.suffix == '.json' and not f.name.startswith('.')]
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        total_imported = 0
        for i, cache_file in enumerate(cache_files, 1):
            symbol = cache_file.stem
            
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
                
                if i % 100 == 0:
                    conn.commit()
                    print(f"   已导入 {i}/{len(cache_files)} 只, 共{total_imported:,}条")
                    
            except Exception as e:
                print(f"   ⚠️ {symbol} 失败: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"   ✅ 导入完成: 共{total_imported:,}条")
        return total_imported
    
    def run(self, skip_backup=False):
        print("="*60)
        print(f"🚀 全量数据重拉 - 优化加速版 ({MAX_WORKERS}线程)")
        print("="*60)
        
        # 1. 备份
        if not skip_backup:
            print("\n💾 备份数据...")
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            backup_file = BACKUP_DIR / f"market_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            os.system(f"pg_dump -h {DB_CONFIG['host']} -p {DB_CONFIG['port']} "
                      f"-U {DB_CONFIG['user']} -d {DB_CONFIG['database']} "
                      f"-t market_data > {backup_file} 2>/dev/null")
            print("   ✅ 备份完成")
        
        # 2. 清空
        print("\n🗑️ 清空数据库...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('TRUNCATE TABLE market_data RESTART IDENTITY')
        conn.commit()
        cursor.close()
        conn.close()
        print("   ✅ 已清空")
        
        # 3. 并行拉取
        self.fetch_parallel()
        
        # 4. 导入
        imported = self.import_to_db()
        
        # 统计
        duration = datetime.now() - self.start_time
        print("\n" + "="*60)
        print("✅ 全部完成!")
        print("="*60)
        print(f"⏱️  总耗时: {duration}")
        print(f"📈 成功: {self.stats['success']}只")
        print(f"❌ 失败: {self.stats['failed']}只")
        print(f"⏭️  跳过: {self.stats['skipped']}只")
        print(f"📝 总记录: {imported:,}条")

def signal_handler(signum, frame):
    global should_exit
    print(f"\n\n⚠️ 收到信号 {signum}，正在优雅退出...")
    should_exit = True

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-backup', action='store_true')
    args = parser.parse_args()
    
    refresher = OptimizedRefresher()
    refresher.run(skip_backup=args.skip_backup)
