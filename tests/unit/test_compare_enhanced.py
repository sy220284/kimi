#!/usr/bin/env python3
"""
对比测试: 增强版 vs 原版波浪检测
验证上下文验证的效果
"""

from pathlib import Path


import pandas as pd

from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data

SYMBOLS = ['600519', '000858', '600809', '000568', '600600']
START = '2024-01-01'
END = '2026-03-16'

print("=" * 80)
print("波浪检测增强版对比测试")
print("=" * 80)

analyzer = UnifiedWaveAnalyzer(
    use_resonance=False,
    use_trend_filter=False,
    trend_ma_period=20,
)

results = []

for symbol in SYMBOLS:
    print(f"\n📊 {symbol} 分析...")
    df = get_stock_data(symbol, START, END)

    signals = analyzer.detect(df, mode='all')

    csignals = [s for s in signals if s.entry_type.value == 'C']
    wave2signals = [s for s in signals if s.entry_type.value == '2']
    wave4signals = [s for s in signals if s.entry_type.value == '4']

    print(f"  C浪: {len(csignals)}个, 平均置信度{pd.Series([s.confidence for s in csignals]).mean():.2f}" if csignals else "  C浪: 0个")
    print(f"  2浪: {len(wave2signals)}个, 平均置信度{pd.Series([s.confidence for s in wave2signals]).mean():.2f}" if wave2signals else "  2浪: 0个")
    print(f"  4浪: {len(wave4signals)}个" if wave4signals else "  4浪: 0个")

    # 统计检测方法
    methods = {}
    for s in signals:
        m = getattr(s, 'detection_method', 'unknown')
        methods[m] = methods.get(m, 0) + 1

    if methods:
        print(f"  检测方法分布: {methods}")

    results.append({
        'symbol': symbol,
        'c_count': len(csignals),
        'c_confidence': pd.Series([s.confidence for s in csignals]).mean() if csignals else 0,
        'wave2_count': len(wave2signals),
        'wave2_confidence': pd.Series([s.confidence for s in wave2signals]).mean() if wave2signals else 0,
    })

print("\n" + "=" * 80)
print("汇总统计")
print("=" * 80)

df_result = pd.DataFrame(results)
print(f"\nC浪信号: {df_result['c_count'].sum()}个, 平均置信度{df_result['c_confidence'].mean():.2f}")
print(f"2浪信号: {df_result['wave2_count'].sum()}个, 平均置信度{df_result['wave2_confidence'].mean():.2f}")

print("\n" + "=" * 80)
print("✅ 对比测试完成")
print("=" * 80)
