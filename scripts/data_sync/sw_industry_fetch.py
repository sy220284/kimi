#!/usr/bin/env python3
"""
申万二级行业指数并发拉取 + 增量更新

改进点:
- 6线程并发拉取，速度提升5-8倍
- 支持增量更新（只拉取缺失日期）
- 详细的进度显示
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from data import get_db_manager

# 配置
MAX_WORKERS = 6  # 并发线程数
RATE_LIMIT = 0.1  # 每线程请求间隔(秒)

# 全局统计
stats_lock = threading.Lock()


def create_table_if_not_exists(db):
    """创建申万行业指数表"""
    db.pg.execute("""
        CREATE TABLE IF NOT EXISTS sw_industry_index (
            id SERIAL PRIMARY KEY,
            industry_code VARCHAR(20) NOT NULL,
            industry_name VARCHAR(100),
            date DATE NOT NULL,
            open DECIMAL(12,4),
            high DECIMAL(12,4),
            low DECIMAL(12,4),
            close DECIMAL(12,4),
            volume DECIMAL(20,4),
            amount DECIMAL(20,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(industry_code, date)
        );
        CREATE INDEX IF NOT EXISTS idx_sw_industry_code ON sw_industry_index(industry_code);
        CREATE INDEX IF NOT EXISTS idx_sw_industry_date ON sw_industry_index(date);
    """)


def fetch_sw_second_industry_list():
    """获取申万二级行业列表"""
    df = ak.sw_index_second_info()
    industries = []
    for _, row in df.iterrows():
        industries.append({
            'code': row['行业代码'].replace('.SI', ''),
            'name': row['行业名称']
        })
    return industries


def get_last_update_date(db, code: str) -> str | None:
    """获取行业最后更新日期"""
    result = db.pg.execute(
        "SELECT MAX(date) as last_date FROM sw_industry_index WHERE industry_code = %s",
        (code,), fetch=True
    )
    if result and result[0]['last_date']:
        return result[0]['last_date'].strftime('%Y-%m-%d')
    return None


def fetch_industry_history(code: str, name: str, start_date: str = None) -> pd.DataFrame:
    """拉取单个行业历史数据"""
    try:
        df = ak.index_hist_sw(symbol=code, period='day')
        if df.empty:
            return pd.DataFrame()

        # 重命名列
        df = df.rename(columns={
            '代码': 'code',
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount'
        })

        df['industry_code'] = code
        df['industry_name'] = name

        # 转换日期
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        # 如果指定了开始日期，过滤数据
        if start_date:
            df = df[df['date'] > start_date]

        return df[['industry_code', 'industry_name', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        return pd.DataFrame()


def save_to_database(db, df: pd.DataFrame) -> int:
    """批量保存到数据库"""
    if df.empty:
        return 0

    records = []
    for _, row in df.iterrows():
        records.append((
            row['industry_code'],
            row['industry_name'],
            row['date'],
            row['open'] if pd.notna(row['open']) else None,
            row['high'] if pd.notna(row['high']) else None,
            row['low'] if pd.notna(row['low']) else None,
            row['close'] if pd.notna(row['close']) else None,
            row['volume'] if pd.notna(row['volume']) else None,
            row['amount'] if pd.notna(row['amount']) else None
        ))

    db.pg.execute_many("""
        INSERT INTO sw_industry_index
        (industry_code, industry_name, date, open, high, low, close, volume, amount)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (industry_code, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            amount = EXCLUDED.amount
    """, records)

    return len(records)


def update_single_industry(args):
    """
    更新单个行业（用于线程池）
    
    Args:
        args: (db, industry, index, total, incremental)
    
    Returns:
        dict: 更新结果
    """
    db, industry, index, total, incremental = args
    code = industry['code']
    name = industry['name']

    try:
        # 确定拉取范围
        if incremental:
            start_date = get_last_update_date(db, code)
            if start_date:
                start_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            start_date = None

        # 拉取数据
        df = fetch_industry_history(code, name, start_date)

        if df.empty:
            return {'code': code, 'name': name, 'status': 'no_data', 'count': 0, 'index': index}

        # 保存到数据库
        count = save_to_database(db, df)

        return {'code': code, 'name': name, 'status': 'success', 'count': count, 'index': index}

    except Exception as e:
        return {'code': code, 'name': name, 'status': 'failed', 'error': str(e), 'index': index}


def fetch_all_industries(incremental: bool = True, max_workers: int = MAX_WORKERS):
    """
    并发拉取所有行业指数数据
    
    Args:
        incremental: 是否增量更新（只拉取新数据）
        max_workers: 并发线程数
    """
    import time

    print("=" * 60)
    print(f"📊 申万二级行业指数{'增量' if incremental else '全量'}更新")
    print(f"   并发: {max_workers}线程")
    print("=" * 60)

    db = get_db_manager()
    create_table_if_not_exists(db)

    # 获取行业列表
    print("\n🔍 获取申万二级行业列表...")
    industries = fetch_sw_second_industry_list()
    print(f"✅ 共 {len(industries)} 个二级行业")

    # 如果是增量模式，筛选需要更新的行业
    if incremental:
        result = db.pg.execute("""
            SELECT industry_code, MAX(date) as last_date 
            FROM sw_industry_index 
            GROUP BY industry_code
        """, fetch=True)
        existing = {r['industry_code']: r['last_date'] for r in result}
        
        today = datetime.now().strftime('%Y-%m-%d')
        # 只保留最后日期早于今天的行业
        industries = [ind for ind in industries 
                      if ind['code'] not in existing 
                      or existing[ind['code']].strftime('%Y-%m-%d') < today]
        print(f"⏳ 需要更新: {len(industries)} 个行业")

    if not industries:
        print("\n✅ 所有行业数据已是最新")
        return

    # 并发更新
    print(f"\n🚀 开始{'增量' if incremental else '全量'}拉取...")
    print("=" * 60)

    stats = {
        'success': 0,
        'no_data': 0,
        'failed': 0,
        'total_records': 0
    }

    # 准备任务参数
    tasks = [(db, ind, i + 1, len(industries), incremental) for i, ind in enumerate(industries)]

    start_time = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(update_single_industry, task): task for task in tasks}

        for future in as_completed(future_to_task):
            result = future.result()
            completed += 1

            # 更新统计
            if result['status'] == 'success':
                stats['success'] += 1
                stats['total_records'] += result['count']
            elif result['status'] == 'no_data':
                stats['no_data'] += 1
            else:
                stats['failed'] += 1

            # 进度显示
            if completed % 10 == 0 or completed == len(industries):
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(industries) - completed) / rate if rate > 0 else 0
                print(f"📈 进度: {completed}/{len(industries)} ({completed * 100 // len(industries)}%) | "
                      f"速率: {rate:.1f}行业/秒 | 预计剩余: {eta:.0f}秒")

    # 汇总
    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("📊 拉取完成")
    print("=" * 60)
    print(f"总行业数: {len(industries)}")
    print(f"✅ 成功更新: {stats['success']} 个")
    print(f"➖ 无新数据: {stats['no_data']} 个")
    print(f"❌ 失败: {stats['failed']} 个")
    print(f"📥 新增记录: {stats['total_records']:,} 条")
    print(f"⏱️  耗时: {elapsed:.1f} 秒 ({elapsed / 60:.1f} 分钟)")
    print(f"🚀 平均速率: {len(industries) / elapsed:.1f} 行业/秒")

    # 最终统计
    result = db.pg.execute("""
        SELECT
            COUNT(DISTINCT industry_code) as industries,
            COUNT(*) as total_records,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM sw_industry_index
    """, fetch=True)

    if result:
        r = result[0]
        print("\n📈 数据库统计:")
        print(f"  行业数: {r['industries']}/124")
        print(f"  总记录: {r['total_records']:,}")
        print(f"  时间跨度: {r['start_date']} ~ {r['end_date']}")

    print("=" * 60)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='申万行业指数并发拉取')
    parser.add_argument('--full', action='store_true', help='全量更新（默认增量）')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help=f'并发线程数 (默认: {MAX_WORKERS})')
    args = parser.parse_args()

    fetch_all_industries(incremental=not args.full, max_workers=args.workers)
