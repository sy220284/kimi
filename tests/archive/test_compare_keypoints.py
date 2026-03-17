#!/usr/bin/env python3
"""
对比原始vs增强版检测器在同一数据上的表现
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave.elliott_wave import ElliottWaveAnalyzer

symbol = '600519'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

print(f"🔍 对比测试 {symbol}\n")
print("="*80)

# 测试几个关键时间点
test_dates = [
    ('2023-05-22', '2023年5月'),
    ('2023-08-16', '2023年8月'),
    ('2024-09-18', '2024年9月'),
    ('2025-06-30', '2025年6月'),
]

for date_str, label in test_dates:
    # 找到这个日期附近的数据索引
    df['date'] = pd.to_datetime(df['date'])
    target_idx = df[df['date'] >= date_str].index[0] if len(df[df['date'] >= date_str]) > 0 else None
    
    if target_idx is None:
        continue
    
    # 取前60天数据
    start_idx = max(0, target_idx - 60)
    test_df = df.iloc[start_idx:target_idx+1].copy()
    
    print(f"\n{label} ({date_str})")
    print("-"*60)
    
    # 原始检测器
    analyzer_old = ElliottWaveAnalyzer(
        min_wave_length=5,
        max_wave_length=100,
        confidence_threshold=0.5,
        atr_period=14,
        atr_mult=0.5,
        min_dist=3
    )
    pattern_old = analyzer_old.detect_wave_pattern(test_df)
    
    if pattern_old and pattern_old.points:
        latest_old = pattern_old.points[-1]
        print(f"原始: 类型={pattern_old.wave_type.value:8s} 浪={str(latest_old.wave_num):3s} 置信度={pattern_old.confidence:.2f} 方向={pattern_old.direction.value}")
    else:
        print(f"原始: 未识别")

print("\n" + "="*80)
print("分析: 增强版检测器可能改变了检测逻辑，导致买入时点不同")
print("需要检查 _detect_pivots vs enhanced_pivot_detection 的差异")
