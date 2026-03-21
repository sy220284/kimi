"""
analysis/factors/multi_factor.py

A股多因子选股引擎

基于A股实证有效因子：
  一级因子（高权重）：
    - 价量动量     游资追涨+散户跟风的惯性效应
    - 换手率趋势   主力建仓/出货的量化信号
    - 小盘溢价     机构难覆盖导致的定价偏差
    - 趋势强度     技术面多头排列

  二级因子（中权重）：
    - RSI健康区间  避免极度超买/超卖
    - 量价配合     价升量增为健康上涨
    - 成本均线距离 入场性价比

  负向过滤（硬条件）：
    - 极度超买（RSI > 80）
    - 成交量极度枯竭（可能退市/停牌风险）
    - 价格低于长期均线太多（趋势彻底破坏）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FactorScore:
    """单股因子评分结果"""
    symbol:         str
    total_score:    float          # 0-100综合评分
    # 一级因子得分
    momentum_score:  float = 0.0   # 价量动量
    turnover_score:  float = 0.0   # 换手率趋势
    trend_score:     float = 0.0   # 趋势强度
    # 二级因子得分
    rsi_score:       float = 0.0   # RSI健康度
    vol_price_score: float = 0.0   # 量价配合
    cost_score:      float = 0.0   # 成本性价比
    # 过滤标志
    passed_filter:  bool  = True
    filter_reason:  str   = ""
    # 原始信号值（供调试）
    signals:        dict[str, Any] = field(default_factory=dict)

    @property
    def grade(self) -> str:
        if self.total_score >= 75:   return "A"
        if self.total_score >= 60:   return "B"
        if self.total_score >= 45:   return "C"
        return "D"


class AShareMultiFactor:
    """
    A股多因子评分引擎

    用法::

        engine = AShareMultiFactor()
        scores = engine.score_batch(symbol_df_dict)
        top = engine.select_top(scores, n=10)
    """

    # ── 因子权重（合计100）──────────────────────
    WEIGHTS = {
        "momentum":   35,   # 一级：价量动量（A股最有效）
        "turnover":   20,   # 一级：换手率趋势
        "trend":      20,   # 一级：趋势多头排列
        "rsi":        10,   # 二级：RSI健康区间
        "vol_price":  10,   # 二级：量价配合
        "cost":        5,   # 二级：成本均线距离
    }

    def __init__(
        self,
        # 动量参数
        momentum_short:  int   = 5,
        momentum_medium: int   = 20,
        momentum_long:   int   = 60,
        # 均线参数
        ma_fast:  int = 5,
        ma_slow:  int = 20,
        ma_trend: int = 60,
        ma_cost:  int = 120,   # 成本均线（长期持仓者均成本）
        # 换手率窗口
        turnover_window: int = 10,
        # RSI
        rsi_period: int = 14,
        # 过滤参数
        rsi_overbought:     float = 82,   # RSI超买阈值（A股适当放宽）
        rsi_oversold:       float = 20,   # RSI超卖（放弃下跌中途抢反弹）
        price_below_ma_pct: float = 0.12, # 价格低于成本均线超过12%则过滤
        min_volume:         float = 1e5,  # 最低日均成交量（过滤无流动性）
    ):
        self.momentum_short  = momentum_short
        self.momentum_medium = momentum_medium
        self.momentum_long   = momentum_long
        self.ma_fast   = ma_fast
        self.ma_slow   = ma_slow
        self.ma_trend  = ma_trend
        self.ma_cost   = ma_cost
        self.turnover_window = turnover_window
        self.rsi_period = rsi_period
        self.rsi_overbought  = rsi_overbought
        self.rsi_oversold    = rsi_oversold
        self.price_below_ma_pct = price_below_ma_pct
        self.min_volume = min_volume

    # ─────────────────────────────────────────────
    # 主接口
    # ─────────────────────────────────────────────

    def score(self, symbol: str, df: pd.DataFrame) -> FactorScore:
        """对单只股票评分"""
        if len(df) < self.ma_cost + 5:
            return FactorScore(symbol=symbol, total_score=0, passed_filter=False,
                               filter_reason="数据不足")

        df = df.copy().sort_values("date").reset_index(drop=True)
        c = df["close"].values.astype(float)
        v = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(df))

        # ── 负向过滤 ─────────────────────────────
        passed, reason = self._hard_filter(c, v)
        if not passed:
            return FactorScore(symbol=symbol, total_score=0,
                               passed_filter=False, filter_reason=reason)

        # ── 各因子评分 ───────────────────────────
        m_s, m_sigs   = self._momentum_factor(c, v)
        t_s, t_sigs   = self._turnover_factor(v)
        tr_s, tr_sigs = self._trend_factor(c)
        r_s, r_sigs   = self._rsi_factor(c)
        vp_s, vp_sigs = self._vol_price_factor(c, v)
        co_s, co_sigs = self._cost_factor(c)

        # ── 加权总分 ─────────────────────────────
        w = self.WEIGHTS
        total = (
            m_s  * w["momentum"]   +
            t_s  * w["turnover"]   +
            tr_s * w["trend"]      +
            r_s  * w["rsi"]        +
            vp_s * w["vol_price"]  +
            co_s * w["cost"]
        )   # 0-100

        all_signals = {**m_sigs, **t_sigs, **tr_sigs, **r_sigs, **vp_sigs, **co_sigs}

        return FactorScore(
            symbol=symbol,
            total_score=round(total, 2),
            momentum_score=round(m_s * 100, 1),
            turnover_score=round(t_s * 100, 1),
            trend_score=round(tr_s * 100, 1),
            rsi_score=round(r_s * 100, 1),
            vol_price_score=round(vp_s * 100, 1),
            cost_score=round(co_s * 100, 1),
            passed_filter=True,
            signals=all_signals,
        )

    def score_batch(
        self,
        symbol_dfs: dict[str, pd.DataFrame],
        min_score: float = 0,
    ) -> list[FactorScore]:
        """批量评分，返回列表按总分降序"""
        results = []
        for sym, df in symbol_dfs.items():
            try:
                s = self.score(sym, df)
                if s.passed_filter and s.total_score >= min_score:
                    results.append(s)
            except Exception:
                pass
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def select_top(
        self,
        scores: list[FactorScore],
        n: int = 5,
        min_grade: str = "B",
    ) -> list[FactorScore]:
        """选出前N只，过滤等级不足的"""
        grade_map = {"A": 3, "B": 2, "C": 1, "D": 0}
        min_grade_val = grade_map.get(min_grade, 2)
        filtered = [s for s in scores
                    if s.passed_filter and grade_map.get(s.grade, 0) >= min_grade_val]
        return filtered[:n]

    # ─────────────────────────────────────────────
    # 因子计算
    # ─────────────────────────────────────────────

    def _hard_filter(self, c: np.ndarray, v: np.ndarray) -> tuple[bool, str]:
        """硬条件过滤"""
        price = c[-1]

        # 成交量过滤
        avg_vol = float(np.mean(v[-20:])) if len(v) >= 20 else float(v[-1])
        if avg_vol < self.min_volume:
            return False, f"成交量过低({avg_vol:.0f})"

        # 价格低于成本均线超过阈值
        if len(c) >= self.ma_cost:
            ma_cost = float(np.mean(c[-self.ma_cost:]))
            if price < ma_cost * (1 - self.price_below_ma_pct):
                return False, f"价格低于{self.ma_cost}日均线{self.price_below_ma_pct:.0%}以上"

        # RSI极度超卖（避免接刀子）
        rsi = self._calc_rsi(c, self.rsi_period)
        if rsi < self.rsi_oversold:
            return False, f"RSI超卖({rsi:.1f})"

        return True, ""

    def _momentum_factor(self, c: np.ndarray, v: np.ndarray) -> tuple[float, dict]:
        """
        价量动量因子
        短中长三周期动量加权 + 量能配合加成
        """
        n = len(c)
        ret_short  = (c[-1] / c[-(self.momentum_short+1)]  - 1) if n > self.momentum_short  else 0
        ret_medium = (c[-1] / c[-(self.momentum_medium+1)] - 1) if n > self.momentum_medium else 0
        ret_long   = (c[-1] / c[-(self.momentum_long+1)]   - 1) if n > self.momentum_long   else 0

        # 标准化：每个收益率转换为0-1分
        # A股合理范围：5日±8%，20日±15%，60日±30%
        s_short  = self._normalize(ret_short,  -0.08, 0.08)
        s_medium = self._normalize(ret_medium, -0.15, 0.15)
        s_long   = self._normalize(ret_long,   -0.30, 0.30)

        # 量能加成：近期量能是否支撑动量
        vol_support = self._volume_trend_score(v)
        vol_bonus = 0.05 if vol_support > 0.6 else (-0.05 if vol_support < 0.4 else 0)

        score = (0.25 * s_short + 0.45 * s_medium + 0.30 * s_long) + vol_bonus
        score = max(0, min(1, score))

        return score, {
            "ret_5d":  round(ret_short * 100, 1),
            "ret_20d": round(ret_medium * 100, 1),
            "ret_60d": round(ret_long * 100, 1),
        }

    def _turnover_factor(self, v: np.ndarray) -> tuple[float, dict]:
        """
        换手率趋势因子
        A股换手率是判断主力行为的核心信号：
          缓慢放量（量比1.2-2.0）→ 主力建仓，积极信号
          急速放量（量比>3.0）  → 可能出货，需谨慎
          持续缩量              → 无人关注，消极信号
        """
        if len(v) < self.turnover_window + 5:
            return 0.5, {}

        base_vol = float(np.mean(v[-(self.turnover_window + 10):-(self.turnover_window)]))
        curr_vol = float(np.mean(v[-self.turnover_window:]))
        ratio = curr_vol / (base_vol + 1e-8)

        # 适度放量（1.2-2.5倍）给高分，急速放量降分
        if 1.2 <= ratio <= 2.5:
            score = min(1.0, 0.5 + (ratio - 1.2) / 2.6)
        elif ratio > 2.5:
            # 急速放量可能是出货，适度降分
            score = max(0.3, 1.0 - (ratio - 2.5) * 0.15)
        else:
            # 缩量
            score = max(0, ratio / 1.2 * 0.5)

        # 量能趋势（是否在持续放大）
        recent_half = float(np.mean(v[-self.turnover_window // 2:]))
        earlier_half = float(np.mean(v[-self.turnover_window:-self.turnover_window // 2]))
        trending_up = recent_half > earlier_half * 1.05

        if trending_up:
            score = min(1.0, score + 0.1)

        return score, {
            "vol_ratio": round(ratio, 2),
            "vol_trending_up": trending_up,
        }

    def _trend_factor(self, c: np.ndarray) -> tuple[float, dict]:
        """
        技术趋势因子：均线多头排列强度
        """
        if len(c) < self.ma_cost:
            return 0.5, {}

        ma_fast  = float(np.mean(c[-self.ma_fast:]))
        ma_slow  = float(np.mean(c[-self.ma_slow:]))
        ma_trend = float(np.mean(c[-self.ma_trend:]))
        price    = float(c[-1])

        # 多头排列各条件
        checks = [
            price    > ma_fast,     # 价格在5MA上
            ma_fast  > ma_slow,     # 5MA > 20MA
            ma_slow  > ma_trend,    # 20MA > 60MA
            price    > ma_slow,     # 价格在20MA上
            price    > ma_trend,    # 价格在60MA上
        ]
        weights = [0.25, 0.25, 0.20, 0.15, 0.15]
        score = sum(w for c, w in zip(checks, weights) if c)

        # 距离加成：价格偏离MA的程度（过度偏离不加分）
        dist_from_slow = (price - ma_slow) / (ma_slow + 1e-8)
        if 0.02 <= dist_from_slow <= 0.08:
            score = min(1.0, score + 0.05)  # 合理距离加分

        return score, {
            "price_vs_ma5":   round(price / ma_fast - 1, 3),
            "price_vs_ma20":  round(price / ma_slow - 1, 3),
            "price_vs_ma60":  round(price / ma_trend - 1, 3),
            "bull_arrangement": sum(checks),  # 满足几条
        }

    def _rsi_factor(self, c: np.ndarray) -> tuple[float, dict]:
        """
        RSI健康区间因子
        A股策略：RSI 45-70 为最佳入场区间
          < 40：过度超卖，下跌趋势中
          40-50：反转区间，可布局
          50-65：健康上涨区间，最佳
          65-75：偏热，可持有但不加仓
          > 75：过热，减仓区间
        """
        rsi = self._calc_rsi(c, self.rsi_period)

        if 50 <= rsi <= 65:
            score = 1.0
        elif 45 <= rsi < 50:
            score = 0.85
        elif 65 < rsi <= 72:
            score = 0.75
        elif 40 <= rsi < 45:
            score = 0.60
        elif 72 < rsi <= 80:
            score = 0.50
        elif rsi > 80:
            score = 0.20   # 超买，不宜追高
        else:
            score = 0.35   # 超卖但趋势向下

        return score, {"rsi": round(rsi, 1)}

    def _vol_price_factor(self, c: np.ndarray, v: np.ndarray) -> tuple[float, dict]:
        """
        量价配合因子：价升量增为健康上涨
        """
        if len(c) < 10 or len(v) < 10:
            return 0.5, {}

        # 计算近10日价格变化和量变化的相关性
        price_changes = np.diff(c[-11:]) / (c[-11:-1] + 1e-8)
        vol_changes   = np.diff(v[-11:]) / (v[-11:-1] + 1e-8)

        if len(price_changes) < 3:
            return 0.5, {}

        # 价升量增的天数 vs 价升量缩的天数
        up_with_vol   = np.sum((price_changes > 0) & (vol_changes > 0))
        up_without_vol = np.sum((price_changes > 0) & (vol_changes < 0))
        dn_with_vol   = np.sum((price_changes < 0) & (vol_changes > 0))

        total = len(price_changes)
        healthy_ratio = (up_with_vol - dn_with_vol) / total
        score = max(0, min(1, 0.5 + healthy_ratio * 0.5))

        return score, {
            "up_with_vol":    int(up_with_vol),
            "up_without_vol": int(up_without_vol),
            "dn_with_vol":    int(dn_with_vol),
        }

    def _cost_factor(self, c: np.ndarray) -> tuple[float, dict]:
        """
        成本均线距离因子
        120日均线视为大多数持仓者的成本线
        距离成本线10-20%为最佳性价比区间
        """
        if len(c) < self.ma_cost:
            return 0.5, {}

        ma_cost = float(np.mean(c[-self.ma_cost:]))
        price   = float(c[-1])
        dist    = (price - ma_cost) / (ma_cost + 1e-8)

        if 0.05 <= dist <= 0.20:
            score = 1.0   # 理想区间
        elif 0.20 < dist <= 0.35:
            score = 0.70  # 略偏贵
        elif dist > 0.35:
            score = 0.30  # 明显偏贵，追高风险大
        elif 0 <= dist < 0.05:
            score = 0.85  # 刚突破成本线
        elif -0.05 <= dist < 0:
            score = 0.60  # 轻微跌破，观察
        else:
            score = 0.20  # 深度套牢区

        return score, {
            "dist_from_ma120": round(dist * 100, 1),
            "ma120": round(ma_cost, 2),
        }

    # ─────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────

    @staticmethod
    def _normalize(x: float, lo: float, hi: float) -> float:
        """线性映射到0-1"""
        return max(0.0, min(1.0, (x - lo) / (hi - lo + 1e-12)))

    def _volume_trend_score(self, v: np.ndarray) -> float:
        """量能趋势得分（0-1），简化版"""
        if len(v) < 20:
            return 0.5
        recent = float(np.mean(v[-10:]))
        base   = float(np.mean(v[-20:-10]))
        ratio  = recent / (base + 1e-8)
        return max(0, min(1, 0.5 + (ratio - 1) * 0.5))

    @staticmethod
    def _calc_rsi(c: np.ndarray, period: int = 14) -> float:
        """计算RSI"""
        if len(c) < period + 1:
            return 50.0
        diffs = np.diff(c[-(period + 10):])
        gains  = np.where(diffs > 0, diffs, 0)
        losses = np.where(diffs < 0, -diffs, 0)
        avg_gain = float(np.mean(gains[-period:]))
        avg_loss = float(np.mean(losses[-period:]))
        if avg_loss < 1e-10:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def factor_report(self, score: FactorScore) -> str:
        """生成单股因子报告"""
        if not score.passed_filter:
            return f"  {score.symbol}: ❌ 过滤 ({score.filter_reason})"

        bars = {
            "动量": score.momentum_score,
            "换手": score.turnover_score,
            "趋势": score.trend_score,
            "RSI":  score.rsi_score,
            "量价": score.vol_price_score,
            "成本": score.cost_score,
        }
        bar_str = "  ".join(f"{k}:{v:.0f}" for k, v in bars.items())
        return (f"  {score.symbol} [{score.grade}] 总分={score.total_score:.1f} | {bar_str}")
