#!/usr/bin/env python3
"""
全量个股波浪回测 - 自适应参数版本
利用分析器内置的自适应参数优化
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from data import get_stock_data, get_db_manager
from analysis.wave import UnifiedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester

print("="*80)
print("📈 全量个股波浪回测 - 自适应参数优化")
print("="*80)

# 获取股票列表
manager = get_db_manager()
all_symbols = manager.get_stored_symbols()

# 先测试食品饮料板块的核心股票
food_beverage = [
    '600519', '000858', '000568', '600809', '002304',  # 白酒
    '600887', '600600', '603288', '002507', '603866',   # 乳/啤/调味品/面包
]

# 取交集
test_symbols = [s for s in food_beverage if s in all_symbols]
print(f"\n测试股票: {len(test_symbols)} 只")
print("回测周期: 2021-01-01 ~ 2026-03-16\n")

# 回测结果
results = []

for idx, symbol in enumerate(test_symbols, 1):
    print(f"[{idx}/{len(test_symbols)}] {symbol}")
    print("-" * 60)
    
    try:
        # 获取数据
        df = get_stock_data(symbol, '2021-01-01', '2026-03-16')
        if len(df) < 200:
            print("   ⚠️ 数据不足，跳过\n")
            continue
        
        print(f"   数据: {len(df)}条")
        
        # 使用自适应分析器
        analyzer = UnifiedWaveAnalyzer(use_adaptive_params=True, use_resonance=True)
        backtester = WaveBacktester(analyzer)
        
        # 运行回测
        result = backtester.run(symbol, df, reanalyze_every=10)
        
        # 计算得分
        score = 0
        if result.total_trades >= 3:
            score = (
                result.win_rate * 0.3 +
                result.total_return_pct / 100 * 0.3 +
                (1 - result.max_drawdown_pct / 100) * 0.2 +
                min(result.sharpe_ratio, 3) / 3 * 0.2
            )
        
        results.append({
            'symbol': symbol,
            'win_rate': result.win_rate,
            'return_pct': result.total_return_pct,
            'max_dd': result.max_drawdown_pct,
            'sharpe': result.sharpe_ratio,
            'trades': result.total_trades,
            'score': score
        })
        
        print(f"   ✅ 胜率{result.win_rate:.1%} | 收益{result.total_return_pct:.1f}% | 回撤{result.max_drawdown_pct:.1f}% | 交易{result.total_trades}次\n")
        
    except Exception as e:
        print(f"   ❌ 失败: {str(e)[:50]}\n")

# 统计分析
print("="*80)
print("📊 回测结果统计")
print("="*80)

if results:
    df = pd.DataFrame(results)
    
    print(f"\n成功回测: {len(df)} 只股票")
    print("\n【整体表现】")
    print(f"  平均胜率: {df['win_rate'].mean():.1%}")
    print(f"  平均收益: {df['return_pct'].mean():.1f}%")
    print(f"  平均回撤: {df['max_dd'].mean():.1f}%")
    print(f"  平均Sharpe: {df['sharpe'].mean():.2f}")
    print(f"  平均交易: {df['trades'].mean():.1f}次")
    
    # 按收益排序
    print("\n【收益排名】")
    df_sorted = df.sort_values('return_pct', ascending=False)
    for _, row in df_sorted.iterrows():
        print(f"  {row['symbol']}: 收益{row['return_pct']:.1f}% | 胜率{row['win_rate']:.1%} | {int(row['trades'])}笔交易")
    
    # 分析哪些股票适合波浪策略
    good_performers = df[(df['win_rate'] > 0.5) & (df['return_pct'] > 0)]
    if len(good_performers) > 0:
        print(f"\n【适合波浪策略的股票】({len(good_performers)}只)")
        for _, row in good_performers.iterrows():
            print(f"  ✅ {row['symbol']}: 胜率{row['win_rate']:.1%}, 收益{row['return_pct']:.1f}%")
    
    poor_performers = df[df['win_rate'] < 0.4]
    if len(poor_performers) > 0:
        print(f"\n【表现不佳的股票】({len(poor_performers)}只)")
        for _, row in poor_performers.iterrows():
            print(f"  ⚠️ {row['symbol']}: 胜率{row['win_rate']:.1%}, 可能不适合波浪策略")

print("\n" + "="*80)
print("✅ 回测完成!")
print("="*80)
