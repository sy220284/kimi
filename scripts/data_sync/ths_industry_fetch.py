#!/usr/bin/env python3
"""
同花顺行业指数并发拉取 + 增量更新

特点:
- 90个同花顺行业板块
- 6线程并发拉取
- 支持增量更新
- 数据源: 同花顺 (bk_xxxxx格式)

注意: 同花顺last.js接口返回最近140个交易日数据
      需要每日运行以累积完整历史
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import re
import json
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd

from data import get_db_manager

# 配置
MAX_WORKERS = 6
RATE_LIMIT = 0.05

# 同花顺行业板块列表 (90个)
THS_INDUSTRIES = [
    ('881121', '半导体'), ('881273', '白酒'), ('881131', '白色家电'),
    ('881156', '保险'), ('881138', '包装印刷'), ('881174', '厨卫电器'),
    ('881281', '电池'), ('881277', '电机'), ('881145', '电力'),
    ('881278', '电网设备'), ('881146', '电子化学品'), ('881122', '电子元件'),
    ('881283', '房地产'), ('881164', '纺织制造'), ('881147', '非金属材料'),
    ('881279', '非汽车交运'), ('881280', '服装家纺'), ('881148', '钢铁'),
    ('881282', '港口航运'), ('881149', '高低压设备'), ('881276', '工程机械'),
    ('881275', '工业金属'), ('881285', '公用事业'), ('881150', '光学光电子'),
    ('881284', '贵金属'), ('881286', '国防军工'), ('881151', '化工合成材料'),
    ('881152', '化工新材料'), ('881153', '化学制品'), ('881154', '化学原料'),
    ('881155', '环保'), ('881157', '机场航运'), ('881158', '计算机设备'),
    ('881159', '计算机应用'), ('881160', '家居用品'), ('881161', '家用电器'),
    ('881162', '建筑材料'), ('881163', '建筑装饰'), ('881165', '酒店餐饮'),
    ('881166', '零售'), ('881167', '旅游及景区'), ('881168', '贸易'),
    ('881169', '煤炭开采'), ('881170', '美容护理'), ('881171', '汽车零部件'),
    ('881172', '其他电子'), ('881173', '其他社会服务'), ('881175', '燃气'),
    ('881176', '汽车零部件'), ('881177', '食品加工'), ('881178', '石油加工'),
    ('881179', '石油开采'), ('881180', '通信服务'), ('881181', '通信设备'),
    ('881182', '通用设备'), ('881183', '物流'), ('881184', '小金属'),
    ('881185', '新材料'), ('881186', '油气开采'), ('881187', '饮料制造'),
    ('881188', '银行'), ('881189', '游戏'), ('881190', '证券'),
    ('881191', '专用设备'), ('881192', '自动化设备'), ('881193', '综合'),
    ('881194', '种植业'), ('881195', '养殖业'), ('881196', '医疗器械'),
    ('881197', '医疗服务'), ('881198', '医药商业'), ('881199', '中药'),
    ('881200', '化学制药'), ('881201', '生物制品'), ('881202', '医疗美容'),
    ('881203', '教育'), ('881204', '体育'), ('881205', '文化传媒'),
    ('881206', '互联网电商'), ('881207', '房地产服务'), ('881208', '工程咨询服务'),
    ('881209', '专业连锁'), ('881210', '旅游零售'),
]

# 全局统计
stats_lock = threading.Lock()


def create_table_if_not_exists(db):
    """创建同花顺行业指数表"""
    db.pg.execute("""
        CREATE TABLE IF NOT EXISTS ths_industry_index (
            id SERIAL PRIMARY KEY,
            industry_code VARCHAR(20) NOT NULL,
            industry_name VARCHAR(100),
            date DATE NOT NULL,
            open DECIMAL(12,4),
            high DECIMAL(12,4),
            low DECIMAL(12,4),
            close DECIMAL(12,4),
            volume BIGINT,
            amount DECIMAL(20,4),
            data_source VARCHAR(20) DEFAULT 'THS_INDUSTRY',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(industry_code, date)
        );
        CREATE INDEX IF NOT EXISTS idx_ths_industry_code ON ths_industry_index(industry_code);
        CREATE INDEX IF NOT EXISTS idx_ths_industry_date ON ths_industry_index(date);
    """)


def get_last_update_date(db, code: str) -> str | None:
    """获取行业最后更新日期"""
    result = db.pg.execute(
        "SELECT MAX(date) as last_date FROM ths_industry_index WHERE industry_code = %s",
        (code,), fetch=True
    )
    if result and result[0]['last_date']:
        return result[0]['last_date'].strftime('%Y-%m-%d')
    return None


def fetch_industry_history_ths(code: str, name: str) -> pd.DataFrame:
    """从同花顺获取行业历史数据"""
    try:
        url = f'http://d.10jqka.com.cn/v4/line/bk_{code}/01/last.js'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'http://stockpage.10jqka.com.cn/{code}/'
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return pd.DataFrame()

        match = re.search(r'quotebridge_[\w_]+\(({.+})\);?$', response.text, re.DOTALL)
        if not match:
            return pd.DataFrame()

        data = json.loads(match.group(1))

        if 'data' not in data or not data['data']:
            return pd.DataFrame()

        # 解析数据: "日期,开盘价,最高价,最低价,收盘价,成交量,成交额,..."
        lines = data['data'].split(';')
        records = []

        for line in lines:
            if not line:
                continue
            parts = line.split(',')
            if len(parts) >= 5:
                date_str = parts[0]
                # 日期格式: YYYYMMDD -> YYYY-MM-DD
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                records.append({
                    'industry_code': code,
                    'industry_name': name,
                    'date': formatted_date,
                    'open': float(parts[1]),
                    'high': float(parts[2]),
                    'low': float(parts[3]),
                    'close': float(parts[4]),
                    'volume': int(float(parts[5])) if len(parts) > 5 else 0,
                    'amount': float(parts[6]) if len(parts) > 6 else 0
                })

        return pd.DataFrame(records)

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
            row['volume'] if pd.notna(row['volume']) else 0,
            row['amount'] if pd.notna(row['amount']) else 0
        ))

    db.pg.execute_many("""
        INSERT INTO ths_industry_index
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
    """更新单个行业"""
    db, code, name, index, total, incremental = args

    try:
        # 获取数据
        df = fetch_industry_history_ths(code, name)

        if df.empty:
            return {'code': code, 'name': name, 'status': 'no_data', 'count': 0, 'index': index}

        # 增量模式：过滤已存在的数据
        if incremental:
            last_date = get_last_update_date(db, code)
            if last_date:
                df = df[df['date'] > last_date]

        if df.empty:
            return {'code': code, 'name': name, 'status': 'up_to_date', 'count': 0, 'index': index}

        # 保存到数据库
        count = save_to_database(db, df)

        return {'code': code, 'name': name, 'status': 'success', 'count': count, 'index': index}

    except Exception as e:
        return {'code': code, 'name': name, 'status': 'failed', 'error': str(e), 'index': index}


