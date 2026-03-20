"""
性能动态适配器 (utils/performance_adaptor.py)

根据当前设备硬件自动选择最优运行参数，支持低配到高配全范围设备：

  设备档位（自动检测）：
    LOW    : CPU ≤2核 或 可用内存 ≤2GB  （树莓派、入门云主机）
    MEDIUM : CPU 4核，可用内存 4-8GB     （普通开发机）
    HIGH   : CPU 8核，可用内存 8-16GB   （量化工作站）
    EXTREME: CPU ≥16核 或 可用内存 ≥32GB（生产服务器）

使用方式：
    from utils.performance_adaptor import get_adaptor
    cfg = get_adaptor()

    # 获取参数
    workers  = cfg.scan_workers          # 批量扫描并发数
    max_sym  = cfg.lru_max_symbols       # LRU 缓存只数
    max_mem  = cfg.lru_max_memory_mb     # LRU 内存上限
    ic_size  = cfg.indicator_cache_size  # 指标缓存只数

    # 环境变量覆盖（优先级最高）
    KIMI_SCAN_WORKERS=4 python batch_scanner.py

    # 打印当前配置
    cfg.print_profile()
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from enum import Enum


class DeviceTier(Enum):
    LOW     = "low"      # ≤2核 / ≤2GB 可用内存
    MEDIUM  = "medium"   # 4核  / 4-8GB
    HIGH    = "high"     # 8核  / 8-16GB
    EXTREME = "extreme"  # ≥16核 / ≥32GB


@dataclass
class PerfProfile:
    """一套完整的运行时性能参数"""

    tier: DeviceTier

    # ── 并发 ──────────────────────────────────────────────────────────────
    scan_workers: int           # batch_scanner 并发线程数
    data_fetch_workers: int     # 数据拉取并发（ConcurrentDataManager）
    walk_forward_workers: int   # Walk-Forward 窗口并行数

    # ── 内存 / 缓存 ────────────────────────────────────────────────────────
    lru_max_symbols: int        # OptimizedDataManager LRU 上限（只数）
    lru_max_memory_mb: int      # OptimizedDataManager 内存上限（MB）
    indicator_cache_size: int   # IncrementalIndicatorCache 缓存只数

    # ── 批量大小 ──────────────────────────────────────────────────────────
    batch_chunk_size: int       # 单次处理股票数（分批避免 OOM）
    backtest_max_stocks: int    # 单次回测最多股票数

    # ── 分析参数 ───────────────────────────────────────────────────────────
    scan_days: int              # 默认历史天数
    quick_filter_min_pivots: int # OPT-5 快筛最小极值点数

    # ── 硬件信息（仅供展示）──────────────────────────────────────────────
    cpu_count: int = 0
    memory_total_gb: float = 0.0
    memory_avail_gb: float = 0.0

    def print_profile(self) -> None:
        """打印当前性能配置"""
        print(f"\n{'='*55}")
        print(f"  kimi 性能配置  [{self.tier.value.upper()}]")
        print(f"{'='*55}")
        print(f"  硬件: {self.cpu_count} 核 CPU  "
              f"{self.memory_total_gb:.1f}GB 总内存  "
              f"{self.memory_avail_gb:.1f}GB 可用")
        print(f"  并发配置:")
        print(f"    scan_workers:           {self.scan_workers}")
        print(f"    data_fetch_workers:     {self.data_fetch_workers}")
        print(f"    walk_forward_workers:   {self.walk_forward_workers}")
        print(f"  内存配置:")
        print(f"    lru_max_symbols:        {self.lru_max_symbols}")
        print(f"    lru_max_memory_mb:      {self.lru_max_memory_mb} MB")
        print(f"    indicator_cache_size:   {self.indicator_cache_size}")
        print(f"  批量配置:")
        print(f"    batch_chunk_size:       {self.batch_chunk_size}")
        print(f"    backtest_max_stocks:    {self.backtest_max_stocks}")
        print(f"    scan_days:              {self.scan_days}")
        print(f"{'='*55}\n")


# ── 各档位默认配置 ─────────────────────────────────────────────────────────

_PROFILES: dict[DeviceTier, dict] = {
    DeviceTier.LOW: dict(
        scan_workers          = 2,
        data_fetch_workers    = 2,
        walk_forward_workers  = 2,
        lru_max_symbols       = 200,
        lru_max_memory_mb     = 256,
        indicator_cache_size  = 200,
        batch_chunk_size      = 50,
        backtest_max_stocks   = 100,
        scan_days             = 120,
        quick_filter_min_pivots = 5,
    ),
    DeviceTier.MEDIUM: dict(
        scan_workers          = 4,
        data_fetch_workers    = 3,
        walk_forward_workers  = 4,
        lru_max_symbols       = 800,
        lru_max_memory_mb     = 512,
        indicator_cache_size  = 600,
        batch_chunk_size      = 200,
        backtest_max_stocks   = 500,
        scan_days             = 200,
        quick_filter_min_pivots = 5,
    ),
    DeviceTier.HIGH: dict(
        scan_workers          = 8,
        data_fetch_workers    = 6,
        walk_forward_workers  = 5,
        lru_max_symbols       = 1500,
        lru_max_memory_mb     = 1024,
        indicator_cache_size  = 1200,
        batch_chunk_size      = 500,
        backtest_max_stocks   = 2000,
        scan_days             = 250,
        quick_filter_min_pivots = 4,
    ),
    DeviceTier.EXTREME: dict(
        scan_workers          = 16,
        data_fetch_workers    = 10,
        walk_forward_workers  = 8,
        lru_max_symbols       = 5500,
        lru_max_memory_mb     = 4096,
        indicator_cache_size  = 4000,
        batch_chunk_size      = 1000,
        backtest_max_stocks   = 5500,
        scan_days             = 250,
        quick_filter_min_pivots = 3,
    ),
}


# ── 硬件探测 ────────────────────────────────────────────────────────────────

def _detect_hardware() -> tuple[int, float, float]:
    """
    探测 CPU 核心数和可用内存。

    Returns:
        (cpu_count, total_gb, avail_gb)
    """
    import os
    cpu = os.cpu_count() or 1

    total_gb = avail_gb = 0.0
    try:
        import psutil
        m = psutil.virtual_memory()
        total_gb = m.total  / 1024**3
        avail_gb = m.available / 1024**3
    except ImportError:
        try:
            with open('/proc/meminfo') as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(':')] = int(parts[1])
            total_gb = info.get('MemTotal', 0) / 1024**2
            avail_gb = info.get('MemAvailable', info.get('MemFree', 0)) / 1024**2
        except Exception:
            total_gb = avail_gb = 4.0  # 保守默认值

    return cpu, total_gb, avail_gb


def _classify_tier(cpu: int, avail_gb: float) -> DeviceTier:
    """根据 CPU 和可用内存判断档位"""
    if cpu >= 16 or avail_gb >= 32:
        return DeviceTier.EXTREME
    if cpu >= 8 or avail_gb >= 8:
        return DeviceTier.HIGH
    if cpu >= 4 or avail_gb >= 4:
        return DeviceTier.MEDIUM
    return DeviceTier.LOW


def _apply_env_overrides(profile_kwargs: dict) -> dict:
    """
    读取环境变量覆盖（优先级高于自动检测）。

    支持的变量（均可选）：
        KIMI_SCAN_WORKERS        int  批量扫描并发数
        KIMI_DATA_WORKERS        int  数据拉取并发数
        KIMI_WF_WORKERS          int  Walk-Forward 并行窗口数
        KIMI_LRU_SYMBOLS         int  LRU 缓存股票数
        KIMI_LRU_MEMORY_MB       int  LRU 内存上限 MB
        KIMI_INDICATOR_CACHE     int  指标缓存股票数
        KIMI_BATCH_CHUNK         int  分批大小
        KIMI_SCAN_DAYS           int  历史天数
        KIMI_TIER                str  强制档位 low/medium/high/extreme
    """
    env_map = {
        'KIMI_SCAN_WORKERS':    ('scan_workers',            int),
        'KIMI_DATA_WORKERS':    ('data_fetch_workers',      int),
        'KIMI_WF_WORKERS':      ('walk_forward_workers',    int),
        'KIMI_LRU_SYMBOLS':     ('lru_max_symbols',         int),
        'KIMI_LRU_MEMORY_MB':   ('lru_max_memory_mb',       int),
        'KIMI_INDICATOR_CACHE': ('indicator_cache_size',    int),
        'KIMI_BATCH_CHUNK':     ('batch_chunk_size',        int),
        'KIMI_SCAN_DAYS':       ('scan_days',               int),
    }
    overridden = dict(profile_kwargs)
    for env_var, (param, cast) in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            try:
                overridden[param] = cast(val)
            except ValueError:
                warnings.warn(f"KIMI: 无效环境变量 {env_var}={val!r}，忽略")
    return overridden


# ── 单例 ────────────────────────────────────────────────────────────────────

_adaptor: PerfProfile | None = None


def get_adaptor(force_tier: DeviceTier | None = None) -> PerfProfile:
    """
    获取全局性能适配器单例（惰性初始化）。

    Args:
        force_tier: 强制指定档位（用于测试）；
                    也可通过 KIMI_TIER=low|medium|high|extreme 环境变量覆盖

    Returns:
        PerfProfile 实例
    """
    global _adaptor
    if _adaptor is not None:
        return _adaptor

    cpu, total_gb, avail_gb = _detect_hardware()

    # 档位判断（env > force_tier > 自动）
    env_tier = os.environ.get('KIMI_TIER', '').lower()
    tier_map = {'low': DeviceTier.LOW, 'medium': DeviceTier.MEDIUM,
                'high': DeviceTier.HIGH, 'extreme': DeviceTier.EXTREME}
    if env_tier in tier_map:
        tier = tier_map[env_tier]
    elif force_tier is not None:
        tier = force_tier
    else:
        tier = _classify_tier(cpu, avail_gb)

    kwargs = dict(_PROFILES[tier])
    kwargs = _apply_env_overrides(kwargs)

    _adaptor = PerfProfile(
        tier              = tier,
        cpu_count         = cpu,
        memory_total_gb   = round(total_gb, 1),
        memory_avail_gb   = round(avail_gb, 1),
        **kwargs
    )
    return _adaptor


def reset_adaptor() -> None:
    """重置单例（用于测试或参数变更后重新检测）"""
    global _adaptor
    _adaptor = None


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='打印当前设备性能配置')
    ap.add_argument('--tier', choices=['low','medium','high','extreme'],
                    help='强制指定档位')
    args = ap.parse_args()
    if args.tier:
        os.environ['KIMI_TIER'] = args.tier
    get_adaptor().print_profile()
