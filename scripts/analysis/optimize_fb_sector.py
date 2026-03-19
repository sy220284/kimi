#!/usr/bin/env python3
"""
食品饮料板块波浪分析参数优化
使用历史数据优化波浪检测和交易策略参数
"""
import sys

sys.path.insert(0, 'src')

from analysis.backtest.wave_backtester import WaveBacktester
from analysis.optimization.param_optimizer import run_optimization
from analysis.wave import EnhancedWaveAnalyzer
from data import get_stock_data

print("="*70)
print("🍺 食品饮料板块波浪分析参数优化")
print("="*70)

# 食品饮料板块代表性股票（白酒+乳制品+调味品）
test_stocks = [
    '600519',  # 茅台
    '000858',  # 五粮液
    '000568',  # 泸州老窖
    '600809',  # 山西汾酒
    '600887',  # 伊利股份
    '603288',  # 海天味业
    '600600',  # 青岛啤酒
]

print(f"\n📊 优化股票池: {len(test_stocks)} 只")
print(f"股票: {', '.join(test_stocks)}")

# 数据加载函数
def load_data(symbol):
    """加载股票数据"""
    try:
        df = get_stock_data(symbol, '2020-01-01', '2026-03-16')
        print(f"  {symbol}: {len(df)} 条数据")
        return df
    except Exception as e:
        print(f"  {symbol}: 加载失败 - {e}")
        return None

# 运行优化
print("\n🔧 开始参数优化...")
print("搜索策略: 随机搜索")
print(f"迭代次数: 每只股票20次 (总计约{len(test_stocks)*20}次回测)")
print("-"*70)

try:
    best_params, signal_filter = run_optimization(
        symbols=test_stocks,
        data_loader=load_data,
        analyzer_class=EnhancedWaveAnalyzer,
        backtester_class=WaveBacktester,
        n_iterations=20,
        save_path='data/optimization/food_beverage_params.json'
    )

    print("\n" + "="*70)
    print("✅ 优化完成!")
    print("="*70)

    print("\n🏆 最优参数配置:")
    print("  波浪检测参数:")
    print(f"    - ATR倍数: {best_params.atr_mult:.3f}")
    print(f"    - 置信度门槛: {best_params.confidence_threshold:.2f}")
    print(f"    - 最小变化%: {best_params.min_change_pct:.2f}%")
    print(f"    - 峰值窗口: {best_params.peak_window}")
    print(f"    - 最小距离: {best_params.min_dist}")

    print("\n  共振参数:")
    print(f"    - 共振强度门槛: {best_params.resonance_min_strength:.2f}")
    print(f"    - MACD权重: {best_params.macd_weight:.2f}")
    print(f"    - RSI权重: {best_params.rsi_weight:.2f}")
    print(f"    - Volume权重: {best_params.volume_weight:.2f}")
    print(f"    - Wave权重: {best_params.wave_weight:.2f}")

    print("\n  交易参数:")
    print(f"    - 止损比例: {best_params.stop_loss_pct:.1%}")
    print(f"    - 止盈比例: {best_params.take_profit_pct:.1%}")
    print(f"    - 仓位大小: {best_params.position_size:.1%}")

    # 使用最优参数进行一次完整回测
    print("\n" + "-"*70)
    print("🧪 使用最优参数进行验证回测...")
    print("-"*70)

    for symbol in test_stocks[:3]:  # 只测前3只
        df = load_data(symbol)
        if df is not None:
            analyzer = EnhancedWaveAnalyzer(
                atr_mult=best_params.atr_mult,
                confidence_threshold=best_params.confidence_threshold,
                min_change_pct=best_params.min_change_pct,
                peak_window=best_params.peak_window,
                min_dist=best_params.min_dist
            )

            backtester = WaveBacktester(analyzer)
            backtester.strategy.min_confidence = best_params.confidence_threshold
            backtester.strategy.stop_loss_pct = best_params.stop_loss_pct
            backtester.strategy.take_profit_pct = best_params.take_profit_pct
            backtester.strategy.position_size = best_params.position_size

            result = backtester.run(symbol, df, reanalyze_every=10)

            print(f"\n  {symbol} 回测结果:")
            print(f"    交易次数: {result.total_trades}")
            print(f"    胜率: {result.win_rate:.1%}")
            print(f"    总收益: {result.total_return_pct:.2f}%")
            print(f"    最大回撤: {result.max_drawdown_pct:.2f}%")
            print(f"    Sharpe: {result.sharpe_ratio:.2f}")

    print("\n💾 优化结果已保存到: data/optimization/food_beverage_params.json")

except Exception as e:
    print(f"\n❌ 优化失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("完成!")
print("="*70)
