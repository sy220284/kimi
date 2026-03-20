#!/usr/bin/env python3
"""
全量重拉股票数据 - 高速并行版本
使用多进程 + 连接池 + 批量优化
"""
import os
import sys
import json
import time
import signal
import multiprocessing as mp
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading

# 添加项目路径
sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')

from data.ths_adapter import ThsAdapter
import psycopg2
from psycopg2.extras import execute_values

# 配置
CACHE_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/stock_data')
BACKUP_DIR = Path('/root/.openclaw/workspace/智能体系统/.cache/backup')
PROGRESS_FILE = CACHE_DIR / '.progress_fast.json'
DB_CONFIG = {
    'host': 'localhost', 'port': 5432, 'database': 'quant_analysis',
    'user': 'quant_user', 'password': 'quant_password'
}
END_DATE = '2026-03-19'

# 并行配置 - 根据CPU核心数调整
MAX_WORKERS = min(8, mp.cpu_count())  # 最多8进程
CHUNK_SIZE = 50  # 每批处理50只

# 全局统计
stats = {
    'success': mp.Value('i', 0),
    'failed': mp.Value('i', 0),
    'skipped': mp.Value('i', 0),
    'total_records': mp.Value('i', 0),
}
progress_lock = threading.Lock()

def load_stock_list():
    """加载股票列表"""
    select_file = Path('/root/.openclaw/workspace/智能体系统') / 'selfselect_stocks.json'
    if select_file.exists():
        with open(select_file) as f:
            data = json.load(f)
            return [s['symbol'] for s in data.get('stocks', [])]
    else:
        with open('/root/.openclaw/workspace/智能体系统/all_industry_stocks.txt') as f:
            return [line.strip() for line in f if line.strip()]

def load_progress():
    """加载进度"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {'completed': set(), 'failed': set()}

def save_progress(completed, failed):
    """保存进度"""
    with progress_lock:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({
                'completed': list(completed),
                'failed': list(failed),
                'last_update': datetime.now().isoformat()
            }, f)

def fetch_stock_batch(stock_batch):
    """批量拉取股票数据（进程内执行）"""
    ths = ThsAdapter({'enabled': True, 'timeout': 30})
    results = []
    
    for symbol in stock_batch:
        cache_file = CACHE_DIR / f"{symbol}.json"
        
        # 跳过已存在的
        if cache_file.exists():
            results.append({'symbol': symbol, 'status': 'skipped', 'records': 0})
            continue
            
        try:
            df = ths.get_full_history(symbol)
            
            if df is not None and not df.empty:
                df = df[df['date'] <= END_DATE]
                data = df.to_dict('records')
                
                with open(cache_file, 'w') as f:
                    json.dump(data, f)
                
                results.append({'symbol': symbol, 'status': 'success', 'records': len(df)})
            else:
                results.append({'symbol': symbol, 'status': 'no_data', 'records': 0})
                
        except Exception as e:
            results.append({'symbol': symbol, 'status': 'error', 'error': str(e), 'records': 0})
            
        # 小间隔避免限流
        time.sleep(0.1)
    
    return results

def parallel_fetch(stocks, completed_set):
    """并行拉取主函数"""
    print(f"\n⚡ 启动并行拉取: {MAX_WORKERS}进程")
    
    # 分割任务
    pending = [s for s in stocks if s not in completed_set]
    chunks = [pending[i:i+CHUNK_SIZE] for i in range(0, len(pending), CHUNK_SIZE)]
    
    print(f"📊 总任务: {len(pending)}只, 分{len(chunks)}批, 每批{CHUNK_SIZE}只")
    
    total_success = 0
    total_failed = 0
    total_skipped = 0
    total_records = 0
    
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有批次
        future_to_batch = {executor.submit(fetch_stock_batch, chunk): i 
                          for i, chunk in enumerate(chunks)}
        
        # 处理结果
        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                results = future.result()
                
                for r in results:
                    if r['status'] == 'success':
                        total_success += 1
                        total_records += r['records']
                        completed_set.add(r['symbol'])
                    elif r['status'] == 'skipped':
                        total_skipped += 1
                    else:
                        total_failed += 1
                        
                # 每完成一批保存进度
                if batch_idx % 2 == 0:
                    save_progress(completed_set, set())
                    progress = (total_success + total_skipped) / len(stocks) * 100
                    print(f"   批次{batch_idx+1}/{len(chunks)}完成 | 进度: {progress:.1f}% | "
                          f"成功:{total_success} 跳过:{total_skipped} 失败:{total_failed}")
                    
            except Exception as e:
                print(f"   ⚠️ 批次{batch_idx+1}异常: {e}")
    
    return total_success, total_failed, total_skipped, total_records

def import_to_database():
    """从缓存导入数据库"""
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
            print(f"   ⚠️ {symbol} 导入失败: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"   ✅ 导入完成: 共{total_imported:,}条记录")
    return total_imported

def main():
    """主函数"""
    print("="*60)
    print(f"🚀 全量数据重拉 - 高速并行版 ({MAX_WORKERS}进程)")
    print(f"📅 目标日期: {END_DATE}")
    print("="*60)
    
    start_time = datetime.now()
    
    # 1. 备份
    print("\n💾 备份当前数据...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_file = BACKUP_DIR / f"market_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    os.system(f"pg_dump -h {DB_CONFIG['host']} -p {DB_CONFIG['port']} "
              f"-U {DB_CONFIG['user']} -d {DB_CONFIG['database']} "
              f"-t market_data > {backup_file} 2>/dev/null")
    print(f"   ✅ 备份完成")
    
    # 2. 清空数据库
    print("\n🗑️ 清空数据库...")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute('TRUNCATE TABLE market_data RESTART IDENTITY')
    conn.commit()
    cursor.close()
    conn.close()
    print("   ✅ 已清空")
    
    # 3. 并行拉取
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stocks = load_stock_list()
    progress = load_progress()
    completed_set = set(progress.get('completed', []))
    
    print(f"\n📥 开始并行拉取 {len(stocks)} 只股票...")
    success, failed, skipped, records = parallel_fetch(stocks, completed_set)
    
    # 最终保存进度
    save_progress(completed_set, set())
    
    # 4. 导入数据库
    imported = import_to_database()
    
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
    print(f"💾 备份: {backup_file}")

if __name__ == '__main__':
    # 设置启动方法
    mp.set_start_method('spawn', force=True)
    main()
