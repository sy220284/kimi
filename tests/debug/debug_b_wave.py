#!/usr/bin/env python3
"""
深入调试B浪验证逻辑
"""
from pathlib import Path


import pandas as pd

from src.analysis.wave.enhanced_detector import enhanced_pivot_detection
from src.data import get_stock_data

symbol = '600519.SH'
df = get_stock_data(symbol, start_date='2024-01-01', end_date='2026-03-16')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

# 使用与UnifiedWaveAnalyzer相同的逻辑
window_size = 60
detect_df = df.iloc[-window_size-10:-10]  # 最近60天，去掉最后10天

print("=" * 80)
print(f"B浪验证逻辑调试 - {symbol}")
print("=" * 80)
print("\n分析窗口:")
print(f"  检测数据范围: {detect_df['date'].iloc[0]} ~ {detect_df['date'].iloc[-1]}")
print(f"  检测数据条数: {len(detect_df)}")

# 极值点检测
pivots = enhanced_pivot_detection(
    detect_df,
    atr_period=10,
    atr_mult=0.5,
    minpivots=3,
    trend_confirmation=False
)

print("\n极值点检测:")
print(f"  检测到极值点: {len(pivots)} 个")

if pivots:
    print("\n  所有极值点:")
    for i, p in enumerate(pivots):
        print(f"    [{i}] idx={p.idx}, price=¥{p.price:.2f}, ispeak={p.ispeak}, strength={p.strength}")

# 模拟B浪验证逻辑
print(f"\n{'='*80}")
print("B浪验证逻辑分析")
print(f"{'='*80}")

if len(pivots) >= 4:
    print(f"✓ 极值点数量充足 ({len(pivots)} >= 4)")

    p_before_a = pivots[-4]
    p_a = pivots[-3]
    p_b = pivots[-2]
    p_c = pivots[-1]

    print("\n  关键点:")
    print(f"    p_before_a (A浪前): idx={p_before_a.idx}, price=¥{p_before_a.price:.2f}, ispeak={p_before_a.ispeak}")
    print(f"    p_a (A浪终点): idx={p_a.idx}, price=¥{p_a.price:.2f}, ispeak={p_a.ispeak}")
    print(f"    p_b (B浪终点): idx={p_b.idx}, price=¥{p_b.price:.2f}, ispeak={p_b.ispeak}")
    print(f"    p_c (C浪终点): idx={p_c.idx}, price=¥{p_c.price:.2f}, ispeak={p_c.ispeak}")

    # 验证逻辑
    bounce_size = abs(p_b.price - p_a.price)
    a_size = abs(p_before_a.price - p_a.price)

    print("\n  幅度计算:")
    print(f"    A浪幅度 (|p_before_a - p_a|): ¥{a_size:.2f}")
    print(f"    B浪幅度 (|p_b - p_a|): ¥{bounce_size:.2f}")

    if a_size > 0:
        bounce_ratio = bounce_size / a_size
        print(f"    反弹比例: {bounce_ratio:.2%}")

        is_bounce_from_a = 0.2 <= bounce_ratio <= 1.0
        print(f"    20% <= {bounce_ratio:.2%} <= 100%: {is_bounce_from_a}")
    else:
        print("    A浪幅度为0，无法计算反弹比例")
        is_bounce_from_a = False

    # B浪范围验证
    if p_a.ispeak:
        b_within_range = p_b.price < p_before_a.price
        print("\n  范围验证 (p_a.ispeak=True):")
        print(f"    p_b.price ({p_b.price:.2f}) < p_before_a.price ({p_before_a.price:.2f}): {b_within_range}")
    else:
        b_within_range = p_b.price > p_before_a.price
        print("\n  范围验证 (p_a.ispeak=False):")
        print(f"    p_b.price ({p_b.price:.2f}) > p_before_a.price ({p_before_a.price:.2f}): {b_within_range}")

    b_wave_valid = is_bounce_from_a and b_within_range
    print(f"\n  B浪验证结果: {b_wave_valid}")
    print(f"    is_bounce_from_a: {is_bounce_from_a}")
    print(f"    b_within_range: {b_within_range}")

else:
    print(f"✗ 极值点数量不足 ({len(pivots)} < 4)")
    print("  → b_wave_valid 被强制设为 False")

print("\n" + "=" * 80)
print("诊断结论")
print("=" * 80)
print("""
问题1: 60天滑动窗口可能包含的极值点不足4个
  - 解决方法: 增大窗口到90或120天

问题2: B浪范围验证过于严格
  - p_b不应突破p_before_a的条件可能过于保守
  - 在强势市场中，B浪可能短暂突破前高/前低

问题3: 反弹比例计算
  - 如果A浪幅度很小，反弹比例很容易超出100%
  - 需要处理A浪接近0的边界情况
""")
