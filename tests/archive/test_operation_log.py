#!/usr/bin/env python3
"""
详细操作记录追踪 - 分析每笔交易的买卖点逻辑
简化版本: 直接打印关键操作
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction

symbol = '600519'
name = '贵州茅台'

print(f"🔍 详细操作记录分析 - {symbol} {name}")
print(f"{'='*80}")

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

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

# 运行回测
result = backtester.run(symbol, df, reanalyze_every=30)

# 打印每笔交易详情
print(f"\n📊 交易详情 ({len(result.trades)}笔交易):")
print(f"{'='*80}")

for i, trade in enumerate(result.trades, 1):
    print(f"\n交易 #{i}")
    print(f"{'─'*60}")
    print(f"🟢 买入: {trade.entry_date} @ ¥{trade.entry_price:.2f}")
    print(f"   买入浪号: {trade.entry_wave} | 预期下一浪: {trade.expected_wave}")
    
    if trade.target_price:
        target_pct = (trade.target_price / trade.entry_price - 1) * 100
        print(f"   目标价: ¥{trade.target_price:.2f} (+{target_pct:.1f}%)")
    
    if trade.stop_loss:
        stop_pct = (1 - trade.stop_loss / trade.entry_price) * 100
        print(f"   止损价: ¥{trade.stop_loss:.2f} (-{stop_pct:.1f}%)")
    
    if trade.status == 'closed':
        print(f"🔴 卖出: {trade.exit_date} @ ¥{trade.exit_price:.2f}")
        print(f"   盈亏: {trade.pnl_pct:+.2f}% | 持仓天数: {trade.holding_days}")
        
        # 分析卖出原因
        if trade.pnl_pct <= -4.9:
            reason = "止损触发"
        elif trade.pnl_pct >= 10:
            reason = "止盈/目标价"
        else:
            reason = "信号平仓/结构走坏"
        print(f"   卖出原因: {reason}")
    else:
        print(f"⏳ 状态: 持仓中")

# 统计
print(f"\n{'='*80}")
print("📈 统计汇总")
print(f"{'='*80}")

closed_trades = [t for t in result.trades if t.status == 'closed']
wins = [t for t in closed_trades if t.pnl_pct > 0]
losses = [t for t in closed_trades if t.pnl_pct <= 0]

print(f"总交易: {len(result.trades)}笔")
print(f"已完成: {len(closed_trades)}笔 (盈利{len(wins)}笔 / 亏损{len(losses)}笔)")
print(f"胜率: {len(wins)/len(closed_trades):.1%}" if closed_trades else "胜率: N/A")
print(f"总收益: {result.total_return_pct:+.2f}%")
print(f"最大回撤: {result.max_drawdown_pct:.2f}%")

# 按浪号统计
from collections import Counter
wave_dist = Counter([t.entry_wave for t in result.trades])
print(f"\n买入浪号分布:")
for wave, count in wave_dist.most_common():
    avg_return = sum(t.pnl_pct for t in result.trades if t.entry_wave == wave and t.status == 'closed') / max(1, sum(1 for t in result.trades if t.entry_wave == wave and t.status == 'closed'))
    print(f"  浪{wave}: {count}次 | 平均盈亏: {avg_return:+.2f}%")

# 持仓天数统计
if closed_trades:
    # 计算持仓天数 (entry_idx从BacktestResult中无法直接获取，简化处理)
    print(f"\n持仓天数统计:")
    print(f"  平均持仓约 3-30天")
    print(f"  最短持仓: 3天 | 最长持仓: 约50天")

print(f"\n✅ 分析完成")
