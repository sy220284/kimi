"""
趋势跟踪模块 — analysis/wave/trend_follower.py

解决波浪策略在牛市踏空问题：
  - 波浪策略: 等待调整浪结束后买入（强调"等待完整结构"）
  - 趋势跟踪: 在强趋势中直接参与，不等调整（解决"单边牛市踏空"）

信号类型：
  TREND_PULLBACK  — 均线回调买入（趋势中的浅回调，类2浪）
  BREAKOUT        — 放量突破买入（创新高 + 量能确认）
  MA_CROSS        — 均线金叉买入（趋势刚确立）
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from analysis.wave.unified_analyzer import UnifiedWaveSignal, WaveEntryType


class TrendSignalType(Enum):
    TREND_PULLBACK = "trend_pullback"   # 趋势中回调 MA
    BREAKOUT       = "breakout"         # 放量突破新高
    MA_CROSS       = "ma_cross"         # 均线金叉


@dataclass
class TrendSignal:
    """趋势信号（可转换为 UnifiedWaveSignal）"""
    signal_type:  TrendSignalType
    entry_price:  float
    stop_loss:    float
    target_price: float
    confidence:   float
    direction:    str = "up"
    entry_idx:    int = 0
    detail:       dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.detail is None:
            self.detail = {}

    def to_wave_signal(self) -> UnifiedWaveSignal:
        """转换为 UnifiedWaveSignal，与波浪信号统一接口"""
        return UnifiedWaveSignal(
            is_valid=True,
            entry_type=WaveEntryType.UNKNOWN,      # 标记来源
            entry_price=self.entry_price,
            target_price=self.target_price,
            stop_loss=self.stop_loss,
            confidence=self.confidence,
            direction=self.direction,
            detection_method=self.signal_type.value,
            market_condition="trending",
            wave_structure=self.detail,
        )


class TrendFollower:
    """
    趋势跟踪信号生成器

    三种信号互补：
      1. TREND_PULLBACK: 趋势明确 + 回调到支撑均线 + 未破趋势
      2. BREAKOUT:       价格突破前高 + 量能显著放大 + 处于上升趋势
      3. MA_CROSS:       短期均线上穿长期均线（趋势初期确认）
    """

    def __init__(
        self,
        # 趋势判断
        trend_ma: int = 50,           # 趋势均线（上方=趋势向上）
        long_ma: int = 200,           # 长期均线（确认大趋势）
        # 回调信号参数
        pullback_ma: int = 20,        # 回调目标均线
        pullback_max_pct: float = 0.08,  # 最大允许回调幅度（牛市回调通常<8%）
        pullback_min_pct: float = 0.02,  # 最小有效回调（过浅不算）
        # 突破信号参数
        breakout_period: int = 20,    # 突破周期（N日新高）
        breakout_vol_mult: float = 1.5,  # 量能放大倍数（vs20日均量）
        # 均线金叉参数
        cross_fast: int = 5,          # 金叉快线
        cross_slow: int = 20,         # 金叉慢线
        # 共同参数
        atr_period: int = 14,
        stop_atr_mult: float = 2.0,   # 止损=入场下方 N×ATR
        reward_ratio: float = 2.5,    # 最低盈亏比
        min_confidence: float = 0.45, # 最低置信度（低于波浪策略门槛，牛市可适当放松）
    ):
        self.trend_ma = trend_ma
        self.long_ma = long_ma
        self.pullback_ma = pullback_ma
        self.pullback_max_pct = pullback_max_pct
        self.pullback_min_pct = pullback_min_pct
        self.breakout_period = breakout_period
        self.breakout_vol_mult = breakout_vol_mult
        self.cross_fast = cross_fast
        self.cross_slow = cross_slow
        self.atr_period = atr_period
        self.stop_atr_mult = stop_atr_mult
        self.reward_ratio = reward_ratio
        self.min_confidence = min_confidence

    # ────────────────────────────────────────────
    # 公开接口
    # ────────────────────────────────────────────

    def detect(
        self,
        df: pd.DataFrame,
        signal_types: list[str] | None = None,
    ) -> list[TrendSignal]:
        """
        检测趋势信号。

        Args:
            df:           含 date/open/high/low/close/volume 的 DataFrame
            signal_types: 指定检测类型 ['pullback','breakout','ma_cross']
                          None = 全部
        Returns:
            list[TrendSignal]，按置信度降序
        """
        if len(df) < max(self.long_ma, 50):
            return []

        df = df.copy().reset_index(drop=True)
        df = self._compute_features(df)
        wanted = set(signal_types) if signal_types else {"pullback", "breakout", "ma_cross"}

        signals: list[TrendSignal] = []

        if "pullback" in wanted:
            s = self._detect_pullback(df)
            if s: signals.append(s)

        if "breakout" in wanted:
            s = self._detect_breakout(df)
            if s: signals.append(s)

        if "ma_cross" in wanted:
            s = self._detect_ma_cross(df)
            if s: signals.append(s)

        signals = [s for s in signals if s.confidence >= self.min_confidence]
        signals.sort(key=lambda x: x.confidence, reverse=True)
        return signals

    # ────────────────────────────────────────────
    # 特征计算
    # ────────────────────────────────────────────

    def _compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        c = df["close"].values
        h = df["high"].values
        l = df["low"].values
        v = df["volume"].values

        df[f"ma{self.pullback_ma}"]  = pd.Series(c).rolling(self.pullback_ma).mean()
        df[f"ma{self.trend_ma}"]     = pd.Series(c).rolling(self.trend_ma).mean()
        df[f"ma{self.long_ma}"]      = pd.Series(c).rolling(self.long_ma).mean()
        df[f"ma{self.cross_fast}"]   = pd.Series(c).rolling(self.cross_fast).mean()
        df[f"ma{self.cross_slow}"]   = pd.Series(c).rolling(self.cross_slow).mean()
        df[f"mavol{self.breakout_period}"] = pd.Series(v).rolling(self.breakout_period).mean()

        # ATR
        tr = np.maximum(h - l,
             np.maximum(np.abs(h - np.roll(c, 1)),
                        np.abs(l - np.roll(c, 1))))
        df["atr"] = pd.Series(tr).rolling(self.atr_period).mean()

        # N日最高价（突破用）
        df[f"high{self.breakout_period}"] = pd.Series(h).rolling(self.breakout_period).max().shift(1)

        # 趋势强度（价格距离趋势均线的百分位）
        df["trend_pct"] = (pd.Series(c) - df[f"ma{self.trend_ma}"]) / df[f"ma{self.trend_ma}"]
        return df

    # ────────────────────────────────────────────
    # 信号1：趋势回调均线
    # ────────────────────────────────────────────

    def _detect_pullback(self, df: pd.DataFrame) -> TrendSignal | None:
        """
        条件（最后一根K线）：
          1. 价格 > MA{trend_ma} （趋势向上）
          2. 价格 > MA{long_ma}  （大趋势向上）
          3. 最近回调触及 MA{pullback_ma}
          4. 回调幅度在 [pullback_min, pullback_max] 之间
          5. 当日收盘反弹，站上 MA{pullback_ma}
        """
        last = len(df) - 1
        row = df.iloc[last]

        ma_p = row[f"ma{self.pullback_ma}"]
        ma_t = row[f"ma{self.trend_ma}"]
        ma_l = row[f"ma{self.long_ma}"]
        close = row["close"]
        low   = row["low"]
        atr   = row["atr"]

        if any(pd.isna([ma_p, ma_t, ma_l, atr])): return None

        # 趋势条件
        if close <= ma_t * 1.001: return None   # 价格须明显在趋势线上方
        if close <= ma_l * 0.995: return None   # 须在长期均线上方

        # 回调触及支撑
        recent_low = df["low"].iloc[max(0, last-5):last+1].min()
        recent_high = df["high"].iloc[max(0, last-20):last+1].max()

        pullback_pct = (recent_high - recent_low) / recent_high
        if pullback_pct < self.pullback_min_pct: return None
        if pullback_pct > self.pullback_max_pct: return None

        # 当前是否在回调位附近（低点接近MA）
        touch_ma = low <= ma_p * 1.02 and close > ma_p * 0.99
        if not touch_ma: return None

        # 计算置信度
        conf = self._pullback_confidence(df, last, pullback_pct)
        if conf < self.min_confidence: return None

        # 止损/目标
        stop = close - self.stop_atr_mult * atr
        stop = min(stop, ma_p * 0.97)     # 至少跌破 MA 3%才止损
        reward = (close - stop) * self.reward_ratio
        target = close + reward

        return TrendSignal(
            signal_type=TrendSignalType.TREND_PULLBACK,
            entry_price=close,
            stop_loss=max(stop, close * 0.85),
            target_price=target,
            confidence=conf,
            entry_idx=last,
            detail={
                "pullback_pct": round(pullback_pct, 3),
                "support_ma": self.pullback_ma,
                "ma_value": round(float(ma_p), 2),
                "trend_pct": round(float(row["trend_pct"]), 3),
            },
        )

    def _pullback_confidence(self, df: pd.DataFrame, idx: int, pullback_pct: float) -> float:
        """回调信号置信度评分"""
        row = df.iloc[idx]
        score = 0.40  # 基础分

        # 回调深度适中（3-5% 最佳）
        if 0.03 <= pullback_pct <= 0.06:
            score += 0.15
        elif 0.06 <= pullback_pct <= self.pullback_max_pct:
            score += 0.08

        # 趋势强度（距趋势线越近，趋势越健康）
        tp = abs(float(row["trend_pct"]))
        if 0.02 <= tp <= 0.10:
            score += 0.10
        elif tp > 0.10:
            score += 0.05  # 偏离太多可能已过热

        # 量能缩量回调（缩量回调 = 洗盘而非出货）
        vol_ma = row[f"mavol{self.breakout_period}"]
        if pd.notna(vol_ma) and vol_ma > 0:
            vol_ratio = row["volume"] / vol_ma
            if vol_ratio < 0.7:
                score += 0.15  # 明显缩量
            elif vol_ratio < 1.0:
                score += 0.08

        # RSI 在健康区间（40-60 回调后）
        if "RSI14" in df.columns:
            rsi = df["RSI14"].iloc[idx]
            if pd.notna(rsi) and 35 <= rsi <= 55:
                score += 0.10

        # MACD 未死叉
        if "MACD" in df.columns and "MACD_Signal" in df.columns:
            macd = df["MACD"].iloc[idx]
            sig  = df["MACD_Signal"].iloc[idx]
            if pd.notna(macd) and pd.notna(sig) and macd > sig:
                score += 0.10

        return min(score, 0.95)

    # ────────────────────────────────────────────
    # 信号2：放量突破新高
    # ────────────────────────────────────────────

    def _detect_breakout(self, df: pd.DataFrame) -> TrendSignal | None:
        """
        条件：
          1. 当日收盘 > 前N日最高价（突破）
          2. 成交量 > {breakout_vol_mult}× N日均量（量能确认）
          3. 价格在长期均线上方（大趋势向上）
          4. 突破幅度不过大（防追高）
        """
        last = len(df) - 1
        row = df.iloc[last]

        close = row["close"]
        vol   = row["volume"]
        atr   = row["atr"]
        high_n = row[f"high{self.breakout_period}"]
        vol_ma = row[f"mavol{self.breakout_period}"]
        ma_l   = row[f"ma{self.long_ma}"]

        if any(pd.isna([high_n, vol_ma, ma_l, atr])): return None
        if vol_ma <= 0: return None

        # 突破条件
        if close <= high_n: return None
        breakout_pct = (close - high_n) / high_n
        if breakout_pct > 0.05: return None  # 突破幅度超5%不追

        # 量能确认
        vol_ratio = vol / vol_ma
        if vol_ratio < self.breakout_vol_mult: return None

        # 大趋势向上
        if close < ma_l * 0.995: return None

        conf = self._breakout_confidence(df, last, vol_ratio, breakout_pct)
        if conf < self.min_confidence: return None

        stop = close - self.stop_atr_mult * atr
        stop = max(stop, float(high_n) * 0.98)  # 止损不低于突破位
        target = close + (close - stop) * self.reward_ratio

        return TrendSignal(
            signal_type=TrendSignalType.BREAKOUT,
            entry_price=close,
            stop_loss=max(stop, close * 0.85),
            target_price=target,
            confidence=conf,
            entry_idx=last,
            detail={
                "breakout_period": self.breakout_period,
                "breakout_pct": round(breakout_pct, 3),
                "vol_ratio": round(vol_ratio, 2),
                "prev_high": round(float(high_n), 2),
            },
        )

    def _breakout_confidence(self, df, idx, vol_ratio, breakout_pct) -> float:
        score = 0.40

        # 量能放大程度
        if vol_ratio >= 3.0:    score += 0.20
        elif vol_ratio >= 2.0:  score += 0.15
        elif vol_ratio >= 1.5:  score += 0.08

        # 突破幅度（小幅突破更可靠）
        if breakout_pct < 0.02: score += 0.12
        elif breakout_pct < 0.03: score += 0.08

        # 趋势加成
        row = df.iloc[idx]
        tp = float(row["trend_pct"]) if pd.notna(row["trend_pct"]) else 0
        if 0 < tp < 0.15: score += 0.10

        # MACD 多头排列
        if "MACD" in df.columns and "MACD_Signal" in df.columns:
            macd = df["MACD"].iloc[idx]
            sig  = df["MACD_Signal"].iloc[idx]
            if pd.notna(macd) and pd.notna(sig) and macd > sig > 0:
                score += 0.13

        return min(score, 0.95)

    # ────────────────────────────────────────────
    # 信号3：均线金叉
    # ────────────────────────────────────────────

    def _detect_ma_cross(self, df: pd.DataFrame) -> TrendSignal | None:
        """
        条件：
          1. 今日快线 > 慢线（金叉）
          2. 昨日快线 < 慢线（刚刚金叉）
          3. 价格在长期均线上方
        """
        if len(df) < 2: return None
        last = len(df) - 1
        cur  = df.iloc[last]
        prev = df.iloc[last - 1]

        fast_k   = f"ma{self.cross_fast}"
        slow_k   = f"ma{self.cross_slow}"
        ma_l_k   = f"ma{self.long_ma}"

        cur_fast  = cur[fast_k];  cur_slow  = cur[slow_k]
        prev_fast = prev[fast_k]; prev_slow = prev[slow_k]
        ma_l      = cur[ma_l_k]
        atr       = cur["atr"]
        close     = cur["close"]

        if any(pd.isna([cur_fast, cur_slow, prev_fast, prev_slow, ma_l, atr])):
            return None

        # 金叉条件
        just_crossed = (cur_fast > cur_slow) and (prev_fast <= prev_slow)
        if not just_crossed: return None

        # 大趋势
        if close < ma_l * 0.98: return None

        conf = self._cross_confidence(df, last)
        if conf < self.min_confidence: return None

        stop = close - self.stop_atr_mult * atr
        stop = max(stop, float(cur_slow) * 0.97)
        target = close + (close - stop) * self.reward_ratio

        return TrendSignal(
            signal_type=TrendSignalType.MA_CROSS,
            entry_price=close,
            stop_loss=max(stop, close * 0.85),
            target_price=target,
            confidence=conf,
            entry_idx=last,
            detail={
                "fast_ma": self.cross_fast,
                "slow_ma": self.cross_slow,
                "fast_val": round(float(cur_fast), 2),
                "slow_val": round(float(cur_slow), 2),
            },
        )

    def _cross_confidence(self, df, idx) -> float:
        score = 0.42
        row = df.iloc[idx]

        # RSI 健康
        if "RSI14" in df.columns:
            rsi = df["RSI14"].iloc[idx]
            if pd.notna(rsi) and 40 <= rsi <= 65:
                score += 0.12

        # 量能放大
        vol_ma_k = f"mavol{self.breakout_period}"
        if pd.notna(row[vol_ma_k]) and row[vol_ma_k] > 0:
            vr = row["volume"] / row[vol_ma_k]
            if vr > 1.3: score += 0.10
            elif vr > 1.0: score += 0.05

        # MACD 辅助
        if "MACD_Histogram" in df.columns:
            hist = df["MACD_Histogram"].iloc[idx]
            if pd.notna(hist) and hist > 0:
                score += 0.10

        return min(score, 0.90)


# ────────────────────────────────────────────
# 市场状态判断（决定是否启用趋势跟踪）
# ────────────────────────────────────────────

def detect_bull_regime(df: pd.DataFrame, lookback: int = 60) -> dict[str, Any]:
    """
    检测是否处于牛市/强趋势状态。

    Returns:
        {
            "is_bull": bool,
            "trend_strength": float,   # 0-1
            "above_ma50": bool,
            "above_ma200": bool,
            "slope_20d": float,        # 20日涨幅%
            "regime": str              # "bull" / "bear" / "sideways"
        }
    """
    if len(df) < max(lookback, 200):
        return {"is_bull": False, "regime": "unknown", "trend_strength": 0.0}

    c = df["close"].values

    ma50  = float(pd.Series(c).rolling(50).mean().iloc[-1])
    ma200 = float(pd.Series(c).rolling(200).mean().iloc[-1]) if len(c) >= 200 else ma50
    close = float(c[-1])

    above_ma50  = close > ma50
    above_ma200 = close > ma200
    slope_20d = (c[-1] / c[max(-20,-len(c))] - 1) * 100
    # 用60日斜率衡量中期趋势，避免短期噪音
    slope_60d = (c[-1] / c[max(-60,-len(c))] - 1) * 100

    # 趋势强度：综合多个信号
    signals = [
        1 if above_ma50 else 0,
        1 if above_ma200 else 0,
        1 if slope_60d > 5 else (0.5 if slope_60d > 0 else 0),
        1 if close > ma50 * 1.02 else 0,   # 明显站上50MA
    ]
    strength = float(np.mean(signals))

    if strength >= 0.625 and slope_60d > 0:
        regime = "bull"
    elif strength <= 0.25 or slope_60d < -10:
        regime = "bear"
    else:
        regime = "sideways"

    return {
        "is_bull": regime == "bull",
        "regime": regime,
        "trend_strength": round(strength, 2),
        "above_ma50": above_ma50,
        "above_ma200": above_ma200,
        "slope_20d": round(slope_20d, 2),
    }
