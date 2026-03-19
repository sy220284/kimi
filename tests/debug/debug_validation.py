#!/usr/bin/env python3
"""
验证逻辑调试脚本 - 诊断B浪和1浪验证通过率问题
"""
from pathlib import Path


import pandas as pd

from analysis.wave import UnifiedWaveAnalyzer
from data import get_stock_data

# 数据获取函数

# 测试股票列表
test_stocks = ['600519.SH', '000858.SZ', '300750.SZ']

analyzer = UnifiedWaveAnalyzer(
    use_resonance=True,
    min_resonance_score=0.3,
    trend_ma_period=200,
    use_adaptive_params=False,
)

print("=" * 80)
print("B浪/1浪验证逻辑调试")
print("=" * 80)

for symbol in test_stocks:
    print(f"\n{'='*40}")
    print(f"股票: {symbol}")
    print(f"{'='*40}")

    df = get_stock_data(symbol, start_date='2024-01-01', end_date='2026-03-16')
    if df is None or len(df) < 60:
        print("  数据不足")
        continue

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # 检测信号
    signals = analyzer.detect(df, mode='all')

    csignals = [s for s in signals if s.entry_type.value == 'C']
    w2signals = [s for s in signals if s.entry_type.value == '2']

    print(f"  总信号: {len(signals)}")
    print(f"  C浪信号: {len(csignals)}")
    print(f"  2浪信号: {len(w2signals)}")

    # 检查C浪验证状态
    if csignals:
        valid_count = sum(1 for s in csignals if s.wave_structure.get('b_wave_valid', False))
        print("\n  C浪验证统计:")
        print(f"    总数: {len(csignals)}")
        print(f"    通过验证: {valid_count}")
        print(f"    通过率: {valid_count/len(csignals)*100:.1f}%")

        # 显示第一个信号的详情
        s = csignals[0]
        ws = s.wave_structure or {}
        print("\n  首个C浪信号详情:")
        print(f"    日期: {df.iloc[-1]['date']}")
        print(f"    置信度: {s.confidence:.2f}")
        print(f"    b_wave_valid: {ws.get('b_wave_valid', 'N/A')}")
        print(f"    b_duration: {ws.get('b_duration', 'N/A')}")
        print(f"    detection_method: {s.detection_method}")

    # 检查2浪验证状态
    if w2signals:
        valid_count = sum(1 for s in w2signals if s.wave_structure.get('wave1_valid', False))
        print("\n  2浪验证统计:")
        print(f"    总数: {len(w2signals)}")
        print(f"    通过验证: {valid_count}")
        print(f"    通过率: {valid_count/len(w2signals)*100:.1f}%")

        if w2signals:
            s = w2signals[0]
            ws = s.wave_structure or {}
            print("\n  首个2浪信号详情:")
            print(f"    日期: {df.iloc[-1]['date']}")
            print(f"    置信度: {s.confidence:.2f}")
            print(f"    wave1_valid: {ws.get('wave1_valid', 'N/A')}")
            print(f"    wave1_duration: {ws.get('wave1_duration', 'N/A')}")

print("\n" + "=" * 80)
print("调试完成")
print("=" * 80)
