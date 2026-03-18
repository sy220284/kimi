#!/usr/bin/env python3
"""
测试增强版浪型检测器
"""
import sys
sys.path.insert(0, 'src')

from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy

print("🔧 增强版浪型检测器测试\n")
print("="*80)

# 测试茅台
test_stocks = [
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
]

for symbol, name in test_stocks:
    print(f"\n📈 {symbol} {name}")
    print("-"*60)
    
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    print(f"数据: {len(df)}条")
    
    # 测试增强版检测
    analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
    
    # 分段测试浪型识别
    test_segments = [
        (0, 60, '2023年初'),
        (200, 260, '2023年中'),
        (400, 460, '2024年初'),
        (600, 660, '2024年底'),
        (712, 772, '最近60天')
    ]
    
    print("\n分段浪型识别:")
    for start, end, label in test_segments:
        segment_df = df.iloc[start:end].copy()
        result = analyzer.analyze(symbol, segment_df)
        
        if result and result.primary_pattern:
            p = result.primary_pattern
            latest_wave = p.points[-1].wave_num if p.points else None
            print(f"  {label}: {p.wave_type.value:10s} 浪{str(latest_wave):3s} 置信度{p.confidence:.2f} 方向{p.direction.value}")
        else:
            print(f"  {label}: 未识别")
    
    # 运行完整回测
    print("\n回测结果:")
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
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    print(f"  交易: {result.totaltrades}次 | 胜率: {result.win_rate:.1%} | 收益: {result.total_return_pct:+.1f}%")
    
    if result.trades:
        from collections import Counter
        wave_dist = Counter([t.entry_wave for t in result.trades if t.entry_wave])
        print("\n  买入浪号分布:")
        for wave, count in sorted(wave_dist.items(), key=lambda x: str(x[0])):
            print(f"    浪{wave}: {count}次")

print("\n✅ 测试完成")
