#!/usr/bin/env python3
"""
实用版4浪检测 - 用于回测
在每个时间点检测当前波浪状态
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from data import get_stock_data
from typing import List, Dict, Optional

class Wave4Detector:
    """4浪买入点检测器"""
    
    def __init__(self, 
                 min_wave_pct: float = 0.015,
                 max_wave2_retrace: float = 0.618,
                 max_wave4_retrace: float = 0.5):
        self.min_wave_pct = min_wave_pct
        self.max_wave2_retrace = max_wave2_retrace
        self.max_wave4_retrace = max_wave4_retrace
    
    def detect(self, df: pd.DataFrame, lookback: int = 40) -> Optional[Dict]:
        """
        检测当前是否处于4浪买入点
        
        Returns:
            {
                'is_wave4': bool,
                'entry_price': float,
                'target_price': float,
                'stop_loss': float,
                'confidence': float,
                'direction': str
            }
        """
        if len(df) < lookback:
            return None
        
        df_window = df.iloc[-lookback:].copy().reset_index(drop=True)
        prices = df_window['close'].values
        
        # 找极值点
        pivots = self._find_pivots(prices, window=2)
        if len(pivots) < 4:
            return None
        
        # 取最后4个极值点
        p1_idx, p1_price = pivots[-4]
        p2_idx, p2_price = pivots[-3]
        p3_idx, p3_price = pivots[-2]
        p4_idx, p4_price = pivots[-1]
        
        # 检查极值点类型是否交替
        # 简化：假设p1/p3是同类(底)，p2/p4是同类(顶) 或相反
        
        # 计算波浪幅度
        wave1 = abs(p2_price - p1_price)
        wave2 = abs(p3_price - p2_price)
        wave3 = abs(p4_price - p3_price)
        
        if wave1 < p1_price * self.min_wave_pct:
            return None
        
        # 确定方向
        direction_up = p2_price > p1_price
        
        # 检查结构
        if direction_up:
            # 上升浪: p1<p2, p3<p2, p3>p1, p4>p3
            if not (p2_price > p1_price and p3_price < p2_price and 
                    p3_price > p1_price and p4_price > p3_price):
                return None
        else:
            # 下降浪
            if not (p2_price < p1_price and p3_price > p2_price and 
                    p3_price < p1_price and p4_price < p3_price):
                return None
        
        # 浪2回撤检查
        w2_retrace = wave2 / wave1
        if w2_retrace > self.max_wave2_retrace:
            return None
        
        # 浪3检查
        if wave3 < wave1 * 0.8:
            return None
        
        # 当前价格在浪4中
        current_price = prices[-1]
        
        # 计算从p4开始的回撤
        wave4_sofar = abs(current_price - p4_price)
        w4_retrace = wave4_sofar / wave3 if wave3 > 0 else 1
        
        # 检查是否在有效的4浪区域
        if direction_up:
            if current_price >= p4_price:  # 还没回撤
                return None
            if current_price <= p3_price:  # 回撤太深
                return None
        else:
            if current_price <= p4_price:
                return None
            if current_price >= p3_price:
                return None
        
        if w4_retrace > self.max_wave4_retrace:
            return None
        
        # 计算目标价和止损
        if direction_up:
            target = current_price + wave1
            stop_loss = min(current_price * 0.98, p3_price * 0.99)
        else:
            target = current_price - wave1
            stop_loss = max(current_price * 1.02, p3_price * 1.01)
        
        # 置信度
        confidence = 0.5
        if 0.3 <= w2_retrace <= 0.5:
            confidence += 0.15
        if 0.2 <= w4_retrace <= 0.4:
            confidence += 0.15
        if wave3 > wave1 * 1.5:
            confidence += 0.1
        
        return {
            'is_wave4': True,
            'entry_price': current_price,
            'target_price': target,
            'stop_loss': stop_loss,
            'confidence': min(confidence, 0.9),
            'direction': 'up' if direction_up else 'down',
            'wave2_retrace': w2_retrace,
            'wave4_retrace': w4_retrace
        }
    
    def _find_pivots(self, prices: np.ndarray, window: int = 2) -> List[tuple]:
        """寻找极值点"""
        pivots = []
        for i in range(window, len(prices) - window):
            is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                     all(prices[i] >= prices[i+j] for j in range(1, window+1))
            is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                       all(prices[i] <= prices[i+j] for j in range(1, window+1))
            if is_peak or is_trough:
                pivots.append((i, prices[i]))
        return pivots


# 测试
print("🧪 实用版4浪检测测试")
print("="*70)

test_stocks = [
    ('600519', '茅台'),
    ('000858', '五粮液'),
    ('300750', '宁德时代'),
    ('600036', '招商银行'),
]

detector = Wave4Detector()

for symbol, name in test_stocks:
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    df['date'] = pd.to_datetime(df['date'])
    
    # 滚动检测
    signals = []
    for i in range(60, len(df), 5):  # 每5天检测一次
        window_df = df.iloc[i-60:i].copy()
        result = detector.detect(window_df, lookback=40)
        if result and result['is_wave4'] and result['confidence'] >= 0.5:
            signals.append({
                'date': df.iloc[i]['date'],
                'price': result['entry_price'],
                'target': result['target_price'],
                'confidence': result['confidence'],
                'direction': result['direction']
            })
    
    print(f"\n{symbol} {name}:")
    print(f"  找到 {len(signals)} 个4浪买入信号")
    for sig in signals[:3]:
        target_pct = (sig['target'] / sig['price'] - 1) * 100
        print(f"  {sig['date'].strftime('%Y-%m-%d')}: ¥{sig['price']:.2f} -> ¥{sig['target']:.2f} ({target_pct:+.1f}%) [{sig['direction']}]")

print("\n✅ 测试完成")
