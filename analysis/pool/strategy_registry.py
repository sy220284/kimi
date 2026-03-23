"""
analysis/pool/strategy_registry.py — 策略注册池

设计原则：
  - 每个策略实例有唯一 ID 和完整元数据
  - 生命周期状态机：CANDIDATE → SHADOW → ACTIVE → DEGRADED → RETIRED
  - 注册时自动生成策略 ID（基于参数哈希）
  - 支持参数变种策略（同一风格不同参数）
  - 持久化到 JSON（策略元数据不依赖数据库）

生命周期：
  CANDIDATE  刚注册，待验证
  SHADOW     影子运行（用验证集测试，不实际交易）
  ACTIVE     通过验证，正式启用
  DEGRADED   性能衰减预警，观察期
  RETIRED    淘汰，不再使用

状态转换规则：
  CANDIDATE  → SHADOW     : 通过初始参数检查
  SHADOW     → ACTIVE     : 通过滚动验证 + 统计显著性
  SHADOW     → RETIRED    : 验证失败
  ACTIVE     → DEGRADED   : 性能监控触发警告
  DEGRADED   → ACTIVE     : 性能恢复
  DEGRADED   → RETIRED    : 性能持续恶化
  ACTIVE     → RETIRED    : 主动淘汰 / 规则失效
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────
# 枚举：策略状态
# ─────────────────────────────────────────────────

class StrategyStatus(Enum):
    CANDIDATE = "candidate"   # 候选：刚注册，待验证
    SHADOW    = "shadow"      # 影子：验证集测试中
    ACTIVE    = "active"      # 激活：正式启用
    DEGRADED  = "degraded"    # 衰减：性能预警
    RETIRED   = "retired"     # 退休：永久淘汰

# 状态允许的迁移
_VALID_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    StrategyStatus.CANDIDATE: {StrategyStatus.SHADOW, StrategyStatus.RETIRED},
    StrategyStatus.SHADOW:    {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    StrategyStatus.ACTIVE:    {StrategyStatus.DEGRADED, StrategyStatus.RETIRED},
    StrategyStatus.DEGRADED:  {StrategyStatus.ACTIVE, StrategyStatus.RETIRED},
    StrategyStatus.RETIRED:   set(),
}


# ─────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────

@dataclass
class StrategyRecord:
    """单个策略的完整记录"""
    # 身份
    strategy_id:   str
    name:          str
    style:         str              # short_term / swing / medium_term / custom
    params:        dict[str, Any]   # 策略参数快照

    # 状态
    status:        str = StrategyStatus.CANDIDATE.value
    created_at:    str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at:    str = field(default_factory=lambda: datetime.now().isoformat())
    retired_at:    str | None = None
    retire_reason: str | None = None

    # 验证结果（WalkForward）
    validation_sharpe:   float | None = None
    validation_win_rate: float | None = None
    validation_ret_pct:  float | None = None
    validation_pvalue:   float | None = None   # 统计显著性 p 值
    validation_passed:   bool  = False

    # 线上性能快照（最近一次更新）
    live_sharpe:     float | None = None
    live_win_rate:   float | None = None
    live_ret_pct:    float | None = None
    live_max_dd:     float | None = None
    live_trade_count:int    = 0
    live_updated_at: str | None = None

    # 历史
    transition_log: list[dict] = field(default_factory=list)
    notes:          list[str]  = field(default_factory=list)

    @property
    def status_enum(self) -> StrategyStatus:
        return StrategyStatus(self.status)

    def transition_to(self, new_status: StrategyStatus, reason: str = "") -> None:
        """执行状态迁移（含合法性检查）"""
        current = self.status_enum
        if new_status not in _VALID_TRANSITIONS[current]:
            raise ValueError(
                f"非法状态迁移: {current.value} → {new_status.value}")

        self.transition_log.append({
            "from":   self.status,
            "to":     new_status.value,
            "reason": reason,
            "at":     datetime.now().isoformat(),
        })
        self.status     = new_status.value
        self.updated_at = datetime.now().isoformat()

        if new_status == StrategyStatus.RETIRED:
            self.retired_at    = self.updated_at
            self.retire_reason = reason

        logger.info(f"策略 [{self.strategy_id}] {self.name}: "
                    f"{current.value} → {new_status.value} | {reason}")

    def update_live_metrics(
        self,
        sharpe: float, win_rate: float,
        ret_pct: float, max_dd: float,
        trade_count: int,
    ) -> None:
        """更新线上性能快照"""
        self.live_sharpe      = round(sharpe, 4)
        self.live_win_rate    = round(win_rate, 4)
        self.live_ret_pct     = round(ret_pct, 4)
        self.live_max_dd      = round(max_dd, 4)
        self.live_trade_count = trade_count
        self.live_updated_at  = datetime.now().isoformat()
        self.updated_at       = self.live_updated_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        live = ""
        if self.live_sharpe is not None:
            live = (f"  线上: Sharpe={self.live_sharpe:.2f} "
                    f"胜率={self.live_win_rate:.1%} "
                    f"收益={self.live_ret_pct:+.2f}% "
                    f"交易={self.live_trade_count}笔")
        val = ""
        if self.validation_sharpe is not None:
            val = (f"  验证: Sharpe={self.validation_sharpe:.2f} "
                   f"p={self.validation_pvalue:.3f} "
                   f"通过={self.validation_passed}")
        return (f"[{self.status}] {self.name} ({self.strategy_id})\n"
                f"  风格={self.style}{live}{val}")


# ─────────────────────────────────────────────────
# 策略注册池
# ─────────────────────────────────────────────────

class StrategyRegistry:
    """
    策略注册池

    职责：
      - 注册新策略（自动生成 ID）
      - 管理策略生命周期状态
      - 查询：按状态/风格/性能筛选
      - 持久化：JSON 文件存储
      - 推荐：选出当前最优策略

    用法::
        registry = StrategyRegistry()
        sid = registry.register("短线动量", style="short_term",
                                 params={"min_factor_score": 50})
        registry.transition(sid, StrategyStatus.SHADOW, "参数检查通过")
        ...
        registry.transition(sid, StrategyStatus.ACTIVE, "验证通过")
        best = registry.recommend()
    """

    def __init__(self, storage_path: str = "results/strategy_pool.json"):
        self._path    = Path(storage_path)
        self._records: dict[str, StrategyRecord] = {}
        self._load()

    # ── 注册 ─────────────────────────────────────

    def register(
        self,
        name:   str,
        style:  str,
        params: dict[str, Any] | None = None,
        notes:  list[str] | None = None,
    ) -> str:
        """
        注册新策略，返回策略 ID。

        策略 ID = 名称 + 风格 + 参数哈希（前8位），保证相同参数不重复注册。
        """
        params = params or {}
        fingerprint = hashlib.md5(
            f"{name}:{style}:{json.dumps(params, sort_keys=True)}".encode()
        ).hexdigest()[:8]
        sid = f"{style[:3]}_{fingerprint}"

        if sid in self._records:
            logger.warning(f"策略 {sid} 已存在，跳过注册")
            return sid

        record = StrategyRecord(
            strategy_id = sid,
            name        = name,
            style       = style,
            params      = params,
            notes       = notes or [],
        )
        self._records[sid] = record
        self._save()
        logger.info(f"注册策略: [{sid}] {name} ({style})")
        return sid

    # ── 状态管理 ─────────────────────────────────

    def transition(
        self,
        strategy_id: str,
        new_status:  StrategyStatus,
        reason:      str = "",
    ) -> None:
        record = self._get(strategy_id)
        record.transition_to(new_status, reason)
        self._save()

    def update_validation(
        self,
        strategy_id:  str,
        sharpe:       float,
        win_rate:     float,
        ret_pct:      float,
        pvalue:       float,
        passed:       bool,
    ) -> None:
        record = self._get(strategy_id)
        record.validation_sharpe   = round(sharpe, 4)
        record.validation_win_rate = round(win_rate, 4)
        record.validation_ret_pct  = round(ret_pct, 4)
        record.validation_pvalue   = round(pvalue, 4)
        record.validation_passed   = passed
        record.updated_at = datetime.now().isoformat()
        self._save()

    def update_live(
        self,
        strategy_id: str,
        sharpe:      float,
        win_rate:    float,
        ret_pct:     float,
        max_dd:      float,
        trade_count: int,
    ) -> None:
        record = self._get(strategy_id)
        record.update_live_metrics(sharpe, win_rate, ret_pct, max_dd, trade_count)
        self._save()

    def add_note(self, strategy_id: str, note: str) -> None:
        record = self._get(strategy_id)
        record.notes.append(f"[{datetime.now().strftime('%Y-%m-%d')}] {note}")
        self._save()

    # ── 查询 ─────────────────────────────────────

    def get(self, strategy_id: str) -> StrategyRecord:
        return self._get(strategy_id)

    def list_by_status(self, status: StrategyStatus) -> list[StrategyRecord]:
        return [r for r in self._records.values()
                if r.status == status.value]

    def list_active(self) -> list[StrategyRecord]:
        return self.list_by_status(StrategyStatus.ACTIVE)

    def list_all(self) -> list[StrategyRecord]:
        return list(self._records.values())

    def recommend(self) -> StrategyRecord | None:
        """
        推荐当前最优策略（ACTIVE 中 Sharpe 最高）。
        若无 ACTIVE，从 DEGRADED 中选最好的降级推荐。
        """
        active = self.list_active()
        if active:
            # 优先线上 Sharpe，无则用验证 Sharpe
            def score(r: StrategyRecord) -> float:
                return r.live_sharpe if r.live_sharpe is not None \
                       else (r.validation_sharpe or -999)
            return max(active, key=score)

        degraded = self.list_by_status(StrategyStatus.DEGRADED)
        if degraded:
            logger.warning("无 ACTIVE 策略，从 DEGRADED 降级推荐")
            return max(degraded, key=lambda r: r.live_sharpe or -999)

        return None

    def count(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._records.values():
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    # ── 持久化 ───────────────────────────────────

    def _get(self, sid: str) -> StrategyRecord:
        if sid not in self._records:
            raise KeyError(f"策略 ID 不存在: {sid}")
        return self._records[sid]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {sid: record.to_dict() for sid, record in self._records.items()}
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for sid, d in data.items():
                # 移除不在 dataclass 中的字段（兼容旧格式）
                valid_fields = {f.name for f in StrategyRecord.__dataclass_fields__.values()}
                d = {k: v for k, v in d.items() if k in valid_fields}
                self._records[sid] = StrategyRecord(**d)
            logger.debug(f"加载策略池: {len(self._records)} 条记录")
        except Exception as e:
            logger.warning(f"策略池文件损坏，重置: {e}")
            self._records = {}

    def report(self) -> str:
        lines = ["", "=" * 60, "  策略池状态报告", "=" * 60]
        for status in StrategyStatus:
            recs = self.list_by_status(status)
            if not recs:
                continue
            lines.append(f"\n【{status.value.upper()}】({len(recs)} 个)")
            for r in recs:
                live_info = ""
                if r.live_sharpe is not None:
                    live_info = (f" Sharpe={r.live_sharpe:.2f}"
                                 f" 胜率={r.live_win_rate:.0%}"
                                 f" 收益={r.live_ret_pct:+.1f}%")
                lines.append(f"  {r.strategy_id:<20} {r.name:<20}{live_info}")
        lines.append("=" * 60)
        return "\n".join(lines)
