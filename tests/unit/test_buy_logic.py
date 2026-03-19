#!/usr/bin/env python3
"""
直接测试回测器买入逻辑
"""

from pathlib import Path


import pandas as pd

from src.analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data

SYMBOL = '600519'
START = '2024-06-01'
END = '2026-03-16'

print("回测器买入逻辑测试")
print("=" * 70)

df = get_stock_data(SYMBOL, START, END)
df['date'] = pd.to_datetime(df['date'])
df['ma200'] = df['close'].rolling(200).mean()

analyzer = UnifiedWaveAnalyzer(
    use_resonance=True,
    min_resonance_score=0.3,
    trend_ma_period=200
)

strategy = WaveStrategy(
    initial_capital=1000000,
    use_trend_filter=True,
    trend_ma_period=200,
)

backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

# 测试具体某天的买入逻辑
test_day = 250  # 测试第250天

row = df.iloc[test_day]
date = row['date'].strftime('%Y-%m-%d')
price = row['close']
ma200 = row['ma200']

print(f"\n测试日期: {date}")
print(f"价格: ¥{price:.2f}")
print(f"MA200: ¥{ma200:.2f}" if pd.notna(ma200) else "MA200: N/A")

# 准备数据
lookback_start = max(0, test_day - 60)
window_df = df.iloc[lookback_start:test_day+1].copy()
print(f"分析窗口: {len(window_df)} 天")

# 检测信号
signals = analyzer.detect(window_df, mode='all')
print(f"\n检测到 {len(signals)} 个信号:")

for i, sig in enumerate(signals):
    print(f"\n信号 {i+1}:")
    print(f"  类型: {sig.entry_type.value}")
    print(f"  方向: {sig.direction}")
    print(f"  价格: ¥{sig.entry_price:.2f}")
    print(f"  置信度: {sig.confidence:.2f}")
    print(f"  共振分数: {sig.resonance_score:.2f}")
    print(f"  趋势对齐: {sig.trend_aligned}")
    print(f"  有效: {sig.is_valid}")

    # 检查是否满足买入条件
    can_buy = sig.is_valid and sig.confidence >= 0.5 and sig.direction == 'up'
    print(f"  可买入: {can_buy}")

# 模拟回测器的 _get_best_trade_signal
print("\n" + "-" * 70)
print("回测器内部逻辑模拟:")
print("-" * 70)

backtester.currentsignals = signals
best = backtester._get_best_trade_signal(price)

if best:
    print(f"最佳信号: {best.entry_type.value}浪")
    print(f"  价格: ¥{best.entry_price:.2f}")
    print(f"  置信度: {best.confidence:.2f}")
    print(f"  趋势对齐: {best.trend_aligned}")

    # 检查是否会触发买入
    if best.direction == 'up':
        print("  → 会触发买入")
    else:
        print("  → 方向不是up，不会买入")
else:
    print("没有最佳信号")

# 检查持仓状态
print(f"\n当前持仓: {strategy.positions}")
