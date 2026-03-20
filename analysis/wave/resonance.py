"""
多指标共振分析器 - 波浪 + 技术指标交叉验证
Phase 2: 提高信号可靠性
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd


class SignalDirection(Enum):
    """信号方向"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class IndicatorSignal:
    """单个指标信号"""
    name: str
    direction: SignalDirection
    strength: float  # 0-1
    description: str
    confidence: float  # 0-1


@dataclass
class ResonanceResult:
    """共振分析结果"""
    overall_direction: SignalDirection
    overall_strength: float
    weighted_score: float  # -1 to 1
    signals: list[IndicatorSignal]
    wave_aligned: bool
    tech_aligned: bool
    conflicts: list[str]
    recommendation: str


class MACDAnalyzer:
    """MACD指标分析器"""

    @staticmethod
    def calculate(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD指标"""
        df = df.copy()

        # EMA
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()

        # MACD Line
        df['macd'] = ema_fast - ema_slow

        # Signal Line
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()

        # Histogram
        df['macd_hist'] = df['macd'] - df['macd_signal']

        return df

    @staticmethod
    def analyze_signal(df: pd.DataFrame, lookback: int = 5) -> IndicatorSignal:
        """
        分析MACD信号

        Returns:
            IndicatorSignal
        """
        if len(df) < 30:
            return IndicatorSignal(
                name="MACD",
                direction=SignalDirection.NEUTRAL,
                strength=0.0,
                description="数据不足",
                confidence=0.0
            )

        # 计算MACD
        df = MACDAnalyzer.calculate(df)

        # 取最近数据
        recent = df.tail(lookback)
        latest = recent.iloc[-1]
        prev = recent.iloc[-2] if len(recent) > 1 else recent.iloc[-1]

        macd_val = latest['macd']
        signal_val = latest['macd_signal']
        _hist_val = latest['macd_hist']

        # 判断方向
        direction = SignalDirection.NEUTRAL
        strength = 0.0
        description = ""

        # 金叉/死叉
        if prev['macd'] < prev['macd_signal'] and macd_val > signal_val:
            direction = SignalDirection.BULLISH
            strength = 0.7
            description = "MACD金叉形成"
        elif prev['macd'] > prev['macd_signal'] and macd_val < signal_val:
            direction = SignalDirection.BEARISH
            strength = 0.7
            description = "MACD死叉形成"
        elif macd_val > signal_val:
            direction = SignalDirection.BULLISH
            strength = 0.4
            description = "MACD在零轴上方"
        elif macd_val < signal_val:
            direction = SignalDirection.BEARISH
            strength = 0.4
            description = "MACD在零轴下方"

        # 零轴判断
        if macd_val > 0 and direction == SignalDirection.BULLISH:
            strength += 0.2
            description += "，且位于零轴之上"
        elif macd_val < 0 and direction == SignalDirection.BEARISH:
            strength += 0.2
            description += "，且位于零轴之下"

        # 背离检测
        price_trend = df['close'].iloc[-10:].pct_change().sum()
        macd_trend = df['macd'].iloc[-10:].sum()

        if price_trend > 0 and macd_trend < 0:
            description += "，注意顶背离风险"
            strength *= 0.8
        elif price_trend < 0 and macd_trend > 0:
            description += "，注意底背离机会"
            strength *= 1.2

        return IndicatorSignal(
            name="MACD",
            direction=direction,
            strength=min(1.0, strength),
            description=description,
            confidence=0.75 if direction != SignalDirection.NEUTRAL else 0.5
        )


class RSIAnalyzer:
    """RSI指标分析器"""

    @staticmethod
    def calculate(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算RSI指标"""
        df = df.copy()

        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        return df

    @staticmethod
    def analyze_signal(df: pd.DataFrame, period: int = 14,
                       overbought: float = 70, oversold: float = 30) -> IndicatorSignal:
        """分析RSI信号"""
        if len(df) < period + 5:
            return IndicatorSignal(
                name="RSI",
                direction=SignalDirection.NEUTRAL,
                strength=0.0,
                description="数据不足",
                confidence=0.0
            )

        df = RSIAnalyzer.calculate(df, period)
        rsi_val = df['rsi'].iloc[-1]
        rsi_prev = df['rsi'].iloc[-2]

        direction = SignalDirection.NEUTRAL
        strength = 0.0
        description = f"RSI={rsi_val:.1f}"

        # 超买/超卖
        if rsi_val > overbought:
            direction = SignalDirection.BEARISH
            strength = min(1.0, (rsi_val - overbought) / 20)
            description += "，超买区域"
        elif rsi_val < oversold:
            direction = SignalDirection.BULLISH
            strength = min(1.0, (oversold - rsi_val) / 20)
            description += "，超卖区域"

        # 突破
        if rsi_prev <= oversold and rsi_val > oversold:
            direction = SignalDirection.BULLISH
            strength = 0.8
            description = "RSI突破超卖线，买入信号"
        elif rsi_prev >= overbought and rsi_val < overbought:
            direction = SignalDirection.BEARISH
            strength = 0.8
            description = "RSI跌破超买线，卖出信号"

        # 中性区域判断趋势
        if direction == SignalDirection.NEUTRAL:
            if rsi_val > 50:
                direction = SignalDirection.BULLISH
                strength = (rsi_val - 50) / 50 * 0.5
            else:
                direction = SignalDirection.BEARISH
                strength = (50 - rsi_val) / 50 * 0.5

        return IndicatorSignal(
            name="RSI",
            direction=direction,
            strength=strength,
            description=description,
            confidence=0.7 if rsi_val < oversold or rsi_val > overbought else 0.5
        )


class VolumeAnalyzer:
    """成交量分析器"""

    @staticmethod
    def analyze_signal(df: pd.DataFrame, lookback: int = 20) -> IndicatorSignal:
        """分析成交量信号"""
        if 'volume' not in df.columns or len(df) < lookback:
            return IndicatorSignal(
                name="Volume",
                direction=SignalDirection.NEUTRAL,
                strength=0.0,
                description="无成交量数据",
                confidence=0.0
            )

        recent_vol = df['volume'].tail(5).mean()
        avg_vol = df['volume'].tail(lookback).mean()

        price_change = df['close'].iloc[-1] / df['close'].iloc[-5] - 1

        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        direction = SignalDirection.NEUTRAL
        strength = 0.0
        description = f"成交量比: {vol_ratio:.1f}x"

        # 量价配合
        if vol_ratio > 1.5 and price_change > 0:
            direction = SignalDirection.BULLISH
            strength = min(1.0, (vol_ratio - 1) / 2)
            description += "，放量上涨"
        elif vol_ratio > 1.5 and price_change < 0:
            direction = SignalDirection.BEARISH
            strength = min(1.0, (vol_ratio - 1) / 2)
            description += "，放量下跌"
        elif vol_ratio < 0.7 and abs(price_change) < 0.02:
            description += "，缩量整理"
            strength = 0.2

        return IndicatorSignal(
            name="Volume",
            direction=direction,
            strength=strength,
            description=description,
            confidence=0.6
        )


class KDJAnalyzer:
    """KDJ随机指标分析器 — A股散户常用，权重提升至1.0"""

    @staticmethod
    def calculate(df: pd.DataFrame, k_period: int = 9,
                  d_period: int = 3, j_period: int = 3) -> pd.DataFrame:
        """计算KDJ指标 (RSV → K → D → J)"""
        df = df.copy()
        n = k_period
        low_n  = df['low'].rolling(n, min_periods=1).min()
        high_n = df['high'].rolling(n, min_periods=1).max()
        rsv = (df['close'] - low_n) / (high_n - low_n + 1e-12) * 100
        df['kdj_k'] = rsv.ewm(com=d_period - 1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=d_period - 1, adjust=False).mean()
        df['kdj_j'] = j_period * df['kdj_k'] - (j_period - 1) * df['kdj_d']
        return df

    @staticmethod
    def analyze_signal(df: pd.DataFrame,
                       oversold: float = 20.0,
                       overbought: float = 80.0) -> 'IndicatorSignal':
        """分析KDJ信号：超买/超卖/金叉/死叉"""
        if len(df) < 15:
            return IndicatorSignal(name="KDJ", direction=SignalDirection.NEUTRAL,
                                   strength=0.0, description="数据不足", confidence=0.0)

        df = KDJAnalyzer.calculate(df)
        k = df['kdj_k'].iloc[-1]
        d = df['kdj_d'].iloc[-1]
        j = df['kdj_j'].iloc[-1]
        k_prev = df['kdj_k'].iloc[-2]
        d_prev = df['kdj_d'].iloc[-2]

        direction = SignalDirection.NEUTRAL
        strength = 0.0
        confidence = 0.7

        # 金叉（K上穿D）
        if k_prev <= d_prev and k > d:
            if k < oversold:          # 超卖区金叉，最强买入
                direction = SignalDirection.BULLISH
                strength = 1.0
                desc = f"KDJ超卖金叉({k:.1f})"
            elif k < 50:
                direction = SignalDirection.BULLISH
                strength = 0.7
                desc = f"KDJ金叉({k:.1f})"
            else:
                direction = SignalDirection.BULLISH
                strength = 0.4
                desc = f"KDJ高位金叉({k:.1f})，谨慎"
        # 死叉（K下穿D）
        elif k_prev >= d_prev and k < d:
            if k > overbought:        # 超买区死叉，最强卖出
                direction = SignalDirection.BEARISH
                strength = 1.0
                desc = f"KDJ超买死叉({k:.1f})"
            elif k > 50:
                direction = SignalDirection.BEARISH
                strength = 0.7
                desc = f"KDJ死叉({k:.1f})"
            else:
                direction = SignalDirection.BEARISH
                strength = 0.4
                desc = f"KDJ低位死叉({k:.1f})"
        # 极端值
        elif j < 0:
            direction = SignalDirection.BULLISH
            strength = 0.8
            desc = f"J值极低({j:.1f})，超卖"
        elif j > 100:
            direction = SignalDirection.BEARISH
            strength = 0.8
            desc = f"J值极高({j:.1f})，超买"
        else:
            desc = f"KDJ中性(K={k:.1f},D={d:.1f})"

        return IndicatorSignal(name="KDJ", direction=direction,
                               strength=strength, description=desc,
                               confidence=confidence)


class ResonanceAnalyzer:
    """共振分析器 - 整合波浪 + 技术指标"""

    def __init__(self):
        self.macd_analyzer = MACDAnalyzer()
        self.rsi_analyzer = RSIAnalyzer()
        self.volume_analyzer = VolumeAnalyzer()
        self.kdj_analyzer = KDJAnalyzer()  # A3: KDJ权重1.0，与MACD并列最高

    def analyze(self, df: pd.DataFrame, wave_signal: Any = None) -> ResonanceResult:
        """
        综合分析所有指标

        Args:
            df: 价格数据
            wave_signal: 波浪分析信号 (可选)

        Returns:
            ResonanceResult
        """
        return self._analyze_internal(df, wave_signal, precomputed=False)

    def analyze_precomputed(self, df: pd.DataFrame, wave_signal: Any = None) -> ResonanceResult:
        """
        OPT-1: 快速路径 — df 已包含预计算指标列（macd/rsi/kdj_k/volume）时调用。
        跳过各子分析器内部的重复 calculate()，直接读列值，节省 ~40% 耗时。

        前提：df 中需包含以下列（由 TechnicalIndicators.calculate_all 生成）：
            macd, macd_signal, macd_hist, rsi, kdj_k, kdj_d, kdj_j, volume
        若列缺失，自动降级为完整路径 analyze()。
        """
        _cols = set(df.columns)
        # TechnicalIndicators 输出大写 (MACD/RSI14/K), Resonance内部输出小写 (macd/rsi)
        has_precomputed = (
            {'MACD', 'MACD_Signal', 'MACD_Histogram', 'RSI14', 'K', 'D'}.issubset(_cols) or
            {'macd', 'macd_signal', 'macd_hist', 'rsi', 'kdj_k', 'kdj_d'}.issubset(_cols)
        )
        if not has_precomputed:
            return self._analyze_internal(df, wave_signal, precomputed=False)
        return self._analyze_internal(df, wave_signal, precomputed=True)

    def _analyze_internal(self, df: pd.DataFrame, wave_signal: Any,
                          precomputed: bool) -> ResonanceResult:
        """内部通用实现，precomputed=True 时跳过各子分析器内的重复计算"""
        signals = []

        if precomputed:
            # 直接从已有列读值，构造 IndicatorSignal
            macd_signal = self._macd_signal_from_df(df)
            rsi_signal  = self._rsi_signal_from_df(df)
            kdj_signal  = self.kdj_analyzer.analyze_signal(df)  # KDJ 已在 df 中
            vol_signal  = self.volume_analyzer.analyze_signal(df)
        else:
            macd_signal = self.macd_analyzer.analyze_signal(df)
            rsi_signal  = self.rsi_analyzer.analyze_signal(df)
            kdj_signal  = self.kdj_analyzer.analyze_signal(df)
            vol_signal  = self.volume_analyzer.analyze_signal(df)

        signals.extend([macd_signal, rsi_signal, vol_signal, kdj_signal])

        # 波浪信号 (如果有)
        wave_direction = SignalDirection.NEUTRAL
        wave_strength = 0.0
        if wave_signal:
            if wave_signal.signal_type in ['buy', 'strong_buy']:
                wave_direction = SignalDirection.BULLISH
                wave_strength = wave_signal.confidence
            elif wave_signal.signal_type in ['sell', 'strong_sell']:
                wave_direction = SignalDirection.BEARISH
                wave_strength = wave_signal.confidence

            signals.append(IndicatorSignal(
                name="ElliottWave",
                direction=wave_direction,
                strength=wave_strength,
                description=f"波浪{wave_signal.wave_pattern.wave_type.value}信号",
                confidence=wave_signal.confidence
            ))

        # 计算综合得分
        bullish_score = 0.0
        bearish_score = 0.0
        total_weight = 0.0

        weights = {
            'MACD': 1.0,
            'RSI': 0.8,
            'KDJ': 1.0,      # A3: A股散户最常用，与MACD并列最高
            'Volume': 0.6,
            'ElliottWave': 1.2  # 波浪权重最高
        }

        conflicts = []

        for sig in signals:
            weight = weights.get(sig.name, 0.5) * sig.confidence

            if sig.direction == SignalDirection.BULLISH:
                bullish_score += sig.strength * weight
            elif sig.direction == SignalDirection.BEARISH:
                bearish_score += sig.strength * weight

            total_weight += weight

        # 判断方向
        net_score = (bullish_score - bearish_score) / total_weight if total_weight > 0 else 0.0

        if net_score > 0.3:
            overall_direction = SignalDirection.BULLISH
            overall_strength = min(1.0, net_score)
        elif net_score < -0.3:
            overall_direction = SignalDirection.BEARISH
            overall_strength = min(1.0, abs(net_score))
        else:
            overall_direction = SignalDirection.NEUTRAL
            overall_strength = 0.3

        # 检测冲突
        wave_aligned = True
        tech_aligned = True

        if wave_signal:
            tech_bullish = sum(1 for s in signals if s.name != 'ElliottWave' and s.direction == SignalDirection.BULLISH)
            tech_bearish = sum(1 for s in signals if s.name != 'ElliottWave' and s.direction == SignalDirection.BEARISH)

            if wave_direction == SignalDirection.BULLISH and tech_bearish > tech_bullish:
                conflicts.append("波浪看涨但技术指标看跌")
                wave_aligned = False
            elif wave_direction == SignalDirection.BEARISH and tech_bullish > tech_bearish:
                conflicts.append("波浪看跌但技术指标看涨")
                wave_aligned = False

        # 生成建议
        recommendation = self._generate_recommendation(
            overall_direction, overall_strength,
            wave_aligned, tech_aligned, conflicts
        )

        return ResonanceResult(
            overall_direction=overall_direction,
            overall_strength=overall_strength,
            weighted_score=net_score,
            signals=signals,
            wave_aligned=wave_aligned,
            tech_aligned=tech_aligned,
            conflicts=conflicts,
            recommendation=recommendation
        )

    def _generate_recommendation(
        self,
        direction: SignalDirection,
        strength: float,
        wave_aligned: bool,
        tech_aligned: bool,
        conflicts: list[str]
    ) -> str:
        """生成交易建议"""
        if conflicts:
            return f"⚠️ 信号冲突: {conflicts[0]}，建议观望"

        if direction == SignalDirection.BULLISH:
            if strength > 0.7:
                return "🟢 强烈买入 - 多指标共振看涨"
            elif strength > 0.4:
                return "📈 买入 - 整体趋势向上"
            else:
                return "👀 偏多看涨，但力度较弱"

        elif direction == SignalDirection.BEARISH:
            if strength > 0.7:
                return "🔴 强烈卖出 - 多指标共振看跌"
            elif strength > 0.4:
                return "📉 卖出 - 整体趋势向下"
            else:
                return "👀 偏空看跌，但力度较弱"

        else:
            return "⚖️ 中性 - 多空力量均衡，观望"

    # ── OPT-1: 预计算指标快速路径辅助方法 ──────────────────────────────
    def _macd_signal_from_df(self, df: 'pd.DataFrame') -> IndicatorSignal:
        """从已有 MACD 列直接读取（支持大/小写列名），跳过重新计算"""
        import pandas as _pd
        # 统一：优先大写列名 (TechnicalIndicators), 降级小写 (Resonance内部)
        _c = df.columns
        mc  = 'MACD'           if 'MACD'           in _c else 'macd'
        msc = 'MACD_Signal'    if 'MACD_Signal'    in _c else 'macd_signal'
        mhc = 'MACD_Histogram' if 'MACD_Histogram' in _c else 'macd_hist'
        if mc not in _c or len(df) < 5:
            return IndicatorSignal(name='MACD', direction=SignalDirection.NEUTRAL,
                                   strength=0.0, description='无MACD数据', confidence=0.0)
        latest = df.iloc[-1]; prev = df.iloc[-2] if len(df) >= 2 else latest
        macd_val   = float(latest.get(mc, 0))
        signal_val = float(latest.get(msc, 0))
        prev_macd  = float(prev.get(mc, 0))
        prev_sig   = float(prev.get(msc, 0))
        hist       = float(latest.get(mhc, 0))
        direction = SignalDirection.NEUTRAL; strength = 0.0; desc = f'MACD={macd_val:.3f}'
        if prev_macd < prev_sig and macd_val > signal_val:
            direction = SignalDirection.BULLISH; strength = 0.7; desc = 'MACD金叉'
        elif prev_macd > prev_sig and macd_val < signal_val:
            direction = SignalDirection.BEARISH; strength = 0.7; desc = 'MACD死叉'
        elif hist > 0:
            direction = SignalDirection.BULLISH; strength = min(0.6, abs(hist) * 5)
        elif hist < 0:
            direction = SignalDirection.BEARISH; strength = min(0.6, abs(hist) * 5)
        return IndicatorSignal(name='MACD', direction=direction, strength=strength,
                               description=desc, confidence=0.8)

    def _rsi_signal_from_df(self, df: 'pd.DataFrame',
                             overbought: float = 70, oversold: float = 30) -> IndicatorSignal:
        """从已有 RSI 列直接读取（支持大/小写列名），跳过重新计算"""
        # 大写 RSI14 (TechnicalIndicators) 或小写 rsi (Resonance内部)
        rsi_col = 'RSI14' if 'RSI14' in df.columns else ('rsi' if 'rsi' in df.columns else None)
        if rsi_col is None or len(df) < 2:
            return IndicatorSignal(name='RSI', direction=SignalDirection.NEUTRAL,
                                   strength=0.0, description='无RSI数据', confidence=0.0)
        rsi_val  = float(df[rsi_col].iloc[-1])
        rsi_prev = float(df[rsi_col].iloc[-2])
        direction = SignalDirection.NEUTRAL; strength = 0.0; desc = f'RSI={rsi_val:.1f}'
        if rsi_val > overbought:
            direction = SignalDirection.BEARISH; strength = min(1.0,(rsi_val-overbought)/20); desc += '，超买'
        elif rsi_val < oversold:
            direction = SignalDirection.BULLISH; strength = min(1.0,(oversold-rsi_val)/20); desc += '，超卖'
        elif rsi_prev <= oversold < rsi_val:
            direction = SignalDirection.BULLISH; strength = 0.8; desc = 'RSI突破超卖'
        elif rsi_prev >= overbought > rsi_val:
            direction = SignalDirection.BEARISH; strength = 0.8; desc = 'RSI跌破超买'
        elif rsi_val > 50:
            direction = SignalDirection.BULLISH; strength = (rsi_val-50)/50*0.5
        else:
            direction = SignalDirection.BEARISH; strength = (50-rsi_val)/50*0.5
        conf = 0.7 if (rsi_val < oversold or rsi_val > overbought) else 0.5
        return IndicatorSignal(name='RSI', direction=direction, strength=strength,
                               description=desc, confidence=conf)
