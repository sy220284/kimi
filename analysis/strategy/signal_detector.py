"""
analysis/strategy/signal_detector.py — A股多风格信号检测器

新增信号类型（补充原有4种）：
  短线信号：
    LIMIT_UP_FOLLOW  涨停次日跟进（A股连板效应）
    GAP_UP_BREAKOUT  跳空缺口突破（高开带量）
    MA_GOLDEN_CROSS  均线金叉（MA5上穿MA20）
    INTRADAY_SURGE   日内急涨（量价齐升）
  波段信号：
    SWING_BREAKOUT   波段突破（价格突破近20日平台）
    PULLBACK_MA      回踩均线支撑（MA20/MA60附近止跌）
    VOLUME_DIVERGE   量价背离（价跌量缩，蓄势）
    BAND_RANGE       布林带收口突破
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class ExtendedSignalType(Enum):
    """扩展信号类型（含原有4种 + 新增8种）"""
    # 原有（中线）
    MOMENTUM_BREAKOUT  = "momentum_breakout"
    PULLBACK_ENTRY     = "pullback_entry"
    VOLUME_SURGE       = "volume_surge"
    TREND_CONTINUATION = "trend_continuation"
    # 短线
    LIMIT_UP_FOLLOW    = "limit_up_follow"    # 涨停次日跟进
    GAP_UP_BREAKOUT    = "gap_up_breakout"    # 跳空高开突破
    MA_GOLDEN_CROSS    = "ma_golden_cross"    # 均线金叉
    INTRADAY_SURGE     = "intraday_surge"     # 日内急涨
    # 波段
    SWING_BREAKOUT     = "swing_breakout"     # 平台突破
    PULLBACK_MA        = "pullback_ma"        # 回踩均线
    VOLUME_DIVERGENCE  = "volume_divergence"  # 量价背离（缩量止跌）
    BOLLINGER_BREAKOUT = "bollinger_breakout" # 布林带突破


@dataclass
class DetectedSignal:
    """检测到的信号"""
    signal_type:  ExtendedSignalType
    strength:     float          # 0-1 信号强度
    description:  str
    details:      dict[str, Any] = field(default_factory=dict)


class AShareSignalDetector:
    """
    A股多风格信号检测器

    用法::
        detector = AShareSignalDetector()
        signals = detector.detect_all(df, style='short_term')
        best = detector.get_best_signal(signals)
    """

    def __init__(
        self,
        # 涨停阈值
        limit_up_pct:    float = 0.095,   # 主板9.5%
        limit_up_pct_kc: float = 0.195,   # 科创板/创业板19.5%
        # 缺口参数
        gap_min_pct:     float = 0.02,    # 最小跳空幅度2%
        # 均线参数
        ma_fast:  int = 5,
        ma_slow:  int = 20,
        ma_trend: int = 60,
        # 平台突破
        platform_days:   int   = 20,      # 平台判断天数
        platform_range:  float = 0.08,    # 平台最大振幅8%
        # 布林带
        bb_period: int   = 20,
        bb_std:    float = 2.0,
    ):
        self.limit_up_pct    = limit_up_pct
        self.limit_up_pct_kc = limit_up_pct_kc
        self.gap_min_pct     = gap_min_pct
        self.ma_fast         = ma_fast
        self.ma_slow         = ma_slow
        self.ma_trend        = ma_trend
        self.platform_days   = platform_days
        self.platform_range  = platform_range
        self.bb_period       = bb_period
        self.bb_std          = bb_std

    # ─────────────────────────────────────────────
    # 主接口
    # ─────────────────────────────────────────────

    def detect_all(
        self,
        df: pd.DataFrame,
        style: str = "swing",
        symbol: str = "",
    ) -> list[DetectedSignal]:
        """
        检测所有适合该风格的信号。

        Args:
            df:     含 date/open/high/low/close/volume 的 DataFrame
            style:  'short_term' / 'swing' / 'medium_term'
            symbol: 股票代码（用于判断涨停阈值）
        """
        if len(df) < 30:
            return []

        df = df.copy().sort_values("date").reset_index(drop=True)

        # 判断涨停幅度
        prefix = symbol[:3] if symbol else ""
        limit_pct = self.limit_up_pct_kc if prefix in ("688","300","301") \
                    else self.limit_up_pct

        signals: list[DetectedSignal] = []

        if style == "short_term":
            signals += self._detect_short_term(df, limit_pct)
        elif style == "swing":
            signals += self._detect_swing(df)
        elif style == "medium_term":
            signals += self._detect_medium_term(df)
        else:
            signals += self._detect_short_term(df, limit_pct)
            signals += self._detect_swing(df)

        # 按强度降序
        signals.sort(key=lambda s: s.strength, reverse=True)
        return signals

    def get_best_signal(
        self, signals: list[DetectedSignal], min_strength: float = 0.5
    ) -> DetectedSignal | None:
        """返回最强信号（超过最低强度阈值）"""
        for s in signals:
            if s.strength >= min_strength:
                return s
        return None

    # ─────────────────────────────────────────────
    # 短线信号
    # ─────────────────────────────────────────────

    def _detect_short_term(
        self, df: pd.DataFrame, limit_pct: float
    ) -> list[DetectedSignal]:
        signals = []
        c = df["close"].values.astype(float)
        o = df["open"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        v = df["volume"].values.astype(float)

        # ── 涨停次日跟进 ─────────────────────────
        sig = self._limit_up_follow(c, h, v, limit_pct)
        if sig: signals.append(sig)

        # ── 跳空缺口突破 ─────────────────────────
        sig = self._gap_up_breakout(c, o, h, v)
        if sig: signals.append(sig)

        # ── 均线金叉 ─────────────────────────────
        sig = self._ma_golden_cross(c, v)
        if sig: signals.append(sig)

        # ── 日内急涨 ─────────────────────────────
        sig = self._intraday_surge(c, h, l, v)
        if sig: signals.append(sig)

        return signals

    def _limit_up_follow(
        self, c: np.ndarray, h: np.ndarray,
        v: np.ndarray, limit_pct: float
    ) -> DetectedSignal | None:
        """涨停次日跟进：昨日涨停 + 今日高开（连板或封板效应）"""
        if len(c) < 3:
            return None

        # 昨日是否涨停
        yesterday_return = (c[-2] / c[-3] - 1) if len(c) >= 3 else 0
        was_limit_up = yesterday_return >= limit_pct * 0.95

        if not was_limit_up:
            return None

        # 今日开盘位置（高开至少0.5%）
        today_gap = (c[-1] / c[-2] - 1)
        if today_gap < 0.005:
            return None

        # 今日量能与涨停前基准量对比（跳过涨停日的超大量）
        # v[-2]是涨停日（量极大），v[-3:-2]是涨停前
        base_vol = float(np.mean(v[-5:-2]))  # 涨停前2-4天均量
        vol_ratio = float(v[-1]) / (base_vol + 1e-8)
        if vol_ratio < 1.0:   # 次日量不应低于涨停前均量
            return None

        strength = min(0.95, 0.60 + yesterday_return * 2 + (vol_ratio - 1.15) * 0.1)
        return DetectedSignal(
            signal_type=ExtendedSignalType.LIMIT_UP_FOLLOW,
            strength=round(strength, 3),
            description=f"昨日涨停({yesterday_return:.1%})，今日高开{today_gap:.1%}，量比{vol_ratio:.1f}x",
            details={"yesterday_return": round(yesterday_return, 3),
                     "today_gap": round(today_gap, 3),
                     "vol_ratio": round(vol_ratio, 2)},
        )

    def _gap_up_breakout(
        self, c: np.ndarray, o: np.ndarray,
        h: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """跳空高开突破：今日开盘 > 昨日最高，且成交量放大"""
        if len(c) < 5:
            return None

        gap = (o[-1] - h[-2]) / (h[-2] + 1e-8)
        if gap < self.gap_min_pct:
            return None

        # 量比
        vol_avg = float(np.mean(v[-6:-1]))
        vol_ratio = float(v[-1]) / (vol_avg + 1e-8)
        if vol_ratio < 1.5:
            return None

        # 收盘仍在缺口上方（未回补）
        if c[-1] < o[-1] * 0.98:
            return None

        strength = min(0.90, 0.50 + gap * 5 + (vol_ratio - 1.5) * 0.05)
        return DetectedSignal(
            signal_type=ExtendedSignalType.GAP_UP_BREAKOUT,
            strength=round(strength, 3),
            description=f"跳空高开{gap:.1%}，量比{vol_ratio:.1f}x，缺口未回补",
            details={"gap_pct": round(gap, 3), "vol_ratio": round(vol_ratio, 2)},
        )

    def _ma_golden_cross(
        self, c: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """均线金叉：MA5上穿MA20，且量能放大"""
        need = self.ma_slow + 5
        if len(c) < need:
            return None

        ma_fast_curr  = float(np.mean(c[-self.ma_fast:]))
        ma_fast_prev  = float(np.mean(c[-self.ma_fast-1:-1]))
        ma_slow_curr  = float(np.mean(c[-self.ma_slow:]))
        ma_slow_prev  = float(np.mean(c[-self.ma_slow-1:-1]))

        # 金叉：今日 MA_fast > MA_slow，昨日 MA_fast <= MA_slow
        is_cross = ma_fast_prev <= ma_slow_prev and ma_fast_curr > ma_slow_curr
        if not is_cross:
            return None

        # 量能确认（金叉时放量更可靠）
        vol_ratio = float(np.mean(v[-3:])) / (float(np.mean(v[-8:-3])) + 1e-8)
        if vol_ratio < 0.9:
            return None

        # 价格在MA20上方（多头环境）
        if c[-1] < ma_slow_curr * 0.99:
            return None

        strength = min(0.85, 0.60 + (vol_ratio - 1.0) * 0.15)
        return DetectedSignal(
            signal_type=ExtendedSignalType.MA_GOLDEN_CROSS,
            strength=round(strength, 3),
            description=f"MA{self.ma_fast}上穿MA{self.ma_slow}金叉，量比{vol_ratio:.1f}x",
            details={"ma_fast": round(ma_fast_curr, 2),
                     "ma_slow": round(ma_slow_curr, 2),
                     "vol_ratio": round(vol_ratio, 2)},
        )

    def _intraday_surge(
        self, c: np.ndarray, h: np.ndarray,
        l: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """日内急涨：今日涨幅 > 3%，且成交量为近期均量2倍以上"""
        if len(c) < 6:
            return None

        today_ret = (c[-1] / c[-2] - 1)
        if today_ret < 0.03:
            return None

        vol_ratio = float(v[-1]) / (float(np.mean(v[-6:-1])) + 1e-8)
        if vol_ratio < 1.5:
            return None

        # 收盘位置（收盘靠近最高更好）
        close_pos = (c[-1] - l[-1]) / (h[-1] - l[-1] + 1e-8)
        if close_pos < 0.5:  # 收盘低于日内中位，冲高回落
            return None

        strength = min(0.85, 0.50 + today_ret * 5 + (vol_ratio - 1.5) * 0.05)
        return DetectedSignal(
            signal_type=ExtendedSignalType.INTRADAY_SURGE,
            strength=round(strength, 3),
            description=f"日内急涨{today_ret:.1%}，量比{vol_ratio:.1f}x，收盘靠近高点",
            details={"today_ret": round(today_ret, 3),
                     "vol_ratio": round(vol_ratio, 2),
                     "close_position": round(close_pos, 2)},
        )

    # ─────────────────────────────────────────────
    # 波段信号
    # ─────────────────────────────────────────────

    def _detect_swing(self, df: pd.DataFrame) -> list[DetectedSignal]:
        signals = []
        c = df["close"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        v = df["volume"].values.astype(float)
        bb_up = df["BB_Upper"].values if "BB_Upper" in df.columns else None
        bb_lo = df["BB_Lower"].values if "BB_Lower" in df.columns else None

        for fn in [
            lambda: self._swing_breakout(c, h, v),
            lambda: self._pullback_ma(c, l, v),
            lambda: self._volume_divergence(c, v),
        ]:
            sig = fn()
            if sig: signals.append(sig)

        if bb_up is not None and bb_lo is not None:
            sig = self._bollinger_breakout(c, bb_up, bb_lo, v)
            if sig: signals.append(sig)

        return signals

    def _swing_breakout(
        self, c: np.ndarray, h: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """平台突破：近N日价格区间收窄后向上突破"""
        n = self.platform_days
        if len(c) < n + 5:
            return None

        platform_hi = float(np.max(h[-n-1:-1]))
        platform_lo = float(np.min(c[-n-1:-1]))
        platform_range = (platform_hi - platform_lo) / (platform_lo + 1e-8)

        # 平台收窄判断（振幅 < platform_range）
        if platform_range > self.platform_range * 1.5:  # 实际宽容1.5倍
            return None

        # 今日突破平台高点
        if c[-1] <= platform_hi * 1.005:
            return None

        vol_ratio = float(np.mean(v[-3:])) / (float(np.mean(v[-n:-3])) + 1e-8)
        if vol_ratio < 1.5:
            return None

        breakout_pct = (c[-1] - platform_hi) / (platform_hi + 1e-8)
        strength = min(0.92, 0.55 + breakout_pct * 10 + (vol_ratio - 1.5) * 0.08)
        return DetectedSignal(
            signal_type=ExtendedSignalType.SWING_BREAKOUT,
            strength=round(strength, 3),
            description=f"突破{n}日平台高点{platform_hi:.2f}，平台振幅{platform_range:.1%}，量比{vol_ratio:.1f}x",
            details={"platform_high": round(platform_hi, 2),
                     "platform_range": round(platform_range, 3),
                     "breakout_pct": round(breakout_pct, 3),
                     "vol_ratio": round(vol_ratio, 2)},
        )

    def _pullback_ma(
        self, c: np.ndarray, l: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """回踩均线支撑：价格从高点回调至MA20附近后止跌"""
        if len(c) < self.ma_slow + 5:
            return None

        ma20 = float(np.mean(c[-self.ma_slow:]))
        price = float(c[-1])
        dist = abs(price - ma20) / (ma20 + 1e-8)

        # 价格在MA20附近（±2%）
        if dist > 0.02:
            return None

        # 前5-10日有高点（说明是回调不是下跌趋势中）
        recent_high = float(np.max(c[-10:-1]))
        if recent_high < ma20 * 1.05:
            return None

        # 成交量缩量（缩量回调，主力未出货）
        vol_curr = float(np.mean(v[-3:]))
        vol_base = float(np.mean(v[-10:-3]))
        vol_shrink = vol_curr / (vol_base + 1e-8)
        if vol_shrink > 0.8:  # 未明显缩量
            return None

        # 近2日止跌（低点抬高）
        if l[-1] < l[-2]:
            return None

        strength = min(0.82, 0.55 + (0.02 - dist) * 10 + (0.8 - vol_shrink) * 0.2)
        return DetectedSignal(
            signal_type=ExtendedSignalType.PULLBACK_MA,
            strength=round(strength, 3),
            description=f"回踩MA{self.ma_slow}({ma20:.2f})附近止跌，缩量{vol_shrink:.1f}x，低点抬高",
            details={"ma20": round(ma20, 2), "dist_pct": round(dist, 3),
                     "vol_shrink": round(vol_shrink, 2)},
        )

    def _volume_divergence(
        self, c: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """
        量价背离（缩量止跌/蓄势）：
        价格下跌但成交量持续萎缩，意味着抛压减少，蓄势待发
        """
        if len(c) < 10:
            return None

        # 近5日价格下跌
        ret_5 = (c[-1] / c[-6] - 1)
        if ret_5 >= 0:
            return None

        # 但成交量持续萎缩（近5日量比前5日均量）
        vol_recent = float(np.mean(v[-5:]))
        vol_prior  = float(np.mean(v[-10:-5]))
        vol_ratio  = vol_recent / (vol_prior + 1e-8)
        if vol_ratio >= 0.65:  # 缩量不够明显
            return None

        # 价格跌幅不大（-3%~0%，轻微回调）
        if ret_5 < -0.05:
            return None

        # 均线仍多头排列
        if len(c) >= 20:
            ma5  = float(np.mean(c[-5:]))
            ma20 = float(np.mean(c[-20:]))
            if ma5 < ma20 * 0.99:
                return None

        strength = min(0.78, 0.50 + abs(ret_5) * 3 + (0.65 - vol_ratio) * 0.5)
        return DetectedSignal(
            signal_type=ExtendedSignalType.VOLUME_DIVERGENCE,
            strength=round(strength, 3),
            description=f"价格微跌{ret_5:.1%}但成交量萎缩{vol_ratio:.1f}x，量价背离蓄势",
            details={"ret_5d": round(ret_5, 3), "vol_ratio": round(vol_ratio, 2)},
        )

    def _bollinger_breakout(
        self, c: np.ndarray, bb_up: np.ndarray,
        bb_lo: np.ndarray, v: np.ndarray
    ) -> DetectedSignal | None:
        """布林带突破：价格从下轨附近反弹或突破上轨"""
        if len(c) < 5:
            return None

        price  = float(c[-1])
        bb_u   = float(bb_up[-1])
        bb_l   = float(bb_lo[-1])
        bb_mid = (bb_u + bb_l) / 2
        bb_w   = (bb_u - bb_l) / (bb_mid + 1e-8)  # 带宽

        # 场景A：价格突破上轨（强势信号）
        if price > bb_u and float(c[-2]) <= float(bb_up[-2]):
            vol_ratio = float(v[-1]) / (float(np.mean(v[-6:-1])) + 1e-8)
            if vol_ratio >= 1.3:
                strength = min(0.88, 0.60 + (price/bb_u - 1) * 10 + (vol_ratio-1.3)*0.05)
                return DetectedSignal(
                    signal_type=ExtendedSignalType.BOLLINGER_BREAKOUT,
                    strength=round(strength, 3),
                    description=f"突破布林上轨{bb_u:.2f}，带宽{bb_w:.2%}，量比{vol_ratio:.1f}x",
                    details={"bb_upper": round(bb_u, 2), "band_width": round(bb_w, 3),
                             "vol_ratio": round(vol_ratio, 2), "type": "upper_breakout"},
                )

        # 场景B：从下轨反弹（超卖反弹）
        if float(c[-2]) <= float(bb_lo[-2]) and price > float(bb_lo[-1]):
            strength = min(0.72, 0.52 + (price/bb_l - 1) * 5)
            return DetectedSignal(
                signal_type=ExtendedSignalType.BOLLINGER_BREAKOUT,
                strength=round(strength, 3),
                description=f"从布林下轨{bb_l:.2f}反弹",
                details={"bb_lower": round(bb_l, 2), "type": "lower_bounce"},
            )

        return None

    # ─────────────────────────────────────────────
    # 中线信号（复用波段+中线均线）
    # ─────────────────────────────────────────────

    def _detect_medium_term(self, df: pd.DataFrame) -> list[DetectedSignal]:
        c = df["close"].values.astype(float)
        v = df["volume"].values.astype(float)
        h = df["high"].values.astype(float)
        l = df["low"].values.astype(float)
        signals = []

        # 中线主要看60日突破
        n60 = min(60, len(h) - 1)
        if len(c) >= n60 + 5:
            hi60 = float(np.max(h[-n60-1:-1]))
            if c[-1] > hi60 and float(v[-1]) > float(np.mean(v[-20:-1])) * 1.5:
                signals.append(DetectedSignal(
                    signal_type=ExtendedSignalType.SWING_BREAKOUT,
                    strength=0.80,
                    description=f"突破60日新高{hi60:.2f}，量能放大",
                    details={"high_60d": round(hi60, 2)},
                ))

        # 均线多头排列且MA20上穿MA60
        if len(c) >= 65:
            ma20_curr = float(np.mean(c[-20:]))
            ma60_curr = float(np.mean(c[-60:]))
            ma20_prev = float(np.mean(c[-21:-1]))
            ma60_prev = float(np.mean(c[-61:-1]))
            if ma20_prev <= ma60_prev and ma20_curr > ma60_curr:
                signals.append(DetectedSignal(
                    signal_type=ExtendedSignalType.MA_GOLDEN_CROSS,
                    strength=0.75,
                    description=f"MA20({ma20_curr:.2f})上穿MA60({ma60_curr:.2f})，中线金叉",
                    details={"ma20": round(ma20_curr, 2), "ma60": round(ma60_curr, 2)},
                ))

        return signals
