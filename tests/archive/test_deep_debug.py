#!/usr/bin/env python3
"""
深度调试 - 检查每一步过滤
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from data import get_stock_data

symbol = '600519'
print(f"🧪 深度调试 - {symbol}")
print("="*70)

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
df['date'] = pd.to_datetime(df['date'])

prices = df['close'].values
dates = df['date'].values

# 找极值点
window = 3
pivots = []
for i in range(window, len(prices) - window):
    is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
             all(prices[i] >= prices[i+j] for j in range(1, window+1))
    is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1))
    if is_peak or is_trough:
        pivots.append((i, prices[i], dates[i], 'peak' if is_peak else 'trough'))

print(f"找到 {len(pivots)} 个极值点")
print(f"前5个: ", end="")
for p in pivots[:5]:
    dt = pd.Timestamp(p[2])
    print(f"{dt.strftime('%m-%d')}({p[3][0].upper()})¥{p[1]:.0f} ", end="")
print()

# 统计每一步
stats = {
    'total_windows': 0,
    'wave1_too_small': 0,
    'wrong_direction': 0,
    'wave2_deep': 0,
    'wave3_short': 0,
    'wave4_deep': 0,
    'has_wave5': 0,
    'passed': 0
}

signals = []

for i in range(len(pivots) - 3):
    stats['total_windows'] += 1
    
    p1 = pivots[i]
    p2 = pivots[i+1]
    p3 = pivots[i+2]
    p4 = pivots[i+3]
    
    wave1 = abs(p2[1] - p1[1])
    
    if wave1 < p1[1] * 0.015:
        stats['wave1_too_small'] += 1
        continue
    
    direction_up = p2[1] > p1[1]
    
    # 方向检查
    if direction_up:
        if not (p3[1] > p2[1] and p4[1] < p3[1]):
            stats['wrong_direction'] += 1
            continue
    else:
        if not (p3[1] < p2[1] and p4[1] > p3[1]):
            stats['wrong_direction'] += 1
            continue
    
    wave2 = abs(p3[1] - p2[1])
    wave3 = abs(p4[1] - p3[1])
    
    w2_ret = wave2 / wave1 if wave1 > 0 else 1
    if w2_ret > 0.618:
        stats['wave2_deep'] += 1
        continue
    
    if wave3 < wave1 * 0.8:
        stats['wave3_short'] += 1
        continue
    
    w4_ret = wave3 / wave2 if wave2 > 0 else 1
    if w4_ret > 0.5:
        stats['wave4_deep'] += 1
        continue
    
    # 检查是否有第5个极值点
    if i + 4 < len(pivots):
        stats['has_wave5'] += 1
        continue
    
    stats['passed'] += 1
    
    if direction_up:
        target = p4[1] + wave1
        stop_loss = min(p4[1] * 0.98, p2[1] * 0.99)
    else:
        target = p4[1] - wave1
        stop_loss = max(p4[1] * 1.02, p2[1] * 1.01)
    
    signals.append({
        'entry_date': p4[2],
        'entry_price': p4[1],
        'target': target,
        'stop_loss': stop_loss,
        'w2_ret': w2_ret,
        'w4_ret': w4_ret
    })

print(f"\n统计:")
print(f"  检测窗口: {stats['total_windows']}")
print(f"  浪1太小: {stats['wave1_too_small']}")
print(f"  方向错误: {stats['wrong_direction']}")
print(f"  浪2太深: {stats['wave2_deep']}")
print(f"  浪3太短: {stats['wave3_short']}")
print(f"  浪4太深: {stats['wave4_deep']}")
print(f"  有浪5: {stats['has_wave5']}")
print(f"  通过: {stats['passed']}")

if signals:
    print(f"\n找到 {len(signals)} 个信号")
else:
    print(f"\n❌ 无信号 - 主要卡在: ", end="")
    max_val = max(stats.values())
    for k, v in stats.items():
        if v == max_val and k != 'total_windows':
            print(f"{k} ({v}次)")
            break

print("\n✅ 调试完成")
