"""
analysis/pool/manager.py — 策略池管理器

统一入口，整合：
  StrategyRegistry   策略注册与状态管理
  StrategyValidator  滚动验证 + 统计检验
  StrategyMonitor    性能监控 + 淘汰决策

核心工作流：

  1. 新策略入池：
     pool.register() → CANDIDATE → pool.validate() → SHADOW/ACTIVE/RETIRED

  2. 定期监控：
     pool.monitor_all() → 对 ACTIVE 策略检查 → 可能触发 DEGRADED/RETIRED

  3. 策略推荐：
     pool.recommend() → 返回当前最优 ACTIVE 策略

  4. 策略轮换：
     pool.rotate() → 比较所有 ACTIVE 策略性能 → 返回推荐使用的策略 ID

  5. 批量验证现有策略：
     pool.validate_all() → 对所有 CANDIDATE/SHADOW 策略运行验证

典型使用场景::

    # 初始化
    pool = StrategyPoolManager()

    # 注册并验证三种预设风格
    pool.register_defaults(symbol_dfs)

    # 日常监控（每天盘后）
    alerts = pool.monitor_all()

    # 选择今日使用的策略
    best = pool.recommend()
    if best:
        agent = AShareAgent(strategy=MultiStyleStrategy(style=best.style))
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from analysis.pool.strategy_registry import StrategyRegistry, StrategyStatus, StrategyRecord
from analysis.pool.validator import StrategyValidator, ValidationResult
from analysis.pool.monitor import StrategyMonitor, MonitorSnapshot
from analysis.strategy.multi_style import MultiStyleStrategy
from analysis.strategy.style import TradingStyle, STYLE_CONFIGS
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PoolSummary:
    """策略池摘要"""
    total:      int
    by_status:  dict[str, int]
    active:     list[str]
    degraded:   list[str]
    retired:    list[str]
    best_id:    str | None
    best_name:  str | None
    best_sharpe:float | None
    alerts:     list[str] = field(default_factory=list)


class StrategyPoolManager:
    """
    策略池管理器 — 系统核心调度器

    设计目标：
      - 一行代码完成策略注册+验证+监控
      - 清晰的淘汰决策，有据可查（所有操作记录在 Registry）
      - 易于扩展（自定义策略、自定义阈值）
    """

    def __init__(
        self,
        storage_path:   str = "results/strategy_pool.json",
        validator_cfg:  dict | None = None,
        monitor_cfg:    dict | None = None,
    ):
        self.registry  = StrategyRegistry(storage_path=storage_path)
        self.validator = StrategyValidator(**(validator_cfg or {}))
        self.monitor   = StrategyMonitor(self.registry, **(monitor_cfg or {}))

    # ─────────────────────────────────────────────
    # 注册
    # ─────────────────────────────────────────────

    def register(
        self,
        name:   str,
        style:  str,
        params: dict | None = None,
        notes:  list[str] | None = None,
    ) -> str:
        """注册新策略，返回策略 ID"""
        sid = self.registry.register(name, style, params, notes)
        self.registry.transition(sid, StrategyStatus.SHADOW, "自动进入影子期")
        return sid

    def register_defaults(
        self,
        symbol_dfs: dict[str, pd.DataFrame],
        auto_validate: bool = True,
    ) -> dict[str, str]:
        """
        注册三种预设风格策略并自动验证。

        Returns:
            {style: strategy_id}
        """
        sid_map: dict[str, str] = {}
        for style_enum, cfg in STYLE_CONFIGS.items():
            style = style_enum.value
            sid = self.registry.register(
                name   = f"预设_{cfg.name_cn}策略",
                style  = style,
                params = {
                    "max_holding_days": cfg.max_holding_days,
                    "min_stop_pct":     cfg.min_stop_pct,
                    "max_stop_pct":     cfg.max_stop_pct,
                    "min_rr_ratio":     cfg.min_rr_ratio,
                    "min_factor_score": cfg.min_factor_score,
                },
                notes = [f"系统预设{cfg.name_cn}策略，自动注册"],
            )
            self.registry.transition(sid, StrategyStatus.SHADOW, "预设策略进入影子期")
            sid_map[style] = sid

        if auto_validate and symbol_dfs:
            for style, sid in sid_map.items():
                self._validate_one(sid, style, symbol_dfs)

        return sid_map

    # ─────────────────────────────────────────────
    # 验证
    # ─────────────────────────────────────────────

    def validate(
        self,
        strategy_id: str,
        symbol_dfs:  dict[str, pd.DataFrame],
    ) -> ValidationResult:
        """对指定策略运行完整验证"""
        record = self.registry.get(strategy_id)
        return self._validate_one(strategy_id, record.style, symbol_dfs)

    def validate_all(
        self,
        symbol_dfs: dict[str, pd.DataFrame],
        statuses:   list[StrategyStatus] | None = None,
    ) -> list[ValidationResult]:
        """批量验证（默认对 CANDIDATE + SHADOW 策略）"""
        if statuses is None:
            statuses = [StrategyStatus.CANDIDATE, StrategyStatus.SHADOW]
        results = []
        for status in statuses:
            for record in self.registry.list_by_status(status):
                try:
                    r = self._validate_one(record.strategy_id, record.style, symbol_dfs)
                    results.append(r)
                except Exception as e:
                    logger.warning(f"验证失败 {record.strategy_id}: {e}")
        return results

    def _validate_one(
        self,
        strategy_id: str,
        style:       str,
        symbol_dfs:  dict[str, pd.DataFrame],
    ) -> ValidationResult:
        record = self.registry.get(strategy_id)
        params = record.params or {}

        def factory() -> MultiStyleStrategy:
            return MultiStyleStrategy(
                style=style,
                initial_capital=100_000,
                **{k: v for k, v in params.items()
                   if k not in {'max_holding_days','min_stop_pct','max_stop_pct',
                                'min_rr_ratio','min_factor_score'}
                   }
            )

        t0 = time.time()
        result = self.validator.validate(
            strategy_id      = strategy_id,
            name             = record.name,
            strategy_factory = factory,
            symbol_dfs       = symbol_dfs,
        )
        elapsed = time.time() - t0

        # 更新验证结果到注册表
        self.registry.update_validation(
            strategy_id,
            sharpe   = result.oos_sharpe,
            win_rate = result.oos_win_rate,
            ret_pct  = result.oos_ret,
            pvalue   = result.pvalue,
            passed   = result.passed,
        )

        # 状态迁移
        if result.passed:
            self.registry.transition(
                strategy_id, StrategyStatus.ACTIVE,
                f"验证通过 OOS_Sharpe={result.oos_sharpe:.2f} p={result.pvalue:.3f} ({elapsed:.0f}s)")
        else:
            self.registry.transition(
                strategy_id, StrategyStatus.RETIRED,
                f"验证失败: {'; '.join(result.fail_reasons)}")

        logger.info(f"[{strategy_id}] 验证{'通过' if result.passed else '失败'} "
                    f"耗时{elapsed:.0f}s")
        return result

    # ─────────────────────────────────────────────
    # 监控
    # ─────────────────────────────────────────────

    def record_trade(
        self,
        strategy_id: str,
        date:        str,
        symbol:      str,
        pnl_pct:     float,
        exit_reason: str = "",
    ) -> None:
        """记录策略的实际交易（每次平仓后调用）"""
        self.monitor.record_trade(strategy_id, date, symbol, pnl_pct, exit_reason)

    def monitor_all(self) -> list[MonitorSnapshot]:
        """定期监控所有活跃策略（建议每日盘后调用）"""
        return self.monitor.check_all()

    # ─────────────────────────────────────────────
    # 推荐与轮换
    # ─────────────────────────────────────────────

    def recommend(self) -> StrategyRecord | None:
        """推荐当前最优策略（ACTIVE中Sharpe最高）"""
        return self.registry.recommend()

    def rotate(self) -> list[tuple[str, float]]:
        """
        策略轮换排名：返回所有 ACTIVE 策略按综合得分排序。

        综合得分 = Sharpe×0.4 + 胜率×0.3 + 收益×0.2 + 一致性×0.1
        """
        active = self.registry.list_active()
        scored: list[tuple[str, float]] = []
        for r in active:
            sharpe   = r.live_sharpe or r.validation_sharpe or 0.0
            win_rate = (r.live_win_rate or r.validation_win_rate or 0.0) * 100
            ret      = r.live_ret_pct or r.validation_ret_pct or 0.0
            val_wr   = (r.validation_win_rate or 0.0) * 100
            score = sharpe * 0.4 + win_rate * 0.3 + ret * 0.2 + val_wr * 0.1
            scored.append((r.strategy_id, round(score, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def get_strategy(self, strategy_id: str) -> MultiStyleStrategy:
        """按 ID 创建策略实例"""
        record = self.registry.get(strategy_id)
        return MultiStyleStrategy(
            style          = record.style,
            initial_capital= 100_000,
        )

    # ─────────────────────────────────────────────
    # 摘要
    # ─────────────────────────────────────────────

    def summary(self) -> PoolSummary:
        counts = self.registry.count()
        best   = self.registry.recommend()
        return PoolSummary(
            total     = sum(counts.values()),
            by_status = counts,
            active    = [r.strategy_id for r in self.registry.list_active()],
            degraded  = [r.strategy_id for r in self.registry.list_by_status(StrategyStatus.DEGRADED)],
            retired   = [r.strategy_id for r in self.registry.list_by_status(StrategyStatus.RETIRED)],
            best_id   = best.strategy_id if best else None,
            best_name = best.name if best else None,
            best_sharpe = best.live_sharpe if best else None,
        )

    def report(self) -> str:
        lines = [
            self.registry.report(),
            "",
            self.monitor.summary_report(),
        ]
        best = self.registry.recommend()
        if best:
            lines.append(f"\n▶ 推荐策略: [{best.strategy_id}] {best.name}")
        rotate = self.rotate()
        if rotate:
            lines.append("  策略排名:")
            for i, (sid, score) in enumerate(rotate[:5], 1):
                try:
                    r = self.registry.get(sid)
                    lines.append(f"    {i}. [{sid}] {r.name} 综合得分={score:.2f}")
                except KeyError:
                    pass
        return "\n".join(lines)
