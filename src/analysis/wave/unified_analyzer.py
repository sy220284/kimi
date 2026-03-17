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
    from .resonance import ResonanceAnalyzer, SignalDirection
    from .adaptive_params import AdaptiveParameterOptimizer, MarketCondition
except ImportError:
    from enhanced_detector import enhanced_pivot_detection, PivotPoint, label_wave_numbers
    from elliott_wave import WavePattern, WavePoint, WaveType, WaveDirection
    from resonance import ResonanceAnalyzer, SignalDirection
    from adaptive_params import AdaptiveParameterOptimizer, MarketCondition


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
    
    # 共振分析结果 (新增)
    resonance_score: float = 0.0
    resonance_direction: str = "neutral"
    tech_aligned: bool = False
    
    # 市场状态 (新增)
    market_condition: str = "unknown"
    
    def __repr__(self):
        return f"WaveSignal({self.entry_type.value}, ¥{self.entry_price:.2f}, conf={self.confidence:.2f}, res={self.resonance_score:.2f})"


class UnifiedWaveAnalyzer:
    """
    统一波浪分析器 - 集成优化版
    
    集成功能:
    1. 浪4检测支持3极值点推断模式
    2. 浪C/2区分使用推动浪前序验证
    3. 趋势过滤后置，避免过度过滤
    4. ATR动态止损替代固定止损
    5. 多指标共振验证 (MACD/RSI/量价)
    6. 自适应参数优化 (根据市场状态)
    """
    
    def __init__(self,
                 # 极值点检测参数
                 atr_period: int = 10,
                 atr_mult: float = 0.5,
                 min_pivots: int = 3,
                 
                 # 波浪检测参数
                 min_wave_pct: float = 0.015,
                 max_wave2_retrace: float = 0.50,
                 max_wave4_retrace: float = 0.50,
                 min_retrace: float = 0.382,
                 
                 # 信号过滤
                 min_confidence: float = 0.5,
                 use_trend_filter: bool = True,
                 trend_ma_period: int = 200,  # 优化: 改为200日均线
                 
                 # ATR止损参数
                 atr_stop_mult: float = 2.0,
                 
                 # 共振分析 (新增)
                 use_resonance: bool = True,
                 min_resonance_score: float = 0.3,
                 
                 # 自适应参数 (新增)
                 use_adaptive_params: bool = False,
                 
                 # 便捷模式: 传入自适应参数覆盖手动设置
                 adaptive_params: Optional[Dict] = None):
        
        # 如果使用自适应参数，优先采用
        if adaptive_params:
            self.atr_period = adaptive_params.get('atr_period', atr_period)
            self.atr_mult = adaptive_params.get('atr_mult', atr_mult)
            self.min_pivots = adaptive_params.get('min_pivots', min_pivots)
            self.min_wave_pct = adaptive_params.get('min_wave_pct', min_wave_pct)
            self.min_confidence = adaptive_params.get('confidence_threshold', min_confidence)
            self.use_adaptive_params = False  # 已应用，不再动态调整
        else:
            self.atr_period = atr_period
            self.atr_mult = atr_mult
            self.min_pivots = min_pivots
            self.min_wave_pct = min_wave_pct
            self.min_confidence = min_confidence
            self.use_adaptive_params = use_adaptive_params
        
        self.max_wave2_retrace = max_wave2_retrace
        self.max_wave4_retrace = max_wave4_retrace
        self.min_retrace = min_retrace
        
        self.use_trend_filter = use_trend_filter
        self.trend_ma_period = trend_ma_period  # 200日均线
        
        self.atr_stop_mult = atr_stop_mult
        
        # 共振分析设置
        self.use_resonance = use_resonance
        self.min_resonance_score = min_resonance_score
        self._resonance_analyzer = ResonanceAnalyzer() if use_resonance else None
        
        # 记录当前市场状态
        self._current_market_condition = MarketCondition.TRENDING
    
    def detect(self, df: pd.DataFrame, mode: str = 'all') -> List[UnifiedWaveSignal]:
        """
        检测波浪买入信号 - 集成优化版
        
        流程:
        1. 自适应参数优化 (如启用)
        2. 极值点检测
        3. 波浪检测 (C/2/4)
        4. 共振分析验证
        5. 趋势过滤后置
        6. ATR动态止损计算
        """
        if len(df) < 60:
            return []
        
        # 步骤1: 自适应参数优化
        if self.use_adaptive_params:
            self._apply_adaptive_params(df)
        
        # 检测市场状态
        self._current_market_condition = self._detect_market_condition(df)
        
        signals = []
        
        # 步骤2: 极值点检测
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
        atr = self._calculate_atr(df)
        
        # 步骤3: 检测各浪型
        if mode in ['all', 'C'] and len(pivots) >= 3:
            sig = self._detect_wave_c(pivots, prices, atr)
            if sig:
                signals.append(sig)
        
        if mode in ['all', '2'] and len(pivots) >= 3:
            sig = self._detect_wave2(pivots, prices, atr)
            if sig:
                signals.append(sig)
        
        if mode in ['all', '4']:
            sig = None
            if len(pivots) >= 4:
                sig = self._detect_wave4_standard(pivots, prices, atr)
            if sig is None:
                sig = self._detect_wave4_inferred(pivots, prices, atr, df)
            if sig:
                signals.append(sig)
        
        # 步骤4: 共振分析验证
        if self.use_resonance and signals:
            signals = self._apply_resonance_analysis(signals, df)
        
        # 步骤5: 趋势过滤后置
        if self.use_trend_filter and signals:
            signals = self._apply_trend_filter(signals, df)
        
        # 添加市场状态信息
        for sig in signals:
            sig.market_condition = self._current_market_condition.value
        
        signals.sort(key=lambda x: (x.confidence + x.resonance_score) / 2, reverse=True)
        return signals
    
    def _apply_adaptive_params(self, df: pd.DataFrame):
        """应用自适应参数"""
        try:
            adaptive = AdaptiveParameterOptimizer.optimize(df)
            self.atr_period = adaptive.atr_period
            self.atr_mult = adaptive.atr_mult
            self.min_confidence = adaptive.confidence_threshold
        except:
            pass  # 自适应失败则使用默认参数
    
    def _detect_market_condition(self, df: pd.DataFrame) -> MarketCondition:
        """检测当前市场状态"""
        try:
            from .adaptive_params import VolatilityAnalyzer
            vol_analysis = VolatilityAnalyzer.calculate_volatility_regime(df)
            return vol_analysis['market_condition']
        except:
            return MarketCondition.TRENDING
    
    def _apply_resonance_analysis(self, signals: List[UnifiedWaveSignal], 
                                   df: pd.DataFrame) -> List[UnifiedWaveSignal]:
        """
        应用共振分析验证信号
        
        整合波浪信号与技术指标(MACD/RSI/量价)的一致性
        """
        if not self._resonance_analyzer:
            return signals
        
        validated_signals = []
        
        for sig in signals:
            # 构建临时波浪信号对象供共振分析器使用
            class TempWaveSignal:
                pass
            
            temp_signal = TempWaveSignal()
            temp_signal.signal_type = 'buy' if sig.direction == 'up' else 'sell'
            temp_signal.confidence = sig.confidence
            
            # 创建临时pattern
            class TempPattern:
                pass
            temp_pattern = TempPattern()
            temp_pattern.wave_type = WaveType.CORRECTIVE if sig.entry_type.value == 'C' else WaveType.IMPULSE
            temp_pattern.direction = WaveDirection.UP if sig.direction == 'up' else WaveDirection.DOWN
            temp_signal.wave_pattern = temp_pattern
            
            # 执行共振分析
            resonance_result = self._resonance_analyzer.analyze(df, temp_signal)
            
            # 更新信号
            sig.resonance_score = abs(resonance_result.weighted_score)
            sig.resonance_direction = resonance_result.overall_direction.value
            sig.tech_aligned = resonance_result.wave_aligned
            
            # 过滤：共振分数低于阈值且方向不一致的信号
            if sig.resonance_score >= self.min_resonance_score:
                # 方向检查：买入信号需要共振看涨或中性
                if sig.direction == 'up' and resonance_result.overall_direction in [SignalDirection.BULLISH, SignalDirection.NEUTRAL]:
                    validated_signals.append(sig)
                elif sig.direction == 'down' and resonance_result.overall_direction in [SignalDirection.BEARISH, SignalDirection.NEUTRAL]:
                    validated_signals.append(sig)
                elif sig.confidence >= 0.6:  # 高置信度信号保留 (降低从0.7)
                    validated_signals.append(sig)
            elif sig.confidence >= 0.6:  # 高置信度信号绕过共振过滤 (降低从0.7)
                validated_signals.append(sig)
        
        # 如果全部过滤，返回原信号
        if not validated_signals:
            return signals
            
        return validated_signals
    
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
        后置趋势过滤 - 使用200日均线
        
        趋势判断: 价格 vs 200日均线 (长期趋势)
        """
        if len(df) < self.trend_ma_period:
            return signals
        
        ma200 = df['close'].rolling(self.trend_ma_period).mean().iloc[-1]
        current_price = df['close'].iloc[-1]
        
        # 200日均线趋势判断
        if current_price > ma200 * 1.05:
            trend = 'up'
        elif current_price < ma200 * 0.95:
            trend = 'down'
        else:
            trend = 'neutral'
        
        filtered = []
        for sig in signals:
            # 买入信号应与趋势一致
            if sig.direction == 'up' and trend == 'up':
                sig.trend_aligned = True
                sig.trend_direction = trend
                filtered.append(sig)
            elif sig.direction == 'down' and trend == 'down':
                sig.trend_aligned = True
                sig.trend_direction = trend
                filtered.append(sig)
            elif trend == 'neutral':
                # 震荡市中，高置信度信号保留
                if sig.confidence >= 0.5 or getattr(sig, 'resonance_score', 0) >= 0.4:
                    sig.trend_aligned = True
                    sig.trend_direction = trend
                    filtered.append(sig)
                else:
                    # 低置信度信号也保留，但标记为不对齐
                    sig.trend_aligned = False
                    sig.trend_direction = trend
                    filtered.append(sig)
            elif sig.confidence >= 0.75:  # 极高置信度信号可逆势
                sig.trend_aligned = False
                sig.trend_direction = trend
                filtered.append(sig)
        
        # 如果全部过滤，返回原信号（不过滤）
        if not filtered:
            for sig in signals:
                sig.trend_aligned = False
                sig.trend_direction = trend
            return signals
            
        return filtered
    
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
