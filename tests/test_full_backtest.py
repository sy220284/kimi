#!/usr/bin/env python3
"""
全量个股波浪回测 - 优化分析准确度
对数据库所有股票进行回测，收集统计特征优化参数
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd

from analysis.backtest.wave_backtester import WaveBacktester
from analysis.optimization import ParameterSet
from analysis.wave import UnifiedWaveAnalyzer
from data import DatabaseDataManager, get_stock_data

print("="*80)
print("📈 全量个股波浪回测 - 优化分析准确度")
print("="*80)

# 初始化
manager = DatabaseDataManager()
analyzer = UnifiedWaveAnalyzer()

# 获取所有股票
all_symbols = manager.get_stored_symbols()
print(f"\n数据库共有 {len(all_symbols)} 只股票")
print("回测时间范围: 2021-01-01 至 2026-03-16 (约5年)\n")

# 回测结果收集
backtest_results = []

# 测试多组参数配置
paramconfigs = [
    ('保守', ParameterSet(atr_mult=0.7, confidence_threshold=0.6, min_change_pct=2.5)),
    ('标准', ParameterSet(atr_mult=0.5, confidence_threshold=0.5, min_change_pct=2.0)),
    ('激进', ParameterSet(atr_mult=0.4, confidence_threshold=0.4, min_change_pct=1.5)),
]

# 对每只股票回测
for idx, symbol in enumerate(all_symbols[:20], 1):  # 先测试前20只
    print(f"\n[{idx}/20] {symbol}")
    print("-" * 60)

    try:
        # 获取数据
        df = get_stock_data(symbol, '2021-01-01', '2026-03-16')
        if len(df) < 200:
            print(f"   ⚠️ 数据不足 ({len(df)}条)，跳过")
            continue

        print(f"   数据: {len(df)}条 ({df['date'].min()} ~ {df['date'].max()})")

        # 测试不同参数
        best_result = None
        best_score = -999

        for param_name, params in paramconfigs:
            try:
                # 创建带参数的分析器
                test_analyzer = UnifiedWaveAnalyzer(
                    atr_mult=params.atr_mult,
                    min_change_pct=params.min_change_pct,
                    peak_window=params.peak_window
                )

                # 回测
                backtester = WaveBacktester(test_analyzer)
                backtester.strategy.min_confidence = params.confidence_threshold

                result = backtester.run(symbol, df, reanalyze_every=10)

                # 计算综合得分
                score = (
                    result.win_rate * 0.3 +
                    result.total_return_pct / 100 * 0.3 +
                    (1 - result.max_drawdown_pct / 100) * 0.2 +
                    min(result.sharpe_ratio, 3) / 3 * 0.2
                ) if result.total_trades > 3 else -1

                if score > best_score:
                    best_score = score
                    best_result = {
                        'symbol': symbol,
                        'param': param_name,
                        'win_rate': result.win_rate,
                        'return_pct': result.total_return_pct,
                        'max_dd': result.max_drawdown_pct,
                        'sharpe': result.sharpe_ratio,
                        'trades': result.total_trades,
                        'score': score
                    }

            except Exception as e:
                print(f"   {param_name}参数失败: {str(e)[:30]}")

        if best_result:
            backtest_results.append(best_result)
            print(f"   ✅ 最优: {best_result['param']} | 胜率{best_result['win_rate']:.1%} | 收益{best_result['return_pct']:.1f}% | 交易{best_result['trades']}次")

    except Exception as e:
        print(f"   ❌ 失败: {str(e)[:50]}")

# 统计分析
print("\n" + "="*80)
print("📊 回测结果统计分析")
print("="*80)

if backtest_results:
    df_results = pd.DataFrame(backtest_results)

    print(f"\n成功回测: {len(df_results)} 只股票")

    # 整体统计
    print("\n【整体表现】")
    print(f"  平均胜率: {df_results['win_rate'].mean():.1%}")
    print(f"  平均收益: {df_results['return_pct'].mean():.1f}%")
    print(f"  平均回撤: {df_results['max_dd'].mean():.1f}%")
    print(f"  平均Sharpe: {df_results['sharpe'].mean():.2f}")
    print(f"  平均交易次数: {df_results['trades'].mean():.1f}")

    # 参数偏好统计
    print("\n【最优参数分布】")
    param_counts = df_results['param'].value_counts()
    for param, count in param_counts.items():
        pct = count / len(df_results)
        print(f"  {param}: {count}只 ({pct:.1%})")

    # 高收益股票
    print("\n【收益TOP 5】")
    top5 = df_results.nlargest(5, 'return_pct')
    for _, row in top5.iterrows():
        print(f"  {row['symbol']}: {row['return_pct']:.1f}% (胜率{row['win_rate']:.1%}, {row['param']})")

    # 高胜率股票
    print("\n【胜率TOP 5】")
    top5_wr = df_results.nlargest(5, 'win_rate')
    for _, row in top5_wr.iterrows():
        print(f"  {row['symbol']}: {row['win_rate']:.1%} (收益{row['return_pct']:.1f}%, {row['param']})")

    # 参数优化建议
    print("\n【参数优化建议】")

    # 按参数分组统计
    for param in ['保守', '标准', '激进']:
        subset = df_results[df_results['param'] == param]
        if len(subset) > 0:
            print(f"\n  {param}参数:")
            print(f"    适用股票: {len(subset)}只")
            print(f"    平均胜率: {subset['win_rate'].mean():.1%}")
            print(f"    平均收益: {subset['return_pct'].mean():.1f}%")
            print("    适用场景: ", end="")
            if param == '保守':
                print("高波动股票、风险控制优先")
            elif param == '激进':
                print("趋势明显、希望多交易")
            else:
                print("平衡型、通用场景")

print("\n" + "="*80)
print("✅ 全量回测完成!")
print("="*80)

manager.close()
