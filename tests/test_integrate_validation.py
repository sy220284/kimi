#!/usr/bin/env python3
"""
集成验证测试 - 对比不同参数配置的回测效果
测试内容:
1. 基础配置 (无共振)
2. 共振分析 (min_resonance_score=0.3)
3. 自适应参数模式
4. 不同均线周期 (60/120/200日)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import json

from src.data import get_stock_data
from src.analysis.wave import UnifiedWaveAnalyzer
from src.analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

# 测试股票 (代表性样本)
TEST_STOCKS = [
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
    ('600600', '青岛啤酒'),
    ('300750', '宁德时代'),
]

# 测试周期
START_DATE = '2023-01-01'
END_DATE = '2026-03-16'

# 测试配置
CONFIGS = [
    {
        'name': '基础配置',
        'analyzerparams': {
            'use_resonance': False,
            'use_adaptive_params': False,
            'trend_ma_period': 200,
            'min_confidence': 0.5,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 200,
        }
    },
    {
        'name': '共振分析(低阈值)',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.2,
            'use_adaptive_params': False,
            'trend_ma_period': 200,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 200,
        }
    },
    {
        'name': '共振分析(标准)',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.3,
            'use_adaptive_params': False,
            'trend_ma_period': 200,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 200,
        }
    },
    {
        'name': '共振分析(严格)',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.5,
            'use_adaptive_params': False,
            'trend_ma_period': 200,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 200,
        }
    },
    {
        'name': '自适应参数',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.3,
            'use_adaptive_params': True,
            'trend_ma_period': 200,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 200,
        }
    },
    {
        'name': '60日均线',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.3,
            'use_adaptive_params': False,
            'trend_ma_period': 60,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 60,
        }
    },
    {
        'name': '120日均线',
        'analyzerparams': {
            'use_resonance': True,
            'min_resonance_score': 0.3,
            'use_adaptive_params': False,
            'trend_ma_period': 120,
        },
        'strategyparams': {
            'use_trend_filter': True,
            'trend_ma_period': 120,
        }
    },
]


def run_single_test(symbol, name, config):
    """运行单股票单配置测试"""
    print(f"  测试 {symbol} {name}...", end=' ')
    
    try:
        # 获取数据
        df = get_stock_data(symbol, START_DATE, END_DATE)
        if df is None or len(df) < 100:
            print("数据不足")
            return None
        
        # 创建分析器和策略
        analyzer = UnifiedWaveAnalyzer(**config['analyzerparams'])
        strategy = WaveStrategy(**config['strategyparams'])
        
        # 创建回测器
        backtester = WaveBacktester(analyzer)
        backtester.strategy = strategy
        
        # 运行回测
        result = backtester.run(symbol, df, reanalyze_every=5)
        
        # 统计信号类型分布
        signals_by_type = {'C': 0, '2': 0, '4': 0}
        for trade in result.trades:
            if hasattr(trade, 'entry_wave') and trade.entry_wave:
                wave = trade.entry_wave
                if wave in signals_by_type:
                    signals_by_type[wave] += 1
        
        print(f"✓ 交易{result.total_trades}次 胜率{result.win_rate:.1%} 收益{result.total_return_pct:+.2f}%")
        
        return {
            'symbol': symbol,
            'name': name,
            'config_name': config['name'],
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'return_pct': result.total_return_pct,
            'max_drawdown': result.max_drawdown_pct,
            'sharpe': result.sharpe_ratio,
            'signals_C': signals_by_type['C'],
            'signals_2': signals_by_type['2'],
            'signals_4': signals_by_type['4'],
        }
        
    except Exception as e:
        print(f"✗ 错误: {str(e)[:50]}")
        return None


def main():
    print("=" * 80)
    print("集成验证测试 - 参数配置对比")
    print("=" * 80)
    print(f"测试股票: {len(TEST_STOCKS)}只")
    print(f"测试周期: {START_DATE} ~ {END_DATE}")
    print(f"配置方案: {len(CONFIGS)}种")
    print("=" * 80)
    
    all_results = []
    
    for symbol, name in TEST_STOCKS:
        print(f"\n📊 {symbol} {name}")
        print("-" * 60)
        
        for config in CONFIGS:
            result = run_single_test(symbol, name, config)
            if result:
                all_results.append(result)
    
    # 汇总分析
    print("\n" + "=" * 80)
    print("汇总分析")
    print("=" * 80)
    
    results_df = pd.DataFrame(all_results)
    
    # 按配置分组统计
    summary = results_df.groupby('config_name').agg({
        'trades': 'mean',
        'win_rate': 'mean',
        'return_pct': 'mean',
        'max_drawdown': 'mean',
        'sharpe': 'mean',
        'signals_C': 'sum',
        'signals_2': 'sum',
        'signals_4': 'sum',
    }).round(2)
    
    print("\n📈 各配置平均表现:")
    print(summary.to_string())
    
    # 按股票分组统计
    print("\n📈 各股票最佳配置:")
    for symbol in results_df['symbol'].unique():
        stock_results = results_df[results_df['symbol'] == symbol]
        best = stock_results.loc[stock_results['return_pct'].idxmax()]
        print(f"  {symbol}: {best['config_name']} (收益{best['return_pct']:+.2f}%, 胜率{best['win_rate']:.1%})")
    
    # 保存结果
    output_file = 'tests/results/integrate_validation.json'
    Path(output_file).parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 详细结果已保存: {output_file}")
    print("=" * 80)


if __name__ == '__main__':
    main()
