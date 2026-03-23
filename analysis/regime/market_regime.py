"""
analysis/regime/market_regime.py

A股市场状态识别器（五态模型）

A股五种市场状态：
  POLICY_BOTTOM   政策底：重磅政策出台 + 极度超卖，最佳入场窗口
  BULL_TREND      趋势牛市：量能持续放大 + 指数新高，持股待涨
  STRUCTURAL      结构性行情：指数震荡 + 行业高低切换，做轮动
  STOCK_GAME      存量博弈：量能萎缩 + 热点频换 + 赚钱效应差，轻仓
  SYSTEMIC_RISK   系统性风险：外部冲击 + 杠杆去化，空仓

各状态的仓位上限：90% / 80% / 50% / 20% / 0%
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# 状态枚举
# ─────────────────────────────────────────────

class MarketRegime(Enum):
    POLICY_BOTTOM  = "policy_bottom"   # 政策底
    BULL_TREND     = "bull_trend"      # 趋势牛市
    STRUCTURAL     = "structural"      # 结构性行情
    STOCK_GAME     = "stock_game"      # 存量博弈
    SYSTEMIC_RISK  = "systemic_risk"   # 系统性风险

# 各状态最大允许仓位
REGIME_MAX_POSITION: dict[MarketRegime, float] = {
    MarketRegime.POLICY_BOTTOM:  0.90,
    MarketRegime.BULL_TREND:     0.80,
    MarketRegime.STRUCTURAL:     0.50,
    MarketRegime.STOCK_GAME:     0.20,
    MarketRegime.SYSTEMIC_RISK:  0.00,
}

# 各状态推荐持仓数量
REGIME_MAX_POSITIONS: dict[MarketRegime, int] = {
    MarketRegime.POLICY_BOTTOM:  5,
    MarketRegime.BULL_TREND:     4,
    MarketRegime.STRUCTURAL:     3,
    MarketRegime.STOCK_GAME:     2,
    MarketRegime.SYSTEMIC_RISK:  0,
}


# ─────────────────────────────────────────────
# 诊断结果
# ─────────────────────────────────────────────

@dataclass
class RegimeResult:
    """市场状态诊断结果"""
    regime:           MarketRegime
    confidence:       float          # 置信度 0-1
    max_position:     float          # 最大仓位
    max_positions:    int            # 最大持仓数
    # 各指标得分（供调试）
    trend_score:      float = 0.0
    volume_score:     float = 0.0
    momentum_score:   float = 0.0
    breadth_score:    float = 0.0
    risk_score:       float = 0.0
    # 描述
    description:      str   = ""
    signals:          dict[str, Any] = field(default_factory=dict)

    @property
    def is_tradeable(self) -> bool:
        return self.regime != MarketRegime.SYSTEMIC_RISK

    @property
    def label(self) -> str:
        labels = {
            MarketRegime.POLICY_BOTTOM:  "政策底 🚀",
            MarketRegime.BULL_TREND:     "趋势牛市 📈",
            MarketRegime.STRUCTURAL:     "结构性行情 🔄",
            MarketRegime.STOCK_GAME:     "存量博弈 ⚠️",
            MarketRegime.SYSTEMIC_RISK:  "系统性风险 🛑",
        }
        return labels[self.regime]


# ─────────────────────────────────────────────
# 识别器主类
# ─────────────────────────────────────────────

class AShareMarketRegime:
    """
    A股市场状态识别器

    输入：市场指数级别的 DataFrame（上证/沪深300/全市场等权）
    输出：RegimeResult

    核心指标（按重要性排序）：
      1. 价格趋势  — 均线系统 + 斜率
      2. 量能状态  — 成交额绝对值 + 变化趋势
      3. 市场动量  — 近期涨跌幅 + 新高/新低比
      4. 市场宽度  — 上涨/下跌家数比（需要市场宽度数据）
      5. 风险信号  — 极端波动 + 快速下跌

    没有M1/两融/北向数据时（只有收盘价+量），
    使用 price+volume 的代理指标。
    """

    def __init__(
        self,
        trend_ma_short:  int   = 20,
        trend_ma_medium: int   = 60,
        trend_ma_long:   int   = 120,
        vol_lookback:    int   = 20,   # 成交量比较基准
        momentum_days:   int   = 20,   # 动量计算窗口
        vol_surge_mult:  float = 1.5,  # 放量倍数（vs均量）
        vol_shrink_mult: float = 0.7,  # 缩量倍数
        crash_pct:       float = 0.08, # 系统性崩溃阈值（20日跌幅）
        rally_pct:       float = 0.15, # 强势反弹阈值（20日涨幅）
    ):
        self.trend_ma_short  = trend_ma_short
        self.trend_ma_medium = trend_ma_medium
        self.trend_ma_long   = trend_ma_long
        self.vol_lookback    = vol_lookback
        self.momentum_days   = momentum_days
        self.vol_surge_mult  = vol_surge_mult
        self.vol_shrink_mult = vol_shrink_mult
        self.crash_pct       = crash_pct
        self.rally_pct       = rally_pct

    def detect(self, df: pd.DataFrame) -> RegimeResult:
        """
        检测市场状态。

        Args:
            df: 含 date/close/volume（可选 high/low/amount）的 DataFrame
                代表市场指数或等权市场价格
        """
        min_len = self.trend_ma_long + 10
        if len(df) < min_len:
            return self._default_result("数据不足")

        df = df.copy().sort_values("date").reset_index(drop=True)
        c = df["close"].values
        v = df["volume"].values if "volume" in df.columns else np.ones(len(df))

        # ── 1. 趋势得分 ─────────────────────────────
        trend_score, trend_signals = self._trend_score(c)

        # ── 2. 量能得分 ─────────────────────────────
        volume_score, volume_signals = self._volume_score(v)

        # ── 3. 动量得分 ─────────────────────────────
        momentum_score, momentum_signals = self._momentum_score(c)

        # ── 4. 宽度得分（用高低来代理） ─────────────
        if "high" in df.columns and "low" in df.columns:
            breadth_score, breadth_signals = self._breadth_proxy(
                df["high"].values, df["low"].values, c)
        else:
            breadth_score, breadth_signals = 0.5, {}

        # ── 5. 风险信号 ──────────────────────────────
        risk_score, risk_signals = self._risk_score(c, v)

        # ── 综合判断 ─────────────────────────────────
        signals = {**trend_signals, **volume_signals,
                   **momentum_signals, **breadth_signals, **risk_signals}

        regime, confidence, desc = self._classify(
            trend_score, volume_score, momentum_score, breadth_score, risk_score
        )

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 3),
            max_position=REGIME_MAX_POSITION[regime],
            max_positions=REGIME_MAX_POSITIONS[regime],
            trend_score=round(trend_score, 3),
            volume_score=round(volume_score, 3),
            momentum_score=round(momentum_score, 3),
            breadth_score=round(breadth_score, 3),
            risk_score=round(risk_score, 3),
            description=desc,
            signals=signals,
        )

    # ─────────────── 各项评分 ────────────────────

    def _trend_score(self, c: np.ndarray) -> tuple[float, dict]:
        """均线多空排列得分 0-1"""
        ma_s  = float(np.mean(c[-self.trend_ma_short:]))
        ma_m  = float(np.mean(c[-self.trend_ma_medium:]))
        ma_l  = float(np.mean(c[-self.trend_ma_long:]))
        price = float(c[-1])

        # 多头排列：price > ma_s > ma_m > ma_l
        above_s = price > ma_s
        above_m = price > ma_m
        above_l = price > ma_l
        ma_order = ma_s > ma_m > ma_l  # 完美多头排列

        score = (0.30 * above_s + 0.25 * above_m + 0.20 * above_l
                 + 0.25 * ma_order)

        # 均线斜率（20日斜率相对价格的百分比）
        slope_20 = (c[-1] - c[-self.trend_ma_short]) / (c[-self.trend_ma_short] + 1e-8)
        slope_bonus = 0.1 if slope_20 > 0.05 else (-0.1 if slope_20 < -0.05 else 0)
        score = max(0, min(1, score + slope_bonus))

        return score, {
            "trend_above_ma20": above_s,
            "trend_above_ma60": above_m,
            "trend_above_ma120": above_l,
            "ma_bull_order": ma_order,
            "slope_20d": round(slope_20 * 100, 1),
        }

    def _volume_score(self, v: np.ndarray) -> tuple[float, dict]:
        """
        成交量放量/缩量状态 0-1（0.5=中性）

        改进：
          - 近10日均量（原5日，噪声大）vs 前20日均量基准
          - 量能趋势：近10日 vs 近20日的斜率方向
        """
        lookback = self.vol_lookback   # 默认20
        curr_window = max(10, lookback // 2)   # 10日（比5日稳）

        if len(v) < lookback + curr_window:
            return 0.5, {}

        base_vol  = float(np.mean(v[-(lookback + curr_window):-curr_window]))
        curr_vol  = float(np.mean(v[-curr_window:]))
        ratio     = curr_vol / (base_vol + 1e-8)

        if ratio >= self.vol_surge_mult:
            score = min(1.0, 0.5 + 0.5 * min((ratio - 1), 1.0))
        elif ratio <= self.vol_shrink_mult:
            score = max(0.0, 0.5 * ratio / self.vol_shrink_mult)
        else:
            # 线性插值
            score = 0.5 + (ratio - 1.0) * 0.5 / (self.vol_surge_mult - 1.0)

        # 量能趋势：近10日与前10日对比（是否持续放量）
        prev_vol = float(np.mean(v[-(curr_window * 2):-curr_window]))
        vol_trend = (curr_vol - prev_vol) / (prev_vol + 1e-8)
        if vol_trend > 0.1:
            score = min(1.0, score + 0.05)   # 持续放量加分
        elif vol_trend < -0.1:
            score = max(0.0, score - 0.05)   # 持续缩量减分

        return score, {
            "volume_ratio": round(ratio, 2),
            "volume_trend": round(vol_trend, 2),
            "is_surge":   ratio >= self.vol_surge_mult,
            "is_shrink":  ratio <= self.vol_shrink_mult,
        }

    def _momentum_score(self, c: np.ndarray) -> tuple[float, dict]:
        """价格动量得分 0-1"""
        ret_5  = (c[-1] / c[-6]  - 1) if len(c) >= 6 else 0
        ret_20 = (c[-1] / c[-21] - 1) if len(c) >= 21 else 0
        ret_60 = (c[-1] / c[-61] - 1) if len(c) >= 61 else 0

        # 综合动量得分
        score = 0.5
        score += 0.20 * np.sign(ret_5)  * min(abs(ret_5)  / 0.05, 1)
        score += 0.30 * np.sign(ret_20) * min(abs(ret_20) / 0.10, 1)
        score += 0.20 * np.sign(ret_60) * min(abs(ret_60) / 0.20, 1)
        score = float(max(0, min(1, score)))

        # 新高检测
        high_120 = float(np.max(c[-120:])) if len(c) >= 120 else float(np.max(c))
        near_high = c[-1] >= high_120 * 0.95  # 距离120日高点5%以内

        return score, {
            "ret_5d":   round(ret_5 * 100, 1),
            "ret_20d":  round(ret_20 * 100, 1),
            "ret_60d":  round(ret_60 * 100, 1),
            "near_120d_high": near_high,
        }

    def _breadth_proxy(self, h: np.ndarray, l: np.ndarray,
                        c: np.ndarray) -> tuple[float, dict]:
        """
        用价格振幅代理市场宽度（无法获得全市场数据时）
        高振幅 + 收盘偏上 → 多方主导
        高振幅 + 收盘偏下 → 空方主导
        """
        recent = min(20, len(c))
        ranges = (h[-recent:] - l[-recent:]) / (c[-recent:] + 1e-8)
        avg_range = float(np.mean(ranges))

        # 收盘位置（0=最低，1=最高）
        positions = (c[-recent:] - l[-recent:]) / (h[-recent:] - l[-recent:] + 1e-8)
        avg_pos = float(np.mean(positions))

        score = avg_pos  # 0-1，越高越强势

        return score, {
            "avg_daily_range": round(avg_range * 100, 2),
            "avg_close_position": round(avg_pos, 2),
        }

    def _risk_score(self, c: np.ndarray, v: np.ndarray) -> tuple[float, dict]:
        """
        风险信号得分（0=高风险，1=低风险）
        """
        recent_20 = min(20, len(c))
        ret_20 = (c[-1] / c[-recent_20] - 1)

        # 日收益率序列
        rets = np.diff(c[-30:]) / (c[-30:-1] + 1e-8) if len(c) >= 31 else np.array([0.0])
        volatility = float(np.std(rets)) * np.sqrt(252)

        # 崩溃检测
        is_crash  = ret_20 < -self.crash_pct
        # 快速反弹（可能是政策底）
        is_rally  = ret_20 > self.rally_pct

        score = 0.5
        if is_crash:
            score = 0.1   # 高风险
        elif is_rally:
            score = 0.8   # 可能是政策底后的反弹，不算高风险
        else:
            # 基于波动率
            score = max(0.1, min(0.9, 0.7 - volatility * 0.5))

        return score, {
            "ret_20d":      round(ret_20 * 100, 1),
            "volatility":   round(volatility, 3),
            "is_crash":     is_crash,
            "is_rally":     is_rally,
        }

    # ─────────────── 综合分类 ────────────────────

    def _classify(
        self,
        trend: float, volume: float, momentum: float,
        breadth: float, risk: float
    ) -> tuple[MarketRegime, float, str]:
        """基于五维得分综合判断市场状态"""

        # ── 系统性风险：先检查硬条件 ──
        if risk < 0.15:
            conf = 1 - risk * 5  # risk越低置信度越高
            return MarketRegime.SYSTEMIC_RISK, conf, "价格急跌+高波动，建议空仓"

        # ── 政策底：低位+量能放大+即将反转 ──
        if trend < 0.25 and volume > 0.65 and momentum > 0.35 and risk > 0.5:
            conf = (1 - trend) * volume * 0.7 + risk * 0.3
            return MarketRegime.POLICY_BOTTOM, min(conf, 0.95), "超卖+放量，可能是政策底"

        # ── 趋势牛市：价格+量能+动量三者都强 ──
        if trend > 0.70 and volume > 0.60 and momentum > 0.65:
            conf = (trend + volume + momentum) / 3
            return MarketRegime.BULL_TREND, min(conf, 0.95), "多头排列+放量+动量强，趋势牛市"

        # ── 存量博弈：量能萎缩+趋势不明 ──
        if volume < 0.35 and trend < 0.55:
            conf = (1 - volume) * 0.6 + (1 - trend) * 0.4
            return MarketRegime.STOCK_GAME, min(conf, 0.90), "量能萎缩+趋势弱，存量博弈"

        # ── 结构性行情：其余情况 ──
        # 指数震荡但行业有机会
        conf = abs(trend - 0.5) * 2 * 0.3 + abs(volume - 0.5) * 0.2 + 0.5
        desc = "指数震荡"
        if volume > 0.55:
            desc += "+量能尚可，关注行业轮动"
        else:
            desc += "+量能一般，精选个股"
        return MarketRegime.STRUCTURAL, min(conf, 0.85), desc

    def _default_result(self, reason: str) -> RegimeResult:
        return RegimeResult(
            regime=MarketRegime.STRUCTURAL,
            confidence=0.3,
            max_position=0.30,
            max_positions=2,
            description=f"默认结构性行情（{reason}）",
        )

    def detect_multi_period(
        self, df: pd.DataFrame, windows: list[int] = [60, 120, 250]
    ) -> dict[str, RegimeResult]:
        """多周期状态对比，用于识别大级别和小级别的状态一致性"""
        results = {}
        for w in windows:
            if len(df) >= w:
                sub = df.iloc[-w:]
                results[f"{w}d"] = self.detect(sub)
        return results
    @classmethod
    def from_config(cls, config: dict | None = None) -> "AShareMarketRegime":
        """从 config.yaml analysis.regime 节创建实例"""
        if config is None:
            from utils.config_loader import load_config
            config = load_config()
        s = config.get("analysis", {}).get("regime", {})
        return cls(
            trend_ma_short  = s.get("trend_ma_short",   20),
            trend_ma_medium = s.get("trend_ma_medium",  60),
            trend_ma_long   = s.get("trend_ma_long",   120),
            vol_lookback    = s.get("vol_lookback",      20),
            crash_pct       = s.get("crash_pct",       0.08),
            rally_pct       = s.get("rally_pct",       0.15),
        )

