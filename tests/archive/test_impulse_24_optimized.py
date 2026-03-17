#!/usr/bin/env python3
"""
推动浪2/4浪识别优化测试 - 简化版
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from data import get_stock_data
from analysis.wave.elliott_wave import ElliottWaveAnalyzer, WavePoint, WaveType


def find_impulse_buy_signals(df: pd.DataFrame, symbol: str):
    """
    寻找推动浪2浪和4浪买入信号
    """
    print(f"\n{'='*70}")
    print(f"📊 {symbol} - 推动浪2/4浪买入信号检测")
    print(f"{'='*70}")
    
    prices = df['close'].values
    dates = df['date'].values
    
    # 找极值点
    window = 3
    peaks = []
    troughs = []
    
    for i in range(window, len(prices) - window):
        if all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
           all(prices[i] >= prices[i+j] for j in range(1, window+1)):
            peaks.append((i, prices[i], dates[i]))
        elif all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
             all(prices[i] <= prices[i+j] for j in range(1, window+1)):
            troughs.append((i, prices[i], dates[i]))
    
    pivots = sorted(peaks + troughs, key=lambda x: x[0])
    
    print(f"找到 {len(pivots)} 个极值点")
    
    # 寻找12345模式
    signals = []
    
    for i in range(len(pivots) - 4):
        p1 = pivots[i]
        p2 = pivots[i+1]
        p3 = pivots[i+2]
        p4 = pivots[i+3]
        p5 = pivots[i+4]
        
        # 检查推动浪规则
        wave1 = abs(p2[1] - p1[1])
        wave2 = abs(p3[1] - p2[1])
        wave3 = abs(p4[1] - p3[1])
        wave4 = abs(p5[1] - p4[1])
        
        # 方向
        direction_up = p2[1] > p1[1]
        
        # 规则1: 浪2回撤不超过浪1的61.8%
        w2_retracement = wave2 / wave1 if wave1 > 0 else 1
        if w2_retracement > 0.618:
            continue
        
        # 规则2: 浪3应该比浪1长
        if wave3 < wave1 * 0.8:
            continue
        
        # 规则3: 浪4回撤不超过浪3的50%
        w4_retracement = wave4 / wave3 if wave3 > 0 else 1
        if w4_retracement > 0.5:
            continue
        
        # 找到有效的12345
        confidence = 0.5
        if wave3 > wave1 * 1.5:
            confidence += 0.2  # 浪3强劲
        if w2_retracement < 0.5:
            confidence += 0.1  # 浪2回撤浅
        
        signals.append({
            'type': 'complete_12345',
            'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4, 'p5': p5,
            'direction': 'up' if direction_up else 'down',
            'confidence': min(confidence, 0.9),
            'wave2_ret': w2_retracement,
            'wave4_ret': w4_retracement
        })
    
    # 寻找未完成1234（当前在4浪）
    for i in range(len(pivots) - 3):
        p1 = pivots[i]
        p2 = pivots[i+1]
        p3 = pivots[i+2]
        p4 = pivots[i+3]
        
        wave1 = abs(p2[1] - p1[1])
        wave2 = abs(p3[1] - p2[1])
        wave3 = abs(p4[1] - p3[1])
        
        direction_up = p2[1] > p1[1]
        
        # 检查浪2回撤
        w2_retracement = wave2 / wave1 if wave1 > 0 else 1
        if w2_retracement > 0.618:
            continue
        
        # 检查浪3
        if wave3 < wave1 * 0.8:
            continue
        
        # 当前在浪4，检查回撤是否合理
        current_from_p3 = abs(prices[-1] - p3[1])
        w4_so_far = current_from_p3 / wave3 if wave3 > 0 else 1
        
        if w4_so_far > 0.5:
            continue
        
        signals.append({
            'type': 'wave4_entry',
            'p1': p1, 'p2': p2, 'p3': p3, 'p4': p4,
            'current_price': prices[-1],
            'direction': 'up' if direction_up else 'down',
            'confidence': 0.6,
            'entry_wave': '4',
            'target': p4[1] + wave1 if direction_up else p4[1] - wave1
        })
    
    # 打印结果
    if signals:
        print(f"\n找到 {len(signals)} 个推动浪信号:")
        
        for j, sig in enumerate(signals[:5], 1):
            print(f"\n  信号 #{j}:")
            if sig['type'] == 'wave4_entry':
                print(f"    🟢 4浪买入点!")
                print(f"    1浪: {sig['p1'][2]} ¥{sig['p1'][1]:.2f}")
                print(f"    2浪: {sig['p2'][2]} ¥{sig['p2'][1]:.2f} (回撤 {sig.get('wave2_ret', 0):.1%})")
                print(f"    3浪: {sig['p3'][2]} ¥{sig['p3'][1]:.2f}")
                print(f"    4浪: {sig['p4'][2]} ¥{sig['p4'][1]:.2f}")
                print(f"    当前: ¥{sig['current_price']:.2f}")
                print(f"    方向: {sig['direction']}")
                print(f"    目标价: ¥{sig['target']:.2f}")
                print(f"    置信度: {sig['confidence']:.2f}")
            else:
                print(f"    完整12345浪型")
                print(f"    1-2浪: {sig['p1'][2]} → {sig['p2'][2]} (回撤 {sig['wave2_ret']:.1%})")
                print(f"    3-4浪: {sig['p3'][2]} → {sig['p4'][2]} (回撤 {sig['wave4_ret']:.1%})")
                print(f"    5浪结束: {sig['p5'][2]} ¥{sig['p5'][1]:.2f}")
    else:
        print("\n  未找到推动浪信号")
    
    return signals


# 测试
print("🧪 推动浪2/4浪优化测试")
print("="*70)

test_stocks = [
    ('600519', '茅台'),
    ('000858', '五粮液'),
    ('300750', '宁德时代'),
    ('600036', '招商银行'),
    ('600600', '青岛啤酒'),
]

all_signals = {'2': 0, '4': 0, 'complete': 0}

for symbol, name in test_stocks:
    try:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        signals = find_impulse_buy_signals(df, f"{symbol} {name}")
        
        for sig in signals:
            if sig['type'] == 'wave4_entry':
                all_signals['4'] += 1
            elif sig['type'] == 'complete_12345':
                all_signals['complete'] += 1
                
    except Exception as e:
        print(f"{symbol} 错误: {e}")

print(f"\n{'='*70}")
print("📊 统计:")
print(f"  4浪买入信号: {all_signals['4']} 个")
print(f"  完整12345: {all_signals['complete']} 个")
print(f"\n✅ 测试完成")
