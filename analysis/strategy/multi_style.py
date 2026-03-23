"""
analysis/strategy/multi_style.py — 多风格策略引擎

核心功能：
  1. 根据 TradingStyle 自动应用对应参数
  2. 集成扩展信号检测器（短线/波段/中线信号）
  3. 组合级别风控（最大回撤熔断/连亏冷静期/日亏限额）
  4. 金字塔加仓（浮盈后逐步加仓）

与 AShareStrategy 的关系：
  MultiStyleStrategy 继承 AShareStrategy，通过 StyleConfig 覆盖参数，
  并新增 SignalDetector 集成和组合风控逻辑。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from analysis.strategy.ashare_strategy import (
    AShareStrategy, AShareSignal, AShareTrade, SignalType
)
from analysis.strategy.style import TradingStyle, StyleConfig, get_style_config
from analysis.strategy.signal_detector import AShareSignalDetector, ExtendedSignalType
from analysis.regime.market_regime import RegimeResult, MarketRegime
from analysis.factors.multi_factor import FactorScore


@dataclass
class PortfolioRiskState:
    """组合级别风控状态"""
    # 熔断
    peak_equity:         float = 0.0
    max_drawdown_pct:    float = 0.0
    circuit_break_pct:   float = 0.08   # 组合回撤8%停止新开仓
    circuit_triggered:   bool  = False
    # 连亏冷静期
    consecutive_losses:  int   = 0
    cooldown_days_left:  int   = 0
    max_consec_loss:     int   = 3       # 连亏3次触发冷静
    cooldown_days:       int   = 3       # 冷静3天
    # 日亏限额
    day_pnl:             float = 0.0
    day_stop_pct:        float = 0.03    # 当日亏损3%停止

    def update_peak(self, equity: float) -> None:
        if equity > self.peak_equity:
            self.peak_equity = equity
        if self.peak_equity > 0:
            dd = (self.peak_equity - equity) / self.peak_equity
            self.max_drawdown_pct = max(self.max_drawdown_pct, dd)

    @property
    def can_open_new(self) -> bool:
        return (not self.circuit_triggered
                and self.cooldown_days_left == 0
                and self.day_pnl > -self.day_stop_pct)


class MultiStyleStrategy(AShareStrategy):
    """
    多风格策略引擎

    用法::

        # 短线策略
        short = MultiStyleStrategy(style=TradingStyle.SHORT_TERM)
        # 波段策略
        swing = MultiStyleStrategy(style=TradingStyle.SWING)
        # 中线策略
        medium = MultiStyleStrategy(style=TradingStyle.MEDIUM_TERM)
    """

    def __init__(
        self,
        style:           TradingStyle | str = TradingStyle.SWING,
        initial_capital: float = 100_000,
        # 组合风控参数
        circuit_break_pct:  float = 0.08,   # 组合回撤熔断
        day_stop_pct:       float = 0.03,   # 日亏限额
        max_consec_loss:    int   = 3,      # 连亏冷静触发
        # 金字塔加仓
        enable_pyramid:     bool  = False,  # 是否启用加仓
        pyramid_threshold:  float = 0.05,   # 浮盈5%后可加仓
        pyramid_add_pct:    float = 0.50,   # 加仓仓位为初仓50%
        max_pyramid_adds:   int   = 1,      # 最多加仓1次
        **kwargs,
    ):
        if isinstance(style, str):
            style = TradingStyle(style)

        cfg = get_style_config(style)
        self.style     = style
        self.style_cfg = cfg

        # StyleConfig 控制的参数集合（从 kwargs 中去除，避免重复传入）
        _style_keys = {'max_positions','atr_stop_mult','min_stop_pct','max_stop_pct',
                       'target_lookback','target_buffer','min_rr_ratio','max_holding_days',
                       'trail_activation','trail_pct','breakeven_pct',
                       'min_factor_score','min_confidence'}
        filtered_kwargs = {k:v for k,v in kwargs.items() if k not in _style_keys}

        super().__init__(
            initial_capital  = initial_capital,
            max_positions    = cfg.max_positions,
            atr_stop_mult    = cfg.atr_stop_mult,
            min_stop_pct     = cfg.min_stop_pct,
            max_stop_pct     = cfg.max_stop_pct,
            target_lookback  = cfg.target_lookback,
            target_buffer    = cfg.target_buffer,
            min_rr_ratio     = cfg.min_rr_ratio,
            max_holding_days = cfg.max_holding_days,
            trail_activation = cfg.trail_activation,
            trail_pct        = cfg.trail_pct,
            breakeven_pct    = cfg.breakeven_pct,
            min_factor_score = cfg.min_factor_score,
            min_confidence   = cfg.min_confidence,
            **filtered_kwargs,
        )

        # 扩展信号检测器
        self._signal_detector = AShareSignalDetector()

        # 组合风控状态
        self._risk = PortfolioRiskState(
            circuit_break_pct = circuit_break_pct,
            day_stop_pct      = day_stop_pct,
            max_consec_loss   = max_consec_loss,
        )

        # 金字塔加仓配置
        self.enable_pyramid    = enable_pyramid
        self.pyramid_threshold = pyramid_threshold
        self.pyramid_add_pct   = pyramid_add_pct
        self.max_pyramid_adds  = max_pyramid_adds
        self._pyramid_counts: dict[str, int] = {}  # symbol → 已加仓次数

        # 额外统计
        self._style_signal_counts: dict[str, int] = {}

    # ─────────────────────────────────────────────
    # 信号生成（集成扩展检测器）
    # ─────────────────────────────────────────────

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        factor_score: FactorScore,
        regime: RegimeResult,
    ) -> AShareSignal | None:
        """
        多风格信号生成：
          1. 运行父类基础信号生成
          2. 运行扩展信号检测器（风格专属）
          3. 取强度最高的信号
        """
        # 组合风控：不允许开新仓时直接返回
        if not self._risk.can_open_new:
            return None

        # 父类基础信号
        base_signal = super().generate_signal(symbol, df, factor_score, regime)

        # 扩展风格信号
        ext_signals = self._signal_detector.detect_all(
            df, style=self.style.value, symbol=symbol
        )
        best_ext = self._signal_detector.get_best_signal(
            ext_signals, min_strength=0.5
        )

        if best_ext is None:
            return base_signal  # 无扩展信号，用基础信号

        # 有扩展信号：合成置信度
        ext_confidence = best_ext.strength

        # 若基础信号也存在，取两者最高置信度
        if base_signal and base_signal.is_valid:
            combined_conf = max(base_signal.confidence, ext_confidence * 0.9)
            signal = base_signal
            signal.confidence = round(combined_conf, 3)
            signal.signals["ext_signal"] = best_ext.signal_type.value
            signal.signals["ext_strength"] = best_ext.strength
        else:
            # 仅有扩展信号时，构建完整信号
            if ext_confidence < self.min_confidence:
                return None
            if not factor_score.passed_filter:
                return None
            if factor_score.total_score < self.min_factor_score:
                return None
            if not regime.is_tradeable:
                return None

            c = df["close"].values.astype(float)
            h = df["high"].values.astype(float) if "high" in df.columns else c * 1.005
            l = df["low"].values.astype(float) if "low" in df.columns else c * 0.995
            price = float(c[-1])

            stop   = self._calc_stop_loss(price, h, l, c)
            target = self._calc_target_price(price, h)
            rr     = (target - price) / (price - stop + 1e-8)

            if rr < self.min_rr_ratio:
                return None

            # 映射扩展信号类型到基础 SignalType
            stype_map = {
                ExtendedSignalType.LIMIT_UP_FOLLOW:   SignalType.MOMENTUM_BREAKOUT,
                ExtendedSignalType.GAP_UP_BREAKOUT:   SignalType.MOMENTUM_BREAKOUT,
                ExtendedSignalType.MA_GOLDEN_CROSS:   SignalType.TREND_CONTINUATION,
                ExtendedSignalType.INTRADAY_SURGE:    SignalType.VOLUME_SURGE,
                ExtendedSignalType.SWING_BREAKOUT:    SignalType.MOMENTUM_BREAKOUT,
                ExtendedSignalType.PULLBACK_MA:       SignalType.PULLBACK_ENTRY,
                ExtendedSignalType.VOLUME_DIVERGENCE: SignalType.PULLBACK_ENTRY,
                ExtendedSignalType.BOLLINGER_BREAKOUT:SignalType.MOMENTUM_BREAKOUT,
            }
            stype = stype_map.get(best_ext.signal_type, SignalType.TREND_CONTINUATION)
            position_pct = self._calc_position(regime, ext_confidence, rr)
            buy_cost = price * (1 + self.commission_rate + self.slippage_rate)

            signal = AShareSignal(
                symbol=symbol, signal_type=stype,
                entry_price=round(buy_cost, 3),
                stop_loss=stop, target_price=target,
                confidence=round(ext_confidence, 3),
                factor_score=factor_score.total_score,
                regime=regime.regime,
                position_pct=round(position_pct, 4),
                atr=round(self._calc_atr(h, l, c), 3),
                signals={
                    "ext_signal": best_ext.signal_type.value,
                    "ext_desc": best_ext.description,
                    "rr_ratio": round(rr, 2),
                },
            )

        # 统计信号类型
        key = best_ext.signal_type.value
        self._style_signal_counts[key] = self._style_signal_counts.get(key, 0) + 1

        return signal if signal.is_valid else None

    # ─────────────────────────────────────────────
    # 出场（叠加组合风控）
    # ─────────────────────────────────────────────

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
        result = super().check_exit(symbol, date, price, high, low, data_idx, is_limit_down)
        if result:
            # 更新连亏统计
            trade = None
            for t in self.trades:
                if t.symbol == symbol and t.status == "closed" and t.exit_date == date:
                    trade = t; break
            if trade:
                if trade.pnl < 0:
                    self._risk.consecutive_losses += 1
                    if self._risk.consecutive_losses >= self._risk.max_consec_loss:
                        self._risk.cooldown_days_left = self._risk.cooldown_days
                else:
                    self._risk.consecutive_losses = 0
        return result

    # ─────────────────────────────────────────────
    # 金字塔加仓
    # ─────────────────────────────────────────────

    def check_pyramid_add(
        self,
        symbol: str,
        date: str,
        price: float,
        data_idx: int,
    ) -> bool:
        """检查是否满足金字塔加仓条件并执行"""
        if not self.enable_pyramid:
            return False
        if symbol not in self.positions:
            return False
        if not self._risk.can_open_new:
            return False

        trade = self.positions[symbol]
        adds_done = self._pyramid_counts.get(symbol, 0)
        if adds_done >= self.max_pyramid_adds:
            return False

        profit_pct = (price - trade.entry_price) / trade.entry_price
        if profit_pct < self.pyramid_threshold:
            return False

        # 加仓：基于账户当前资金的一定比例（而非初仓市值的50%）
        # pyramid_add_pct=0.5 表示初仓总价值的50%，但不少于100股
        init_value = trade.quantity * trade.entry_price
        add_capital = max(init_value * self.pyramid_add_pct,
                          price * 100 * 1.1)  # 至少够买100股
        buy_price   = price * (1 + self.commission_rate + self.slippage_rate)
        add_qty     = int(add_capital / buy_price / 100) * 100

        if add_qty < 100 or add_qty * buy_price > self.capital:
            return False

        self.capital -= add_qty * buy_price
        # 更新持仓（调整均价和止损）
        old_qty  = trade.quantity
        total_qty = old_qty + add_qty
        new_avg   = (old_qty * trade.entry_price + add_qty * buy_price) / total_qty
        trade.quantity  = total_qty
        trade.entry_price = round(new_avg, 3)
        trade.stop_loss = round(new_avg * (1 - self.min_stop_pct), 3)

        self._pyramid_counts[symbol] = adds_done + 1
        return True

    # ─────────────────────────────────────────────
    # 每日组合风控更新
    # ─────────────────────────────────────────────

    def update_portfolio_risk(self, date: str, equity: float) -> None:
        """每日收盘后更新组合风控状态"""
        self._risk.update_peak(equity)

        # 熔断检测
        if self._risk.max_drawdown_pct >= self._risk.circuit_break_pct:
            self._risk.circuit_triggered = True

        # 冷静期倒计时
        if self._risk.cooldown_days_left > 0:
            self._risk.cooldown_days_left -= 1

        # 重置日亏（每天重置）
        self._risk.day_pnl = 0.0

    def reset(self) -> None:
        super().reset()
        self._risk = PortfolioRiskState(
            circuit_break_pct = self._risk.circuit_break_pct,
            day_stop_pct      = self._risk.day_stop_pct,
            max_consec_loss   = self._risk.max_consec_loss,
        )
        self._pyramid_counts = {}
        self._style_signal_counts = {}

    # ─────────────────────────────────────────────
    # 统计摘要
    # ─────────────────────────────────────────────

    def get_style_summary(self) -> dict:
        return {
            "style":              self.style.value,
            "style_name":         self.style_cfg.name_cn,
            "max_holding_days":   self.max_holding_days,
            "circuit_triggered":  self._risk.circuit_triggered,
            "consecutive_losses": self._risk.consecutive_losses,
            "style_signals":      self._style_signal_counts,
        }

    @classmethod
    def create_short_term(cls, initial_capital: float = 100_000, **kwargs) -> "MultiStyleStrategy":
        """便捷工厂：短线策略"""
        return cls(style=TradingStyle.SHORT_TERM, initial_capital=initial_capital, **kwargs)

    @classmethod
    def create_swing(cls, initial_capital: float = 100_000, **kwargs) -> "MultiStyleStrategy":
        """便捷工厂：波段策略"""
        return cls(style=TradingStyle.SWING, initial_capital=initial_capital, **kwargs)

    @classmethod
    def create_medium_term(cls, initial_capital: float = 100_000, **kwargs) -> "MultiStyleStrategy":
        """便捷工厂：中线策略"""
        return cls(style=TradingStyle.MEDIUM_TERM, initial_capital=initial_capital, **kwargs)
