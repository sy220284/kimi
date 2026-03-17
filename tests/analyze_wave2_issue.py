#!/usr/bin/env python3
"""
2浪验证反常现象调查 - 为什么验证通过的信号表现更差
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

# 读取数据
df = pd.read_csv('tests/results/full_database_v2.csv')

# 清理异常值
for col in ['return_5d', 'return_10d', 'return_20d']:
    df[col] = df[col].replace([np.inf, -np.inf], np.nan)

print("=" * 80)
print("2浪验证反常现象调查")
print("=" * 80)

# 筛选2浪信号
w2_df = df[df['entry_type'] == '2'].copy()
print(f"\n2浪信号总数: {len(w2_df)}")

# 按验证状态分组
w2_valid = w2_df[w2_df['wave1_valid'] == True]
w2_invalid = w2_df[w2_df['wave1_valid'] == False]

print(f"\n验证通过: {len(w2_valid)} 个")
print(f"验证失败: {len(w2_invalid)} 个")

# 统计各组表现
print("\n" + "=" * 80)
print("表现对比")
print("=" * 80)

for name, group in [('验证通过', w2_valid), ('验证失败', w2_invalid)]:
    print(f"\n{name} ({len(group)} 个):")
    for d in [5, 10, 20]:
        col = f'return_{d}d'
        valid = group[col].dropna()
        if len(valid) > 0:
            win_rate = (valid > 0).mean() * 100
            avg_ret = valid.mean()
            median_ret = valid.median()
            print(f"  {d}天后: 胜率 {win_rate:.1f}%, 平均 {avg_ret:.2f}%, 中位数 {median_ret:.2f}%")

# 检查其他特征差异
print("\n" + "=" * 80)
print("特征对比")
print("=" * 80)

features = ['confidence', 'resonance_score', 'price']
for feat in features:
    if feat in w2_df.columns:
        valid_mean = w2_valid[feat].mean()
        invalid_mean = w2_invalid[feat].mean()
        print(f"\n{feat}:")
        print(f"  验证通过: {valid_mean:.3f}")
        print(f"  验证失败: {invalid_mean:.3f}")
        print(f"  差异: {valid_mean - invalid_mean:+.3f}")

# 按置信度分组分析
print("\n" + "=" * 80)
print("按置信度分组分析")
print("=" * 80)

w2_df['conf_bin'] = pd.cut(w2_df['confidence'], bins=[0.5, 0.6, 0.7, 0.8, 1.0], labels=['0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8+'])

for conf_range, group in w2_df.groupby('conf_bin'):
    if pd.isna(conf_range):
        continue
    valid_count = group['wave1_valid'].sum()
    total_count = len(group)
    valid_rate = valid_count / total_count * 100 if total_count > 0 else 0
    
    valid_returns = group[group['wave1_valid'] == True]['return_5d'].dropna()
    invalid_returns = group[group['wave1_valid'] == False]['return_5d'].dropna()
    
    print(f"\n置信度 {conf_range} ({total_count} 个):")
    print(f"  验证通过率: {valid_rate:.1f}%")
    if len(valid_returns) > 0:
        print(f"  验证通过收益: {valid_returns.mean():.2f}% ({len(valid_returns)} 个)")
    if len(invalid_returns) > 0:
        print(f"  验证失败收益: {invalid_returns.mean():.2f}% ({len(invalid_returns)} 个)")

# 可能原因分析
print("\n" + "=" * 80)
print("可能原因分析")
print("=" * 80)

print("""
1. 推断模式问题 (3个极值点):
   - 只有3个点时，无法验证启动点，只能验证幅度
   - 可能引入了不符合推动浪结构的信号

2. 启动点验证过于严格:
   - 要求 p0.price < p1_start.price (上涨)
   - 可能过滤掉了V型反转等有效结构

3. 幅度门槛仍不合适:
   - 2%可能仍偏高，或者应该采用动态门槛

4. 样本偏差:
   - 验证通过的样本数较少 (1,054 vs 3,819)
   - 可能存在随机性影响
""")

print("=" * 80)
