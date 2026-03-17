#!/usr/bin/env python3
"""
修复版推动浪检测 - 带调试
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from data import get_stock_data

symbol = '600519'
print(f"🧪 修复版检测 - {symbol}")
print("="*70)

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
df['date'] = pd.to_datetime(df['date'])

prices = df['close'].values
dates = df['date'].values

# 找极值点
window = 3
raw_pivots = []
for i in range(window, len(prices) - window):
    is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
             all(prices[i] >= prices[i+j] for j in range(1, window+1))
    is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1))
    if is_peak:
        raw_pivots.append((i, prices[i], dates[i], 'peak'))
    elif is_trough:
        raw_pivots.append((i, prices[i], dates[i], 'trough'))

# 过滤连续同类型
pivots = [raw_pivots[0]]
for p in raw_pivots[1:]:
    if p[3] != pivots[-1][3]:
        pivots.append(p)

print(f"原始极值点: {len(raw_pivots)} 个")
print(f"过滤后: {len(pivots)} 个")

# 检测推动浪
signals = []
min_wave_pct = 0.015
stats = {'checked': 0, 'structure_ok': 0, 'wave1_ok': 0, 'wave2_ok': 0, 'wave3_ok': 0, 'wave4_ok': 0, 'passed': 0}

for i in range(len(pivots) - 3):
    stats['checked'] += 1
    p1, p2, p3, p4 = pivots[i], pivots[i+1], pivots[i+2], pivots[i+3]
    
    wave1 = abs(p2[1] - p1[1])
    if wave1 < p1[1] * min_wave_pct:
        continue
    stats['wave1_ok'] += 1
    
    direction_up = p2[1] > p1[1]
    
    # 验证推动浪结构
    if direction_up:
        if not (p1[3] == 'trough' and p2[3] == 'peak' and p3[3] == 'trough' and p4[3] == 'peak'):
            continue
        if not (p3[1] > p1[1] and p4[1] > p3[1]):
            continue
    else:
        if not (p1[3] == 'peak' and p2[3] == 'trough' and p3[3] == 'peak' and p4[3] == 'trough'):
            continue
        if not (p3[1] < p1[1] and p4[1] < p3[1]):
            continue
    stats['structure_ok'] += 1
    
    # 波浪幅度计算
    # p1=浪1起点, p2=浪1终点/浪2起点, p3=浪2终点/浪3起点, p4=浪3终点/浪4起点
    wave1_amp = abs(p2[1] - p1[1])  # 浪1幅度
    wave2_amp = abs(p3[1] - p2[1])  # 浪2幅度
    wave3_amp = abs(p4[1] - p3[1])  # 浪3幅度
    
    # 浪2回撤 = 浪2幅度 / 浪1幅度
    w2_ret = wave2_amp / wave1_amp
    if w2_ret > 0.618:
        continue
    stats['wave2_ok'] += 1
    
    # 浪3不能比浪1短太多
    if wave3_amp < wave1_amp * 0.8:
        continue
    stats['wave3_ok'] += 1
    
    # 浪4回撤 = 浪4幅度 / 浪3幅度
    # 但当前p4是浪3终点，我们需要看p4之后的价格来判断浪4回撤
    # 简化: 用当前价格相对于p4的位置来估计浪4
    current_price = prices[-1]
    wave4_amp = abs(current_price - p4[1])
    w4_ret = wave4_amp / wave3_amp if wave3_amp > 0 else 1
    
    # 如果是有效的4浪，当前价格应该回撤但未跌破p3
    if direction_up:
        if current_price >= p4[1]:  # 还没回撤
            continue
        if current_price <= p3[1]:  # 回撤太深，可能不是4浪
            continue
    else:
        if current_price <= p4[1]:  # 还没回撤
            continue
        if current_price >= p3[1]:  # 回撤太深
            continue
    
    if w4_ret > 0.5:
        continue
    stats['wave4_ok'] += 1
    
    stats['passed'] += 1
    
    if direction_up:
        target = p4[1] + wave1
        stop_loss = min(p4[1] * 0.98, p3[1] * 0.99)
    else:
        target = p4[1] - wave1
        stop_loss = max(p4[1] * 1.02, p3[1] * 1.01)
    
    confidence = 0.5
    if 0.3 <= w2_ret <= 0.5:
        confidence += 0.15
    if 0.2 <= w4_ret <= 0.4:
        confidence += 0.15
    
    signals.append({
        'entry_date': pd.Timestamp(p4[2]),
        'entry_price': p4[1],
        'target': target,
        'stop_loss': stop_loss,
        'confidence': min(confidence, 0.9),
        'direction': 'up' if direction_up else 'down',
        'w2_ret': w2_ret,
        'w4_ret': w4_ret
    })

print(f"\n统计:")
print(f"  检查窗口: {stats['checked']}")
print(f"  浪1通过: {stats['wave1_ok']}")
print(f"  结构通过: {stats['structure_ok']}")
print(f"  浪2通过: {stats['wave2_ok']}")
print(f"  浪3通过: {stats['wave3_ok']}")
print(f"  浪4通过: {stats['wave4_ok']}")
print(f"  最终通过: {stats['passed']}")

print(f"\n找到 {len(signals)} 个信号")
for i, sig in enumerate(signals[:5], 1):
    print(f"\n信号 #{i}:")
    print(f"  日期: {sig['entry_date'].strftime('%Y-%m-%d')}")
    print(f"  方向: {sig['direction']}")
    print(f"  价格: ¥{sig['entry_price']:.2f}")
    print(f"  目标: ¥{sig['target']:.2f}")
    print(f"  置信度: {sig['confidence']:.2f}")

print("\n✅ 完成")
