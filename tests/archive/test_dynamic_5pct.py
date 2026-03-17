#!/usr/bin/env python3
"""
动态目标价策略 - 最优阈值5%测试
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🎯 动态目标价策略 - 5%最优阈值\n")
print("="*80)

test_stocks = [
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
    ('600887', '伊利股份'),
    ('603288', '海天味业')
]

results = []

for symbol, name in test_stocks:
    print(f"\n📈 {symbol} {name}")
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
        target_proximity_pct=0.05,  # 5%最优阈值
        wave_structure_break_pct=0.03
    )
    
    analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    print(f"  交易: {result.total_trades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}% | 回撤: {result.max_drawdown_pct:.1f}%")
    
    if result.trades:
        profits = [t.pnl_pct for t in result.trades if t.status == 'closed']
        if profits:
            avg_profit = sum(profits) / len(profits)
            max_profit = max(profits)
            min_profit = min(profits)
            print(f"  单笔平均: {avg_profit:+.2f}% | 最大: {max_profit:+.1f}% | 最小: {min_profit:+.1f}%")
    
    results.append({
        'symbol': symbol,
        'name': name,
        'trades': result.total_trades,
        'win_rate': result.win_rate,
        'return': result.total_return_pct,
        'drawdown': result.max_drawdown_pct
    })

print(f"\n{'='*80}")
print("📊 汇总 (动态目标价 5%阈值)")
print(f"{'='*80}")
print(f"{'股票':<12} {'交易':<6} {'胜率':<8} {'收益':<10} {'回撤':<8}")
print("-"*50)
for r in results:
    print(f"{r['symbol']:<12} {r['trades']:<6} {r['win_rate']:<8.1%} {r['return']:<+10.1f}% {r['drawdown']:<8.1f}%")

total = sum(r['trades'] for r in results)
if total > 0:
    avg = sum(r['return'] for r in results) / len(results)
    print(f"\n总计: {total}笔交易 | 平均收益: {avg:+.1f}%")

print("\n✅ 完成")
