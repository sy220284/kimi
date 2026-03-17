#!/usr/bin/env python3
"""
诊断增强版检测器问题
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction

symbol = '600519'
print(f"🔍 诊断 {symbol} 茅台\n")

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
strategy = WaveStrategy(
    initial_capital=1000000,
    position_size=0.2,
    stop_loss_pct=0.05,
    min_confidence=0.35,
    use_resonance=False,
    min_holding_days=3,
    use_trend_filter=False,
)

backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

# 手动追踪前100个bar
df_test = df.head(100).copy()
df_test['date'] = pd.to_datetime(df_test['date'])
df_test = df_test.sort_values('date')

print("手动追踪信号生成:\n")
signal_count = 0
for i in range(60, len(df_test), 10):
    segment_df = df_test.iloc[i-60:i].copy()
    date = df_test.iloc[i]['date'].strftime('%Y-%m-%d')
    price = df_test.iloc[i]['close']
    
    result = analyzer.analyze(symbol, segment_df)
    if result and result.primary_pattern:
        p = result.primary_pattern
        signal = strategy.generate_signal(result, price)
        
        if signal == TradeAction.BUY:
            signal_count += 1
            latest_wave = p.points[-1].wave_num if p.points else 'None'
            print(f"  {date}: BUY信号 浪{latest_wave} 置信度{p.confidence:.2f} 类型{p.wave_type.value}")

print(f"\n共检测到 {signal_count} 个BUY信号")

# 对比原始检测器
print("\n对比: 使用原始检测器...")
analyzer_old = EnhancedWaveAnalyzer(use_adaptive=False)
signal_count_old = 0
for i in range(60, len(df_test), 10):
    segment_df = df_test.iloc[i-60:i].copy()
    result = analyzer_old.analyze(symbol, segment_df)
    if result and result.primary_pattern:
        signal = strategy.generate_signal(result, df_test.iloc[i]['close'])
        if signal == TradeAction.BUY:
            signal_count_old += 1

print(f"原始检测器: {signal_count_old} 个BUY信号")
