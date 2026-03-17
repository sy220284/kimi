#!/usr/bin/env python3
"""
详细调试 - 打印每一步
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data

symbol = '600519'
df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
df['date'] = pd.to_datetime(df['date'])

prices = df['close'].values

# 找极值点
window = 3
pivots = []
for i in range(window, len(prices) - window):
    is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
             all(prices[i] >= prices[i+j] for j in range(1, window+1))
    is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] <= prices[i+j] for j in range(1, window+1))
    if is_peak:
        pivots.append((i, prices[i], 'peak'))
    elif is_trough:
        pivots.append((i, prices[i], 'trough'))

# 过滤连续同类型
filtered = [pivots[0]]
for p in pivots[1:]:
    if p[2] != filtered[-1][2]:
        filtered.append(p)
pivots = filtered

print(f"极值点: {len(pivots)} 个")
print(f"序列: ", end="")
for p in pivots[:10]:
    print(f"{p[2][0].upper()}¥{p[1]:.0f} ", end="")
print("...")

# 检查前几个窗口
print(f"\n检查前3个窗口:")
for i in range(min(3, len(pivots) - 3)):
    p1, p2, p3, p4 = pivots[i], pivots[i+1], pivots[i+2], pivots[i+3]
    print(f"\n窗口 {i}: {p1[2]}-{p2[2]}-{p3[2]}-{p4[2]}")
    print(f"  价格: ¥{p1[1]:.0f} -> ¥{p2[1]:.0f} -> ¥{p3[1]:.0f} -> ¥{p4[1]:.0f}")
    
    wave1 = abs(p2[1] - p1[1])
    print(f"  浪1幅度: ¥{wave1:.2f} ({wave1/p1[1]*100:.2f}%)")
    
    if wave1 < p1[1] * 0.015:
        print(f"  ❌ 浪1太小")
        continue
    
    direction_up = p2[1] > p1[1]
    print(f"  方向: {'上升' if direction_up else '下降'}")
    
    # 检查结构
    if direction_up:
        valid = p1[2] == 'trough' and p2[2] == 'peak' and p3[2] == 'trough' and p4[2] == 'peak'
        print(f"  结构(底-顶-底-顶): {'✓' if valid else '✗'}")
        if not valid:
            print(f"    实际: {p1[2]}-{p2[2]}-{p3[2]}-{p4[2]}")
            continue
        price_valid = p2[1] > p1[1] and p3[1] > p1[1] and p4[1] > p3[1]
        print(f"  价格关系: {'✓' if price_valid else '✗'}")
    else:
        valid = p1[2] == 'peak' and p2[2] == 'trough' and p3[2] == 'peak' and p4[2] == 'trough'
        print(f"  结构(顶-底-顶-底): {'✓' if valid else '✗'}")

print("\n✅ 调试完成")
