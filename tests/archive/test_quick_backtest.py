#!/usr/bin/env python3
"""
快速波浪回测 - 优化版
减少分析频率，提高速度
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester

print("📈 快速波浪回测测试\n")

# 测试几只股票
test_stocks = ['600519', '000858', '600887', '603288']

for symbol in test_stocks:
    print(f"\n{symbol}:")
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        print(f"  数据: {len(df)}条")
        
        analyzer = EnhancedWaveAnalyzer()
        backtester = WaveBacktester(analyzer)
        
        # 每30天分析一次（减少计算）
        result = backtester.run(symbol, df, reanalyze_every=30)
        
        print(f"  ✅ 胜率{result.win_rate:.1%} | 收益{result.total_return_pct:.1f}% | 回撤{result.max_drawdown_pct:.1f}%")
        print(f"  📊 交易{result.total_trades}次 | Sharpe{result.sharpe_ratio:.2f}")
        
    except Exception as e:
        print(f"  ❌ {str(e)[:50]}")

print("\n✅ 完成")
