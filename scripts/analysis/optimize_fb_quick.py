#!/usr/bin/env python3
"""
食品饮料板块波浪分析参数优化 - 轻量级快速版
"""


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np

from analysis.backtest.wave_backtester import WaveBacktester
from analysis.wave import EnhancedWaveAnalyzer
from data import get_stock_data

print("="*70)
print("🍺 食品饮料板块参数优化 (轻量版)")
print("="*70)

# 测试股票
test_stocks = ['600519', '000858', '600887']

# 预设几组典型参数组合进行测试
param_candidates = [
    # 保守型 - 高门槛，少交易
    {
        'name': '保守型',
        'atr_mult': 0.8,
        'confidence_threshold': 0.6,
        'min_change_pct': 3.0,
        'peak_window': 3,
        'stop_loss_pct': 0.04,
        'take_profit_pct': 0.12
    },
    # 平衡型
    {
        'name': '平衡型',
        'atr_mult': 0.5,
        'confidence_threshold': 0.5,
        'min_change_pct': 2.0,
        'peak_window': 3,
        'stop_loss_pct': 0.05,
        'take_profit_pct': 0.15
    },
    # 积极型 - 低门槛，多交易
    {
        'name': '积极型',
        'atr_mult': 0.3,
        'confidence_threshold': 0.4,
        'min_change_pct': 1.5,
        'peak_window': 2,
        'stop_loss_pct': 0.06,
        'take_profit_pct': 0.18
    },
    # 超敏感型
    {
        'name': '超敏感型',
        'atr_mult': 0.2,
        'confidence_threshold': 0.35,
        'min_change_pct': 1.0,
        'peak_window': 2,
        'stop_loss_pct': 0.07,
        'take_profit_pct': 0.20
    }
]

results = []

for params in param_candidates:
    print(f"\n{'='*70}")
    print(f"📊 测试参数: {params['name']}")
    print(f"{'='*70}")

    stock_results = []

    for symbol in test_stocks:
        try:
            df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

            analyzer = EnhancedWaveAnalyzer(
                use_adaptive=False,
                atr_mult=params['atr_mult'],
                confidence_threshold=params['confidence_threshold'],
                min_change_pct=params['min_change_pct'],
                peak_window=params['peak_window']
            )

            backtester = WaveBacktester(analyzer)
            backtester.strategy.min_confidence = params['confidence_threshold']
            backtester.strategy.stop_loss_pct = params['stop_loss_pct']
            backtester.strategy.take_profit_pct = params['take_profit_pct']
            backtester.strategy.use_resonance = False  # 关闭共振验证

            result = backtester.run(symbol, df, reanalyze_every=30)

            stock_results.append({
                'symbol': symbol,
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'max_dd': result.max_drawdown_pct,
                'sharpe': result.sharpe_ratio
            })

        except Exception as e:
            print(f"  {symbol}: 失败 - {e}")

    # 计算平均表现
    if stock_results:
        avg_trades = np.mean([r['trades'] for r in stock_results])
        avg_win_rate = np.mean([r['win_rate'] for r in stock_results])
        avg_return = np.mean([r['return'] for r in stock_results])
        avg_sharpe = np.mean([r['sharpe'] for r in stock_results])

        results.append({
            'name': params['name'],
            'params': params,
            'avg_trades': avg_trades,
            'avg_win_rate': avg_win_rate,
            'avg_return': avg_return,
            'avg_sharpe': avg_sharpe,
            'details': stock_results
        })

        print(f"\n  平均交易次数: {avg_trades:.1f}")
        print(f"  平均胜率: {avg_win_rate:.1%}")
        print(f"  平均收益: {avg_return:.1f}%")
        print(f"  平均Sharpe: {avg_sharpe:.2f}")

# 找出最佳参数
print("\n" + "="*70)
print("🏆 参数对比排名")
print("="*70)

# 按综合得分排序 (胜率40% + 收益40% + sharpe20%)
for r in results:
    r['score'] = r['avg_win_rate']*0.4 + (r['avg_return']/100)*0.4 + min(r['avg_sharpe'],3)/3*0.2

results.sort(key=lambda x: x['score'], reverse=True)

for i, r in enumerate(results, 1):
    print(f"\n#{i} {r['name']} (综合得分: {r['score']:.3f})")
    print(f"   交易次数: {r['avg_trades']:.1f} | 胜率: {r['avg_win_rate']:.1%} | 收益: {r['avg_return']:.1f}% | Sharpe: {r['avg_sharpe']:.2f}")
    print(f"   关键参数: ATR={r['params']['atr_mult']}, 置信度={r['params']['confidence_threshold']}, 变化%={r['params']['min_change_pct']}")

# 输出最佳参数详情
if results:
    best = results[0]
    print("\n" + "="*70)
    print(f"✅ 推荐参数配置: {best['name']}")
    print("="*70)
    print(f"""
波浪检测参数:
  - ATR倍数: {best['params']['atr_mult']}
  - 置信度门槛: {best['params']['confidence_threshold']}
  - 最小变化%: {best['params']['min_change_pct']}%
  - 峰值窗口: {best['params']['peak_window']}

交易参数:
  - 止损比例: {best['params']['stop_loss_pct']:.1%}
  - 止盈比例: {best['params']['take_profit_pct']:.1%}

预期表现:
  - 平均每只股票交易{best['avg_trades']:.0f}次
  - 胜率约{best['avg_win_rate']:.1%}
  - 总收益约{best['avg_return']:.1f}%
""")

print("\n" + "="*70)
print("完成!")
print("="*70)
