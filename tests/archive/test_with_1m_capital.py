#!/usr/bin/env python3
"""
充足资金回测 - 初始资金100万
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("💰 充足资金回测 - 初始资金100万\n")
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
    
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        
        # 使用100万初始资金
        strategy = WaveStrategy(
            initial_capital=1000000,  # 100万
            position_size=0.2,        # 20%仓位 = 20万
            min_confidence=0.35,
            use_resonance=False,
            min_holding_days=3,
            use_trend_filter=False,
            stop_loss_pct=0.05,
            take_profit_pct=0.10
        )
        
        analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
        backtester = WaveBacktester(analyzer)
        backtester.strategy = strategy
        
        result = backtester.run(symbol, df, reanalyze_every=30)
        
        print(f"  交易: {result.total_trades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}% | 回撤: {result.max_drawdown_pct:.1f}%")
        
        if result.trades:
            print(f"  最近3笔:")
            for t in result.trades[-3:]:
                exit_info = f"{t.exit_date or '持仓'} {t.pnl_pct:+.1f}%" if t.status == 'closed' else "持仓中"
                print(f"    {t.entry_date} ¥{t.entry_price:.2f} x {t.quantity}股 -> {exit_info}")
        
        results.append({
            'symbol': symbol,
            'name': name,
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'return': result.total_return_pct,
            'drawdown': result.max_drawdown_pct
        })
        
    except Exception as e:
        print(f"  ❌ 错误: {e}")

# 汇总
print(f"\n{'='*80}")
print("📊 汇总对比 (初始资金100万)")
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
