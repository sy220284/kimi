#!/usr/bin/env python3
"""
动态目标价策略 - 放宽阈值测试
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🎯 动态目标价策略 - 放宽阈值测试\n")

# 测试不同阈值
thresholds = [0.03, 0.05, 0.08, 0.10]

for threshold in thresholds:
    print(f"\n{'='*60}")
    print(f"接近目标价阈值: {threshold:.0%}")
    print(f"{'='*60}")
    
    symbol = '600519'
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    
    strategy = WaveStrategy(
        initial_capital=1000000,
        position_size=0.2,
        stop_loss_pct=0.05,
        min_confidence=0.35,
        use_resonance=False,
        min_holding_days=3,
        use_trend_filter=False,
        use_dynamic_target=True,
        target_proximity_pct=threshold,
    )
    
    analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    print(f"  交易: {result.total_trades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}% | 回撤: {result.max_drawdown_pct:.1f}%")

print("\n✅ 完成")
