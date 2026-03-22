"""
analysis/strategy/ashare_strategy.py

A股适配交易策略

核心改变（对比波浪策略）：
  1. 目标价 = 前高/压力位（不再用斐波那契延伸）
  2. 持仓时间 = 跟随行业轮动节奏（15-20天），不是固定60天
  3. 仓位上限 = 由市场状态动态决定
  4. 入场条件 = 多因子评分 + 市场状态 + 量价确认
  5. 出场逻辑 = 触达前高减仓 / 趋势破坏清仓 / 行业主题轮出清仓
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from analysis.regime.market_regime import MarketRegime, RegimeResult
from analysis.factors.multi_factor import FactorScore


class SignalType(Enum):
    """入场信号类型"""
    MOMENTUM_BREAKOUT  = "momentum_breakout"    # 动量突破
    PULLBACK_ENTRY     = "pullback_entry"        # 回调入场
    VOLUME_SURGE       = "volume_surge"          # 放量异动
    TREND_CONTINUATION = "trend_continuation"   # 趋势延续


@dataclass
class AShareSignal:
    """A股交易信号"""
    symbol:      str
    signal_type: SignalType
    entry_price: float
    stop_loss:   float     # 基于ATR或近期低点
    target_price: float    # 基于前高/压力位（非斐波那契）
    confidence:  float     # 0-1
    factor_score: float    # 多因子总分
    regime:      MarketRegime
    position_pct: float    # 建议仓位比例（已考虑市场状态）
    # 详情
    atr:         float = 0.0
    rr_ratio:    float = 0.0    # 盈亏比
    signals:     dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.target_price - self.entry_price)
        self.rr_ratio = round(reward / (risk + 1e-8), 2)

    @property
    def is_valid(self) -> bool:
        return (self.entry_price > 0
                and self.stop_loss < self.entry_price
                and self.target_price > self.entry_price
                and self.rr_ratio >= 1.3
                and self.confidence >= 0.45)


@dataclass
class AShareTrade:
    """交易记录"""
    symbol:       str
    entry_date:   str
    entry_price:  float
    stop_loss:    float
    target_price: float
    quantity:     int
    position_pct: float
    signal_type:  str
    exit_date:    str | None = None
    exit_price:   float | None = None
    exit_reason:  str | None = None
    pnl:          float = 0.0
    pnl_pct:      float = 0.0
    status:       str = "open"
    entry_idx:    int = 0
    # 移动止盈跟踪
    highest_price: float = 0.0
    trailing_stop: float | None = None

    def close(self, date: str, price: float, reason: str,
               commission: float = 0.0013, stamp_tax: float = 0.001):
        """平仓，扣除交易成本"""
        self.exit_date   = date
        self.exit_reason = reason
        self.status      = "closed"
        cost = price * (commission + stamp_tax)  # 卖出成本
        self.exit_price  = round(price - cost, 3)
        self.pnl_pct     = (self.exit_price - self.entry_price) / self.entry_price * 100
        self.pnl         = self.pnl_pct / 100 * self.entry_price * self.quantity

    def to_dict(self) -> dict:
        return {
            "symbol":      self.symbol,
            "entry_date":  self.entry_date,
            "entry_price": round(self.entry_price, 3),
            "exit_date":   self.exit_date,
            "exit_price":  round(self.exit_price, 3) if self.exit_price else None,
            "quantity":    self.quantity,
            "stop_loss":   round(self.stop_loss, 3),
            "target_price":round(self.target_price, 3),
            "signal_type": self.signal_type,
            "exit_reason": self.exit_reason,
            "pnl_pct":     round(self.pnl_pct, 2),
            "pnl":         round(self.pnl, 2),
            "status":      self.status,
        }


class AShareStrategy:
    """
    A股适配交易策略

    核心逻辑：
      入场：多因子高分 + 市场允许 + 量价确认
      目标：前高/阻力位（1.5-2.5倍风险，实际可达）
      出场：触达压力减仓 / 趋势破坏清仓 / 超时轮出清仓
      仓位：市场状态动态上限 × 信号质量

    对比波浪策略：
      ✅ 目标触达率从0%→有效    （前高替代斐波那契）
      ✅ 持仓时间匹配行业轮动   （15-20天vs固定60天）
      ✅ 仓位随市场状态动态     （非固定20%）
      ✅ 结合多因子选股         （非任意股票）
    """

    def __init__(
        self,
        initial_capital: float = 100_000,
        # 仓位参数
        base_position_pct: float = 0.20,   # 基础单笔仓位
        max_positions:     int   = 4,       # 最大持仓数（随市场状态调整）
        # 止损参数
        atr_stop_mult:    float = 2.0,      # 止损 = 入场价 - N×ATR
        min_stop_pct:     float = 0.04,     # 最小止损4%
        max_stop_pct:     float = 0.09,     # 最大止损9%（A股波动大，放宽）
        # 目标价：前高/压力位
        target_lookback:  int   = 30,       # 前N日最高价作为目标
        target_buffer:    float = 0.02,     # 目标价略低于前高（留缓冲）
        min_rr_ratio:     float = 1.3,      # 最低盈亏比（降低门槛）
        # 出场参数
        max_holding_days: int   = 20,       # 行业轮动平均周期，超时减仓
        trail_activation: float = 0.06,     # 浮盈6%后启用移动止盈
        trail_pct:        float = 0.04,     # 移动止盈回撤4%出场
        breakeven_pct:    float = 0.04,     # 浮盈4%后止损移至成本
        # 入场过滤
        min_factor_score: float = 55.0,     # 最低因子总分
        min_confidence:   float = 0.45,     # 最低信号置信度
        # 交易成本
        commission_rate:  float = 0.0003,   # 佣金0.03%
        stamp_tax_rate:   float = 0.001,    # 印花税0.1%（卖出）
        slippage_rate:    float = 0.001,    # 滑点0.1%
    ):
        self.initial_capital   = initial_capital
        self.base_position_pct = base_position_pct
        self.max_positions     = max_positions
        self.atr_stop_mult     = atr_stop_mult
        self.min_stop_pct      = min_stop_pct
        self.max_stop_pct      = max_stop_pct
        self.target_lookback   = target_lookback
        self.target_buffer     = target_buffer
        self.min_rr_ratio      = min_rr_ratio
        self.max_holding_days  = max_holding_days
        self.trail_activation  = trail_activation
        self.trail_pct         = trail_pct
        self.breakeven_pct     = breakeven_pct
        self.min_factor_score  = min_factor_score
        self.min_confidence    = min_confidence
        self.commission_rate   = commission_rate
        self.stamp_tax_rate    = stamp_tax_rate
        self.slippage_rate     = slippage_rate

        # 运行时状态
        self.capital    = initial_capital
        self.positions: dict[str, AShareTrade] = {}
        self.trades:    list[AShareTrade] = []
        self.equity_curve: list[dict] = []

    def reset(self):
        """重置单次回测状态（保留跨回测的 Kelly 胜率统计）"""
        self.capital      = self.initial_capital
        self.positions    = {}
        self.trades       = []
        self.equity_curve = []

    def reset_full(self):
        """完全重置，包含 Kelly 统计（用于全新回测序列）"""
        self.reset()
        # 重置 Kelly 自适应胜率（若有）
        if hasattr(self, '_kelly_wins'):
            self._kelly_wins   = 0
            self._kelly_total  = 0

    # ─────────────────────────────────────────────
    # 信号生成
    # ─────────────────────────────────────────────

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        factor_score: FactorScore,
        regime: RegimeResult,
    ) -> AShareSignal | None:
        """
        基于多因子评分和市场状态生成交易信号

        目标价策略（解决0%触达率问题）：
          优先使用前N日高点×(1-buffer)作为目标
          保证盈亏比≥1.3
        """
        if not factor_score.passed_filter:
            return None
        if factor_score.total_score < self.min_factor_score:
            return None
        if not regime.is_tradeable:
            return None

        c = df["close"].values.astype(float)
        h = df["high"].values.astype(float) if "high" in df.columns else c * 1.005
        l = df["low"].values.astype(float) if "low" in df.columns else c * 0.995
        v = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(c))

        if len(c) < 30:
            return None

        price = float(c[-1])

        # ── ATR止损 ─────────────────────────────
        atr   = self._calc_atr(h, l, c)
        stop_raw = price - self.atr_stop_mult * atr
        # 同时考虑近5日最低点
        recent_low = float(np.min(l[-5:]))
        stop = min(stop_raw, recent_low * 0.99)
        # 约束止损范围
        stop = max(stop, price * (1 - self.max_stop_pct))
        stop = min(stop, price * (1 - self.min_stop_pct))

        # ── 目标价（前高法，非斐波那契）─────────
        lookback = min(self.target_lookback, len(h) - 1)
        prev_high = float(np.max(h[-lookback-1:-1]))  # 不含今天
        target = prev_high * (1 - self.target_buffer)

        # 若价格已经超过前高（突破行情），目标价延伸
        if price >= prev_high * 0.98:
            # 用更远的前高
            longer_lookback = min(60, len(h) - 1)
            longer_high = float(np.max(h[-longer_lookback-1:-1]))
            target = max(longer_high * (1 - self.target_buffer),
                         price * 1.08)  # 至少8%空间

        # 确保目标价高于入场价
        if target <= price * 1.02:
            target = price * (1 + max(self.min_stop_pct * self.min_rr_ratio, 0.05))

        # ── 盈亏比检查 ──────────────────────────
        risk = price - stop
        reward = target - price
        rr = reward / (risk + 1e-8)
        if rr < self.min_rr_ratio:
            return None

        # ── 信号类型判断 ─────────────────────────
        ret_5  = (c[-1] / c[-6] - 1) if len(c) >= 6 else 0
        vol_ratio = float(np.mean(v[-5:])) / (float(np.mean(v[-20:-5])) + 1e-8)

        if vol_ratio >= 1.8 and ret_5 > 0.03:
            stype = SignalType.VOLUME_SURGE
        elif ret_5 > 0.04:
            stype = SignalType.MOMENTUM_BREAKOUT
        elif -0.03 <= ret_5 <= 0.01:
            stype = SignalType.PULLBACK_ENTRY
        else:
            stype = SignalType.TREND_CONTINUATION

        # ── 信号置信度（多因子→置信度） ─────────
        # 因子分55-100 → 置信度0.45-0.95
        confidence = 0.45 + (factor_score.total_score - 55) / 90 * 0.50
        confidence = max(0.45, min(0.95, confidence))

        # 市场状态加成
        regime_boost = {
            MarketRegime.POLICY_BOTTOM: 0.10,
            MarketRegime.BULL_TREND:    0.05,
            MarketRegime.STRUCTURAL:    0.00,
            MarketRegime.STOCK_GAME:   -0.05,
        }.get(regime.regime, 0)
        confidence = max(0.45, min(0.95, confidence + regime_boost))

        if confidence < self.min_confidence:
            return None

        # ── 仓位计算（市场状态×信号质量） ────────
        position_pct = self._calc_position(regime, confidence, rr)

        # 买入成本（含佣金+滑点）
        buy_cost = price * (1 + self.commission_rate + self.slippage_rate)

        return AShareSignal(
            symbol=symbol,
            signal_type=stype,
            entry_price=round(buy_cost, 3),
            stop_loss=round(stop, 3),
            target_price=round(target, 3),
            confidence=round(confidence, 3),
            factor_score=factor_score.total_score,
            regime=regime.regime,
            position_pct=round(position_pct, 4),
            atr=round(atr, 3),
            signals={
                "vol_ratio": round(vol_ratio, 2),
                "ret_5d":    round(ret_5 * 100, 1),
                "rr_ratio":  round(rr, 2),
                "prev_high": round(prev_high, 2),
                **factor_score.signals,
            },
        )

    # ─────────────────────────────────────────────
    # 仓位管理
    # ─────────────────────────────────────────────

    def _calc_position(
        self,
        regime: RegimeResult,
        confidence: float,
        rr_ratio: float,
    ) -> float:
        """
        动态仓位计算

        仓位 = 市场状态上限 × 信号质量调节
        信号质量 = confidence × min(rr_ratio/2, 1)
        """
        regime_cap = regime.max_position
        quality = confidence * min(rr_ratio / 2.0, 1.0)

        # 基础仓位 = 市场上限 × (0.5 + quality×0.5)
        base = regime_cap * (0.5 + quality * 0.5)

        # 不超过单笔建议上限
        return min(base, self.base_position_pct * 2, regime_cap / max(regime.max_positions, 1))

    # ─────────────────────────────────────────────
    # 执行交易
    # ─────────────────────────────────────────────

    def execute_buy(
        self,
        signal: AShareSignal,
        date: str,
        data_idx: int,
        is_limit_up: bool = False,
    ) -> bool:
        """执行买入，返回是否成功"""
        if is_limit_up:
            return False
        if signal.symbol in self.positions:
            return False
        if len(self.positions) >= self.max_positions:
            return False
        if not signal.is_valid:
            return False

        capital_to_use = self.capital * signal.position_pct
        buy_price = signal.entry_price
        quantity = int(capital_to_use / buy_price / 100) * 100

        if quantity < 100:
            if capital_to_use >= buy_price * 100:
                quantity = 100
            else:
                return False

        actual_cost = quantity * buy_price
        if actual_cost > self.capital:
            return False

        trade = AShareTrade(
            symbol=signal.symbol,
            entry_date=date,
            entry_price=buy_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            quantity=quantity,
            position_pct=signal.position_pct,
            signal_type=signal.signal_type.value,
            entry_idx=data_idx,
            highest_price=buy_price,
        )
        self.positions[signal.symbol] = trade
        self.trades.append(trade)
        self.capital -= actual_cost
        return True

    def check_exit(
        self,
        symbol: str,
        date: str,
        price: float,
        high: float,
        low: float,
        data_idx: int,
        is_limit_down: bool = False,
    ) -> str | None:
        """
        检查出场条件，返回出场原因或None

        出场优先级：
          1. 固定止损（绝对保护）
          2. 时间止损（行业轮动超时）
          3. 保本止损（浮盈后上移）
          4. 移动止盈（趋势跟踪）
          5. 目标止盈（到达压力位）
        """
        if symbol not in self.positions:
            return None
        if is_limit_down:
            return None

        trade = self.positions[symbol]
        holding_days = data_idx - trade.entry_idx

        # 最小持仓3天（避免被日内噪声扫出）
        if holding_days < 3:
            return None

        # 更新历史最高价
        trade.highest_price = max(trade.highest_price, high)

        # ── 1. 固定止损 ─────────────────────────
        if low <= trade.stop_loss:
            self._close(symbol, date, trade.stop_loss, "stop_loss")
            return "stop_loss"

        # ── 2. 时间止损（超时减仓）──────────────
        if holding_days >= self.max_holding_days:
            self._close(symbol, date, price, "time_stop")
            return "time_stop"

        # ── 3. 保本止损 ─────────────────────────
        profit_pct = (price - trade.entry_price) / trade.entry_price
        if profit_pct >= self.breakeven_pct and trade.stop_loss < trade.entry_price:
            trade.stop_loss = trade.entry_price  # 移至成本

        # ── 4. 移动止盈 ─────────────────────────
        # 激活条件：浮盈首次达到 trail_activation
        if profit_pct >= self.trail_activation or trade.trailing_stop is not None:
            trail_price = trade.highest_price * (1 - self.trail_pct)
            if trade.trailing_stop is None:
                trade.trailing_stop = trail_price   # 首次激活
            else:
                trade.trailing_stop = max(trade.trailing_stop, trail_price)  # 只升不降

            if low <= trade.trailing_stop:
                self._close(symbol, date, trade.trailing_stop, "trailing_stop")
                return "trailing_stop"

        # ── 5. 目标止盈（触达前高压力位）────────
        if price >= trade.target_price:
            self._close(symbol, date, price, "target_reached")
            return "target_reached"

        return None

    def _close(self, symbol: str, date: str, price: float, reason: str):
        """平仓"""
        if symbol not in self.positions:
            return
        trade = self.positions[symbol]
        trade.close(date, price, reason,
                    self.commission_rate, self.stamp_tax_rate)
        self.capital += trade.quantity * (trade.exit_price or price)
        del self.positions[symbol]

    def record_equity(self, date: str, prices: dict[str, float]):
        """记录每日权益（接收价格字典，多股精确估值）"""
        pos_value = sum(
            self.positions[sym].quantity * prices.get(sym, self.positions[sym].entry_price)
            for sym in self.positions
        )
        total = self.capital + pos_value
        self.equity_curve.append({
            "date":         date,
            "capital":      round(self.capital, 2),
            "position_val": round(pos_value, 2),
            "total":        round(total, 2),
            "return_pct":   round((total / self.initial_capital - 1) * 100, 3),
        })

    # ─────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────

    @staticmethod
    def _calc_atr(h, l, c, period: int = 14) -> float:
        n = len(c)
        if n < 2:
            return float(h[0] - l[0])
        tr = np.empty(n)
        tr[0] = h[0] - l[0]
        tr[1:] = np.maximum(
            h[1:] - l[1:],
            np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1]))
        )
        atr_period = min(period, n)
        return float(np.mean(tr[-atr_period:]))
