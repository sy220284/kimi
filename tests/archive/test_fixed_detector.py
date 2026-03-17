#!/usr/bin/env python3
"""
验证修复后的增强版检测器
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🎯 验证修复后的增强版检测器\n")
print("="*80)

test_stocks = [
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
]

for symbol, name in test_stocks:
    print(f"\n📈 {symbol} {name}")
    print("-"*60)
    
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    
    # 使用修复后的检测器
    analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
    
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
    
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    print(f"  数据: {len(df)}条")
    print(f"  交易: {result.total_trades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}% | 回撤: {result.max_drawdown_pct:.1f}%")
    
    if result.trades:
        from collections import Counter
        wave_dist = Counter([t.entry_wave for t in result.trades if t.entry_wave])
        none_count = sum(1 for t in result.trades if t.entry_wave is None)
        
        print(f"\n  买入浪号分布:")
        if none_count:
            print(f"    浪None: {none_count}次")
        for wave, count in sorted(wave_dist.items(), key=lambda x: str(x[0])):
            print(f"    浪{wave}: {count}次")
        
        # 显示最近几笔交易的详情
        print(f"\n  最近3笔交易:")
        for t in result.trades[-3:]:
            target_pct = (t.target_price / t.entry_price - 1) * 100 if t.target_price else 0
            exit_info = f"{t.exit_date} {t.pnl_pct:+.1f}%" if t.status == 'closed' else "持仓中"
            print(f"    {t.entry_date} 浪{t.entry_wave}→{t.expected_wave}")
            print(f"       买入¥{t.entry_price:.2f} 目标¥{t.target_price:.2f}({target_pct:+.1f}%) -> {exit_info}")

print("\n✅ 测试完成")
