#!/usr/bin/env python3
"""
修复后的回测测试 - 仅测试603288
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🔧 修复后回测测试 - 603288 海天味业\n")

symbol = '603288'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
print(f"数据条数: {len(df)}")

# 使用修复后的策略
strategy = WaveStrategy(
    min_confidence=0.35,
    use_resonance=False,
    min_holding_days=3,  # 最小持仓3天
    use_trend_filter=True,  # 启用趋势过滤
    trend_ma_period=60,  # 60日均线
    stop_loss_pct=0.05,
    take_profit_pct=0.10
)

analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

print("\n开始回测...")
result = backtester.run(symbol, df, reanalyze_every=30)

print(f"\n{'='*60}")
print(f"📊 回测结果")
print(f"{'='*60}")
print(f"总交易: {result.total_trades}次")
print(f"盈利: {result.winning_trades}次")
print(f"亏损: {result.losing_trades}次")
print(f"胜率: {result.win_rate:.1%}")
print(f"总收益: {result.total_return_pct:.1f}%")
print(f"最大回撤: {result.max_drawdown_pct:.1f}%")

if result.trades:
    print(f"\n📋 交易明细:")
    for i, t in enumerate(result.trades, 1):
        exit_date = t.exit_date or '持仓中'
        pnl = f"{t.pnl_pct:+.1f}%" if t.status == 'closed' else '-'
        print(f"\n  交易#{i}: {t.entry_date} 买入 ¥{t.entry_price:.2f}")
        print(f"    卖出: {exit_date} {f'¥{t.exit_price:.2f}' if t.exit_price else '-'}")
        print(f"    盈亏: {pnl}")
        print(f"    设置: 目标¥{t.target_price:.2f} ({(t.target_price/t.entry_price-1)*100:+.1f}%) 止损¥{t.stop_loss:.2f} ({(t.stop_loss/t.entry_price-1)*100:+.1f}%)")

print("\n✅ 完成")
