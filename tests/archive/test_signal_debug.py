#!/usr/bin/env python3
"""
调试版 - 检查信号检测问题
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from datetime import datetime
from data import get_stock_data

symbol = '600519'
print(f"🧪 调试信号检测 - {symbol}")
print("="*70)

df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
df['date'] = pd.to_datetime(df['date'])

# 找极值点
prices = df['close'].values
dates = df['date'].values

window = 3
pivots = []
for i in range(window, len(prices) - window):
    is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
             all(prices[i] >= prices[i+j] for j in range(1, window+1))
    is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1))
    if is_peak or is_trough:
        pivots.append((i, prices[i], dates[i]))

print(f"找到 {len(pivots)} 个极值点")

# 寻找4浪买入点
signals = []
for i in range(len(pivots) - 3):
    p1 = pivots[i]
    p2 = pivots[i+1]
    p3 = pivots[i+2]
    p4 = pivots[i+3]
    
    wave1 = abs(p2[1] - p1[1])
    wave2 = abs(p3[1] - p2[1])
    wave3 = abs(p4[1] - p3[1])
    
    if wave1 < p1[1] * 0.015:
        continue
    
    direction_up = p2[1] > p1[1]
    
    # 方向检查
    if direction_up:
        if not (p3[1] > p2[1] and p4[1] < p3[1]):
            continue
    else:
        if not (p3[1] < p2[1] and p4[1] > p3[1]):
            continue
    
    # 回撤检查
    w2_ret = wave2 / wave1 if wave1 > 0 else 1
    if w2_ret > 0.618:
        continue
    
    if wave3 < wave1 * 0.8:
        continue
    
    w4_ret = wave3 / wave2 if wave2 > 0 else 1
    if w4_ret > 0.5:
        continue
    
    # 简化：只要p4是最后一个极值点，就认为在4浪
    # 检查p4之后是否有新的极值点（即浪5）
    if i + 4 < len(pivots):
        continue  # 有第5个极值点，说明浪5已形成
    
    # 找到4浪买入点
    if direction_up:
        target = p4[1] + wave1
        stop_loss = min(p4[1] * 0.98, p2[1] * 0.99)
    else:
        target = p4[1] - wave1
        stop_loss = max(p4[1] * 1.02, p2[1] * 1.01)
    
    confidence = 0.5
    if 0.3 <= w2_ret <= 0.5:
        confidence += 0.15
    if 0.2 <= w4_ret <= 0.4:
        confidence += 0.15
    
    signals.append({
        'entry_date': p4[2],
        'entry_price': p4[1],
        'target': target,
        'stop_loss': stop_loss,
        'confidence': min(confidence, 0.9),
        'w2_ret': w2_ret,
        'w4_ret': w4_ret
    })

print(f"\n找到 {len(signals)} 个4浪买入信号")

for i, sig in enumerate(signals[:5], 1):
    print(f"\n信号 #{i}:")
    print(f"  日期: {sig['entry_date'].strftime('%Y-%m-%d')}")
    print(f"  价格: ¥{sig['entry_price']:.2f}")
    print(f"  目标: ¥{sig['target']:.2f} ({(sig['target']/sig['entry_price']-1)*100:+.1f}%)")
    print(f"  止损: ¥{sig['stop_loss']:.2f}")
    print(f"  置信度: {sig['confidence']:.2f}")
    print(f"  浪2回撤: {sig['w2_ret']:.1%}")
    print(f"  浪4回撤: {sig['w4_ret']:.1%}")

# 检查这些日期在回测中是否能匹配
print(f"\n检查信号匹配...")
for sig in signals[:3]:
    sig_date = sig['entry_date']
    # 找前后3天
    for offset in range(-3, 4):
        check_date = sig_date + pd.Timedelta(days=offset)
        matching_rows = df[df['date'] == check_date]
        if len(matching_rows) > 0:
            price = matching_rows.iloc[0]['close']
            ratio = price / sig['entry_price']
            if 0.95 <= ratio <= 1.05:
                print(f"  ✓ {check_date.strftime('%Y-%m-%d')}: ¥{price:.2f} (匹配度 {ratio:.2%})")
                break
    else:
        print(f"  ✗ {sig_date.strftime('%Y-%m-%d')}: 未找到匹配价格")

print("\n✅ 调试完成")
