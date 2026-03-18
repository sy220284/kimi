#!/usr/bin/env python3
"""
对比分析报告: 增强版 vs 上一版本
"""

import pandas as pd
import json

print("=" * 90)
print("📊 波浪检测对比分析报告")
print("增强版(带上下文验证) vs 上一版本")
print("=" * 90)

# 读取两个版本的结果
try:
    df_v1 = pd.read_csv('tests/results/batch_wave_analysis.csv')
    with open('tests/results/batch_wave_analysissummary.json', 'r') as f:
        summary_v1 = json.load(f)
except Exception:
    # 如果v1没有summary文件，手动计算
    df_v1 = pd.read_csv('tests/results/batch_wave_analysis.csv')
    summary_v1 = {
        'totalsignals': len(df_v1),
        'by_type': df_v1['entry_type'].value_counts().to_dict(),
        'avg_confidence': df_v1['confidence'].mean(),
        'win_rate_5d': (df_v1['return_5d'] > 0).mean() * 100,
        'win_rate_20d': (df_v1['return_20d'] > 0).mean() * 100,
    }

df_v2 = pd.read_csv('tests/results/batch_enhanced_v2.csv')
with open('tests/results/batch_enhanced_v2summary.json', 'r') as f:
    summary_v2 = json.load(f)

print("\n【一、整体指标对比】")
print("-" * 90)
print(f"{'指标':<30} {'上一版本':<20} {'增强版':<20} {'变化':<15}")
print("-" * 90)

# 信号总数
v1_total = summary_v1['totalsignals']
v2_total = summary_v2['totalsignals']
change_total = v2_total - v1_total
print(f"{'总信号数':<30} {v1_total:<20} {v2_total:<20} {change_total:+d}")

# 平均置信度
v1_conf = summary_v1['avg_confidence']
v2_conf = summary_v2['avg_confidence']
change_conf = v2_conf - v1_conf
print(f"{'平均置信度':<30} {v1_conf:<20.3f} {v2_conf:<20.3f} {change_conf:+.3f}")

# 5天胜率
v1_wr5 = summary_v1['win_rate_5d']
v2_wr5 = summary_v2['win_rate_5d']
change_wr5 = v2_wr5 - v1_wr5
print(f"{'5天胜率':<30} {v1_wr5:<20.2f}% {v2_wr5:<20.2f}% {change_wr5:+.2f}%")

# 20天胜率
v1_wr20 = summary_v1['win_rate_20d']
v2_wr20 = summary_v2['win_rate_20d']
change_wr20 = v2_wr20 - v1_wr20
print(f"{'20天胜率':<30} {v1_wr20:<20.2f}% {v2_wr20:<20.2f}% {change_wr20:+.2f}%")

print("-" * 90)

print("\n【二、浪型分布对比】")
print("-" * 90)
print(f"{'浪型':<15} {'上一版本':<20} {'增强版':<20} {'变化':<15}")
print("-" * 90)

v1_types = summary_v1.get('by_type', df_v1['entry_type'].value_counts().to_dict())
v2_types = summary_v2.get('by_type', {})

for wave_type in ['C', '2', '4']:
    v1_count = v1_types.get(wave_type, 0)
    v2_count = v2_types.get(wave_type, 0)
    change = v2_count - v1_count
    print(f"{wave_type + '浪':<15} {v1_count:<20} {v2_count:<20} {change:+d}")

print("-" * 90)

print("\n【三、置信度分布对比】")
print("-" * 90)

bins = [0.5, 0.6, 0.7, 0.8, 1.0]
labels = ['0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8+']

v1_dist = pd.cut(df_v1['confidence'], bins=bins, labels=labels).value_counts().sort_index()
v2_dist = pd.cut(df_v2['confidence'], bins=bins, labels=labels).value_counts().sort_index()

print(f"{'置信度区间':<20} {'上一版本':<15} {'增强版':<15} {'变化':<15}")
print("-" * 90)
for label in labels:
    v1_c = v1_dist.get(label, 0)
    v2_c = v2_dist.get(label, 0)
    change = v2_c - v1_c
    print(f"{label:<20} {v1_c:<15} {v2_c:<15} {change:+d}")

print("-" * 90)

print("\n【四、上下文验证效果分析】")
print("-" * 90)

# 分析增强版中通过验证的信号表现
if 'wave1_valid' in df_v2.columns:
    valid_2 = df_v2[df_v2['wave1_valid']]
    invalid_2 = df_v2[~df_v2['wave1_valid']]
    
    print("\n2浪验证:")
    print(f"  通过验证: {len(valid_2)}个, 平均置信度{valid_2['confidence'].mean():.2f}")
    if len(valid_2) > 0:
        print(f"  5天胜率: {(valid_2['return_5d'] > 0).mean()*100:.1f}%")
    print(f"  未通过验证: {len(invalid_2)}个, 平均置信度{invalid_2['confidence'].mean():.2f}")
    if len(invalid_2) > 0:
        print(f"  5天胜率: {(invalid_2['return_5d'] > 0).mean()*100:.1f}%")

if 'b_wave_valid' in df_v2.columns:
    valid_c = df_v2[df_v2['b_wave_valid']]
    invalid_c = df_v2[~df_v2['b_wave_valid']]
    
    print("\nC浪验证:")
    print(f"  通过验证: {len(valid_c)}个, 平均置信度{valid_c['confidence'].mean():.2f}")
    if len(valid_c) > 0:
        print(f"  5天胜率: {(valid_c['return_5d'] > 0).mean()*100:.1f}%")
    print(f"  未通过验证: {len(invalid_c)}个, 平均置信度{invalid_c['confidence'].mean():.2f}")
    if len(invalid_c) > 0:
        print(f"  5天胜率: {(invalid_c['return_5d'] > 0).mean()*100:.1f}%")

print("\n【五、关键发现】")
print("-" * 90)

if abs(change_wr5) < 1:
    print("⚠️  胜率变化不明显(5天胜率变化 < 1%)")
    print("   可能原因:")
    print("   1. 上下文验证对信号数量的影响有限")
    print("   2. 验证逻辑过于宽松,未能有效过滤假信号")
    print("   3. 需要调整验证阈值")
elif change_wr5 > 0:
    print(f"✅ 5天胜率提升{change_wr5:.1f}%, 上下文验证有效")
else:
    print(f"⚠️  5天胜率下降{abs(change_wr5):.1f}%, 可能需要调整验证逻辑")

if change_conf < 0:
    print(f"✅ 平均置信度下降{abs(change_conf):.3f}, 低质量信号被过滤")
else:
    print("ℹ️  平均置信度持平或上升")

print("\n【六、建议】")
print("-" * 90)
print("1. 收紧验证条件 - 如果验证通过率过高(>90%),应提高验证标准")
print("2. 分析失败信号 - 查看未通过验证的信号后续表现,验证逻辑是否正确")
print("3. 调整置信度权重 - 根据验证结果调整置信度计算公式")

print("\n" + "=" * 90)
print("报告生成完成")
print("=" * 90)
