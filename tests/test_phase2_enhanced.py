#!/usr/bin/env python3
"""
Phase 2 测试 - 增强版波浪分析
测试: 完整形态库 + 自适应参数 + 多指标共振
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import get_stock_data
from analysis.wave.enhanced_analyzer import EnhancedWaveAnalyzer, analyze_stock_full
from analysis.wave.adaptiveparams import get_adaptiveparams

print("="*80)
print("🔬 Phase 2 测试 - 增强版波浪分析")
print("="*80)

# 测试股票
symbols = [
    ("600138", "中青旅"),
    ("002184", "海得控制"),
    ("600556", "天下秀"),
    ("002358", "森源电气"),
]

analyzer = EnhancedWaveAnalyzer()

for symbol, name in symbols:
    print(f"\n{'='*80}")
    print(f"📊 {name} ({symbol})")
    print('='*80)
    
    try:
        # 获取数据
        df = get_stock_data(symbol, '2024-01-01', '2026-03-16')
        print(f"📈 数据: {len(df)} 条 ({df['date'].min()} ~ {df['date'].max()})")
        
        # 1. 自适应参数测试
        print("\n【1. 自适应参数优化】")
        params = get_adaptiveparams(df, 'day')
        print(f"  ATR周期: {params['atr_period']}")
        print(f"  ATR倍数: {params['atr_mult']:.2f}")
        print(f"  置信度阈值: {params['confidence_threshold']:.2f}")
        
        # 2. 增强版分析
        print("\n【2. 增强版波浪分析】")
        result = analyzer.analyze(symbol, df)
        
        pattern = result.primary_pattern
        print(f"  形态: {pattern.wave_type.value.upper()}")
        print(f"  方向: {'📈 上升' if pattern.direction.value == 'up' else '📉 下降'}")
        print(f"  置信度: {pattern.confidence:.1%}")
        print(f"  市场状态: {result.market_condition}")
        
        # 3. 特殊形态检测
        print("\n【3. 特殊形态检测】")
        if result.triangle_detected:
            print("  🔺 三角形调整")
        if result.wxy_detected:
            print("  📎 WXY联合调整")
        if result.complete_structure.warnings:
            for w in result.complete_structure.warnings:
                print(f"  ⚠️ {w}")
        if not result.triangle_detected and not result.wxy_detected and not result.complete_structure.warnings:
            print("  标准形态")
        
        # 4. 多指标共振
        print("\n【4. 多指标共振分析】")
        if result.resonance:
            res = result.resonance
            print(f"  综合方向: {res.overall_direction.value}")
            print(f"  共振强度: {res.overall_strength:.1%}")
            print(f"  加权得分: {res.weighted_score:+.2f}")
            
            print("\n  各指标信号:")
            for sig in res.signals:
                icon = "📈" if hasattr(sig.direction, 'value') and sig.direction.value == 'bullish' else \
                       "📉" if hasattr(sig.direction, 'value') and sig.direction.value == 'bearish' else "➖"
                print(f"    {icon} {sig.name}: {sig.description[:30]}... (强度{sig.strength:.0%})")
            
            print(f"\n  💡 建议: {res.recommendation}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

# 多时间框架测试
print(f"\n\n{'='*80}")
print("【多时间框架分析示例】")
print('='*80)

try:
    df = get_stock_data('002184', '2023-01-01', '2026-03-16')
    print(f"海得控制 - 完整历史数据: {len(df)} 条")
    
    # 多周期分析
    results = analyze_stock_full('002184', df)
    
    for timeframe, result in results.items():
        if result.primary_pattern.confidence > 0:
            print(f"\n{timeframe.upper()}:")
            print(f"  {result.primary_pattern.wave_type.value} | "
                  f"{'📈' if result.primary_pattern.direction.value == 'up' else '📉'} | "
                  f"置信度 {result.primary_pattern.confidence:.0%} | "
                  f"共振 {result.resonance.overall_strength:.0%}")

except Exception as e:
    print(f"❌ 错误: {e}")

print("\n" + "="*80)
print("Phase 2 测试完成!")
print("="*80)
