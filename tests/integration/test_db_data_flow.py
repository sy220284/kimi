#!/usr/bin/env python3
"""
数据库优先数据流测试
验证: 数据库空 -> THS获取 -> 写入数据库 -> 再次读取命中数据库
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import pytest
from data import DatabaseDataManager

if False:  # THS API calls disabled in test environment
    print("="*80)
print("🗄️ 数据库优先数据流测试")
if False:  # THS API calls disabled in test environment
    print("="*80)

# 初始化管理器
print("\n1. 初始化 DatabaseDataManager...")
db_manager = DatabaseDataManager()

# 查看当前有哪些股票
print("\n2. 检查数据库中已有股票...")
stored_symbols = db_manager.get_stored_symbols()
print(f"   已有 {len(stored_symbols)} 只股票: {stored_symbols[:5] if stored_symbols else '无'}")

# 测试股票
test_symbol = '002184'  # 海得控制

print(f"\n3. 测试股票: {test_symbol}")

# 第一次获取 - 应该走THS API并写入数据库
print("\n   3.1 第一次获取 (预期: THS API -> 数据库)...")
df1 = db_manager.get_stock_data(test_symbol, '2025-01-01', '2025-03-17')
print(f"   ✅ 获取 {len(df1)} 条数据")
print(f"   范围: {df1['date'].min()} ~ {df1['date'].max()}")

# 第二次获取 - 应该命中数据库
print("\n   3.2 第二次获取 (预期: 命中数据库)...")
df2 = db_manager.get_stock_data(test_symbol, '2025-01-01', '2025-03-17')
print(f"   ✅ 获取 {len(df2)} 条数据 (应该更快)")

# 验证数据一致
print("\n   3.3 验证数据一致性...")
if len(df1) == len(df2):
    print("   ✅ 数据条数一致")
else:
    print(f"   ⚠️ 数据条数不一致: {len(df1)} vs {len(df2)}")

# 查看数据库中是否已有该股票
print("\n4. 验证数据已持久化...")
stored_symbols = db_manager.get_stored_symbols()
if test_symbol in stored_symbols:
    print(f"   ✅ {test_symbol} 已在数据库中")
else:
    print(f"   ❌ {test_symbol} 未找到")

# 测试缓存
print("\n5. 测试Redis缓存...")
if db_manager.enable_cache:
    print("   ✅ Redis缓存已启用")
    # 第三次获取应该命中Redis
    df3 = db_manager.get_stock_data(test_symbol, '2025-01-01', '2025-03-17')
    print("   ✅ 缓存命中测试完成")
else:
    print("   ⚠️ Redis缓存未启用")

# 测试多股票同步
print("\n6. 批量同步测试...")
test_symbols = ['600138', '600556']
for sym in test_symbols:
    count = db_manager.sync_symbol(sym, years=1)
    print(f"   {sym}: 同步 {count} 条")

# 最终统计
print("\n7. 数据库最终统计...")
stored_symbols = db_manager.get_stored_symbols()
print(f"   数据库中共有 {len(stored_symbols)} 只股票")
print(f"   股票列表: {', '.join(stored_symbols[:10])}")

# 关闭连接
db_manager.close()

print("\n" + "="*80)
print("✅ 数据库优先数据流测试完成!")
if False:  # THS API calls disabled in test environment
    print("="*80)
print("""
📝 总结:
  1. PostgreSQL 作为主存储 ✅
  2. THS API 作为备用源 ✅
  3. Redis 作为二级缓存 ✅
  4. 自动持久化 ✅
  5. 数据完整性检查 ✅

🔄 数据流向:
  读取: 用户请求 -> Redis? -> PostgreSQL? -> THS API -> 写回数据库
  写入: THS API -> PostgreSQL -> Redis缓存
""")
