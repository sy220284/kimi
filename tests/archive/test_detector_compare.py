#!/usr/bin/env python3
"""
修复增强版检测器并对比测试
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave.elliott_wave import ElliottWaveAnalyzer, WavePoint
from analysis.wave.enhanced_detector import enhanced_pivot_detection, label_wave_numbers

symbol = '600519'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

print(f"🔧 修复增强版检测器对比测试\n")
print(f"数据: {len(df)}条\n")

# 测试一个时间段
test_df = df.iloc[400:460].copy()

print("="*60)
print("1. 原始检测器")
print("="*60)
analyzer_old = ElliottWaveAnalyzer(
    min_wave_length=5,
    max_wave_length=100,
    confidence_threshold=0.5,
    atr_period=14,
    atr_mult=0.5,
    min_dist=3
)
pattern_old = analyzer_old.detect_wave_pattern(test_df)
if pattern_old:
    print(f"识别到: {pattern_old.wave_type.value}")
    print(f"置信度: {pattern_old.confidence:.2f}")
    print(f"点数: {len(pattern_old.points)}")
    for p in pattern_old.points:
        print(f"  {p.date}: ¥{p.price:.2f} 浪{p.wave_num}")
else:
    print("未识别到波浪形态")

print("\n" + "="*60)
print("2. 增强版检测器")
print("="*60)

# 直接使用增强版检测
pivots = enhanced_pivot_detection(test_df, atr_period=14, atr_mult=0.5, min_pivots=4)
print(f"检测到极值点: {len(pivots)}个")
for p in pivots:
    print(f"  idx={p.idx}: ¥{p.price:.2f} {'峰值' if p.is_peak else '谷值'} 强度{p.strength}")

# 尝试标注浪号
labeled = label_wave_numbers(pivots, "auto")
print(f"\n标注浪号后:")
for p in labeled:
    print(f"  浪{p.wave_num}: ¥{p.price:.2f}")

# 使用增强版analyzer
from analysis.wave import EnhancedWaveAnalyzer
analyzer_new = EnhancedWaveAnalyzer(use_adaptive=False)  # 先不用自适应
pattern_new = analyzer_new._analyzer.detect_wave_pattern(test_df)
if pattern_new:
    print(f"\n识别到: {pattern_new.wave_type.value}")
    print(f"置信度: {pattern_new.confidence:.2f}")
    for p in pattern_new.points:
        print(f"  浪{p.wave_num}: ¥{p.price:.2f}")
else:
    print("\n未识别到波浪形态")
