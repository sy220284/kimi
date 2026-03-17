#!/usr/bin/env python3
"""
修复后的回测测试 - 全部4只核心股票
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🔧 修复后回测测试 - 核心股票组合\n")
print("="*80)

# 4只核心股票
test_stocks = [
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
    ('600887', '伊利股份'),
    ('603288', '海天味业')
]

results_summary = []

for symbol, name in test_stocks:
    print(f"\n📈 {symbol} {name}")
    print("-"*60)
    
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        print(f"数据: {len(df)}条")
        
        # 使用修复后的策略
        strategy = WaveStrategy(
            min_confidence=0.35,
            use_resonance=False,
            min_holding_days=3,
            use_trend_filter=True,
            trend_ma_period=60,
            stop_loss_pct=0.05,
            take_profit_pct=0.10
        )
        
        analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
        backtester = WaveBacktester(analyzer)
        backtester.strategy = strategy
        
        result = backtester.run(symbol, df, reanalyze_every=30)
        
        print(f"\n结果:")
        print(f"  交易: {result.total_trades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}% | 回撤: {result.max_drawdown_pct:.1f}%")
        
        # 详细分析每笔交易
        if result.trades:
            print(f"\n  交易明细:")
            for i, t in enumerate(result.trades, 1):
                exit_date = t.exit_date or '持仓中'
                pnl = f"{t.pnl_pct:+.1f}%" if t.status == 'closed' else '-'
                holding_days = "-"
                if t.status == 'closed' and t.exit_date:
                    try:
                        from datetime import datetime
                        d1 = datetime.strptime(t.entry_date, '%Y-%m-%d')
                        d2 = datetime.strptime(t.exit_date, '%Y-%m-%d')
                        holding_days = f"{(d2-d1).days}天"
                    except:
                        holding_days = "-"
                
                print(f"    #{i}: {t.entry_date} ¥{t.entry_price:.2f} -> {exit_date} {pnl} ({holding_days})")
                
                # 检查是否有问题
                if t.target_price and t.target_price <= t.entry_price:
                    print(f"       ⚠️ 目标价错误: ¥{t.target_price:.2f} <= 买入价")
                if t.stop_loss and t.stop_loss >= t.entry_price:
                    print(f"       ⚠️ 止损价错误: ¥{t.stop_loss:.2f} >= 买入价")
        
        results_summary.append({
            'symbol': symbol,
            'name': name,
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'return': result.total_return_pct,
            'drawdown': result.max_drawdown_pct
        })
        
    except Exception as e:
        print(f"  ❌ 错误: {str(e)[:100]}")
        results_summary.append({
            'symbol': symbol,
            'name': name,
            'trades': 0,
            'win_rate': 0,
            'return': 0,
            'drawdown': 0,
            'error': str(e)
        })

# 汇总
print(f"\n{'='*80}")
print("📊 汇总对比")
print(f"{'='*80}")
print(f"{'股票':<10} {'交易':<6} {'胜率':<8} {'收益':<10} {'回撤':<8}")
print("-"*50)
for r in results_summary:
    print(f"{r['symbol']:<10} {r['trades']:<6} {r['win_rate']:<8.1%} {r['return']:<+10.1f}% {r['drawdown']:<8.1f}%")

# 总体统计
total_trades = sum(r['trades'] for r in results_summary if 'error' not in r)
if total_trades > 0:
    avg_return = sum(r['return'] for r in results_summary if 'error' not in r) / len([r for r in results_summary if 'error' not in r])
    print(f"\n总计: {total_trades}笔交易 | 平均收益: {avg_return:+.1f}%")

print("\n✅ 完成")
