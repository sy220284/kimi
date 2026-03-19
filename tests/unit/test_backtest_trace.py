#!/usr/bin/env python3
"""
回测详细诊断
"""

from pathlib import Path


import pandas as pd

from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave import UnifiedWaveAnalyzer
from data import get_stock_data

SYMBOL = '600519'
START = '2024-06-01'  # 使用较近期数据，MA200已可用
END = '2026-03-16'

print("回测详细诊断")
print("=" * 70)

df = get_stock_data(SYMBOL, START, END)
df['date'] = pd.to_datetime(df['date'])
df['ma200'] = df['close'].rolling(200).mean()

print(f"数据条数: {len(df)}")
print(f"日期范围: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")

analyzer = UnifiedWaveAnalyzer(
    use_resonance=True,
    min_resonance_score=0.3,
    trend_ma_period=200
)

strategy = WaveStrategy(
    use_trend_filter=True,
    trend_ma_period=200,
)

backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

# 模拟回测流程的前50天
print("\n" + "-" * 70)
print("模拟回测流程 (部分天数)")
print("-" * 70)
print(f"{'日期':<12} {'价格':>10} {'MA200':>10} {'趋势':>6} {'分析':>10} {'信号':>6} {'买入':>6}")
print("-" * 70)

count = 0
for i in range(200, min(200+50, len(df))):  # 从200开始确保MA200有效
    row = df.iloc[i]
    date = row['date'].strftime('%m-%d')
    price = row['close']
    ma200 = row['ma200']

    # 趋势判断
    trend = 'N/A'
    if pd.notna(ma200):
        if price > ma200 * 1.05:
            trend = 'UP'
        elif price < ma200 * 0.95:
            trend = 'DOWN'
        else:
            trend = 'SIDE'

    # 模拟回测器逻辑
    analyzed = False
    signal_count = 0
    buy_triggered = False

    # 定期重新分析
    if i % 10 == 0:
        lookback = max(0, i - 60)
        window_df = df.iloc[lookback:i+1].copy()
        if len(window_df) >= 30:
            signals = analyzer.detect(window_df, mode='all')
            analyzed = True
            signal_count = len(signals)

            # 检查是否有买入信号
            if signals and SYMBOL not in strategy.positions:
                best = signals[0]
                if best.is_valid and best.confidence >= 0.5 and best.direction == 'up':
                    # 检查趋势对齐
                    if best.trend_aligned:
                        buy_triggered = True
                        count += 1

    if analyzed:
        print(f"{date:<12} {price:>10.2f} {ma200:>10.2f} {trend:>6} {'✓':>10} {signal_count:>6} {'✓' if buy_triggered else '':>6}")
        if signals:
            for sig in signals[:2]:
                print(f"      → {sig.entry_type.value}浪 ¥{sig.entry_price:.2f} 置信{sig.confidence:.2f} 趋势{'✓' if sig.trend_aligned else '✗'} 共振{sig.resonance_score:.2f}")

print("-" * 70)
print("\n诊断结果:")
print(f"  检测到 {count} 次潜在买入机会")
print(f"  实际持仓数: {len(strategy.positions)}")
