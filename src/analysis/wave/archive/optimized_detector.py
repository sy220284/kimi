#!/usr/bin/env python3
"""
优化版波浪分析器 - 增强2/4浪买卖点识别
集成到现有框架中
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum


class WaveType(Enum):
    IMPULSE = "impulse"
    CORRECTIVE = "corrective"
    ZIGZAG = "zigzag"


class WaveDirection(Enum):
    UP = "up"
    DOWN = "down"


@dataclass
class WavePoint:
    index: int
    date: str
    price: float
    wave_num: Optional[str] = None


@dataclass
class WavePattern:
    wave_type: WaveType
    direction: WaveDirection
    points: List[WavePoint]
    confidence: float
    entry_wave: Optional[str] = None  # 可买入的浪号
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None


class OptimizedWaveDetector:
    """
    优化的波浪检测器 - 专门增强2/4浪识别
    """
    
    def __init__(self):
        self.confidence_threshold = 0.35
    
    def detect(self, df: pd.DataFrame) -> Optional[WavePattern]:
        """
        检测波浪形态 - 优先识别推动浪的2浪和4浪
        """
        # 1. 首先尝试识别推动浪12345
        impulse = self._detect_impulse_wave(df)
        if impulse and impulse.confidence >= self.confidence_threshold:
            return impulse
        
        # 2. 然后尝试识别ZigZag
        zigzag = self._detect_zigzag_wave(df)
        if zigzag and zigzag.confidence >= self.confidence_threshold:
            return zigzag
        
        return None
    
    def _detect_impulse_wave(self, df: pd.DataFrame) -> Optional[WavePattern]:
        """
        检测推动浪12345 - 重点关注2浪和4浪买入点
        """
        prices = df['close'].values
        highs = df['high'].values if 'high' in df.columns else prices
        lows = df['low'].values if 'low' in df.columns else prices
        
        # 寻找5个关键极值点
        pivots = self._find_swing_points(prices, window=2)
        if len(pivots) < 5:
            return None
        
        best_pattern = None
        best_score = 0
        
        # 滑动窗口寻找最佳12345匹配
        for i in range(len(pivots) - 4):
            p1_idx, p1_price, p1_type = pivots[i]
            
            for j in range(i+1, min(i+3, len(pivots)-3)):
                p2_idx, p2_price, p2_type = pivots[j]
                
                # 确定方向
                direction_up = p2_price > p1_price
                
                for k in range(j+1, min(j+4, len(pivots)-2)):
                    p3_idx, p3_price, p3_type = pivots[k]
                    
                    # 浪3应该在浪1方向延伸
                    if direction_up and p3_price <= p2_price:
                        continue
                    if not direction_up and p3_price >= p2_price:
                        continue
                    
                    for m in range(k+1, min(k+4, len(pivots)-1)):
                        p4_idx, p4_price, p4_type = pivots[m]
                        
                        # 浪4回撤检查
                        wave3_range = abs(p3_price - p2_price)
                        wave4_range = abs(p4_price - p3_price)
                        
                        if wave4_range > wave3_range * 0.618:
                            continue  # 回撤太深
                        
                        # 检查是否有第5点
                        has_wave5 = m + 1 < len(pivots)
                        
                        if has_wave5:
                            p5_idx, p5_price, p5_type = pivots[m+1]
                            current_wave = '5'
                            entry_wave = None
                            final_idx = p5_idx
                            final_price = p5_price
                        else:
                            current_wave = '4'
                            entry_wave = '4'  # 4浪买入点！
                            final_idx = p4_idx
                            final_price = p4_price
                        
                        # 评分
                        score = self._score_impulse(
                            p1_price, p2_price, p3_price, p4_price,
                            final_price if has_wave5 else p4_price,
                            direction_up
                        )
                        
                        if score > best_score:
                            best_score = score
                            
                            points = [
                                WavePoint(p1_idx, str(df.iloc[p1_idx]['date']), p1_price, '1'),
                                WavePoint(p2_idx, str(df.iloc[p2_idx]['date']), p2_price, '2'),
                                WavePoint(p3_idx, str(df.iloc[p3_idx]['date']), p3_price, '3'),
                                WavePoint(p4_idx, str(df.iloc[p4_idx]['date']), p4_price, '4'),
                            ]
                            
                            if has_wave5:
                                points.append(WavePoint(p5_idx, str(df.iloc[p5_idx]['date']), p5_price, '5'))
                            
                            # 计算目标价
                            wave1_amp = abs(p2_price - p1_price)
                            if direction_up:
                                target = final_price + wave1_amp  # 5浪等幅
                                stop_loss = min(p3_price, p4_price * 0.98)
                            else:
                                target = final_price - wave1_amp
                                stop_loss = max(p3_price, p4_price * 1.02)
                            
                            best_pattern = WavePattern(
                                wave_type=WaveType.IMPULSE,
                                direction=WaveDirection.UP if direction_up else WaveDirection.DOWN,
                                points=points,
                                confidence=min(score, 0.9),
                                entry_wave=entry_wave,
                                target_price=target,
                                stop_loss=stop_loss
                            )
        
        return best_pattern
    
    def _detect_zigzag_wave(self, df: pd.DataFrame) -> Optional[WavePattern]:
        """检测ZigZag ABC"""
        prices = df['close'].values
        
        pivots = self._find_swing_points(prices, window=2)
        if len(pivots) < 4:
            return None
        
        # 取最后4个点
        p0_idx, p0_price, _ = pivots[-4]
        pA_idx, pA_price, _ = pivots[-3]
        pB_idx, pB_price, _ = pivots[-2]
        pC_idx, pC_price, _ = pivots[-1]
        
        # 简单验证ABC形态
        a_len = abs(pA_price - p0_price)
        b_len = abs(pB_price - pA_price)
        c_len = abs(pC_price - pB_price)
        
        # C浪应该比B浪长
        if c_len < b_len * 0.5:
            return None
        
        direction_up = pC_price > pB_price
        
        points = [
            WavePoint(p0_idx, str(df.iloc[p0_idx]['date']), p0_price, None),
            WavePoint(pA_idx, str(df.iloc[pA_idx]['date']), pA_price, 'A'),
            WavePoint(pB_idx, str(df.iloc[pB_idx]['date']), pB_price, 'B'),
            WavePoint(pC_idx, str(df.iloc[pC_idx]['date']), pC_price, 'C'),
        ]
        
        # 计算目标价
        if direction_up:
            target = pC_price + a_len
            stop_loss = pB_price
        else:
            target = pC_price - a_len
            stop_loss = pB_price
        
        confidence = 0.5 + min(c_len / a_len, 0.3)
        
        return WavePattern(
            wave_type=WaveType.ZIGZAG,
            direction=WaveDirection.UP if direction_up else WaveDirection.DOWN,
            points=points,
            confidence=confidence,
            entry_wave='C',
            target_price=target,
            stop_loss=stop_loss
        )
    
    def _find_swing_points(self, prices: np.ndarray, window: int = 2) -> List[tuple]:
        """寻找摆动点"""
        swings = []
        
        for i in range(window, len(prices) - window):
            is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                     all(prices[i] >= prices[i+j] for j in range(1, window+1))
            
            is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                       all(prices[i] <= prices[i+j] for j in range(1, window+1))
            
            if is_peak:
                swings.append((i, prices[i], 'peak'))
            elif is_trough:
                swings.append((i, prices[i], 'trough'))
        
        return swings
    
    def _score_impulse(self, p1, p2, p3, p4, p5, direction_up) -> float:
        """评分推动浪质量"""
        score = 0.5
        
        wave1 = abs(p2 - p1)
        wave2 = abs(p3 - p2)
        wave3 = abs(p4 - p3)
        wave4 = abs(p5 - p4) if p5 else 0
        
        # 浪3通常最长
        if wave3 > wave1:
            score += 0.1
        if wave3 > wave2:
            score += 0.1
        
        # 浪2回撤合理
        w2_ret = wave2 / wave1 if wave1 > 0 else 1
        if 0.3 <= w2_ret <= 0.618:
            score += 0.1
        
        # 浪4回撤合理
        if wave4 > 0:
            w4_ret = wave4 / wave3 if wave3 > 0 else 1
            if w4_ret <= 0.5:
                score += 0.1
        else:
            # 当前在4浪，回撤合理
            w4_so_far = abs(p4 - p3) / wave3 if wave3 > 0 else 1
            if w4_so_far <= 0.5:
                score += 0.1
        
        return min(score, 0.9)


if __name__ == "__main__":
    from data import get_stock_data
    
    print("🧪 优化版波浪检测器测试 (增强2/4浪识别)")
    print("="*70)
    
    test_stocks = [
        ('600519', '茅台'),
        ('000858', '五粮液'),
        ('300750', '宁德时代'),
        ('600036', '招商银行'),
        ('600600', '青岛啤酒'),
    ]
    
    detector = OptimizedWaveDetector()
    
    wave_stats = {'2': 0, '4': 0, 'C': 0, 'None': 0}
    
    for symbol, name in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        
        # 分段检测
        for i in range(60, len(df), 30):
            window_df = df.iloc[i-60:i].copy()
            
            pattern = detector.detect(window_df)
            if pattern and pattern.entry_wave:
                wave_stats[pattern.entry_wave] = wave_stats.get(pattern.entry_wave, 0) + 1
                
                if i == 60:  # 只打印第一个
                    print(f"\n{symbol} {name}:")
                    print(f"  检测到: {pattern.wave_type.value}")
                    print(f"  买入浪: {pattern.entry_wave}")
                    print(f"  方向: {pattern.direction.value}")
                    print(f"  置信度: {pattern.confidence:.2f}")
                    print(f"  目标价: ¥{pattern.target_price:.2f}")
                    print(f"  止损价: ¥{pattern.stop_loss:.2f}")
                    print(f"  浪号: {'-'.join([p.wave_num or '?' for p in pattern.points])}")
    
    print(f"\n{'='*70}")
    print("📊 买入浪号分布统计:")
    for wave, count in sorted(wave_stats.items()):
        if count > 0:
            print(f"  浪{wave}: {count}次")
    
    print("\n✅ 测试完成")
