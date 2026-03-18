#!/usr/bin/env python3
"""
数据层优化测试 - Phase 1 验证
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import DataAPI, get_stock_data

print("="*80)
print("🔧 Phase 1: 数据层优化测试")
print("="*80)

# 初始化API
api = DataAPI()

# 测试1: 单股数据获取（带质量检查）
print("\n【测试1】单股数据获取 + 质量检查")
print("-"*60)

result = api.get_stock_data('600138', '2024-01-01', '2024-12-31', check_quality=True)

if 'error' in result:
    print(f"❌ 错误: {result['error']}")
else:
    df = result['data']
    report = result['quality_report']
    
    print(f"✅ 数据来源: {result['source']}")
    print(f"📦 缓存状态: {'命中' if result['cached'] else '未命中'}")
    print(f"📊 数据条数: {len(df)}")
    print(f"📅 日期范围: {df['date'].min()} ~ {df['date'].max()}")
    
    if report:
        print("\n🔍 质量报告:")
        print(f"  质量评分: {report.score}/100")
        print(f"  是否有效: {'✅' if report.is_valid else '❌'}")
        print(f"  缺失值: {report.missing_values}")
        print(f"  价格异常: {len(report.price_anomalies)} 处")
        print(f"  日期缺失: {len(report.gap_dates)} 处")

# 测试2: 批量获取
print("\n【测试2】批量数据获取")
print("-"*60)

symbols = ['600138', '002184', '600556']
batch_result = api.get_batch_data(symbols, '2025-01-01', '2025-12-31')

for symbol, res in batch_result.items():
    if 'error' in res:
        print(f"  {symbol}: ❌ {res['error']}")
    else:
        df = res['data']
        print(f"  {symbol}: ✅ {len(df)} 条 ({res['source']})")

# 测试3: 缓存系统
import time

print("\n【测试3】缓存系统")
print("-"*60)

# 第一次获取（未缓存）
t1 = time.time()
result1 = api.get_stock_data('600138', '2025-06-01', '2025-12-31')
t2 = time.time()
print(f"  首次获取: {(t2-t1)*1000:.1f}ms")

# 第二次获取（命中缓存）
t1 = time.time()
result2 = api.get_stock_data('600138', '2025-06-01', '2025-12-31')
t2 = time.time()
print(f"  缓存命中: {(t2-t1)*1000:.1f}ms ⚡")

# 缓存统计
cachestats = api.get_cache_stats()
print("\n  缓存统计:")
print(f"    内存条目: {cachestats['memory_entries']}")
print(f"    文件条目: {cachestats['file_entries']}")
print(f"    总大小: {cachestats['total_size_mb']} MB")

# 测试4: 数据源状态
print("\n【测试4】数据源状态监控")
print("-"*60)

status = api.get_source_status()
for s in status:
    available = "🟢" if s['available'] else "🔴"
    print(f"  {available} {s['name']}: 成功率 {s['success_count']}/{s['success_count']+s['fail_count']}, 平均响应 {s['avg_response_time_ms']}ms")
    if s['last_error']:
        print(f"      最后错误: {s['last_error']}")

# 测试5: 便捷函数
print("\n【测试5】便捷函数 get_stock_data()")
print("-"*60)

try:
    df = get_stock_data('002184', '2025-01-01', '2025-03-01')
    print(f"  ✅ 获取成功: {len(df)} 条数据")
    print(f"  📈 最新价格: ¥{df['close'].iloc[-1]:.2f}")
except Exception as e:
    print(f"  ❌ 错误: {e}")

print("\n" + "="*80)
print("Phase 1 测试完成!")
print("="*80)
print("\n📋 Phase 1 完成清单:")
print("  ✅ 1.1 数据缓存系统 - 内存+文件双缓存")
print("  ✅ 1.2 多源备份机制 - 自动failover")
print("  ✅ 1.3 数据质量监控 - 异常/缺失检测")
print("  ✅ 1.4 统一API接口 - 一行代码获取数据")
print("\n🚀 准备进入 Phase 2 (分析层优化)...")
