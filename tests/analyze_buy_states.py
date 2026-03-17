#!/usr/bin/env python3
"""
分析买入时的波浪状态
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer

symbol = '600519'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

print(f"🔍 分析 {symbol} 买入时的波浪状态\n")
print("="*80)

analyzer = EnhancedWaveAnalyzer(use_adaptive=False)

# 检查几个关键买入点
test_indices = [
    (60, '2023年3月'),
    (150, '2023年7月'),
    (250, '2023年12月'),
    (400, '2024年7月'),
    (550, '2025年3月'),
    (700, '2025年10月'),
]

for idx, label in test_indices:
    start_idx = max(0, idx - 60)
    test_df = df.iloc[start_idx:idx+1].copy()
    
    result = analyzer.analyze(symbol, test_df)
    
    print(f"\n{label} (索引{idx}):")
    if result and result.primary_pattern:
        p = result.primary_pattern
        n_points = len(p.points)
        latest_wave = p.points[-1].wave_num if p.points else None
        latest_price = p.points[-1].price if p.points else 0
        
        print(f"  浪型: {p.wave_type.value:12s} 方向: {p.direction.value:4s}")
        print(f"  点数: {n_points}  最新浪: {latest_wave}  价格: ¥{latest_price:.2f}")
        print(f"  置信度: {p.confidence:.2f}")
        
        # 显示完整序列
        if p.points:
            waves = [pt.wave_num for pt in p.points]
            prices = [f"¥{pt.price:.0f}" for pt in p.points]
            print(f"  浪号序列: {' -> '.join(waves)}")
    else:
        print("  未识别到波浪")

print("\n✅ 完成")
