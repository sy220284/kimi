#!/usr/bin/env python3
"""
快速波浪回测 - 放宽参数版
测试是否能产生交易
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("📈 快速波浪回测 - 放宽参数测试\n")

# 测试几只股票
test_stocks = ['600519', '000858', '600887', '603288']

for symbol in test_stocks:
    print(f"\n{'='*60}")
    print(f"{symbol}:")
    print('='*60)
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        print(f"  数据: {len(df)}条")
        
        # 使用放宽参数的策略
        strategy = WaveStrategy(
            min_confidence=0.35,      # 从0.5降到0.35
            use_resonance=False       # 关闭共振验证
        )
        
        analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
        backtester = WaveBacktester(analyzer)
        backtester.strategy = strategy  # 替换策略
        
        # 每30天分析一次
        result = backtester.run(symbol, df, reanalyze_every=30)
        
        print(f"\n  ✅ 胜率{result.win_rate:.1%} | 收益{result.total_return_pct:.1f}% | 回撤{result.max_drawdown_pct:.1f}%")
        print(f"  📊 交易{result.total_trades}次 | Sharpe{result.sharpe_ratio:.2f}")
        
        if result.total_trades > 0:
            print(f"\n  交易明细:")
            for t in result.trades:
                exit_info = f"{t.exit_date or '持仓'} {t.exit_price:.2f}" if t.exit_price else f"{t.exit_date or '持仓'} -"
                print(f"    {t.entry_date} 买入 {t.entry_price:.2f} -> {exit_info} | 盈亏{t.pnl_pct:.1f}%")
        else:
            print(f"\n  ⚠️ 没有交易产生")
        
    except Exception as e:
        print(f"  ❌ {str(e)[:80]}")

print("\n✅ 完成")
