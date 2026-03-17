#!/usr/bin/env python3
"""
统一波浪分析器 - Unified Wave Analyzer (优化版)
整合所有波浪检测功能到一个入口

优化内容:
1. 浪4检测放宽 - 支持3极值点推断模式
2. 浪C/2区分 - 添加推动浪前序验证
3. 趋势过滤后置 - 买入前检查趋势方向
4. ATR动态止损 - 替代固定百分比止损
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    from .enhanced_detector import enhanced_pivot_detection, PivotPoint, label_wave_numbers
    from .elliott_wave import WavePattern, WavePoint, WaveType, WaveDirection
except ImportError:
    from enhanced_detector import enhanced_pivot_detection, PivotPoint, label_wave_numbers
    from elliott_wave import WavePattern, WavePoint, WaveType, WaveDirection


class WaveEntryType(Enum):
    """波浪买入类型"""
    WAVE_C = "C"
    WAVE_2 = "2"
    WAVE_4 = "4"
    UNKNOWN = "unknown"


@dataclass
class UnifiedWaveSignal:
    """统一波浪信号"""
    is_valid: bool
    entry_type: WaveEntryType
    entry_price: float
    target_price: float
    stop_loss: float
    confidence: float
    direction: str
    
    # 波浪细节
    wave_structure: Optional[Dict] = None
    
    # 检测元数据
    detection_method: str = ""
    pivot_count: int = 0
    
    # 趋势信息
    trend_aligned: bool = False
    trend_direction: str = "unknown"
    
    def __repr__(self):
        return f"WaveSignal({self.entry_type.value}, ¥{self.entry_price:.2f}, conf={self.confidence:.2f})"


class UnifiedWaveAnalyzer:
    """
    统一波浪分析器 - 优化版
    
    优化:
    1. 浪4检测支持3极值点推断模式
    2. 浪C/2区分使用推动浪前序验证
    3. 趋势过滤后置，避免过度过滤
    4. ATR动态止损替代固定止损
    """
    
    def __init__(self,
                 # 极值点检测参数
                 atr_period: int = 10,           # 优化: 从14缩短至10，获取更多极值点
                 atr_mult: float = 0.5,
                 min_pivots: int = 3,            # 优化: 从4降至3，支持浪4检测
                 
                 # 波浪检测参数
                 min_wave_pct: float = 0.015,
                 max_wave2_retrace: float = 0.50,  # 优化: 收紧至50%
                 max_wave4_retrace: float = 0.50,
                 min_retrace: float = 0.382,       # 优化: 从30%提高至38.2%
                 
                 # 信号过滤
                 min_confidence: float = 0.5,
                 use_trend_filter: bool = True,    # 优化: 改为后置趋势过滤
                 
                 # ATR止损参数
                 atr_stop_mult: float = 2.0):      # 新增: ATR止损倍数
        
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.min_pivots = min_pivots
        
        self.min_wave_pct = min_wave_pct
        self.max_wave2_retrace = max_wave2_retrace
        self.max_wave4_retrace = max_wave4_retrace
        self.min_retrace = min_retrace
        
        self.min_confidence = min_confidence
        self.use_trend_filter = use_trend_filter
        self.atr_stop_mult = atr_stop_mult
    
    def detect(self, df: pd.DataFrame, mode: str = 'all') -> List[UnifiedWaveSignal]:
        """
        检测波浪买入信号 - 优化版
        
        流程:
        1. 极值点检测 (不使用趋势确认，避免过度过滤)
        2. 波浪检测 (C/2/4)
        3. 趋势过滤后置 (买入前检查)
        4. ATR动态止损计算
        """
        if len(df) < 60:
            return []
        
        signals = []
        
        # 优化1: 极值点检测不使用趋势确认，获取更多点
        # 修复: 预留10天数据给浪3/4发展，避免最后一个点是极值点
        detect_df = df.iloc[:-10] if len(df) > 70 else df
        
        pivots = enhanced_pivot_detection(
            detect_df,
            atr_period=self.atr_period,
            atr_mult=self.atr_mult,
            min_pivots=self.min_pivots,
            trend_confirmation=False
        )
        
        if len(pivots) < 3:
            return []
        
        # 使用完整数据计算当前价格和ATR
        prices = df['close'].values
        current_price = prices[-1]
        
        # 计算ATR用于动态止损
        atr = self._calculate_atr(df)
        
        # 检测各浪型
        if mode in ['all', 'C'] and len(pivots) >= 3:
            sig = self._detect_wave_c(pivots, prices, atr)
            if sig:
                signals.append(sig)
        
        if mode in ['all', '2'] and len(pivots) >= 3:
            sig = self._detect_wave2(pivots, prices, atr)
            if sig:
                signals.append(sig)
        
        # 优化2: 浪4检测支持3极值点推断模式
        if mode in ['all', '4']:
            sig = None
            if len(pivots) >= 4:
                sig = self._detect_wave4_standard(pivots, prices, atr)
            # 标准检测失败或未满足条件，尝试推断检测
            if sig is None:
                sig = self._detect_wave4_inferred(pivots, prices, atr, df)
            if sig:
                signals.append(sig)
        
        # 优化3: 趋势过滤后置
        if self.use_trend_filter and signals:
            signals = self._apply_trend_filter(signals, df)
        
        signals.sort(key=lambda x: x.confidence, reverse=True)
        return signals
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """计算当前ATR值"""
        if len(df) < self.atr_period + 1:
            return df['close'].std()
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        tr1 = highs[-self.atr_period:] - lows[-self.atr_period:]
        tr2 = np.abs(highs[-self.atr_period:] - closes[-self.atr_period-1:-1])
        tr3 = np.abs(lows[-self.atr_period:] - closes[-self.atr_period-1:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        return float(np.mean(tr))
    
    def _apply_trend_filter(self, signals: List[UnifiedWaveSignal], 
                           df: pd.DataFrame) -> List[UnifiedWaveSignal]:
        """
        后置趋势过滤 - 只保留与趋势一致的信号
        
        趋势判断: 价格 vs 20日均线
        """
        if len(df) < 20:
            return signals
        
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # 简单趋势判断
        if current_price > ma20 * 1.02:
            trend = 'up'
        elif current_price < ma20 * 0.98:
            trend = 'down'
        else:
            trend = 'neutral'
        
        filtered = []
        for sig in signals:
            # 信号方向与趋势一致，或在震荡市中
            if trend == 'neutral' or sig.direction == trend:
                sig.trend_aligned = True
                sig.trend_direction = trend
                filtered.append(sig)
            elif sig.confidence >= 0.7:  # 高置信度信号保留
                sig.trend_aligned = False
                sig.trend_direction = trend
                filtered.append(sig)
        
        return filtered if filtered else signals  # 如果全部过滤，返回原信号
    
    def _detect_wave_c(self, pivots: List[PivotPoint], prices: np.ndarray, 
                       atr: float) -> Optional[UnifiedWaveSignal]:
        """
        检测C浪结束信号 - 优化版
        
        优化: 添加与推动浪的区别验证
        """
        if len(pivots) < 3:
            return None
        
        p_a = pivots[-3]
        p_b = pivots[-2]
        p_c = pivots[-1]
        
        # A-C同方向 (调整浪特征)
        ac_same_direction = (p_a.price < p_b.price and p_b.price > p_c.price) or \
                           (p_a.price > p_b.price and p_b.price < p_c.price)
        
        if not ac_same_direction:
            return None
        
        wave_a = abs(p_b.price - p_a.price)
        wave_c = abs(p_c.price - p_b.price)
        
        if wave_a < p_a.price * self.min_wave_pct:
            return None
        
        # 优化: C浪长度检查，与推动浪区分
        # 调整浪的C浪通常与A浪相近或更长
        if wave_c < wave_a * 0.5:
            return None
        
        current_price = prices[-1]
        direction_up = p_c.price > p_b.price
        
        # ATR动态止损
        atr_stop = self.atr_stop_mult * atr
        
        if direction_up:
            target = current_price + wave_a * 0.618
            stop_loss = max(p_c.price * 0.97, current_price - atr_stop)
        else:
            target = current_price - wave_a * 0.618
            stop_loss = min(p_c.price * 1.03, current_price + atr_stop)
        
        confidence = 0.5
        if wave_c >= wave_a * 0.8:
            confidence += 0.15
        if p_c.strength >= 3:
            confidence += 0.1
        # 优化: C浪长于A浪，更可能是真调整浪结束
        if wave_c >= wave_a:
            confidence += 0.1
        
        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_C,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(confidence, 0.9),
            direction='up' if direction_up else 'down',
            detection_method='enhanced',
            pivot_count=len(pivots)
        )
    
    def _detect_wave2(self, pivots: List[PivotPoint], prices: np.ndarray, 
                      atr: float) -> Optional[UnifiedWaveSignal]:
        """
        检测2浪回撤信号 - 优化版
        
        优化: 
        1. 收紧回撤区间至38.2%-50% (最优区域)
        2. 添加强推动浪前序验证
        """
        if len(pivots) < 3:
            return None
        
        p1 = pivots[-3]
        p2 = pivots[-2]
        p3 = pivots[-1]
        
        wave1 = abs(p2.price - p1.price)
        if wave1 < p1.price * self.min_wave_pct:
            return None
        
        direction_up = p2.price > p1.price
        
        # 验证浪2结构
        if direction_up:
            if not (p1.price < p3.price < p2.price):
                return None
        else:
            if not (p1.price > p3.price > p2.price):
                return None
        
        wave2 = abs(p3.price - p2.price)
        retrace = wave2 / wave1
        
        # 优化: 收紧回撤区间至38.2%-50%
        if not (self.min_retrace <= retrace <= self.max_wave2_retrace):
            return None
        
        # 优化: 添加强推动浪验证
        # 浪1应该足够强 (波动>3%)
        if wave1 < p1.price * 0.03:
            return None
        
        current_price = prices[-1]
        
        if direction_up:
            if current_price < p3.price * 0.98:
                return None
            target = current_price + wave1 * 1.618  # 优化: 浪3通常延长
            atr_stop = self.atr_stop_mult * atr
            stop_loss = max(p1.price * 0.99, current_price - atr_stop)
        else:
            if current_price > p3.price * 1.02:
                return None
            target = current_price - wave1 * 1.618
            atr_stop = self.atr_stop_mult * atr
            stop_loss = min(p1.price * 1.01, current_price + atr_stop)
        
        # 优化: 置信度加权
        confidence = 0.5
        if 0.382 <= retrace <= 0.5:  # 最优回撤区域
            confidence += 0.25
        elif 0.5 < retrace <= 0.618:
            confidence += 0.1
        if p3.strength >= 3:
            confidence += 0.1
        if wave1 > p1.price * 0.05:  # 强浪1
            confidence += 0.1
        
        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_2,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(confidence, 0.85),
            direction='up' if direction_up else 'down',
            detection_method='enhanced',
            pivot_count=len(pivots),
            wave_structure={'wave1': wave1, 'retrace': retrace}
        )
    
    def _detect_wave4_standard(self, pivots: List[PivotPoint], prices: np.ndarray, 
                               atr: float) -> Optional[UnifiedWaveSignal]:
        """标准4浪检测 (需要4个极值点)"""
        if len(pivots) < 4:
            return None
        
        p1 = pivots[-4]
        p2 = pivots[-3]
        p3 = pivots[-2]
        p4 = pivots[-1]
        
        wave1 = abs(p2.price - p1.price)
        wave2 = abs(p3.price - p2.price)
        wave3 = abs(p4.price - p3.price)
        
        if wave1 < p1.price * self.min_wave_pct:
            return None
        
        direction_up = p2.price > p1.price
        
        # 验证推动浪结构
        if direction_up:
            if not (p2.price > p1.price and p3.price < p2.price and 
                    p3.price > p1.price and p4.price > p3.price):
                return None
        else:
            if not (p2.price < p1.price and p3.price > p2.price and 
                    p3.price < p1.price and p4.price < p3.price):
                return None
        
        w2_retrace = wave2 / wave1
        if w2_retrace > self.max_wave2_retrace:
            return None
        
        if wave3 < wave1 * 0.8:
            return None
        
        current_price = prices[-1]
        wave4_sofar = abs(current_price - p4.price)
        w4_retrace = wave4_sofar / wave3 if wave3 > 0 else 1
        
        if direction_up:
            if current_price >= p4.price or current_price <= p3.price:
                return None
        else:
            if current_price <= p4.price or current_price >= p3.price:
                return None
        
        if w4_retrace > self.max_wave4_retrace:
            return None
        
        # ATR动态止损
        atr_stop = self.atr_stop_mult * atr
        
        if direction_up:
            target = current_price + wave1
            stop_loss = max(min(current_price * 0.98, p3.price * 0.99), current_price - atr_stop)
        else:
            target = current_price - wave1
            stop_loss = min(max(current_price * 1.02, p3.price * 1.01), current_price + atr_stop)
        
        confidence = 0.5
        if 0.382 <= w2_retrace <= 0.5:
            confidence += 0.15
        if 0.2 <= w4_retrace <= 0.382:
            confidence += 0.2
        elif 0.382 < w4_retrace <= 0.5:
            confidence += 0.1
        if wave3 > wave1 * 1.5:
            confidence += 0.1
        if p4.strength >= 3:
            confidence += 0.1
        
        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_4,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(confidence, 0.9),
            direction='up' if direction_up else 'down',
            detection_method='enhanced',
            pivot_count=len(pivots),
            wave_structure={'wave1': wave1, 'wave2_retrace': w2_retrace, 'wave4_retrace': w4_retrace}
        )
    
    def _detect_wave4_inferred(self, pivots: List[PivotPoint], prices: np.ndarray, 
                               atr: float, df: pd.DataFrame) -> Optional[UnifiedWaveSignal]:
        """
        推断4浪检测 - 简化版
        
        核心逻辑:
        1. 有1-2浪结构 (3个极值点)
        2. 从浪2终点后有上涨(上升)或下跌(下降)形成浪3
        3. 当前价格从浪3高点/低点回撤中
        """
        if len(pivots) < 3:
            return None
        
        p1 = pivots[-3]
        p2 = pivots[-2] 
        p3 = pivots[-1]
        
        wave1 = abs(p2.price - p1.price)
        wave2 = abs(p3.price - p2.price)
        
        if wave1 < p1.price * self.min_wave_pct:
            return None
        
        direction_up = p2.price > p1.price
        
        # 验证1-2浪结构
        if direction_up:
            if not (p1.price < p3.price < p2.price):
                return None
        else:
            if not (p1.price > p3.price > p2.price):
                return None
        
        w2_retrace = wave2 / wave1
        # 修复: 放宽到61.8%以便检测到更多4浪
        if w2_retrace > 0.618:
            return None
        
        current_price = prices[-1]
        
        # 简化: 从p3之后找最高/最低点作为推断的浪3终点
        prices_after_p3 = prices[p3.idx:]
        if len(prices_after_p3) < 3:
            return None
        
        if direction_up:
            high_idx = np.argmax(prices_after_p3)
            high_price = prices_after_p3[high_idx]
            
            # 浪3必须存在 (从p3上涨)
            if high_price <= p3.price * 1.01:
                return None
            
            inferred_wave3 = high_price - p3.price
            if inferred_wave3 < wave1 * 0.5:
                return None
            
            # 当前在回撤中 (价格低于高点)
            if current_price >= high_price * 0.99:
                return None
            
            wave4_sofar = high_price - current_price
            w4_retrace = wave4_sofar / inferred_wave3
            
            # 回撤不能太深 (不能破p3)
            if current_price <= p3.price:
                return None
                
        else:
            low_idx = np.argmin(prices_after_p3)
            low_price = prices_after_p3[low_idx]
            
            if low_price >= p3.price * 0.99:
                return None
            
            inferred_wave3 = p3.price - low_price
            if inferred_wave3 < wave1 * 0.5:
                return None
            
            if current_price <= low_price * 1.01:
                return None
            
            wave4_sofar = current_price - low_price
            w4_retrace = wave4_sofar / inferred_wave3
            
            if current_price >= p3.price:
                return None
        
        # 放宽回撤限制到50%，提高检测率
        if w4_retrace > 0.50 or w4_retrace < 0.05:
            return None
        
        atr_stop = self.atr_stop_mult * atr
        
        if direction_up:
            target = current_price + wave1
            stop_loss = max(p3.price * 0.98, current_price - atr_stop)
        else:
            target = current_price - wave1
            stop_loss = min(p3.price * 1.02, current_price + atr_stop)
        
        # 置信度计算
        confidence = 0.5
        if 0.382 <= w2_retrace <= 0.5:
            confidence += 0.1
        if 0.20 <= w4_retrace <= 0.382:
            confidence += 0.15
        if inferred_wave3 > wave1:
            confidence += 0.1
        
        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_4,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(confidence, 0.85),
            direction='up' if direction_up else 'down',
            detection_method='inferred',
            pivot_count=len(pivots),
            wave_structure={'wave1': wave1, 'w2_retrace': w2_retrace, 
                           'inferred_wave3': inferred_wave3, 'w4_retrace': w4_retrace}
        )
    
    def get_best_signal(self, df: pd.DataFrame, min_confidence: float = 0.5) -> Optional[UnifiedWaveSignal]:
        """获取最佳信号"""
        signals = self.detect(df, mode='all')
        for sig in signals:
            if sig.confidence >= min_confidence:
                return sig
        return None


# 便捷函数
def detect_waves(df: pd.DataFrame, **kwargs) -> List[UnifiedWaveSignal]:
    """检测所有波浪信号"""
    analyzer = UnifiedWaveAnalyzer(**kwargs)
    return analyzer.detect(df, mode='all')


def detect_wave_by_type(df: pd.DataFrame, wave_type: str, **kwargs) -> Optional[UnifiedWaveSignal]:
    """检测特定类型波浪"""
    analyzer = UnifiedWaveAnalyzer(**kwargs)
    signals = analyzer.detect(df, mode=wave_type)
    return signals[0] if signals else None


if __name__ == "__main__":
    from data import get_stock_data
    
    print("🧪 统一波浪分析器 - 优化版测试")
    print("=" * 70)
    
    test_stocks = [
        ('600519', '茅台'),
        ('000858', '五粮液'),
        ('600600', '青岛啤酒'),
    ]
    
    analyzer = UnifiedWaveAnalyzer()
    
    for symbol, name in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        df['date'] = pd.to_datetime(df['date'])
        
        all_signals = {'C': 0, '2': 0, '4': 0}
        inferred_4 = 0
        
        for i in range(60, len(df), 20):
            window_df = df.iloc[i-60:i].copy()
            signals = analyzer.detect(window_df, mode='all')
            
            for sig in signals:
                if sig.confidence >= 0.5:
                    all_signals[sig.entry_type.value] += 1
                    if sig.entry_type.value == '4' and sig.detection_method == 'inferred':
                        inferred_4 += 1
        
        print(f"\n{symbol} {name}:")
        print(f"  浪C信号: {all_signals['C']} 次")
        print(f"  浪2信号: {all_signals['2']} 次")
        print(f"  浪4信号: {all_signals['4']} 次 (推断: {inferred_4})")
    
    print("\n✅ 测试完成")
