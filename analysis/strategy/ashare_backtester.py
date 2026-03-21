"""
analysis/strategy/ashare_backtester.py

A股新策略回测引擎（单股）

流程：
  每个交易日：
    1. 计算当前市场状态（每5天重算）
    2. 对该股票进行多因子评分
    3. 若满足入场条件 → 生成信号 → 尝试买入
    4. 检查已持仓的出场条件
    5. 记录权益
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from analysis.regime.market_regime import AShareMarketRegime, MarketRegime, RegimeResult
from analysis.factors.multi_factor import AShareMultiFactor, FactorScore
from analysis.strategy.ashare_strategy import AShareStrategy, AShareSignal, AShareTrade
from analysis.technical.indicators import TechnicalIndicators


@dataclass
class AShareBacktestResult:
    symbol: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    avg_return_per_trade: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float
    trades: list[AShareTrade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    # 新增：信号类型统计
    signal_type_counts: dict[str, int] = field(default_factory=dict)
    exit_reason_counts: dict[str, int] = field(default_factory=dict)
    regime_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":               self.symbol,
            "start_date":           str(self.start_date),
            "end_date":             str(self.end_date),
            "total_trades":         self.total_trades,
            "win_rate":             self.win_rate,
            "win_rate_pct":         f"{self.win_rate:.1%}",
            "total_return_pct":     self.total_return_pct,
            "avg_return_per_trade": self.avg_return_per_trade,
            "max_drawdown_pct":     self.max_drawdown_pct,
            "sharpe_ratio":         self.sharpe_ratio,
            "sortino_ratio":        self.sortino_ratio,
            "calmar_ratio":         self.calmar_ratio,
            "profit_factor":        min(self.profit_factor, 999.99),
            "signal_type_counts":   self.signal_type_counts,
            "exit_reason_counts":   self.exit_reason_counts,
        }


class AShareBacktester:
    """
    A股新策略单股回测器

    对比旧波浪回测的改进：
      ✅ 目标价用前高，而非斐波那契
      ✅ 止损基于当日low，而非仅收盘价
      ✅ record_equity 使用各股自己的价格（非单价代理）
      ✅ 市场状态决定仓位上限
      ✅ 多因子评分作为选股过滤
    """

    def __init__(
        self,
        strategy: AShareStrategy | None = None,
        reanalyze_every: int = 5,
        min_data_rows: int = 130,
    ):
        self.strategy        = strategy or AShareStrategy()
        self.reanalyze_every = reanalyze_every
        self.min_data_rows   = min_data_rows
        self._regime_detector = AShareMarketRegime()
        self._factor_engine   = AShareMultiFactor()
        self._ti              = TechnicalIndicators()

    def run(self, symbol: str, df: pd.DataFrame) -> AShareBacktestResult:
        """运行单股回测"""
        if df is None or len(df) < self.min_data_rows:
            return self._empty_result(symbol, df)

        # 准备数据
        df = df.copy().sort_values("date").reset_index(drop=True)
        df["date"] = df["date"].astype(str)

        # 计算技术指标（一次性，供多因子使用）
        try:
            df = self._ti.calculate_all(df)
        except Exception:
            pass

        # 涨跌停标记
        sym_prefix = symbol[:3] if len(symbol) >= 3 else symbol
        limit_pct  = 0.195 if sym_prefix in ("688", "300", "301") else 0.095
        df["pct_change"]  = df["close"].pct_change()
        df["is_limit_up"] = df["pct_change"] >= limit_pct
        df["is_limit_dn"] = df["pct_change"] <= -limit_pct

        # 重置策略状态
        self.strategy.reset()

        # 缓存变量
        closes  = df["close"].values.astype(float)
        highs   = df["high"].values.astype(float) if "high" in df.columns else closes * 1.005
        lows    = df["low"].values.astype(float)  if "low"  in df.columns else closes * 0.995
        dates   = df["date"].values
        limit_u = df["is_limit_up"].values.astype(bool)
        limit_d = df["is_limit_dn"].values.astype(bool)

        _regime:  RegimeResult | None = None
        _fscore:  FactorScore  | None = None

        for i in range(self.min_data_rows, len(df)):
            date  = str(dates[i])
            price = float(closes[i])
            high  = float(highs[i])
            low   = float(lows[i])

            # 每 reanalyze_every 天重新计算市场状态 & 因子评分
            if i % self.reanalyze_every == 0 or _regime is None:
                sub = df.iloc[max(0, i - 250):i]
                _regime = self._regime_detector.detect(sub)
                _fscore = self._factor_engine.score(symbol, sub)

            # ── 出场检查（先于入场，避免同天买卖）────
            self.strategy.check_exit(
                symbol, date, price, high, low, i,
                is_limit_down=bool(limit_d[i])
            )

            # ── 入场检查 ─────────────────────────────
            if (symbol not in self.strategy.positions
                    and _regime is not None
                    and _fscore is not None
                    and _regime.is_tradeable
                    and not bool(limit_u[i])):

                sub_entry = df.iloc[max(0, i - 90):i]
                signal = self.strategy.generate_signal(
                    symbol, sub_entry, _fscore, _regime
                )
                if signal and signal.is_valid:
                    self.strategy.execute_buy(
                        signal, date, i, is_limit_up=bool(limit_u[i])
                    )

            # ── 记录权益（使用实际价格）─────────────
            self.strategy.record_equity(date, {symbol: price})

        # 强制平仓未平仓的持仓
        if symbol in self.strategy.positions:
            last_date  = str(dates[-1])
            last_price = float(closes[-1])
            self.strategy._close(symbol, last_date, last_price, "end_of_backtest")

        return self._calc_result(symbol, df)

    # ─────────────────────────────────────────────
    # 结果计算
    # ─────────────────────────────────────────────

    def _calc_result(self, symbol: str, df: pd.DataFrame) -> AShareBacktestResult:
        trades    = self.strategy.trades
        closed    = [t for t in trades if t.status == "closed"]
        eq_values = [e["total"] for e in self.strategy.equity_curve]

        if not closed:
            return AShareBacktestResult(
                symbol=symbol,
                start_date=df["date"].iloc[0],
                end_date=df["date"].iloc[-1],
                total_trades=0,
                winning_trades=0, losing_trades=0,
                win_rate=0.0, total_return_pct=0.0,
                avg_return_per_trade=0.0, max_drawdown_pct=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0,
                calmar_ratio=0.0, profit_factor=0.0,
                trades=trades, equity_curve=self.strategy.equity_curve,
            )

        winners = [t for t in closed if t.pnl > 0]
        losers  = [t for t in closed if t.pnl <= 0]
        win_rate = len(winners) / len(closed)

        gross_profit = sum(t.pnl for t in winners)
        gross_loss   = abs(sum(t.pnl for t in losers))
        profit_factor = gross_profit / (gross_loss + 1e-8)

        # 收益率（基于权益曲线）
        if eq_values and len(eq_values) >= 2:
            total_ret_pct = (eq_values[-1] / self.strategy.initial_capital - 1) * 100
            daily_rets    = pd.Series(eq_values).pct_change().dropna()
            rf_daily      = 0.03 / 252
            std = float(daily_rets.std())
            sharpe  = ((daily_rets.mean() - rf_daily) / std * np.sqrt(252)) if std > 0 else 0.0
            down    = daily_rets[daily_rets < rf_daily] - rf_daily
            dstd    = float(down.std()) if len(down) > 1 else 0.0
            sortino = ((daily_rets.mean() - rf_daily) / dstd * np.sqrt(252)) if dstd > 0 else 0.0
        else:
            total_ret_pct = 0.0; sharpe = sortino = 0.0

        # 最大回撤
        max_dd_pct = 0.0
        peak = eq_values[0] if eq_values else self.strategy.initial_capital
        for eq in eq_values:
            if eq > peak: peak = eq
            if peak > 0:
                dd = (peak - eq) / peak * 100
                if dd > max_dd_pct: max_dd_pct = dd

        # Calmar（复利年化）
        n_days = len(eq_values)
        compound_ann = (1 + total_ret_pct / 100) ** (252 / max(n_days, 1)) - 1
        calmar = (compound_ann / (max_dd_pct / 100)) if max_dd_pct > 0 else 0.0

        # 信号/退出统计
        signal_counts: dict[str, int] = {}
        exit_counts:   dict[str, int] = {}
        regime_counts: dict[str, int] = {}
        for t in closed:
            signal_counts[t.signal_type] = signal_counts.get(t.signal_type, 0) + 1
            key = t.exit_reason or "unknown"
            exit_counts[key] = exit_counts.get(key, 0) + 1

        return AShareBacktestResult(
            symbol=symbol,
            start_date=df["date"].iloc[0],
            end_date=df["date"].iloc[-1],
            total_trades=len(closed),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=win_rate,
            total_return_pct=round(total_ret_pct, 4),
            avg_return_per_trade=round(
                float(np.mean([t.pnl_pct for t in closed])) if closed else 0, 3
            ),
            max_drawdown_pct=round(max_dd_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
            profit_factor=round(profit_factor, 4),
            trades=trades,
            equity_curve=self.strategy.equity_curve,
            signal_type_counts=signal_counts,
            exit_reason_counts=exit_counts,
            regime_counts=regime_counts,
        )

    def _empty_result(self, symbol: str, df: pd.DataFrame | None) -> AShareBacktestResult:
        start = df["date"].iloc[0] if df is not None and len(df) > 0 else ""
        end   = df["date"].iloc[-1] if df is not None and len(df) > 0 else ""
        return AShareBacktestResult(
            symbol=symbol, start_date=start, end_date=end,
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0.0, total_return_pct=0.0,
            avg_return_per_trade=0.0, max_drawdown_pct=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0,
            calmar_ratio=0.0, profit_factor=0.0,
        )
