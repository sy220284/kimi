#!/usr/bin/env python3
"""
全量重拉股票数据 - 并行版本
使用多线程加速拉取
"""
import os
import sys
import json
import time
import signal
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# 添加项目路径
sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')

from data.ths_adapter import ThsAdapter
import psycopg2
from psycopg2.extras import execute_values

# 配置
CACHE_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/stock_data')
BACKUP_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/backup')
PROGRESS_FILE = CACHE_DIR / '.progress_parallel.json'
DB_CONFIG = {
    'host': 'localhost', 'port': 5432, 'database': 'quant_analysis',
    'user': 'quant_user', 'password': 'quant_password'
}
END_DATE = '2026-03-19'

# 并行配置
MAX_WORKERS = 5  # 并发线程数
RATE_LIMIT = 0.5  # 每个线程最小间隔(秒)

# 全局变量
should_exit = False
stats_lock = Lock()
progress_lock = Lock()

class ParallelDataRefresher:
    def __init__(self):
        self.ths = ThsAdapter({'enabled': True, 'timeout': 30})
        self.stats = {
            'start_time': datetime.now(),
            'total_stocks': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_records': 0
        }
        self._load_stock_list()
        self._load_progress()
        
    def _load_stock_list(self):
        """加载股票列表"""
        select_file = Path('/root/.openclaw/workspace/智能体系统') / 'selfselect_stocks.json'
        if select_file.exists():
            with open(select_file) as f:
                data = json.load(f)
                self.stocks = [s['symbol'] for s in data.get('stocks', [])]
        else:
            with open('/root/.openclaw/workspace/智能体系统/all_industry_stocks.txt') as f:
                self.stocks = [line.strip() for line in f if line.strip()]
        
        self.stats['total_stocks'] = len(self.stocks)
        print(f"📋 股票列表加载完成: {len(self.stocks)} 只")
        print(f"⚡ 并行配置: {MAX_WORKERS}线程, 每线程间隔{RATE_LIMIT}秒")
        
    def _load_progress(self):
        """加载进度"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE) as f:
                self.progress = json.load(f)
            completed = len(self.progress.get('completed', []))
            print(f"📂 加载已有进度: 已完成{completed}只 ({completed/len(self.stocks)*100:.1f}%)")
        else:
            self.progress = {'completed': [], 'failed': [], 'last_update': None}
            
    def _save_progress(self):
        """保存进度"""
        with progress_lock:
            self.progress['last_update'] = datetime.now().isoformat()
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(self.progress, f)
            
    def backup_current_data(self):
        """备份当前数据"""
        print("\n💾 步骤1: 备份当前数据...")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_file = BACKUP_DIR / f"market_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        os.system(f"pg_dump -h {DB_CONFIG['host']} -p {DB_CONFIG['port']} "
                  f"-U {DB_CONFIG['user']} -d {DB_CONFIG['database']} "
                  f"-t market_data > {backup_file} 2>/dev/null")
        
        print(f"   ✅ 备份完成: {backup_file}")
        return backup_file
        
    def clear_database(self):
        """清空数据库"""
        print("\n🗑️ 步骤2: 清空market_data表...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('TRUNCATE TABLE market_data RESTART IDENTITY')
        conn.commit()
        cursor.close()
        conn.close()
        print("   ✅ 数据已清空")
        
    def fetch_single_stock(self, symbol_info):
        """拉取单只股票数据（供线程池调用）"""
        idx, symbol, total = symbol_info
        
        if should_exit:
            return None
            
        cache_file = CACHE_DIR / f"{symbol}.json"
        
        # 跳过已存在的
        if cache_file.exists():
            with stats_lock:
                self.stats['skipped'] += 1
                if symbol not in self.progress['completed']:
                    self.progress['completed'].append(symbol)
            return {'symbol': symbol, 'status': 'skipped', 'records': 0}
            
        try:
            # 每个线程独立创建adapter（线程安全）
            ths = ThsAdapter({'enabled': True, 'timeout': 30})
            df = ths.get_full_history(symbol)
            
            if df is not None and not df.empty:
                # 过滤到2026-03-19
                df = df[df['date'] <= END_DATE]
                
                # 保存到缓存
                data = df.to_dict('records')
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
                
                # 更新统计
                with stats_lock:
                    self.stats['success'] += 1
                    self.stats['total_records'] += len(df)
                    self.progress['completed'].append(symbol)
                
                # 打印进度
                progress_pct = len(self.progress['completed']) / total * 100
                print(f"✅ [{idx}/{total}] {symbol}: {len(df)}条 ({progress_pct:.1f}%)")
                
                return {'symbol': symbol, 'status': 'success', 'records': len(df)}
            else:
                with stats_lock:
                    self.stats['failed'] += 1
                    self.progress['failed'].append(symbol)
                print(f"⚠️ [{idx}/{total}] {symbol}: 无数据")
                return {'symbol': symbol, 'status': 'no_data', 'records': 0}
                
        except Exception as e:
            with stats_lock:
                self.stats['failed'] += 1
                self.progress['failed'].append(symbol)
            print(f"❌ [{idx}/{total}] {symbol}: {str(e)[:30]}")
            return {'symbol': symbol, 'status': 'error', 'records': 0}
        finally:
            # 速率控制
            time.sleep(RATE_LIMIT)
            
    def fetch_to_cache_parallel(self):
        """并行拉取数据到缓存"""
        print(f"\n📥 步骤3: 并行拉取数据 ({MAX_WORKERS}线程)...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 获取待处理列表
        completed = set(self.progress['completed'])
        pending = [(i+1, s, len(self.stocks)) for i, s in enumerate(self.stocks) if s not in completed]
        
        print(f"   📊 已缓存: {len(completed)}只, 待拉取: {len(pending)}只")
        
        # 使用线程池并行拉取
        last_save_time = time.time()
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(self.fetch_single_stock, info): info 
                for info in pending[:100]  # 先提交前100个
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_symbol):
                result = future.result()
                
                # 每10秒保存一次进度
                if time.time() - last_save_time > 10:
                    self._save_progress()
                    self._print_progress()
                    last_save_time = time.time()
                    
                # 检查是否应该退出
                if should_exit:
                    executor.shutdown(wait=False)
                    break
        
        # 最终保存
        self._save_progress()
        print(f"\n   ✅ 拉取完成: 成功{self.stats['success']}只, 失败{self.stats['failed']}只, 跳过{self.stats['skipped']}只")
        
    def _print_progress(self):
        """打印进度摘要"""
        completed = len(self.progress['completed'])
        total = self.stats['total_stocks']
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = completed / elapsed * 60 if elapsed > 0 else 0
        eta = (total - completed) / rate * 60 if rate > 0 else 0
        
        print(f"\n📊 进度: {completed}/{total} ({completed/total*100:.1f}%) | "
              f"速度: {rate:.1f}只/分钟 | 预计剩余: {eta/60:.1f}分钟")
        
    def import_to_database(self):
        """从缓存导入数据库"""
        print("\n💾 步骤4: 导入数据到数据库...")
        
        cache_files = list(CACHE_DIR.glob('*.json'))
        cache_files = [f for f in cache_files if f.name not in ('failed_stocks.json', '.progress.json', '.progress_parallel.json')]
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        total_imported = 0
        for i, cache_file in enumerate(cache_files, 1):
            symbol = cache_file.stem
            
            with open(cache_file) as f:
                data = json.load(f)
                
            if not data:
                continue
                
            # 准备插入数据
            records = [
                (
                    d['symbol'] if 'symbol' in d else symbol,
                    d['date'],
                    float(d['open']),
                    float(d['high']),
                    float(d['low']),
                    float(d['close']),
                    int(d['volume']),
                    float(d.get('amount', 0)),
                    'THS'
                )
                for d in data
            ]
            
            # 批量插入
            try:
                execute_values(
                    cursor,
                    '''INSERT INTO market_data 
                       (symbol, date, open, high, low, close, volume, amount, data_source)
                       VALUES %s
                       ON CONFLICT (symbol, date) DO NOTHING''',
                    records
                )
                total_imported += len(records)
            except Exception as e:
                print(f"   ⚠️ {symbol} 导入失败: {e}")
            
            if i % 50 == 0:
                conn.commit()
                print(f"   已导入 {i}/{len(cache_files)} 只股票, 共{total_imported:,}条记录")
                
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"   ✅ 导入完成: 共{total_imported:,}条记录")
        return total_imported
        
    def run(self):
        """执行完整流程"""
        print("="*60)
        print(f"🚀 全量数据重拉任务启动 (并行模式)")
        print(f"📅 目标日期: {END_DATE}")
        print(f"📊 股票数量: {len(self.stocks)}只")
        print("="*60)
        
        try:
            # 步骤1: 备份
            backup_file = self.backup_current_data()
            
            # 步骤2: 清空（仅在非断点续传时）
            if not self.progress['completed']:
                self.clear_database()
            else:
                print(f"\n🗑️ 跳过清空（已有{len(self.progress['completed'])}只缓存）")
                
            # 步骤3: 并行拉取到缓存
            self.fetch_to_cache_parallel()
            
            # 步骤4: 导入数据库
            imported = self.import_to_database()
            
            # 统计
            duration = datetime.now() - self.stats['start_time']
            print("\n" + "="*60)
            print("✅ 任务完成!")
            print("="*60)
            print(f"⏱️  耗时: {duration}")
            print(f"📈 成功: {self.stats['success']}只股票")
            print(f"❌ 失败: {self.stats['failed']}只股票")
            print(f"⏭️  跳过: {self.stats['skipped']}只股票")
            print(f"📝 导入记录: {imported:,}条")
            print(f"💾 备份文件: {backup_file}")
                
        except Exception as e:
            print(f"\n❌ 任务异常: {e}")
            self._save_progress()
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    refresher = ParallelDataRefresher()
    refresher.run()
