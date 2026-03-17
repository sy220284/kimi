#!/usr/bin/env python3
"""
修复后的回测测试
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🔧 修复后回测测试\n")
print("="*80)

# 测试603288
test_stocks = ['603288', '600519', '000858', '600887']

for symbol in test_stocks:
    print(f"\n📈 {symbol}")
    print("="*60)
    
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        
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
        
        result = backtester.run(symbol, df, reanalyze_every=30)
        
        print(f"\n  总交易: {result.total_trades}次")
        print(f"  胜率: {result.win_rate:.1%}")
        print(f"  总收益: {result.total_return_pct:.1f}%")
        print(f"  最大回撤: {result.max_drawdown_pct:.1f}%")
        
        if result.trades:
            print(f"\n  最近3笔交易:")
            for t in result.trades[-3:]:
                exit_info = f"{t.exit_date or '持仓'}"
                pnl_info = f"{t.pnl_pct:.1f}%" if t.status == 'closed' else "-"
                print(f"    {t.entry_date} 买入¥{t.entry_price:.2f} -> {exit_info} | {pnl_info}")
                if t.target_price:
                    print(f"      (目标¥{t.target_price:.2f}, 止损¥{t.stop_loss:.2f})")
        
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n✅ 修复测试完成")
