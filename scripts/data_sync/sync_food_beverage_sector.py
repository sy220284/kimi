#!/usr/bin/env python3
"""
食品饮料板块成分股全量历史数据同步
申万食品饮料行业主要成份股
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from pathlib import Path


from data import DatabaseDataManager, ThsAdapter

print("="*80)
print("🍺 食品饮料板块 - 全量历史数据同步")
print("="*80)

# 申万食品饮料行业主要成份股 (白酒、啤酒、调味品、乳制品、食品)
FOOD_BEVERAGE_STOCKS = [
    # 白酒 (核心)
    ('600519', '贵州茅台', 2001),
    ('000858', '五粮液', 1998),
    ('000568', '泸州老窖', 1994),
    ('600809', '山西汾酒', 1994),
    ('002304', '洋河股份', 2009),
    ('603369', '今世缘', 2014),
    ('600779', '水井坊', 1996),
    ('000596', '古井贡酒', 1996),
    ('600702', '舍得酒业', 1996),
    ('600197', '伊力特', 1999),
    ('603198', '迎驾贡酒', 2015),
    ('603589', '口子窖', 2015),
    ('600559', '老白干酒', 2002),
    ('000799', '酒鬼酒', 1997),
    ('603919', '金徽酒', 2016),

    # 啤酒
    ('600600', '青岛啤酒', 1993),
    ('002461', '珠江啤酒', 2010),
    ('600132', '重庆啤酒', 1997),
    ('000729', '燕京啤酒', 1997),

    # 乳制品
    ('600887', '伊利股份', 1996),
    ('600597', '光明乳业', 2002),
    ('002732', '燕塘乳业', 2014),
    ('002946', '新乳业', 2019),

    # 调味品
    ('603288', '海天味业', 2014),
    ('603027', '千禾味业', 2016),
    ('600872', '中炬高新', 1995),
    ('002507', '涪陵榨菜', 2010),
    ('603317', '天味食品', 2019),

    # 食品综合
    ('300999', '金龙鱼', 2020),
    ('002557', '洽洽食品', 2011),
    ('603517', '绝味食品', 2017),
    ('300146', '汤臣倍健', 2010),
    ('603043', '广州酒家', 2017),
    ('600298', '安琪酵母', 2000),
    ('002568', '百润股份', 2011),
    ('603345', '安井食品', 2017),
    ('300973', '立高食品', 2021),
    ('605499', '东鹏饮料', 2021),
]

manager = DatabaseDataManager()
ths = ThsAdapter({'enabled': True})

print(f"\n准备同步 {len(FOOD_BEVERAGE_STOCKS)} 只食品饮料股...")
print("="*80)

results = []
total_records = 0
success_count = 0
fail_count = 0

for i, (symbol, name, ipo_year) in enumerate(FOOD_BEVERAGE_STOCKS, 1):
    print(f"\n[{i}/{len(FOOD_BEVERAGE_STOCKS)}] {name} ({symbol}) - {ipo_year}年上市")
    print("-" * 70)

    try:
        # 从上市年份获取全量数据
        df = ths.get_full_history(symbol, ipo_year, 2026)

        if df.empty:
            print("   ⚠️ 无数据，尝试获取近5年...")
            df = ths.get_full_history(symbol, 2021, 2026)
            if df.empty:
                print("   ❌ 仍无数据，跳过")
                results.append({'symbol': symbol, 'name': name, 'error': '无数据'})
                fail_count += 1
                continue

        # 保存到数据库
        count = len(df)
        manager._save_to_database(symbol, df)
        total_records += count
        success_count += 1

        result = {
            'symbol': symbol,
            'name': name,
            'synced': count,
            'start_date': df['date'].min(),
            'end_date': df['date'].max(),
        }
        results.append(result)

        print(f"   ✅ 同步完成: {count:,} 条")
        print(f"   📅 范围: {df['date'].min()} ~ {df['date'].max()}")

    except Exception as e:
        print(f"   ❌ 失败: {str(e)[:60]}")
        results.append({'symbol': symbol, 'name': name, 'error': str(e)})
        fail_count += 1

# 最终统计
print("\n" + "="*80)
print("📊 食品饮料板块同步统计")
print("="*80)

print("\n总计:")
print(f"  成功: {success_count} 只")
print(f"  失败: {fail_count} 只")
print(f"  总记录数: {total_records:,} 条")

# 按子行业分组显示
print("\n白酒:")
for r in results:
    if 'error' not in r and r['name'] in ['贵州茅台','五粮液','泸州老窖','山西汾酒','洋河股份','今世缘','水井坊','古井贡酒','舍得酒业','伊力特','迎驾贡酒','口子窖','老白干酒','酒鬼酒','金徽酒']:
        print(f"   ✅ {r['symbol']} {r['name']}: {r['synced']:,}条 ({r['start_date']}~{r['end_date']})")

print("\n啤酒:")
for r in results:
    if 'error' not in r and r['name'] in ['青岛啤酒','珠江啤酒','重庆啤酒','燕京啤酒']:
        print(f"   ✅ {r['symbol']} {r['name']}: {r['synced']:,}条")

print("\n乳制品:")
for r in results:
    if 'error' not in r and r['name'] in ['伊利股份','光明乳业','燕塘乳业','新乳业']:
        print(f"   ✅ {r['symbol']} {r['name']}: {r['synced']:,}条")

print("\n调味品:")
for r in results:
    if 'error' not in r and r['name'] in ['海天味业','千禾味业','中炬高新','涪陵榨菜','天味食品']:
        print(f"   ✅ {r['symbol']} {r['name']}: {r['synced']:,}条")

# 数据库最终统计
print("\n" + "="*80)
print("🗄️ 数据库最终统计")
print("="*80)

stored = manager.get_stored_symbols()
food_stocks = [r['symbol'] for r in results if 'error' not in r]
print(f"食品饮料板块: {len(food_stocks)} 只股票已入库")
print(f"数据库总计: {len(stored)} 只股票")

manager.close()

print("\n✅ 食品饮料板块数据同步完成!")
print(f"📊 板块总计: {total_records:,} 条历史记录")
