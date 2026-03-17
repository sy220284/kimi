#!/usr/bin/env python3
"""
分析买入浪号分布和目标价计算
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("📊 买入浪号分布分析\n")
print("="*80)

test_stocks = ['600519', '000858', '600887', '603288']

for symbol in test_stocks:
    print(f"\n📈 {symbol}")
    print("-"*60)
    
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
        target_proximity_pct=0.05,
    )
    
    analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    # 分析每笔交易的买入浪号
    wave_counts = {}
    for trade in result.trades:
        # 从position_analysis中获取买入时的分析结果
        # 注意: 交易完成后position_analysis会被清理
        # 这里简化处理，显示目标涨幅
        target_pct = (trade.target_price / trade.entry_price - 1) * 100
        print(f"  {trade.entry_date} 买入¥{trade.entry_price:.2f} 目标{target_pct:.1f}%")

print("\n✅ 完成")
