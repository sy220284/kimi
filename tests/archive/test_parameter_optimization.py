#!/usr/bin/env python3
"""
参数优化测试脚本 - 演示完整优化流程
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester
from analysis.optimization.param_optimizer import (
    ParameterOptimizer, ParameterSet, SignalFilter, run_optimization
)
from analysis.optimization.adaptive_backtest import AdaptiveBacktester, BacktestAnalyzer

print("="*80)
print("🔧 回测参数优化系统测试")
print("="*80)

# 测试股票列表
TEST_SYMBOLS = ['002184', '600138', '600556']

def data_loader(symbol: str) -> pd.DataFrame:
    """数据加载包装器"""
    try:
        return get_stock_data(symbol, '2024-01-01', '2025-01-01')
    except Exception as e:
        print(f"加载 {symbol} 失败: {e}")
        return None

# ========================================
# 方案A: 简化版测试 (快速)
# ========================================
print("\n" + "="*80)
print("方案A: 单股票参数调优测试")
print("="*80)

try:
    symbol = '002184'
    print(f"\n📊 加载 {symbol} 数据...")
    df = data_loader(symbol)
    
    if df is not None and len(df) > 100:
        print(f"✅ 获取 {len(df)} 条数据")
        
        # 测试不同参数组合
        test_params = [
            ParameterSet(atr_mult=0.5, confidence_threshold=0.5, min_change_pct=2.0),
            ParameterSet(atr_mult=0.7, confidence_threshold=0.6, min_change_pct=1.5),
            ParameterSet(atr_mult=0.4, confidence_threshold=0.4, min_change_pct=2.5),
        ]
        
        optimizer = ParameterOptimizer(EnhancedWaveAnalyzer, WaveBacktester)
        results = []
        
        for i, params in enumerate(test_params, 1):
            print(f"\n测试参数组 {i}/{len(test_params)}: {params.get_id()}")
            print(f"  ATR={params.atr_mult}, 置信度={params.confidence_threshold}, 变化率={params.min_change_pct}%")
            
            result = optimizer._single_backtest(params, symbol, df, '', '')
            if result:
                results.append(result)
                print(f"  ✅ 得分={result.composite_score:.3f}, 胜率={result.win_rate:.1%}, 收益={result.total_return:.1f}%")
        
        # 排序找出最佳
        if results:
            results.sort(key=lambda x: x.composite_score, reverse=True)
            best = results[0]
            
            print(f"\n🏆 最优参数: {best.params.get_id()}")
            print(f"   综合得分: {best.composite_score:.3f}")
            print(f"   胜率: {best.win_rate:.1%}")
            print(f"   收益: {best.total_return:.1f}%")
            print(f"   回撤: {best.max_drawdown:.1f}%")
            
            # 创建信号过滤器
            filter = SignalFilter(results)
            print(f"\n📋 信号过滤规则:")
            print(f"   最小置信度: {filter.filters['min_confidence']}")
            print(f"   最小共振强度: {filter.filters['min_resonance_strength']}")
    else:
        print("❌ 数据不足")
        
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# ========================================
# 方案B: 自适应回测测试
# ========================================
print("\n" + "="*80)
print("方案B: 自适应回测测试")
print("="*80)

try:
    symbol = '002184'
    df = data_loader(symbol)
    
    if df is not None and len(df) > 200:
        print(f"\n运行自适应回测...")
        
        adaptive_bt = AdaptiveBacktester(
            initial_params=ParameterSet(),
            optimization_interval=60,
            lookback_window=120
        )
        
        report = adaptive_bt.run_adaptive_backtest(symbol, df, enable_optimization=True)
        
        # 生成改进建议
        if 'error' not in report:
            print(f"\n💡 系统改进建议:")
            
            # 模拟分析交易模式
            mock_result = {
                'win_rate': report['win_rate'],
                'max_drawdown_pct': report.get('max_drawdown', 10),
                'profit_factor': 1.2,
                'total_trades': report['total_trades']
            }
            
            suggestions = BacktestAnalyzer.generate_improvement_suggestions(mock_result, {})
            for s in suggestions:
                print(f"   • {s}")
    
except Exception as e:
    print(f"❌ 自适应回测失败: {e}")
    import traceback
    traceback.print_exc()

# ========================================
# 总结
# ========================================
print("\n" + "="*80)
print("📊 优化系统能力总结")
print("="*80)
print("""
✅ 已实现功能:

1. 参数优化器 (param_optimizer.py)
   • 定义了12个可调参数
   • 随机搜索 + 综合评分
   • 训练集/验证集分割防过拟合
   • 最优参数持久化

2. 自适应回测器 (adaptive_backtest.py)
   • 滑动窗口回测
   • 根据胜率动态调整参数
   • 记录参数演变历史
   • 识别最佳参数配置

3. 信号过滤器 (SignalFilter)
   • 基于回测结果动态过滤
   • 多维度信号验证
   • 仓位大小调整建议

4. 回测分析器 (BacktestAnalyzer)
   • 交易模式分析
   • 改进建议生成
   • 最佳时段识别

📈 优化流程:
   加载数据 → 参数搜索 → 回测评分 → 验证集测试 → 信号过滤 → 改进建议

🎯 下一步:
   运行完整优化: python tests/test_full_optimization.py
""")
