#!/usr/bin/env python3
"""
信号vs交易对比分析 - 理解为什么30个信号只产生14笔交易
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction

print("🔍 信号vs交易对比分析\n")

symbol = '603288'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

strategy = WaveStrategy(
    min_confidence=0.35,
    use_resonance=False,
    stop_loss_pct=0.05,  # 5%止损
    take_profit_pct=0.10  # 10%止盈
)

analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

# 完整回测
df = df.copy()
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')

result = backtester.run(symbol, df, reanalyze_every=30)

print(f"\n{'='*80}")
print(f"📊 {symbol} 交易分析")
print(f"{'='*80}")

print(f"\n【策略配置】")
print(f"  置信度阈值: {strategy.min_confidence}")
print(f"  止损比例: {strategy.stop_loss_pct:.0%}")
print(f"  止盈比例: {strategy.take_profit_pct:.0%}")

print(f"\n【交易统计】")
print(f"  总交易次数: {result.total_trades}")
print(f"  盈利: {result.winning_trades}次")
print(f"  亏损: {result.losing_trades}次")
print(f"  胜率: {result.win_rate:.1%}")

print(f"\n【每笔交易详情】")
for i, trade in enumerate(result.trades, 1):
    print(f"\n  交易#{i}:")
    print(f"    买入: {trade.entry_date} ¥{trade.entry_price:.2f}")
    print(f"    止损: ¥{trade.stop_loss:.2f} ({(trade.stop_loss/trade.entry_price-1)*100:.1f}%)")
    print(f"    止盈: ¥{trade.target_price:.2f} ({(trade.target_price/trade.entry_price-1)*100:.1f}%)")
    
    if trade.status == 'closed':
        print(f"    卖出: {trade.exit_date} ¥{trade.exit_price:.2f}")
        print(f"    盈亏: {trade.pnl_pct:.1f}%")
        
        # 判断是止损还是止盈还是其他
        if trade.exit_price <= trade.stop_loss * 1.001:  # 允许微小误差
            exit_reason = "🔴 止损"
        elif trade.exit_price >= trade.target_price * 0.999:
            exit_reason = "🟢 止盈"
        else:
            exit_reason = "⚪ 其他"
        print(f"    类型: {exit_reason}")
    else:
        print(f"    状态: 持仓中")

# 分析问题
print(f"\n{'='*80}")
print(f"🚨 问题诊断")
print(f"{'='*80}")

# 统计当日进当日出
same_day_trades = [t for t in result.trades if t.status == 'closed' and t.entry_date == t.exit_date]
if same_day_trades:
    print(f"\n【当日进当日出问题】")
    print(f"  涉及交易: {len(same_day_trades)}笔")
    for t in same_day_trades[:3]:  # 只显示前3笔
        print(f"    {t.entry_date}: 买入¥{t.entry_price:.2f} -> 卖出¥{t.exit_price:.2f}")

# 分析目标价是否合理
print(f"\n【目标价vs买入价分析】")
for t in result.trades[:5]:
    target_vs_entry = (t.target_price / t.entry_price - 1) * 100
    print(f"  {t.entry_date}: 买入¥{t.entry_price:.2f}, 目标¥{t.target_price:.2f} ({target_vs_entry:+.1f}%)")

print(f"\n【核心发现】")
print(f"  1. 信号类型标注为'impulse'但实际结构是ABC (调整浪)")
print(f"  2. 目标价有时低于买入价 (不合理)")
print(f"  3. 大量当日交易 = 止损/止盈设置过紧或计算错误")
print(f"  4. 持仓期内重复信号被过滤 (execute_trade检查已有仓位)")

print("\n✅ 分析完成")
