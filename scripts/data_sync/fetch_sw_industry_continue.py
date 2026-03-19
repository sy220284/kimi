#!/usr/bin/env python3
"""
继续拉取剩余申万二级行业指数历史数据
"""
import sys
from pathlib import Path
# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import akshare as ak
import pandas as pd

from data import get_db_manager


def fetch_industry_history(code: str, name: str) -> pd.DataFrame:
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

        return df[['industry_code', 'industry_name', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        print(f"  ❌ {code} 拉取失败: {e}")
        return pd.DataFrame()


def save_to_database(db, df: pd.DataFrame):
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


def main():
    print("=" * 60)
    print("📊 继续拉取申万二级行业指数数据")
    print("=" * 60)

    db = get_db_manager()

    # 获取行业列表
    industries_df = ak.sw_index_second_info()
    industries = []
    for _, row in industries_df.iterrows():
        industries.append({
            'code': row['行业代码'].replace('.SI', ''),
            'name': row['行业名称']
        })

    # 检查已存在的行业
    result = db.pg.execute('SELECT DISTINCT industry_code FROM sw_industry_index', fetch=True)
    existing_codes = {r['industry_code'] for r in result}
    print(f"✅ 已有 {len(existing_codes)} 个行业")

    # 筛选未完成的行业
    pending = [ind for ind in industries if ind['code'] not in existing_codes]
    print(f"⏳ 待拉取 {len(pending)} 个行业")

    # 拉取每个行业的历史数据
    print("\n📥 开始拉取...")
    total_records = 0
    success_count = 0

    for i, industry in enumerate(pending, 1):
        code = industry['code']
        name = industry['name']

        print(f"[{i}/{len(pending)}] {code} {name}...", end=' ', flush=True)

        df = fetch_industry_history(code, name)
        if not df.empty:
            count = save_to_database(db, df)
            total_records += count
            success_count += 1
            print(f"✅ {count}条")
        else:
            print("❌ 无数据")

    print("\n" + "=" * 60)
    print("📊 拉取完成")
    print("=" * 60)
    print(f"成功行业: {success_count}/{len(pending)}")
    print(f"新增记录: {total_records:,}")

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


if __name__ == '__main__':
    main()