def fetch_all_industries(incremental: bool = True, max_workers: int = MAX_WORKERS):
    """并发拉取所有同花顺行业指数"""
    import time

    print("=" * 60)
    print(f"📊 同花顺行业指数{'增量' if incremental else '全量'}更新")
    print(f"   并发: {max_workers}线程")
    print("=" * 60)

    db = get_db_manager()
    create_table_if_not_exists(db)

    # 获取行业列表
    industries = THS_INDUSTRIES
    print(f"\n🔍 同花顺行业板块: {len(industries)} 个")

    # 如果是增量模式，筛选需要更新的行业
    if incremental:
        result = db.pg.execute("""
            SELECT industry_code, MAX(date) as last_date 
            FROM ths_industry_index 
            GROUP BY industry_code
        """, fetch=True)
        existing = {r['industry_code']: r['last_date'] for r in result}

        today = datetime.now().strftime('%Y-%m-%d')
        industries = [(c, n) for c, n in industries
                      if c not in existing
                      or existing[c].strftime('%Y-%m-%d') < today]
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
        'up_to_date': 0,
        'failed': 0,
        'total_records': 0
    }

    tasks = [(db, c, n, i + 1, len(industries), incremental) for i, (c, n) in enumerate(industries)]

    start_time = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(update_single_industry, task): task for task in tasks}

        for future in as_completed(future_to_task):
            result = future.result()
            completed += 1

            if result['status'] == 'success':
                stats['success'] += 1
                stats['total_records'] += result['count']
            elif result['status'] == 'no_data':
                stats['no_data'] += 1
            elif result['status'] == 'up_to_date':
                stats['up_to_date'] += 1
            else:
                stats['failed'] += 1

            if completed % 10 == 0 or completed == len(industries):
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(industries) - completed) / rate if rate > 0 else 0
                print(f"📈 进度: {completed}/{len(industries)} ({completed * 100 // len(industries)}%) | "
                      f"速率: {rate:.1f}行业/秒 | 预计剩余: {eta:.0f}秒")

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("📊 拉取完成")
    print("=" * 60)
    print(f"总行业数: {len(tasks)}")
    print(f"✅ 成功更新: {stats['success']} 个")
    print(f"➖ 无新数据: {stats['no_data']} 个")
    print(f"✓ 已是最新: {stats['up_to_date']} 个")
    print(f"❌ 失败: {stats['failed']} 个")
    print(f"📥 新增记录: {stats['total_records']:,} 条")
    print(f"⏱️  耗时: {elapsed:.1f} 秒 ({elapsed / 60:.1f} 分钟)")
    print(f"🚀 平均速率: {len(tasks) / elapsed:.1f} 行业/秒")

    # 最终统计
    result = db.pg.execute("""
        SELECT
            COUNT(DISTINCT industry_code) as industries,
            COUNT(*) as total_records,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM ths_industry_index
    """, fetch=True)

    if result:
        r = result[0]
        print("\n📈 数据库统计:")
        print(f"  行业数: {r['industries']}/{len(THS_INDUSTRIES)}")
        print(f"  总记录: {r['total_records']:,}")
        print(f"  时间跨度: {r['start_date']} ~ {r['end_date']}")
        print(f"  ⚠️ 注意: 同花顺接口返回最近140个交易日数据")
        print(f"    建议每日运行以累积完整历史")

    print("=" * 60)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='同花顺行业指数并发拉取')
    parser.add_argument('--full', action='store_true', help='全量更新（默认增量）')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS,
                        help=f'并发线程数 (默认: {MAX_WORKERS})')
    args = parser.parse_args()

    fetch_all_industries(incremental=not args.full, max_workers=args.workers)
