#!/usr/bin/env python3
"""
极值点检测调试 - 分析为什么极值点数量不足
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from src.analysis.wave.enhanced_detector import enhanced_pivot_detection
from src.data import get_stock_data

# 测试股票
symbol = '600519.SH'
df = get_stock_data(symbol, start_date='2024-01-01', end_date='2026-03-16')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

print("=" * 80)
print(f"极值点检测调试 - {symbol}")
print("=" * 80)
print(f"\n数据概况:")
print(f"  总记录数: {len(df)}")
print(f"  日期范围: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
print(f"  价格范围: ¥{df['close'].min():.2f} ~ ¥{df['close'].max():.2f}")

# 使用不同参数测试极值点检测
configs = [
    {'atr_period': 10, 'atr_mult': 0.5, 'min_pivots': 3},
    {'atr_period': 5, 'atr_mult': 0.3, 'min_pivots': 3},
    {'atr_period': 14, 'atr_mult': 1.0, 'min_pivots': 3},
]

print("\n" + "=" * 80)
print("不同参数下的极值点检测")
print("=" * 80)

for i, cfg in enumerate(configs):
    pivots = enhanced_pivot_detection(
        df,  # 传入DataFrame
        **cfg
    )
    
    print(f"\n配置 {i+1}: atr_period={cfg['atr_period']}, atr_mult={cfg['atr_mult']}")
    print(f"  检测到极值点: {len(pivots)} 个")
    
    if pivots:
        print(f"  最近5个极值点:")
        for p in pivots[-5:]:
            print(f"    idx={p.idx}, price=¥{p.price:.2f}, is_peak={p.is_peak}, strength={p.strength}")

print("\n" + "=" * 80)
print("问题诊断")
print("=" * 80)
print("""
如果极值点数量 < 4:
  - 无法验证B浪结构 (需要至少4个点: p_before_a, p_a, p_b, p_c)
  - b_wave_valid 被强制设为 False
  
解决方案:
  1. 降低极值点检测门槛 (减小 atr_mult)
  2. 在只有3个点时也尝试验证 (使用推断模式)
  3. 增加 lookback 窗口大小
""")
