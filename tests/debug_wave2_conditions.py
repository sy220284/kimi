#!/usr/bin/env python3
"""
2浪验证条件深度分析 - 调试具体哪个条件导致问题
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data
from src.analysis.wave.enhanced_detector import enhanced_pivot_detection

# 测试股票
symbol = '600519.SH'
print("=" * 80)
print(f"2浪验证条件深度分析 - {symbol}")
print("=" * 80)

df = get_stock_data(symbol, start_date='2020-01-01', end_date='2026-03-16')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

# 取一个典型窗口进行详细分析
window_start = len(df) - 200
window_df = df.iloc[window_start:window_start+60].copy()

print(f"\n分析窗口: {window_df['date'].iloc[0]} ~ {window_df['date'].iloc[-1]}")
print(f"价格范围: ¥{window_df['close'].min():.2f} ~ ¥{window_df['close'].max():.2f}")

# 极值点检测
pivots = enhanced_pivot_detection(
    window_df,
    atr_period=10,
    atr_mult=0.5,
    min_pivots=3,
    trend_confirmation=False
)

print(f"\n极值点数量: {len(pivots)}")
for i, p in enumerate(pivots):
    print(f"  [{i}] idx={p.idx}, date={p.date}, price=¥{p.price:.2f}, is_peak={p.is_peak}")

# 分析2浪验证条件
print("\n" + "=" * 80)
print("2浪验证条件分析")
print("=" * 80)

if len(pivots) >= 4:
    p0 = pivots[-4]
    p1_start = pivots[-3]
    p1_end = pivots[-2]
    p2_end = pivots[-1]
    
    wave1 = abs(p1_end.price - p1_start.price)
    direction_up = p1_end.price > p1_start.price
    
    print(f"\n关键点:")
    print(f"  p0 (前序): price=¥{p0.price:.2f}")
    print(f"  p1_start (1浪起点): price=¥{p1_start.price:.2f}")
    print(f"  p1_end (1浪终点/2浪起点): price=¥{p1_end.price:.2f}")
    print(f"  p2_end (2浪终点): price=¥{p2_end.price:.2f}")
    
    print(f"\n计算:")
    print(f"  方向: {'上涨' if direction_up else '下跌'}")
    print(f"  1浪幅度: ¥{wave1:.2f} ({wave1/p1_start.price*100:.2f}%)")
    
    # 条件1: 启动点验证
    if direction_up:
        wave1_valid_start = p0.price < p1_start.price
        print(f"\n  条件1 (启动点验证):")
        print(f"    p0.price ({p0.price:.2f}) < p1_start.price ({p1_start.price:.2f}): {wave1_valid_start}")
    else:
        wave1_valid_start = p0.price > p1_start.price
        print(f"\n  条件1 (启动点验证):")
        print(f"    p0.price ({p0.price:.2f}) > p1_start.price ({p1_start.price:.2f}): {wave1_valid_start}")
    
    # 条件2: 幅度验证
    wave1_strong = wave1 >= p1_start.price * 0.02
    print(f"\n  条件2 (幅度验证):")
    print(f"    wave1 ({wave1:.2f}) >= p1_start.price * 0.02 ({p1_start.price * 0.02:.2f}): {wave1_strong}")
    
    # 综合
    wave1_valid = wave1_valid_start and wave1_strong
    print(f"\n  综合验证结果: {wave1_valid}")
    
    if not wave1_valid:
        print(f"\n  ❌ 验证失败原因:")
        if not wave1_valid_start:
            print(f"    - 启动点验证失败")
        if not wave1_strong:
            print(f"    - 幅度不足 (仅{wave1/p1_start.price*100:.2f}%)")

elif len(pivots) == 3:
    print(f"\n只有3个极值点 - 使用推断模式")
    p1_start = pivots[-3]
    p1_end = pivots[-2]
    
    wave1 = abs(p1_end.price - p1_start.price)
    wave1_strong = wave1 >= p1_start.price * 0.02
    
    print(f"  1浪幅度: ¥{wave1:.2f} ({wave1/p1_start.price*100:.2f}%)")
    print(f"  幅度验证 (>=2%): {wave1_strong}")
    print(f"  推断模式结果: {wave1_strong}")
    print(f"\n  ⚠️ 推断模式不验证启动点，可能引入噪音")

print("\n" + "=" * 80)
print("调查结论")
print("=" * 80)
print("""
关键问题:
1. 启动点验证 (p0.price vs p1_start.price) 可能过于严格
   - 要求1浪必须从相对低位/高位启动
   - 但V型反转、W底等结构中，1浪可能从平台启动

2. 推断模式 (3点) 只验证幅度，不验证启动点
   - 可能将非推动浪结构误判为2浪
   - 这是导致验证通过信号表现差的主因

建议修复:
1. 放宽启动点验证条件
2. 或完全取消启动点验证，只保留幅度验证
3. 对推断模式增加额外限制
""")
