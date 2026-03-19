#!/usr/bin/env python3
"""
拉取申万二级行业指数历史数据
"""
import sys
from pathlib import Path

import akshare as ak
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from data import get_db_manager


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
    print("✅ 表结构已创建/更新")


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
    print("📊 申万二级行业指数数据拉取")
    print("=" * 60)

    db = get_db_manager()
    create_table_if_not_exists(db)

    # 获取行业列表
    print("\n🔍 获取申万二级行业列表...")
    industries = fetch_sw_second_industry_list()
    print(f"✅ 共 {len(industries)} 个二级行业")

    # 检查已存在的数据
    result = db.pg.execute("SELECT COUNT(DISTINCT industry_code) as cnt FROM sw_industry_index", fetch=True)
    existing_industries = result[0]['cnt'] if result else 0
    print(f"📈 数据库已有 {existing_industries} 个行业数据")

    # 拉取每个行业的历史数据
    print("\n📥 开始拉取历史数据...")
    total_records = 0
    success_count = 0

    for i, industry in enumerate(industries, 1):
        code = industry['code']
        name = industry['name']

        print(f"\n[{i}/{len(industries)}] {code} {name}")

        df = fetch_industry_history(code, name)
        if not df.empty:
            count = save_to_database(db, df)
            total_records += count
            success_count += 1
            print(f"  ✅ 保存 {count} 条记录")

    print("\n" + "=" * 60)
    print("📊 拉取完成")
    print("=" * 60)
    print(f"成功行业: {success_count}/{len(industries)}")
    print(f"总记录数: {total_records:,}")

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
        print(f"  行业数: {r['industries']}")
        print(f"  总记录: {r['total_records']:,}")
        print(f"  时间跨度: {r['start_date']} ~ {r['end_date']}")


if __name__ == '__main__':
    main()
