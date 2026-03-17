#!/usr/bin/env python3
"""
全量历史数据同步 - 从上市日起
将多只股票从IPO到目前的完整历史导入数据库
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from data import DatabaseDataManager, ThsAdapter
from datetime import datetime

print("="*80)
print("📥 全量历史数据同步 - 从上市日起")
print("="*80)

# 股票列表 (代码, 名称, 上市年份)
STOCKS = [
    ('000001', '平安银行', 1991),
    ('000858', '五粮液', 1998),
    ('002184', '海得控制', 2007),
    ('002594', '比亚迪', 2011),
    ('300750', '宁德时代', 2018),
    ('600138', '中青旅', 1997),
    ('600519', '贵州茅台', 2001),
    ('600556', '天下秀', 2000),
]

manager = DatabaseDataManager()
ths = ThsAdapter({'enabled': True})

print(f"\n准备同步 {len(STOCKS)} 只股票的完整历史数据...")
print("数据范围: 从上市日至 2026-03-16\n")

results = []
total_records = 0

for symbol, name, ipo_year in STOCKS:
    print(f"📊 {name} ({symbol}) - {ipo_year}年上市")
    print("-" * 70)
    
    try:
        # 从上市年份获取全量数据
        df = ths.get_full_history(symbol, ipo_year, 2026)
        
        if df.empty:
            print(f"   ❌ 无数据")
            results.append({'symbol': symbol, 'name': name, 'error': '无数据'})
            continue
        
        # 保存到数据库
        count = len(df)
        manager._save_to_database(symbol, df)
        total_records += count
        
        result = {
            'symbol': symbol,
            'name': name,
            'synced': count,
            'start_date': df['date'].min(),
            'end_date': df['date'].max(),
            'years': 2026 - ipo_year + 1
        }
        results.append(result)
        
        print(f"   ✅ 同步完成: {count:,} 条记录")
        print(f"   📅 数据范围: {df['date'].min()} ~ {df['date'].max()}")
        print(f"   📊 约 {result['years']} 年数据")
        
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results.append({'symbol': symbol, 'name': name, 'error': str(e)})
    
    print()

# 最终统计
print("="*80)
print("📈 同步结果统计")
print("="*80)

success = sum(1 for r in results if 'synced' in r)

print(f"\n成功: {success}/{len(STOCKS)} 只股票")
print(f"总记录数: {total_records:,} 条")

print("\n详细:")
for r in results:
    if 'error' in r:
        print(f"   ❌ {r['symbol']} ({r['name']}): {r['error'][:50]}")
    else:
        print(f"   ✅ {r['symbol']} ({r['name']}): {r['synced']:,} 条 ({r['start_date']} ~ {r['end_date']})")

# 数据库最终统计
print("\n" + "="*80)
print("🗄️ 数据库最终统计")
print("="*80)

stored = manager.get_stored_symbols()
print(f"共 {len(stored)} 只股票")

# 查询每只股票的数据量
for symbol in sorted(stored):
    try:
        df = manager._query_database(symbol, '1990-01-01', '2026-12-31')
        if not df.empty:
            start = df['date'].min()
            end = df['date'].max()
            count = len(df)
            print(f"   {symbol}: {count:,} 条 ({start} ~ {end})")
    except:
        pass

manager.close()

print("\n✅ 全量历史数据同步完成!")
print(f"📊 总计: {total_records:,} 条记录已入库")
