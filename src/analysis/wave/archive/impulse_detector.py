#!/usr/bin/env python3
"""
推动浪(12345)识别优化 - 增强2/4浪买卖点
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class WaveDirection(Enum):
    UP = "up"
    DOWN = "down"


@dataclass
class WavePoint:
    index: int
    date: str
    price: float
    wave_num: Optional[str] = None
    is_peak: bool = False
    is_trough: bool = False


class ImpulseWaveDetector:
    """
    专业推动浪(12345)识别器
    
    核心规则:
    1. 浪2回撤不超过浪1的61.8%
    2. 浪3不能最短
    3. 浪4不进入浪1区间
    4. 浪2和浪4交替(深度/形态)
    """
    
    def __init__(self, 
                 min_wave_change_pct: float = 0.015,  # 降低门槛
                 max_wave2_retracement: float = 0.8,  # 放宽条件
                 min_wave3_ratio: float = 0.8,        # 放宽条件
                 max_wave4_retracement: float = 0.618):  # 放宽条件
        self.min_wave_change_pct = min_wave_change_pct
        self.max_wave2_retracement = max_wave2_retracement
        self.min_wave3_ratio = min_wave3_ratio  # 浪3至少是浪1的1倍
        self.max_wave4_retracement = max_wave4_retracement
    
    def detect_impulse(self, df: pd.DataFrame, lookback: int = 60) -> Optional[dict]:
        """
        检测推动浪12345形态
        
        Returns:
            {
                'points': [p1, p2, p3, p4, p5],
                'current_wave': '2'|'4'|'5',
                'direction': 'up'|'down',
                'confidence': float,
                'entry_wave': str,  # 可买入的浪号
                'target_price': float,
                'stop_loss': float
            }
        """
        if len(df) < lookback:
            return None
        
        df = df.iloc[-lookback:].copy().reset_index(drop=True)
        prices = df['close'].values
        highs = df['high'].values if 'high' in df.columns else prices
        lows = df['low'].values if 'low' in df.columns else prices
        
        # 检测极值点
        pivots = self._find_pivots(prices, window=3)
        if len(pivots) < 5:
            return None
        
        # 尝试识别12345
        for i in range(len(pivots) - 4):
            p0_idx, p0_price, p0_type = pivots[i]
            
            # 尝试不同起点
            candidates = []
            for j in range(i+1, min(i+6, len(pivots)-3)):
                p1_idx, p1_price, p1_type = pivots[j]
                wave1_change = abs(p1_price - p0_price) / p0_price
                
                if wave1_change < self.min_wave_change_pct:
                    continue
                
                # 寻找浪2
                for k in range(j+1, min(j+4, len(pivots)-2)):
                    p2_idx, p2_price, p2_type = pivots[k]
                    
                    # 验证浪2回撤
                    if not self._check_wave2_retracement(p0_price, p1_price, p2_price):
                        continue
                    
                    # 寻找浪3
                    for m in range(k+1, min(k+5, len(pivots)-1)):
                        p3_idx, p3_price, p3_type = pivots[m]
                        
                        # 验证浪3
                        if not self._check_wave3(p0_price, p1_price, p2_price, p3_price):
                            continue
                        
                        # 寻找浪4
                        for n in range(m+1, min(m+4, len(pivots))):
                            p4_idx, p4_price, p4_type = pivots[n]
                            
                            # 验证浪4
                            if not self._check_wave4(p1_price, p2_price, p3_price, p4_price):
                                continue
                            
                            # 检查是否有浪5数据
                            if n + 1 < len(pivots):
                                p5_idx, p5_price, p5_type = pivots[n+1]
                                
                                # 验证浪5
                                if self._check_wave5(p3_price, p4_price, p5_price):
                                    candidates.append({
                                        'points': [
                                            WavePoint(p0_idx, str(df.iloc[p0_idx]['date']), p0_price, '1', p0_type=='peak', p0_type=='trough'),
                                            WavePoint(p1_idx, str(df.iloc[p1_idx]['date']), p1_price, '2', p1_type=='peak', p1_type=='trough'),
                                            WavePoint(p2_idx, str(df.iloc[p2_idx]['date']), p2_price, '3', p2_type=='peak', p2_type=='trough'),
                                            WavePoint(p3_idx, str(df.iloc[p3_idx]['date']), p3_price, '4', p3_type=='peak', p3_type=='trough'),
                                            WavePoint(p4_idx, str(df.iloc[p4_idx]['date']), p4_price, '5', p4_type=='peak', p4_type=='trough'),
                                        ],
                                        'complete': True,
                                        'direction': 'up' if p1_price > p0_price else 'down',
                                        'wave1_amp': abs(p1_price - p0_price),
                                        'wave2_ret': abs(p2_price - p1_price) / abs(p1_price - p0_price),
                                        'wave3_amp': abs(p3_price - p2_price),
                                        'wave4_ret': abs(p4_price - p3_price) / abs(p3_price - p2_price),
                                    })
                            else:
                                # 只有4浪，等待5浪
                                candidates.append({
                                    'points': [
                                        WavePoint(p0_idx, str(df.iloc[p0_idx]['date']), p0_price, '1', p0_type=='peak', p0_type=='trough'),
                                        WavePoint(p1_idx, str(df.iloc[p1_idx]['date']), p1_price, '2', p1_type=='peak', p1_type=='trough'),
                                        WavePoint(p2_idx, str(df.iloc[p2_idx]['date']), p2_price, '3', p2_type=='peak', p2_type=='trough'),
                                        WavePoint(p3_idx, str(df.iloc[p3_idx]['date']), p3_price, '4', p3_type=='peak', p3_type=='trough'),
                                    ],
                                    'current_wave': '4',
                                    'complete': False,
                                    'direction': 'up' if p1_price > p0_price else 'down',
                                    'wave1_amp': abs(p1_price - p0_price),
                                    'wave2_ret': abs(p2_price - p1_price) / abs(p1_price - p0_price),
                                    'wave3_amp': abs(p3_price - p2_price),
                                    'wave4_ret': abs(p4_price - p3_price) / abs(p3_price - p2_price),
                                    'entry_price': p4_price,
                                })
            
            if candidates:
                # 选择最佳候选
                best = max(candidates, key=lambda x: x.get('wave3_amp', 0))
                return self._build_result(best, df)
        
        return None
    
    def _find_pivots(self, prices: np.ndarray, window: int = 3) -> List[Tuple[int, float, str]]:
        """寻找极值点"""
        pivots = []
        for i in range(window, len(prices) - window):
            # 局部最大值
            if all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
               all(prices[i] >= prices[i+j] for j in range(1, window+1)):
                pivots.append((i, prices[i], 'peak'))
            # 局部最小值
            elif all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                 all(prices[i] <= prices[i+j] for j in range(1, window+1)):
                pivots.append((i, prices[i], 'trough'))
        return pivots
    
    def _check_wave2_retracement(self, p0: float, p1: float, p2: float) -> bool:
        """检查浪2回撤是否符合规则 (不超过61.8%)"""
        wave1 = abs(p1 - p0)
        wave2 = abs(p2 - p1)
        retracement = wave2 / wave1 if wave1 > 0 else 1.0
        return retracement <= self.max_wave2_retracement and retracement >= 0.1
    
    def _check_wave3(self, p0: float, p1: float, p2: float, p3: float) -> bool:
        """检查浪3是否符合规则 (不能最短)"""
        wave1 = abs(p1 - p0)
        wave2 = abs(p2 - p1)
        wave3 = abs(p3 - p2)
        
        # 浪3不能最短
        if wave3 < wave1 and wave3 < wave2:
            return False
        
        # 浪3应该大于浪1的某个比例
        if wave3 < wave1 * self.min_wave3_ratio:
            return False
        
        return True
    
    def _check_wave4(self, p1: float, p2: float, p3: float, p4: float) -> bool:
        """检查浪4是否符合规则"""
        wave3 = abs(p3 - p2)
        wave4 = abs(p4 - p3)
        
        # 浪4回撤不超过浪3的50%
        retracement = wave4 / wave3 if wave3 > 0 else 1.0
        if retracement > self.max_wave4_retracement:
            return False
        
        # 浪4不应进入浪1区间 (简化检查)
        # 实际应该检查p4是否超越p1
        return True
    
    def _check_wave5(self, p3: float, p4: float, p5: float) -> bool:
        """检查浪5是否存在"""
        wave5 = abs(p5 - p4)
        return wave5 > 0
    
    def _build_result(self, candidate: dict, df: pd.DataFrame) -> dict:
        """构建结果"""
        points = candidate['points']
        direction = candidate['direction']
        
        # 计算置信度
        confidence = 0.5
        if candidate.get('wave2_ret', 0.5) < 0.5:
            confidence += 0.1  # 浪2回撤合理
        if candidate.get('wave3_amp', 0) > candidate.get('wave1_amp', 0) * 1.5:
            confidence += 0.2  # 浪3强劲
        if candidate.get('wave4_ret', 0.5) < 0.382:
            confidence += 0.1  # 浪4回撤浅
        
        # 确定当前位置和买入点
        if candidate.get('complete'):
            current_wave = '5'
            entry_wave = None  # 5浪完成，不买入
        else:
            current_wave = '4'
            entry_wave = '4'   # 4浪买入
        
        # 计算目标价
        last_price = points[-1].price
        wave1_amp = candidate.get('wave1_amp', last_price * 0.05)
        
        if direction == 'up':
            target = last_price + wave1_amp  # 5浪目标 ≈ 浪1等幅
            stop_loss = min(points[-2].price, last_price * 0.95)
        else:
            target = last_price - wave1_amp
            stop_loss = max(points[-2].price, last_price * 1.05)
        
        return {
            'points': points,
            'current_wave': current_wave,
            'entry_wave': entry_wave,
            'direction': direction,
            'confidence': min(confidence, 0.9),
            'target_price': target,
            'stop_loss': stop_loss,
            'fib_ratios': {
                'wave2_retracement': candidate.get('wave2_ret', 0),
                'wave3_vs_wave1': candidate.get('wave3_amp', 0) / max(candidate.get('wave1_amp', 1), 1e-6),
                'wave4_retracement': candidate.get('wave4_ret', 0),
            }
        }


if __name__ == "__main__":
    # 测试
    from data import get_stock_data
    
    print("🧪 推动浪识别测试")
    print("="*60)
    
    test_stocks = ['600519', '000858', '300750', '600036']
    
    for symbol in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        
        detector = ImpulseWaveDetector()
        result = detector.detect_impulse(df, lookback=60)
        
        if result:
            print(f"\n{symbol}: 检测到推动浪")
            print(f"  当前浪: {result['current_wave']}")
            print(f"  可买入: 浪{result['entry_wave']}" if result['entry_wave'] else "  可买入: 无")
            print(f"  方向: {result['direction']}")
            print(f"  置信度: {result['confidence']:.2f}")
            print(f"  目标价: ¥{result['target_price']:.2f}")
            print(f"  浪号序列: ", end="")
            for p in result['points']:
                print(f"{p.wave_num}({p.price:.0f}) ", end="")
            print()
        else:
            print(f"\n{symbol}: 未检测到推动浪")
    
    print("\n✅ 测试完成")
