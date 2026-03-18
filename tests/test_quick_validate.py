#!/usr/bin/env python3
"""
快速集成验证 - 单股票单配置测试
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import get_stock_data
from src.analysis.wave import UnifiedWaveAnalyzer
from src.analysis.backtest.wave_backtester import WaveBacktester

# 单股票测试
SYMBOL = '600519'
NAME = '贵州茅台'
START = '2024-01-01'
END = '2026-03-16'

print("=" * 70)
print("快速集成验证")
print("=" * 70)
print(f"\n测试股票: {SYMBOL} {NAME}")
print(f"测试周期: {START} ~ {END}")

# 获取数据
print("\n📥 获取数据...")
df = get_stock_data(SYMBOL, START, END)
print(f"✓ 获取 {len(df)} 条数据")

# 测试1: 基础分析器
print("\n" + "-" * 70)
print("测试1: 基础配置 (无共振)")
print("-" * 70)

analyzer1 = UnifiedWaveAnalyzer(
    use_resonance=False,
    use_adaptive_params=False,
    trend_ma_period=200
)

signals1 = analyzer1.detect(df, mode='all')
print(f"检测信号数: {len(signals1)}")
if signals1:
    for sig in signals1[:3]:
        print(f"  - {sig.entry_type.value}浪 价格¥{sig.entry_price:.2f} 置信度{sig.confidence:.2f}")

# 测试2: 共振分析
print("\n" + "-" * 70)
print("测试2: 共振分析 (min_resonance_score=0.3)")
print("-" * 70)

analyzer2 = UnifiedWaveAnalyzer(
    use_resonance=True,
    min_resonance_score=0.3,
    use_adaptive_params=False,
    trend_ma_period=200
)

signals2 = analyzer2.detect(df, mode='all')
print(f"检测信号数: {len(signals2)}")
if signals2:
    for sig in signals2[:3]:
        res_info = f" 共振{sig.resonance_score:.2f}" if hasattr(sig, 'resonance_score') else ""
        print(f"  - {sig.entry_type.value}浪 价格¥{sig.entry_price:.2f} 置信度{sig.confidence:.2f}{res_info}")

# 测试3: 回测框架
print("\n" + "-" * 70)
print("测试3: 回测框架集成")
print("-" * 70)

backtester = WaveBacktester(analyzer2)
print("✓ WaveBacktester 初始化成功")
print(f"✓ 策略200日均线: {backtester.strategy.trend_ma_period}日")

result = backtester.run(SYMBOL, df, reanalyze_every=10)

print("\n📊 回测结果:")
print(f"  交易次数: {result.total_trades}")
print(f"  胜率: {result.win_rate:.1%}")
print(f"  总收益: {result.total_return_pct:+.2f}%")
print(f"  最大回撤: {result.max_drawdown_pct:.2f}%")
print(f"  夏普比率: {result.sharpe_ratio:.2f}")

# 统计信号类型
if result.trades:
    waves = {}
    for t in result.trades:
        w = t.entry_wave or 'unknown'
        waves[w] = waves.get(w, 0) + 1
    print(f"\n  浪型分布: {waves}")

print("\n" + "=" * 70)
print("✅ 快速验证完成")
print("=" * 70)
