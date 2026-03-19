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

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

try:
    from .adaptive_params import AdaptiveParameterOptimizer, MarketCondition
    from .elliott_wave import WaveDirection, WaveType
    from .enhanced_detector import PivotPoint, enhanced_pivot_detection
    from .entry_optimizer import WaveEntryOptimizer
    from .resonance import ResonanceAnalyzer, SignalDirection
except ImportError:
    from adaptive_params import AdaptiveParameterOptimizer, MarketCondition
    from elliott_wave import WaveDirection, WaveType
    from enhanced_detector import PivotPoint, enhanced_pivot_detection
    from entry_optimizer import WaveEntryOptimizer
    from resonance import ResonanceAnalyzer, SignalDirection


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
    wave_structure: dict | None = None

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

    # 量价优化评分 (新增)
    quality_score: float = 0.0
    volume_score: float = 0.0
    time_score: float = 0.0

    def __repr__(self):
        return f"WaveSignal({self.entry_type.value}, ¥{self.entry_price:.2f}, conf={self.confidence:.2f}, res={self.resonance_score:.2f}, quality={self.quality_score:.2f})"


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
                 adaptive_params: dict | None = None):

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

        # 量价优化器 (新增)
        self._entry_optimizer = WaveEntryOptimizer()
        self.use_quality_filter = True
        self.min_quality_score = 0.55  # 权重合计1.0，门槛0.55有效过滤劣质信号

        # 记录当前市场状态
        self._current_market_condition = MarketCondition.TRENDING

    def detect(self, df: pd.DataFrame, mode: str = 'all') -> list[UnifiedWaveSignal]:
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

        # prices 与 detect_df 对齐，避免独立调用时极值点索引引用到未来K线
        # _calculate_atr 和 current_price 仍用完整 df（不涉及极值点索引）
        prices = detect_df['close'].values
        current_price = df['close'].values[-1]  # noqa: F841
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

        # 步骤4.5: 量价优化 (新增)
        if self.use_quality_filter and signals:
            signals = self._apply_quality_optimization(signals, df, pivots)

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
        except Exception:
            pass  # 自适应失败则使用默认参数

    def _detect_market_condition(self, df: pd.DataFrame) -> MarketCondition:
        """检测当前市场状态"""
        try:
            from .adaptive_params import VolatilityAnalyzer
            vol_analysis = VolatilityAnalyzer.calculate_volatility_regime(df)
            return vol_analysis['market_condition']
        except Exception:
            return MarketCondition.TRENDING

    def _apply_resonance_analysis(self, signals: list[UnifiedWaveSignal],
                                   df: pd.DataFrame) -> list[UnifiedWaveSignal]:
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
                if sig.direction == 'up' and resonance_result.overall_direction in [SignalDirection.BULLISH, SignalDirection.NEUTRAL] or sig.direction == 'down' and resonance_result.overall_direction in [SignalDirection.BEARISH, SignalDirection.NEUTRAL] or sig.confidence >= 0.6:
                    validated_signals.append(sig)
            elif sig.confidence >= 0.6:  # 高置信度信号绕过共振过滤 (降低从0.7)
                validated_signals.append(sig)

        # 如果全部过滤，返回空列表（共振过滤应严格执行，避免噪声信号入场）
        if not validated_signals:
            return []

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

    def _apply_trend_filter(self, signals: list[UnifiedWaveSignal],
                           df: pd.DataFrame) -> list[UnifiedWaveSignal]:
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
            if sig.direction == 'up' and trend == 'up' or sig.direction == 'down' and trend == 'down':
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

    def _apply_quality_optimization(self, signals: list[UnifiedWaveSignal],
                                    df: pd.DataFrame,
                                    pivots: list) -> list[UnifiedWaveSignal]:
        """
        应用量价优化 - 针对C/2/4浪的不同特征进行质量评分

        新增步骤:
        1. C浪: 缩量调整+放量反弹确认
        2. 2浪: 缩量回撤+MACD金叉确认
        3. 4浪: 时间比例+波动率收缩确认
        """
        if not self._entry_optimizer or len(df) < 30:
            return signals

        optimized_signals = []
        entry_idx = len(df) - 1

        for sig in signals:
            try:
                if sig.entry_type.value == 'C':
                    # C浪优化 - 使用pivots的实际索引
                    # wave_a_idx 取 pivots[-4]（A浪真正起点），wave_b_idx 取 pivots[-3]（B浪起点/C浪终点前）
                    if len(pivots) >= 4 and sig.wave_structure:
                        wave_a_idx = pivots[-4].idx if hasattr(pivots[-4], 'idx') else max(0, len(df) - 20)
                        wave_b_idx = pivots[-2].idx if hasattr(pivots[-2], 'idx') else max(0, len(df) - 5)
                        quality = self._entry_optimizer.optimize_wave_c(
                            df, entry_idx,
                            wave_a_idx, wave_b_idx,
                            sig.confidence
                        )
                    elif len(pivots) >= 3 and sig.wave_structure:
                        # 只有3个极值点时，以 pivots[-3] 作为起点近似
                        wave_a_idx = pivots[-3].idx if hasattr(pivots[-3], 'idx') else max(0, len(df) - 20)
                        wave_b_idx = pivots[-2].idx if hasattr(pivots[-2], 'idx') else max(0, len(df) - 5)
                        quality = self._entry_optimizer.optimize_wave_c(
                            df, entry_idx,
                            wave_a_idx, wave_b_idx,
                            sig.confidence
                        )
                    else:
                        optimized_signals.append(sig)  # 无法优化时保留原信号
                        continue

                elif sig.entry_type.value == '2':
                    # 2浪优化
                    if len(pivots) >= 3 and sig.wave_structure:
                        wave1_start_idx = pivots[-3].idx if hasattr(pivots[-3], 'idx') else max(0, len(df) - 20)
                        wave1_end_idx = pivots[-2].idx if hasattr(pivots[-2], 'idx') else max(0, len(df) - 5)
                        quality = self._entry_optimizer.optimize_wave2(
                            df, entry_idx,
                            wave1_start_idx, wave1_end_idx,
                            sig.confidence
                        )
                    else:
                        optimized_signals.append(sig)  # 无法优化时保留原信号
                        continue

                elif sig.entry_type.value == '4':
                    # 4浪优化
                    if len(pivots) >= 4 and sig.wave_structure:
                        wave3_start_idx = pivots[-4].idx if hasattr(pivots[-4], 'idx') else max(0, len(df) - 25)
                        wave3_end_idx = pivots[-2].idx if hasattr(pivots[-2], 'idx') else max(0, len(df) - 5)
                        quality = self._entry_optimizer.optimize_wave4(
                            df, entry_idx,
                            wave3_start_idx, wave3_end_idx,
                            sig.confidence
                        )
                    else:
                        optimized_signals.append(sig)  # 无法优化时保留原信号
                        continue
                else:
                    optimized_signals.append(sig)
                    continue

                # 更新信号质量分数
                sig.quality_score = quality.final_score
                sig.volume_score = quality.volume_score
                sig.time_score = quality.time_score

                # 质量过滤
                if quality.final_score >= self.min_quality_score:
                    optimized_signals.append(sig)

            except Exception:
                # 优化失败保留原信号
                optimized_signals.append(sig)

        # 如果全部过滤，返回空列表（严格过滤）
        if not optimized_signals:
            return []

        return optimized_signals

    def _detect_wave_c(self, pivots: list[PivotPoint], prices: np.ndarray,
                       atr: float) -> UnifiedWaveSignal | None:
        """
        检测C浪结束信号 - 增强版

        关键改进:
        1. 验证前一浪是B浪(反弹) - 确保ABC调整结构完整
        2. 验证B浪特征: 从A浪低点反弹,但未创新高/低
        3. C浪长度检查,与推动浪区分
        """
        if len(pivots) < 3:
            return None

        # 需要至少4个点验证B浪前序
        if len(pivots) >= 4:
            p_before_a = pivots[-4]  # A浪前一点(推动浪结束点)
            p_a = pivots[-3]         # A浪终点(调整开始)
            p_b = pivots[-2]         # B浪终点(反弹结束)
            p_c = pivots[-1]         # C浪终点(当前)

            # 验证B浪结构:
            # 1. B浪是从A浪低点/高点的反弹,幅度为A浪的20%-100% (基于历史统计:平均17.7%,范围2.1%-98.7%)
            # 2. B浪高点/低点不应突破A浪起点(即推动浪终点)
            bounce_size = abs(p_b.price - p_a.price)
            a_size = abs(p_before_a.price - p_a.price) if p_before_a else bounce_size

            is_bounce_from_a = False
            b_within_range = False
            _b_wave_duration_ok = True  # 移除时间硬性要求,改为软性判断

            if a_size > 0:
                bounce_ratio = bounce_size / a_size
                # 放宽到20%-200% (原来38.2%-80%，后改为20%-100%)
                # B浪可以超过A浪幅度的100%（扩散平台型调整），极端情况下可达200%
                if 0.2 <= bounce_ratio <= 2.0:
                    is_bounce_from_a = True

            # B浪不应突破A浪起点
            if p_before_a:
                if p_a.is_peak and p_b.price < p_before_a.price or not p_a.is_peak and p_b.price > p_before_a.price:
                    b_within_range = True
            else:
                b_within_range = True  # 无前序数据时默认通过

            # 计算B浪时间(软性判断,不硬性过滤)
            try:
                from datetime import datetime
                d_b_start = datetime.strptime(str(p_a.date)[:10], '%Y-%m-%d')
                d_b_end = datetime.strptime(str(p_b.date)[:10], '%Y-%m-%d')
                b_duration = (d_b_end - d_b_start).days
                # 时间不作为硬性门槛,只记录用于置信度加权
                _b_wave_duration_ok = b_duration >= 0  # 只要求时间合理(非负)
            except Exception:
                b_duration = 0

            # B浪验证: 幅度验证通过即可,时间仅影响置信度
            b_wave_valid = is_bounce_from_a and b_within_range
        else:
            p_a = pivots[-3]
            p_b = pivots[-2]
            p_c = pivots[-1]
            b_wave_valid = False  # 无足够数据验证

        # A-C同方向 (调整浪特征)
        ac_same_direction = (p_a.price < p_b.price and p_b.price > p_c.price) or \
                           (p_a.price > p_b.price and p_b.price < p_c.price)

        if not ac_same_direction:
            return None

        wave_a = abs(p_b.price - p_a.price)
        wave_c = abs(p_c.price - p_b.price)

        if wave_a < p_a.price * self.min_wave_pct:
            return None

        # C浪长度检查: 调整浪的C浪通常与A浪相近或更长
        if wave_c < wave_a * 0.5:
            return None

        current_price = prices[-1]
        direction_up = p_c.price > p_b.price

        # ATR动态止损
        atr_stop = self.atr_stop_mult * atr

        if direction_up:
            target = current_price + wave_a * 1.0  # C浪目标 = 1.0×A浪（ZigZag理论标准，原0.618过于保守）
            stop_loss = max(p_c.price * 0.97, current_price - atr_stop)
        else:
            target = current_price - wave_a * 1.0  # C浪目标 = 1.0×A浪
            stop_loss = min(p_c.price * 1.03, current_price + atr_stop)

        confidence = 0.3  # 基础分降至0.3，需通过验证项积累才能达到0.5+阈值
        if wave_c >= wave_a * 0.8:
            confidence += 0.1
        if p_c.strength >= 3:
            confidence += 0.1
        # C浪长于A浪，更可能是真调整浪结束
        if wave_c >= wave_a:
            confidence += 0.1
        # B浪验证奖励(基于修正后的宽松条件)
        if b_wave_valid:
            confidence += 0.15  # 幅度和范围验证通过,加分
            # B浪时间软性加权
            if b_duration < 3:
                confidence -= 0.05  # 短B浪轻微惩罚
            elif b_duration > 15:
                confidence += 0.05  # 长期B浪加分(历史统计显示长期B浪后续表现更好)
        else:
            confidence -= 0.1   # B浪验证失败,减分
        # 4个点以上可以更好验证结构,加分
        if len(pivots) >= 4:
            confidence += 0.05

        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_C,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(max(confidence, 0.3), 0.9),
            direction='up' if direction_up else 'down',
            detection_method='enhanced_context_v2',
            pivot_count=len(pivots),
            wave_structure={'wave_a': wave_a, 'wave_c': wave_c, 'b_duration': b_duration if len(pivots) >= 4 else 0, 'b_wave_valid': b_wave_valid}
        )

    def _detect_wave2(self, pivots: list[PivotPoint], prices: np.ndarray,
                      atr: float) -> UnifiedWaveSignal | None:
        """
        检测2浪回撤信号 - 增强版

        关键改进:
        1. 验证前一浪是1浪(推动上涨) - 确保12345结构
        2. 浪1特征: 从低位启动,幅度足够,时间合理
        3. 收紧回撤区间至38.2%-50%
        """
        if len(pivots) < 3:
            return None

        # 需要4个点验证完整的浪1-2结构
        if len(pivots) >= 4:
            p0 = pivots[-4]  # 浪1起点前(可能是前一浪结束或底部)
            p1_start = pivots[-3]  # 浪1起点
            p1_end = pivots[-2]    # 浪1终点 = 浪2起点
            p2_end = pivots[-1]    # 浪2终点 = 当前点

            # 验证浪1是推动浪(从低位启动)
            wave1 = abs(p1_end.price - p1_start.price)
            direction_up = p1_end.price > p1_start.price

            # 浪1特征验证:
            # 1. 浪1应该从相对低位/高位启动 (放宽条件: 允许平盘启动)
            # 原逻辑过于严格，导致下跌方向的2浪无法通过验证
            wave1_valid_start = True  # 默认通过，取消严格的启动点验证

            # 可选: 宽松的启动点验证 (偏离不超过10%)
            if direction_up:
                # 上涨时，p0不应远高于p1_start (允许平盘或略高)
                wave1_valid_start = p0.price <= p1_start.price * 1.10
            else:
                # 下跌时，p0不应远低于p1_start (允许平盘或略低)
                wave1_valid_start = p0.price >= p1_start.price * 0.90

            # 2. 浪1幅度足够(>2% - 放宽从3%)
            wave1_strong = wave1 >= p1_start.price * 0.02

            # 3. 浪1时间(软性判断,不作为硬性门槛)
            try:
                from datetime import datetime
                d1 = datetime.strptime(str(p1_start.date)[:10], '%Y-%m-%d')
                d2 = datetime.strptime(str(p1_end.date)[:10], '%Y-%m-%d')
                wave1_duration = (d2 - d1).days
                # 时间仅用于置信度加权,不作为硬性过滤
                _wave1_valid_time = wave1_duration >= 0  # 只要求合理(非负)
            except Exception:
                wave1_duration = 0
                _wave1_valid_time = True  # 无法解析日期时默认通过

            # 浪1验证: 启动点和幅度验证通过即可,时间仅影响置信度
            wave1_valid = wave1_valid_start and wave1_strong
        else:
            # 只有3个极值点: 尝试推断1浪结构
            p1_start = pivots[-3]
            p1_end = pivots[-2]
            p2_end = pivots[-1]
            wave1 = abs(p1_end.price - p1_start.price)
            direction_up = p1_end.price > p1_start.price

            # 推断模式: 只验证幅度(>2%)，不验证启动点
            wave1_strong = wave1 >= p1_start.price * 0.02
            wave1_valid = wave1_strong  # 推断模式下只要求幅度足够
            wave1_duration = 0

        if wave1 < p1_start.price * self.min_wave_pct:
            return None

        # 验证浪2结构: 回撤在浪1范围内
        if direction_up:
            if not (p1_start.price < p2_end.price < p1_end.price):
                return None
        else:
            if not (p1_start.price > p2_end.price > p1_end.price):
                return None

        wave2 = abs(p2_end.price - p1_end.price)
        retrace = wave2 / wave1

        # 收紧回撤区间至38.2%-50% (最优区域)
        if not (self.min_retrace <= retrace <= self.max_wave2_retrace):
            return None

        # 浪1应该足够强 (波动>2% - 与验证逻辑保持一致)
        if wave1 < p1_start.price * 0.02:
            return None

        current_price = prices[-1]

        if direction_up:
            if current_price < p2_end.price * 0.98:
                return None
            target = current_price + wave1 * 1.618  # 浪3通常延长
            atr_stop = self.atr_stop_mult * atr
            stop_loss = max(p1_start.price * 0.99, current_price - atr_stop)
        else:
            if current_price > p2_end.price * 1.02:
                return None
            target = current_price - wave1 * 1.618
            atr_stop = self.atr_stop_mult * atr
            stop_loss = min(p1_start.price * 1.01, current_price + atr_stop)

        # 置信度加权
        confidence = 0.3  # 基础分降至0.3，需通过验证项积累才能达到0.5+阈值
        if 0.382 <= retrace <= 0.5:  # 最优回撤区域
            confidence += 0.2
        elif 0.5 < retrace <= 0.618:
            confidence += 0.1
        if p2_end.strength >= 3:
            confidence += 0.1
        if wave1 > p1_start.price * 0.05:  # 强浪1
            confidence += 0.1
        # 浪1验证奖励/惩罚(基于修正后的宽松条件)
        if wave1_valid:
            confidence += 0.15  # 浪1结构正确,大幅加分
            # 浪1时间软性加权
            if wave1_duration < 3:
                confidence -= 0.03  # 短浪1轻微惩罚(仅3.2%影响)
            elif wave1_duration > 20:
                confidence += 0.03  # 长期浪1加分
        else:
            confidence -= 0.1   # 浪1结构存疑,减分
        # 4个点以上可以验证完整结构
        if len(pivots) >= 4:
            confidence += 0.05

        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_2,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(max(confidence, 0.3), 0.9),
            direction='up' if direction_up else 'down',
            detection_method='enhanced_context_v2',
            pivot_count=len(pivots),
            wave_structure={'wave1': wave1, 'retrace': retrace, 'wave1_valid': wave1_valid, 'wave1_duration': wave1_duration}
        )

    def _detect_wave4_standard(self, pivots: list[PivotPoint], prices: np.ndarray,
                               atr: float) -> UnifiedWaveSignal | None:
        """
        标准4浪检测 - 增强版 (需要4个极值点)

        关键改进:
        1. 验证前面是完整的1-2-3浪结构
        2. 浪3特征: 幅度最大(通常>浪1),时间足够
        3. 浪3幅度验证: 不能是最短浪
        """
        if len(pivots) < 4:
            return None

        # 需要5个点验证完整的1-2-3-4结构
        if len(pivots) >= 5:
            p0 = pivots[-5]          # 浪1起点前(前一浪结束或底部)
            p1 = pivots[-4]          # 浪1起点
            p2 = pivots[-3]          # 浪2终点 = 浪1终点
            p3 = pivots[-2]          # 浪3终点 = 浪4起点
            p4 = pivots[-1]          # 浪4终点 = 当前

            wave1 = abs(p2.price - p1.price)
            wave2 = abs(p3.price - p2.price)  # 这里p3是浪3起点,需要重新理解
            # 实际上: p1(1起点)->p2(2起点)->p3(3起点)->p4(4起点)
            # 但极值点应该是: p1(低点)->p2(高点)->p3(低点)->p4(高点)->p5(低点)
            # 所以重新映射

            # 正确的推动浪极值点序列 (上涨):
            # p1=低点(1起点), p2=高点(1终点=2起点), p3=低点(2终点=3起点), p4=高点(3终点=4起点), p5=低点(4终点)

            # 重新计算
            wave1 = abs(p2.price - p1.price)
            wave2 = abs(p3.price - p2.price)
            wave3 = abs(p4.price - p3.price)

            direction_up = p2.price > p1.price

            # 验证浪3是推动浪(幅度最大,不能是最短)
            # 规则: 浪3通常是最长的,至少不能比浪1短
            wave3_is_strongest = wave3 >= wave1 * 1.1  # 浪3比浪1长10%以上
            wave3_not_shortest = wave3 >= wave1 * 0.8   # 浪3不能比浪1短太多

            # 验证浪3时间足够(至少3天)
            try:
                from datetime import datetime
                d3_start = datetime.strptime(str(p3.date)[:10], '%Y-%m-%d')
                d3_end = datetime.strptime(str(p4.date)[:10], '%Y-%m-%d')
                wave3_duration = (d3_end - d3_start).days
                _wave3_valid_time = wave3_duration >= 3
            except Exception:
                _wave3_valid_time = True

            # 验证1-2浪结构合理
            w2_retrace = wave2 / wave1 if wave1 > 0 else 1
            wave2_valid = w2_retrace <= self.max_wave2_retrace

            # 浪1起点验证(从相对低位启动)
            wave1_valid_start = False
            if direction_up and p0.price < p1.price or not direction_up and p0.price > p1.price:
                wave1_valid_start = True

            # 整体123结构验证
            wave123_valid = wave1_valid_start and wave2_valid and wave3_not_shortest
        else:
            p1 = pivots[-4]
            p2 = pivots[-3]
            p3 = pivots[-2]
            p4 = pivots[-1]

            wave1 = abs(p2.price - p1.price)
            wave2 = abs(p3.price - p2.price)
            wave3 = abs(p4.price - p3.price)
            direction_up = p2.price > p1.price
            wave123_valid = False
            wave3_is_strongest = wave3 >= wave1

        if wave1 < p1.price * self.min_wave_pct:
            return None

        # 验证推动浪结构
        if direction_up:
            if not (p2.price > p1.price and p3.price < p2.price and
                    p3.price > p1.price and p4.price > p3.price):
                return None
        else:
            if not (p2.price < p1.price and p3.price > p2.price and
                    p3.price < p1.price and p4.price < p3.price):
                return None

        # 浪2回撤检查
        w2_retrace = wave2 / wave1
        if w2_retrace > self.max_wave2_retrace:
            return None

        # 浪3幅度检查 - 不能是最短浪
        if wave3 < wave1 * 0.8:
            return None

        current_price = prices[-1]
        wave4_sofar = abs(current_price - p4.price)
        w4_retrace = wave4_sofar / wave3 if wave3 > 0 else 1

        # 浪4回撤范围检查
        if direction_up:
            if current_price >= p4.price or current_price <= p3.price:
                return None
        else:
            if current_price <= p4.price or current_price >= p3.price:
                return None

        # 浪4回撤不应超过浪3的50%
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

        # 置信度加权
        confidence = 0.3  # 基础分降至0.3，需通过验证项积累才能达到0.5+阈值
        if 0.382 <= w2_retrace <= 0.5:
            confidence += 0.1
        if 0.2 <= w4_retrace <= 0.382:
            confidence += 0.15
        elif 0.382 < w4_retrace <= 0.5:
            confidence += 0.1
        if wave3 > wave1 * 1.5:
            confidence += 0.1
        if p4.strength >= 3:
            confidence += 0.1
        # 123浪结构验证奖励
        if wave123_valid:
            confidence += 0.2  # 完整123结构,大幅加分
        if wave3_is_strongest:
            confidence += 0.1  # 浪3是最强浪,加分
        # 5个点以上可以验证完整1234结构
        if len(pivots) >= 5:
            confidence += 0.05

        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.WAVE_4,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(max(confidence, 0.3), 0.9),
            direction='up' if direction_up else 'down',
            detection_method='enhanced_context',
            pivot_count=len(pivots),
            wave_structure={
                'wave1': wave1,
                'wave2_retrace': w2_retrace,
                'wave4_retrace': w4_retrace,
                'wave123_valid': wave123_valid,
                'wave3_is_strongest': wave3_is_strongest
            }
        )

    def _detect_wave4_inferred(self, pivots: list[PivotPoint], prices: np.ndarray,
                               atr: float, df: pd.DataFrame) -> UnifiedWaveSignal | None:
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
        confidence = 0.3  # 基础分降至0.3，需通过验证项积累才能达到0.5+阈值
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

    def get_best_signal(self, df: pd.DataFrame, min_confidence: float = 0.5) -> UnifiedWaveSignal | None:
        """获取最佳信号"""
        signals = self.detect(df, mode='all')
        for sig in signals:
            if sig.confidence >= min_confidence:
                return sig
        return None


# 便捷函数
def detect_waves(df: pd.DataFrame, **kwargs) -> list[UnifiedWaveSignal]:
    """检测所有波浪信号"""
    analyzer = UnifiedWaveAnalyzer(**kwargs)
    return analyzer.detect(df, mode='all')


def detect_wave_by_type(df: pd.DataFrame, wave_type: str, **kwargs) -> UnifiedWaveSignal | None:
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
