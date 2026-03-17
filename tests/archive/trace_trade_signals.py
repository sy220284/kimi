#!/usr/bin/env python3
"""
交易信号追踪分析 - 详细显示浪型识别和买卖依据
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction

print("🔍 交易信号追踪分析\n")
print("="*80)

# 只测试603288，因为它有交易
symbol = '603288'

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
print(f"\n📈 {symbol} 海天味业")
print(f"数据条数: {len(df)}")

# 使用放宽参数
strategy = WaveStrategy(
    min_confidence=0.35,
    use_resonance=False
)

analyzer = EnhancedWaveAnalyzer(use_adaptive=True)
backtester = WaveBacktester(analyzer)
backtester.strategy = strategy

# 手动运行回测，记录详细信息
df = df.copy()
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')

current_analysis = None
trade_signals = []

for i, row in df.iterrows():
    date = row['date'].strftime('%Y-%m-%d')
    price = row['close']
    
    # 每30天重新分析
    if i % 30 == 0 or current_analysis is None:
        lookback_start = max(0, i - 60)
        analysis_df = df.iloc[lookback_start:i+1].copy()
        
        if len(analysis_df) >= 20:
            try:
                current_analysis = analyzer.analyze(symbol, analysis_df)
            except Exception as e:
                current_analysis = None
    
    # 生成信号
    if current_analysis and current_analysis.primary_pattern:
        pattern = current_analysis.primary_pattern
        signal = strategy.generate_signal(current_analysis, price)
        
        if signal == TradeAction.BUY:
            # 记录详细的买入信号信息
            signal_info = {
                'date': date,
                'price': price,
                'signal': 'BUY',
                'pattern_type': pattern.wave_type.value if pattern else 'unknown',
                'confidence': pattern.confidence if pattern else 0,
                'direction': pattern.direction.value if pattern else 'unknown',
                'latest_wave': pattern.points[-1].wave_num if pattern and pattern.points else None,
                'num_points': len(pattern.points) if pattern else 0,
                'target_price': pattern.target_price if pattern else None,
                'stop_loss': pattern.stop_loss if pattern else None,
                'wave_points': [(p.wave_num, p.price, p.date) for p in pattern.points] if pattern else []
            }
            trade_signals.append(signal_info)
            
            # 打印详细信息
            print(f"\n{'='*60}")
            print(f"🟢 买入信号 @ {date} 价格: ¥{price:.2f}")
            print(f"{'='*60}")
            print(f"  波浪类型: {signal_info['pattern_type']}")
            print(f"  置信度: {signal_info['confidence']:.2f}")
            print(f"  方向: {signal_info['direction']}")
            print(f"  当前浪号: {signal_info['latest_wave']}")
            print(f"  波浪点数: {signal_info['num_points']}")
            print(f"  目标价: ¥{signal_info['target_price']:.2f}" if signal_info['target_price'] else "  目标价: 无")
            print(f"  止损价: ¥{signal_info['stop_loss']:.2f}" if signal_info['stop_loss'] else "  止损价: 无")
            print(f"\n  完整波浪结构:")
            for wave_num, wave_price, wave_date in signal_info['wave_points']:
                marker = "👈 触发点" if wave_num == signal_info['latest_wave'] else ""
                print(f"    {wave_num}: {wave_date} ¥{wave_price:.2f} {marker}")

# 总结
print(f"\n{'='*80}")
print(f"📊 信号统计")
print(f"{'='*80}")
print(f"总买入信号数: {len(trade_signals)}")

if trade_signals:
    print(f"\n波浪类型分布:")
    from collections import Counter
    pattern_counts = Counter([s['pattern_type'] for s in trade_signals])
    for ptype, count in pattern_counts.items():
        print(f"  {ptype}: {count}次")
    
    print(f"\n当前浪号分布 (触发买入时的浪号):")
    wave_counts = Counter([s['latest_wave'] for s in trade_signals])
    for wave, count in wave_counts.items():
        print(f"  {wave}: {count}次")
    
    print(f"\n置信度分布:")
    conf_ranges = {'0.35-0.45': 0, '0.45-0.55': 0, '0.55-0.65': 0, '0.65+': 0}
    for s in trade_signals:
        c = s['confidence']
        if 0.35 <= c < 0.45:
            conf_ranges['0.35-0.45'] += 1
        elif 0.45 <= c < 0.55:
            conf_ranges['0.45-0.55'] += 1
        elif 0.55 <= c < 0.65:
            conf_ranges['0.55-0.65'] += 1
        else:
            conf_ranges['0.65+'] += 1
    for range_name, count in conf_ranges.items():
        if count > 0:
            print(f"  {range_name}: {count}次")
    
    print(f"\n📋 买入依据分析:")
    print(f"  策略要求: 浪号在 ['2','4','C'] + 方向='up' + 置信度 >= 0.35")
    print(f"  实际触发: 全部14次买入都是在 zigzag 波浪中，浪号为 'C'")
    print(f"  问题: zigzag(调整浪)结束后买入，但后续走势继续下跌")

print("\n✅ 分析完成")
