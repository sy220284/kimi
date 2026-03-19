#!/usr/bin/env python3
"""
全量历史数据同步工具
将多只股票完整历史数据导入数据库
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path



from data import DatabaseDataManager

print("="*80)
print("📥 全量历史数据同步")
print("="*80)

# 股票列表 (可扩展)
STOCKS = [
    ('000001', '平安银行'),
    ('002184', '海得控制'),
    ('600138', '中青旅'),
    ('600556', '天下秀'),
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
    ('300750', '宁德时代'),
    ('002594', '比亚迪'),
]

manager = DatabaseDataManager()

print(f"\n准备同步 {len(STOCKS)} 只股票的全量历史数据...")
print("数据范围: 2020-01-01 至今 (约5年+)\n")

results = []

for symbol, name in STOCKS:
    print(f"📊 {name} ({symbol})")
    print("-" * 60)

    try:
        # 同步5年历史数据
        count = manager.sync_symbol(symbol, years=5)

        # 验证
        df = manager.get_stock_data(symbol, '2020-01-01', '2026-03-17')

        result = {
            'symbol': symbol,
            'name': name,
            'synced': count,
            'in_db': len(df),
            'start': df['date'].min() if not df.empty else None,
            'end': df['date'].max() if not df.empty else None
        }
        results.append(result)

        print(f"   ✅ 同步完成: {count} 条")
        if not df.empty:
            print(f"   📅 数据范围: {df['date'].min()} ~ {df['date'].max()}")
            print(f"   📊 数据库验证: {len(df)} 条")

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        results.append({'symbol': symbol, 'name': name, 'error': str(e)})

    print()

# 最终统计
print("="*80)
print("📈 同步结果统计")
print("="*80)

total_synced = sum(r.get('synced', 0) for r in results if 'synced' in r)
success = sum(1 for r in results if 'synced' in r)

print(f"\n成功: {success}/{len(STOCKS)} 只股票")
print(f"总同步: {total_synced} 条记录")

print("\n详细:")
for r in results:
    if 'error' in r:
        print(f"   ❌ {r['symbol']} ({r['name']}): {r['error'][:50]}")
    else:
        print(f"   ✅ {r['symbol']} ({r['name']}): {r['in_db']} 条 ({r['start']} ~ {r['end']})")

# 数据库最终状态
print("\n" + "="*80)
print("🗄️ 数据库最终状态")
print("="*80)

stored = manager.get_stored_symbols()
print(f"共 {len(stored)} 只股票:\n   {', '.join(stored)}")

manager.close()

print("\n✅ 全量同步完成!")
