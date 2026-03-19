#!/usr/bin/env python3
"""
测试价格在MA200上方时的买入逻辑
"""

from pathlib import Path


import pandas as pd

from src.analysis.backtest.wave_backtester import TradeAction, WaveBacktester, WaveStrategy
from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data

SYMBOL = '600519'
START = '2023-01-01'  # 使用更早的数据
END = '2026-03-16'

print("价格高于MA200时的买入逻辑测试")
print("=" * 70)

df = get_stock_data(SYMBOL, START, END)
df['date'] = pd.to_datetime(df['date'])
df['ma200'] = df['close'].rolling(200).mean()

# 找到价格高于MA200 5%以上的日期
mask = (df['close'] > df['ma200'] * 1.05) & (df['ma200'].notna())
valid_days = df[mask]

if len(valid_days) == 0:
    print("未找到价格高于MA200 5%以上的日期")
    sys.exit(0)

print(f"找到 {len(valid_days)} 天价格高于MA200 5%以上")

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

# 测试前10个这样的日子
print("\n" + "-" * 70)
print(f"{'日期':<12} {'价格':>10} {'MA200':>10} {'价格/MA':>8} {'信号数':>6} {'买入':>6}")
print("-" * 70)

buy_count = 0
for idx in valid_days.index[:20]:
    row = df.loc[idx]
    date = row['date'].strftime('%Y-%m-%d')
    price = row['close']
    ma200 = row['ma200']
    ratio = price / ma200

    # 准备数据
    pos = df.index.get_loc(idx)
    lookback = max(0, pos - 60)
    window_df = df.iloc[lookback:pos+1].copy()

    # 检测信号
    signals = analyzer.detect(window_df, mode='all')
    signal_count = len(signals)

    # 检查是否会买入
    backtester.currentsignals = signals
    best = backtester._get_best_trade_signal(price)
    will_buy = '✓' if (best and best.direction == 'up' and SYMBOL not in strategy.positions) else ''
    if will_buy:
        buy_count += 1
        # 模拟买入
        strategy.executetrade(SYMBOL, date, price, TradeAction.BUY,
                              target_price=best.target_price,
                              stop_loss=best.stop_loss,
                              wavesignal=best)

    print(f"{date:<12} {price:>10.2f} {ma200:>10.2f} {ratio:>8.3f} {signal_count:>6} {will_buy:>6}")

print("-" * 70)
print(f"\n检测到 {buy_count} 次买入机会")
print(f"当前持仓: {len(strategy.positions)} 个")
