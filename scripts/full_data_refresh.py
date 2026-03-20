#!/usr/bin/env python3
"""
全量重拉股票数据 - 从上市到2026-03-19
支持断点续传，分批拉取，容错处理
"""
import os
import sys
import json
import time
import signal
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')

from data.ths_adapter import ThsAdapter
import psycopg2
from psycopg2.extras import execute_values

# 配置
CACHE_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/stock_data')
BACKUP_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/backup')
PROGRESS_FILE = CACHE_DIR / '.progress.json'
DB_CONFIG = {
    'host': 'localhost', 'port': 5432, 'database': 'quant_analysis',
    'user': 'quant_user', 'password': 'quant_password'
}
END_DATE = '2026-03-19'
BATCH_SIZE = 20  # 减小批次大小，避免长时间阻塞
BATCH_DELAY = 30  # 减少等待时间

# 全局变量用于信号处理
should_exit = False

def signal_handler(signum, frame):
    global should_exit
    print(f"\n\n⚠️ 收到信号 {signum}，将在当前股票完成后退出...")
    should_exit = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

class FullDataRefresher:
    def __init__(self):
        self.ths = ThsAdapter({'enabled': True, 'timeout': 30})
        self.stats = {
            'start_time': datetime.now(),
            'total_stocks': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_records': 0,
            'batches_completed': 0
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
        
    def _load_progress(self):
        """加载进度"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE) as f:
                self.progress = json.load(f)
            print(f"📂 加载已有进度: 已完成{len(self.progress.get('completed', []))}只")
        else:
            self.progress = {'completed': [], 'failed': [], 'last_update': None}
            
    def _save_progress(self):
        """保存进度"""
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
        
    def fetch_to_cache(self):
        """拉取数据到缓存（支持断点续传）"""
        print(f"\n📥 步骤3: 拉取数据到缓存 (共{len(self.stocks)}只股票)...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 获取待处理列表
        completed = set(self.progress['completed'])
        pending = [s for s in self.stocks if s not in completed]
        
        print(f"   📊 已缓存: {len(completed)}只, 待拉取: {len(pending)}只")
        
        failed_stocks = []
        batch_count = 0
        last_save_time = time.time()
        
        for i, symbol in enumerate(pending, 1):
            if should_exit:
                print(f"\n⏹️  用户中断，已保存进度")
                break
                
            cache_file = CACHE_DIR / f"{symbol}.json"
            
            # 跳过已存在的
            if cache_file.exists():
                print(f"   [{i}/{len(pending)}] {symbol} - 缓存已存在，跳过")
                self.progress['completed'].append(symbol)
                self.stats['skipped'] += 1
                continue
                
            print(f"   [{i}/{len(pending)}] {symbol} - 拉取中...", end=' ', flush=True)
            
            try:
                # 获取历史数据
                df = self.ths.get_full_history(symbol)
                
                if df is not None and not df.empty:
                    # 过滤到2026-03-19
                    df = df[df['date'] <= END_DATE]
                    
                    # 保存到缓存
                    data = df.to_dict('records')
                    with open(cache_file, 'w') as f:
                        json.dump(data, f)
                    
                    print(f"✅ {len(df)}条")
                    self.progress['completed'].append(symbol)
                    self.stats['success'] += 1
                    self.stats['total_records'] += len(df)
                else:
                    print(f"⚠️ 无数据")
                    failed_stocks.append(symbol)
                    self.progress['failed'].append(symbol)
                    self.stats['failed'] += 1
                    
            except Exception as e:
                print(f"❌ 失败: {str(e)[:30]}")
                failed_stocks.append(symbol)
                self.progress['failed'].append(symbol)
                self.stats['failed'] += 1
            
            # 每10秒保存一次进度
            if time.time() - last_save_time > 10:
                self._save_progress()
                last_save_time = time.time()
            
            # 批次控制
            batch_count += 1
            if batch_count >= BATCH_SIZE:
                self.stats['batches_completed'] += 1
                self._save_progress()
                print(f"\n   ⏸️ 批次完成 ({BATCH_SIZE}只)，暂停{BATCH_DELAY}秒...")
                time.sleep(BATCH_DELAY)
                batch_count = 0
        
        # 最终保存
        self._save_progress()
                
        # 保存失败列表
        if failed_stocks:
            with open(CACHE_DIR / 'failed_stocks.json', 'w') as f:
                json.dump(failed_stocks, f)
                
        print(f"\n   ✅ 拉取阶段完成: 成功{self.stats['success']}只, 失败{self.stats['failed']}只, 跳过{self.stats['skipped']}只")
        return failed_stocks
        
    def import_to_database(self):
        """从缓存导入数据库"""
        print("\n💾 步骤4: 导入数据到数据库...")
        
        cache_files = list(CACHE_DIR.glob('*.json'))
        cache_files = [f for f in cache_files if f.name not in ('failed_stocks.json', '.progress.json')]
        
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
        
    def run(self, skip_backup=False, skip_fetch=False):
        """执行完整流程"""
        print("="*60)
        print(f"🚀 全量数据重拉任务启动")
        print(f"📅 目标日期: {END_DATE}")
        print(f"📊 股票数量: {len(self.stocks)}只")
        print("="*60)
        
        try:
            # 步骤1: 备份
            if not skip_backup:
                backup_file = self.backup_current_data()
            else:
                print("\n💾 跳过备份（使用 --skip-backup）")
                
            # 步骤2: 清空（仅在非断点续传时）
            if not self.progress['completed'] and not skip_backup:
                self.clear_database()
            else:
                print(f"\n🗑️ 跳过清空（已有{len(self.progress['completed'])}只缓存）")
                
            # 步骤3: 拉取到缓存
            if not skip_fetch:
                failed = self.fetch_to_cache()
            else:
                print("\n📥 跳过拉取（使用 --skip-fetch）")
                
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
            if not skip_backup:
                print(f"💾 备份文件: {backup_file}")
                
        except Exception as e:
            print(f"\n❌ 任务异常: {e}")
            self._save_progress()
            import traceback
            traceback.print_exc()
            raise

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-backup', action='store_true', help='跳过备份')
    parser.add_argument('--skip-fetch', action='store_true', help='跳过拉取，直接导入缓存')
    args = parser.parse_args()
    
    refresher = FullDataRefresher()
    refresher.run(skip_backup=args.skip_backup, skip_fetch=args.skip_fetch)
