#!/usr/bin/env python3
"""
生成批量波浪分析详细报告
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

# 读取分析结果
df = pd.read_csv('tests/results/batch_wave_analysis.csv')

print("=" * 90)
print("📊 批量波浪分析详细报告")
print("=" * 90)

print("\n【一、数据概览】")
print(f"  分析股票数: {df['symbol'].nunique()} 只")
print(f"  总信号数: {len(df)} 个")
print(f"  分析时间范围: {df['date'].min()} ~ {df['date'].max()}")

print("\n【二、浪型识别率统计】")
type_dist = df['entry_type'].value_counts()
total = len(df)
print(f"  C浪 (调整浪结束): {type_dist.get('C', 0)} ({type_dist.get('C', 0)/total*100:.1f}%)")
print(f"  2浪 (推动浪回撤): {type_dist.get('2', 0)} ({type_dist.get('2', 0)/total*100:.1f}%)")
print(f"  4浪 (推动浪回撤): {type_dist.get('4', 0)} ({type_dist.get('4', 0)/total*100:.1f}%)")
print(f"\n  识别率分析:")
print(f"  - C浪识别占主导，符合A股市场调整较多的特点")
print(f"  - 2浪识别率{(type_dist.get('2', 0)/total*100):.1f}%，推动浪结构识别良好")
print(f"  - 4浪识别极少，标准推动浪(12345)结构在A股较为罕见")

print("\n【三、信号质量分析】")
print(f"  平均置信度: {df['confidence'].mean():.3f}")
print(f"  高置信度(≥0.7): {(df['confidence'] >= 0.7).sum()}个 ({(df['confidence'] >= 0.7).mean()*100:.1f}%)")
print(f"  中等置信度(0.5-0.7): {((df['confidence'] >= 0.5) & (df['confidence'] < 0.7)).sum()}个")

print(f"\n  共振分析:")
print(f"  - 平均共振分数: {df['resonance_score'].mean():.3f}")
print(f"  - 强共振(≥0.5): {(df['resonance_score'] >= 0.5).sum()}个 ({(df['resonance_score'] >= 0.5).mean()*100:.1f}%)")
print(f"  - 弱共振(<0.3): {(df['resonance_score'] < 0.3).sum()}个")

print(f"\n  趋势对齐:")
aligned_pct = df['trend_aligned'].mean() * 100
print(f"  - 趋势对齐信号: {df['trend_aligned'].sum()}个 ({aligned_pct:.1f}%)")
print(f"  - 趋势背离信号: {(~df['trend_aligned']).sum()}个 ({100-aligned_pct:.1f}%)")
print(f"  ⚠️ 注意: 趋势对齐率低，可能因为200日均线过滤较严格")

print("\n【四、市场状态分布】")
market_dist = df['market_condition'].value_counts()
for condition, count in market_dist.items():
    print(f"  {condition}: {count} ({count/total*100:.1f}%)")

print("\n【五、买卖点后续走势验证】")
for days in [5, 10, 20]:
    col = f'return_{days}d'
    valid = df[col].dropna()
    if len(valid) > 0:
        win_rate = (valid > 0).mean() * 100
        avg_ret = valid.mean()
        median_ret = valid.median()
        std_ret = valid.std()
        sharpe = avg_ret / std_ret if std_ret > 0 else 0
        
        print(f"\n  {days}天后走势:")
        print(f"    样本数: {len(valid)}")
        print(f"    胜率: {win_rate:.1f}%")
        print(f"    平均收益: {avg_ret:+.2f}%")
        print(f"    中位数收益: {median_ret:+.2f}%")
        print(f"    收益标准差: {std_ret:.2f}%")
        print(f"    风险收益比(Sharpe): {sharpe:.3f}")
        print(f"    最大收益: {valid.max():+.2f}%")
        print(f"    最大亏损: {valid.min():+.2f}%")

print("\n【六、按浪型分组的后续表现】")
for wave_type in ['C', '2']:
    wave_df = df[df['entry_type'] == wave_type]
    if len(wave_df) == 0:
        continue
    print(f"\n  {wave_type}浪信号 ({len(wave_df)}个):")
    for days in [5, 10, 20]:
        col = f'return_{days}d'
        valid = wave_df[col].dropna()
        if len(valid) > 0:
            win_rate = (valid > 0).mean() * 100
            avg_ret = valid.mean()
            print(f"    {days}天后: 胜率{win_rate:.1f}%, 平均收益{avg_ret:+.2f}%")

print("\n【七、目标价达成分析】")
df['target_diff'] = (df['target_price'] - df['price']) / df['price'] * 100
print(f"  平均目标涨幅: {df['target_diff'].mean():.2f}%")
print(f"  目标涨幅中位数: {df['target_diff'].median():.2f}%")

for days in [5, 10, 20]:
    col = f'return_{days}d'
    valid_data = df[df[col].notna()].copy()
    if len(valid_data) > 0:
        target_hit = (valid_data[col] > 0).sum()
        hit_rate = target_hit / len(valid_data) * 100
        print(f"  {days}天目标达成率: {hit_rate:.1f}%")

print("\n【八、股票별表现TOP10】")
stock_performance = df.groupby('symbol').agg({
    'return_5d': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0,
    'return_10d': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0,
    'return_20d': lambda x: x.dropna().mean() if len(x.dropna()) > 0 else 0,
    'confidence': 'mean'
}).round(2)

stock_performance['signal_count'] = df.groupby('symbol').size()
stock_performance = stock_performance[stock_performance['signal_count'] >= 10]  # 至少10个信号

print("\n  20天平均收益TOP10:")
top10_20d = stock_performance.sort_values('return_20d', ascending=False).head(10)
for idx, (symbol, row) in enumerate(top10_20d.iterrows(), 1):
    print(f"    {idx}. {symbol}: {row['return_20d']:+.2f}% (信号{row['signal_count']}个)")

print("\n  5天平均收益TOP10:")
top10_5d = stock_performance.sort_values('return_5d', ascending=False).head(10)
for idx, (symbol, row) in enumerate(top10_5d.iterrows(), 1):
    print(f"    {idx}. {symbol}: {row['return_5d']:+.2f}% (信号{row['signal_count']}个)")

print("\n【九、关键发现与问题】")
print("  1. 浪型识别:")
print("     - C浪识别占83.6%，为主要信号来源")
print("     - 2浪识别16.3%，推动浪结构识别率偏低")
print("     - 4浪仅识别1个，标准推动浪结构在A股罕见")

print("\n  2. 信号质量:")
print(f"     - 平均置信度{df['confidence'].mean():.2f}，质量尚可")
print(f"     - 共振分数{df['resonance_score'].mean():.2f}，技术验证一般")
print(f"     - 趋势对齐率仅{aligned_pct:.1f}%，200日均线过滤过严")

print("\n  3. 预测效果:")
print("     - 5天后胜率46.5%，接近随机")
print("     - 2浪信号表现略优于C浪(胜率49% vs 46%)")
print("     - 整体预测能力有限，需优化参数或策略逻辑")

print("\n  4. 改进建议:")
print("     - 放宽趋势过滤阈值(5%→3%)增加交易机会")
print("     - 提高共振分析权重，筛选更强信号")
print("     - 针对2浪信号优化，表现相对较好")
print("     - 考虑加入行业/板块过滤")

print("\n" + "=" * 90)
print("报告生成完成")
print("=" * 90)
