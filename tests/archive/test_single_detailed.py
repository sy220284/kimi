#!/usr/bin/env python3
"""
单股票详细回测分析
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

symbol = '600519'
name = '贵州茅台'

print(f"🔧 详细回测分析: {symbol} {name}\n")

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
print(f"数据条数: {len(df)}")
print(f"数据范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"价格范围: ¥{df['close'].min():.2f} ~ ¥{df['close'].max():.2f}")

# 策略配置
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

print(f"\n策略配置:")
print(f"  置信度阈值: {strategy.min_confidence}")
print(f"  最小持仓: {strategy.min_holding_days}天")
print(f"  趋势均线: {strategy.trend_ma_period}日")
print(f"  止损: {strategy.stop_loss_pct:.0%} 止盈: {strategy.take_profit_pct:.0%}")

print(f"\n开始回测...")
result = backtester.run(symbol, df, reanalyze_every=30)

print(f"\n{'='*60}")
print(f"📊 回测结果")
print(f"{'='*60}")
print(f"总交易: {result.total_trades}次")
print(f"盈利: {result.winning_trades}次")
print(f"亏损: {result.losing_trades}次")
print(f"胜率: {result.win_rate:.1%}")
print(f"总收益: {result.total_return_pct:+.2f}%")
print(f"最大回撤: {result.max_drawdown_pct:.2f}%")
print(f"Sharpe: {result.sharpe_ratio:.2f}")

if result.trades:
    print(f"\n📋 详细交易记录:")
    for i, t in enumerate(result.trades, 1):
        print(f"\n  交易#{i}:")
        print(f"    买入: {t.entry_date} ¥{t.entry_price:.2f}")
        print(f"    设置: 目标¥{t.target_price:.2f} (+{(t.target_price/t.entry_price-1)*100:.1f}%) 止损¥{t.stop_loss:.2f} ({(t.stop_loss/t.entry_price-1)*100:.1f}%)")
        
        if t.status == 'closed':
            print(f"    卖出: {t.exit_date} ¥{t.exit_price:.2f}")
            print(f"    盈亏: {t.pnl_pct:+.2f}%")
            
            # 判断退出原因
            if t.exit_price <= t.stop_loss * 1.001:
                exit_reason = "🔴 止损"
            elif t.exit_price >= t.target_price * 0.999:
                exit_reason = "🟢 止盈"
            else:
                exit_reason = "⚪ 其他"
            print(f"    类型: {exit_reason}")
        else:
            print(f"    状态: 持仓中")
else:
    print(f"\n⚠️ 没有产生交易")
    print(f"可能原因:")
    print(f"  1. 置信度阈值过高")
    print(f"  2. 趋势过滤过于严格")
    print(f"  3. 股票长期处于均线下方")

print("\n✅ 完成")
