"""
analysis/pool/monitor.py — 策略性能监控与淘汰引擎

监控指标（每周/每月更新）：
  - 滚动 Sharpe（近20/60笔交易）
  - 胜率趋势（近期 vs 历史）
  - 最大回撤（持续时间 + 幅度）
  - 目标止盈触达率（策略有效性代理）
  - 连续亏损笔数

淘汰规则（触发任一即降级/淘汰）：
  降级（ACTIVE → DEGRADED）：
    R1: 滚动20笔 Sharpe < 0（收益转负）
    R2: 近20笔胜率 < 30%（远低于验证期）
    R3: 最大回撤超过验证期2倍
    R4: 目标止盈触达率连续2周为0%
    R5: 连续亏损≥5笔

  淘汰（DEGRADED → RETIRED）：
    E1: 降级后60天仍未恢复
    E2: 滚动60笔 Sharpe < -0.5（持续亏损）
    E3: 总回撤超过止损线（如 -20%）
    E4: 验证期 Sharpe 与当前差距 > 1.5（规则彻底失效）
    E5: 人工标记淘汰

恢复规则（DEGRADED → ACTIVE）：
    V1: 近20笔 Sharpe 恢复至 > 0.3
    V2: 近20笔胜率 > 40%
    V3: 连续亏损 < 3笔
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from analysis.pool.strategy_registry import StrategyRegistry, StrategyStatus, StrategyRecord
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────

@dataclass
class TradeRecord:
    """单笔交易记录（用于监控）"""
    date:       str
    symbol:     str
    pnl_pct:    float
    exit_reason:str

    @property
    def is_win(self) -> bool:
        return self.pnl_pct > 0


@dataclass
class MonitorSnapshot:
    """监控快照"""
    strategy_id:    str
    snapshot_at:    str
    # 滚动指标
    rolling_n:      int       # 近 N 笔
    rolling_sharpe: float
    rolling_win_rate:float
    rolling_ret:    float
    rolling_max_dd: float
    consec_losses:  int       # 当前连续亏损数
    # 触发规则
    triggered_rules:list[str]
    recommended_action: str   # "ok" / "degrade" / "retire"


@dataclass
class StrategyMonitorState:
    """单策略监控状态（内存）"""
    strategy_id:   str
    trades:        list[TradeRecord] = field(default_factory=list)
    degraded_since:str | None = None    # 进入 DEGRADED 的时间

    def add_trade(self, t: TradeRecord) -> None:
        self.trades.append(t)

    def rolling_metrics(self, n: int = 20) -> dict:
        """计算近 N 笔的性能指标"""
        recent = self.trades[-n:] if len(self.trades) >= n else self.trades
        if not recent:
            return {"sharpe": 0.0, "win_rate": 0.0, "ret": 0.0,
                    "max_dd": 0.0, "consec_losses": 0}

        rets = np.array([t.pnl_pct / 100 for t in recent])
        mu   = float(np.mean(rets))
        std  = float(np.std(rets, ddof=1)) if len(rets) > 1 else 1e-8
        sharpe = (mu / std * np.sqrt(252 / max(len(rets), 1))) if std > 1e-10 else 0.0
        win_rate = float(np.mean([1 if t.is_win else 0 for t in recent]))
        cumret   = float((1 + rets).prod() - 1) * 100
        peak     = 1.0; max_dd = 0.0; cum = 1.0
        for r in rets:
            cum *= (1 + r)
            if cum > peak: peak = cum
            dd = (peak - cum) / peak * 100
            max_dd = max(max_dd, dd)

        # 连续亏损
        consec = 0
        for t in reversed(self.trades):
            if t.is_win: break
            consec += 1

        return {"sharpe": round(sharpe, 4), "win_rate": round(win_rate, 4),
                "ret": round(cumret, 4), "max_dd": round(max_dd, 4),
                "consec_losses": consec}


# ─────────────────────────────────────────────────
# 监控引擎
# ─────────────────────────────────────────────────

class StrategyMonitor:
    """
    策略性能监控与淘汰引擎

    用法::
        monitor = StrategyMonitor(registry)
        # 每笔交易完成后记录
        monitor.record_trade(strategy_id, date, symbol, pnl_pct, exit_reason)
        # 定期检查（每周/每日）
        snapshots = monitor.check_all()
        for snap in snapshots:
            if snap.recommended_action in ("degrade","retire"):
                print(snap)
    """

    def __init__(
        self,
        registry:        StrategyRegistry,
        # 降级阈值
        degrade_sharpe:  float = 0.0,    # R1: 滚动Sharpe低于此值
        degrade_winrate: float = 0.30,   # R2: 近期胜率低于此值
        degrade_dd_mult: float = 2.0,    # R3: 回撤超验证期倍数
        degrade_consec:  int   = 5,      # R5: 连续亏损笔数
        # 淘汰阈值
        retire_days:     int   = 60,     # E1: 降级后多少天未恢复
        retire_sharpe60: float = -0.5,   # E2: 60笔Sharpe低于此值
        retire_total_dd: float = 20.0,   # E3: 总回撤阈值(%)
        retire_decay:    float = 1.5,    # E4: Sharpe衰减阈值
        # 恢复阈值
        recover_sharpe:  float = 0.3,    # V1: 恢复Sharpe
        recover_winrate: float = 0.40,   # V2: 恢复胜率
        recover_consec:  int   = 3,      # V3: 连续亏损上限
        # 窗口
        short_window:    int   = 20,
        long_window:     int   = 60,
    ):
        self.registry        = registry
        self.degrade_sharpe  = degrade_sharpe
        self.degrade_winrate = degrade_winrate
        self.degrade_dd_mult = degrade_dd_mult
        self.degrade_consec  = degrade_consec
        self.retire_days     = retire_days
        self.retire_sharpe60 = retire_sharpe60
        self.retire_total_dd = retire_total_dd
        self.retire_decay    = retire_decay
        self.recover_sharpe  = recover_sharpe
        self.recover_winrate = recover_winrate
        self.recover_consec  = recover_consec
        self.short_window    = short_window
        self.long_window     = long_window
        self._states: dict[str, StrategyMonitorState] = {}

    # ─────────────────────────────────────────────
    # 交易记录
    # ─────────────────────────────────────────────

    def record_trade(
        self,
        strategy_id: str,
        date:        str,
        symbol:      str,
        pnl_pct:     float,
        exit_reason: str = "",
    ) -> None:
        """记录一笔已平仓交易"""
        state = self._get_state(strategy_id)
        state.add_trade(TradeRecord(date, symbol, pnl_pct, exit_reason))
        logger.debug(f"[{strategy_id}] 记录交易 {symbol} {date}: {pnl_pct:+.2f}%")

    # ─────────────────────────────────────────────
    # 定期检查
    # ─────────────────────────────────────────────

    def check(self, strategy_id: str) -> MonitorSnapshot:
        """对单个策略进行监控检查"""
        record = self.registry.get(strategy_id)
        state  = self._get_state(strategy_id)

        short_m = state.rolling_metrics(self.short_window)
        long_m  = state.rolling_metrics(self.long_window)

        triggered: list[str] = []
        action = "ok"

        if record.status_enum == StrategyStatus.ACTIVE:
            action = self._check_degrade(record, state, short_m, long_m, triggered)
        elif record.status_enum == StrategyStatus.DEGRADED:
            action = self._check_retire_or_recover(record, state, short_m, long_m, triggered)

        # 更新线上指标
        if len(state.trades) > 0:
            self.registry.update_live(
                strategy_id,
                sharpe      = short_m["sharpe"],
                win_rate    = short_m["win_rate"],
                ret_pct     = short_m["ret"],
                max_dd      = short_m["max_dd"],
                trade_count = len(state.trades),
            )

        snap = MonitorSnapshot(
            strategy_id         = strategy_id,
            snapshot_at         = datetime.now().isoformat(),
            rolling_n           = min(len(state.trades), self.short_window),
            rolling_sharpe      = short_m["sharpe"],
            rolling_win_rate    = short_m["win_rate"],
            rolling_ret         = short_m["ret"],
            rolling_max_dd      = short_m["max_dd"],
            consec_losses       = short_m["consec_losses"],
            triggered_rules     = triggered,
            recommended_action  = action,
        )

        if action == "degrade" and record.status_enum == StrategyStatus.ACTIVE:
            self.registry.transition(
                strategy_id, StrategyStatus.DEGRADED,
                f"监控降级: {'; '.join(triggered)}"
            )
            state.degraded_since = datetime.now().isoformat()
        elif action == "retire":
            self.registry.transition(
                strategy_id, StrategyStatus.RETIRED,
                f"监控淘汰: {'; '.join(triggered)}"
            )
        elif action == "recover" and record.status_enum == StrategyStatus.DEGRADED:
            self.registry.transition(
                strategy_id, StrategyStatus.ACTIVE,
                f"性能恢复: Sharpe={short_m['sharpe']:.2f} 胜率={short_m['win_rate']:.0%}"
            )
            state.degraded_since = None

        return snap

    def check_all(self) -> list[MonitorSnapshot]:
        """检查所有 ACTIVE + DEGRADED 策略"""
        snapshots = []
        for record in self.registry.list_all():
            if record.status_enum in (StrategyStatus.ACTIVE, StrategyStatus.DEGRADED):
                try:
                    snapshots.append(self.check(record.strategy_id))
                except Exception as e:
                    logger.warning(f"检查策略 {record.strategy_id} 失败: {e}")
        return snapshots

    # ─────────────────────────────────────────────
    # 降级/恢复/淘汰规则
    # ─────────────────────────────────────────────

    def _check_degrade(
        self, record: StrategyRecord, state: StrategyMonitorState,
        short_m: dict, long_m: dict, triggered: list[str]
    ) -> str:
        if len(state.trades) < 5:
            return "ok"  # 交易不足，不判断

        # R1: 滚动 Sharpe 转负
        if short_m["sharpe"] < self.degrade_sharpe:
            triggered.append(f"R1:Sharpe={short_m['sharpe']:.2f}")

        # R2: 近期胜率骤降
        if short_m["win_rate"] < self.degrade_winrate and len(state.trades) >= 10:
            triggered.append(f"R2:胜率={short_m['win_rate']:.0%}")

        # R3: 回撤超验证期2倍
        if record.validation_sharpe is not None:
            ref_dd = record.live_max_dd or 5.0
            if short_m["max_dd"] > ref_dd * self.degrade_dd_mult:
                triggered.append(f"R3:DD={short_m['max_dd']:.1f}%>{ref_dd*self.degrade_dd_mult:.1f}%")

        # R5: 连续亏损
        if short_m["consec_losses"] >= self.degrade_consec:
            triggered.append(f"R5:连亏{short_m['consec_losses']}笔")

        return "degrade" if triggered else "ok"

    def _check_retire_or_recover(
        self, record: StrategyRecord, state: StrategyMonitorState,
        short_m: dict, long_m: dict, triggered: list[str]
    ) -> str:
        # 检查是否可以恢复
        can_recover = (
            short_m["sharpe"]       >= self.recover_sharpe  and
            short_m["win_rate"]     >= self.recover_winrate and
            short_m["consec_losses"] < self.recover_consec
        )
        if can_recover:
            return "recover"

        # 检查是否应该淘汰
        # E1: 降级超过 retire_days 天
        if state.degraded_since:
            degraded_dt = datetime.fromisoformat(state.degraded_since)
            days_degraded = (datetime.now() - degraded_dt).days
            if days_degraded >= self.retire_days:
                triggered.append(f"E1:降级{days_degraded}天未恢复")

        # E2: 长期 Sharpe 持续负值
        if len(state.trades) >= self.long_window and long_m["sharpe"] < self.retire_sharpe60:
            triggered.append(f"E2:60笔Sharpe={long_m['sharpe']:.2f}")

        # E3: 总回撤超阈值
        if long_m["max_dd"] > self.retire_total_dd:
            triggered.append(f"E3:总DD={long_m['max_dd']:.1f}%")

        # E4: Sharpe 衰减 vs 验证期
        if record.validation_sharpe is not None:
            decay = record.validation_sharpe - short_m["sharpe"]
            if decay > self.retire_decay:
                triggered.append(f"E4:Sharpe衰减{decay:.2f}")

        return "retire" if triggered else "ok"

    # ─────────────────────────────────────────────
    # 工具
    # ─────────────────────────────────────────────

    def _get_state(self, sid: str) -> StrategyMonitorState:
        if sid not in self._states:
            self._states[sid] = StrategyMonitorState(strategy_id=sid)
        return self._states[sid]

    def summary_report(self) -> str:
        lines = ["", "=" * 60, "  策略监控报告", "=" * 60]
        for sid, state in self._states.items():
            try:
                rec = self.registry.get(sid)
            except KeyError:
                continue
            m = state.rolling_metrics(self.short_window)
            lines.append(
                f"  [{rec.status}] {sid:<20} "
                f"近{min(len(state.trades),self.short_window)}笔: "
                f"Sharpe={m['sharpe']:+.2f} "
                f"胜率={m['win_rate']:.0%} "
                f"收益={m['ret']:+.1f}% "
                f"连亏={m['consec_losses']}"
            )
        lines.append("=" * 60)
        return "\n".join(lines)
