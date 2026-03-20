"""
增量技术指标缓存 (OPT-7)

问题：每次 detect() 都对全量历史重算 MACD/RSI/KDJ 等 20+ 指标。
      每日增量更新只新增 1 条 K 线，完全没必要重算全部历史。

方案：
  - 缓存 {symbol: (last_date, df_with_indicators)}
  - 若当日最新 date 未变，直接返回缓存的指标 df
  - 若有新 K 线，仅重算（仍全量，但下次复用）
  - 内存限制：LRU，最多缓存 max_symbols 只股票
  - 线程安全：使用 threading.Lock

使用方式：
    from data.incremental_indicator_cache import get_indicator_cache
    cache = get_indicator_cache()
    df_ind = cache.get(symbol, df_raw)   # 有缓存则返回缓存，否则计算+缓存
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass


class IncrementalIndicatorCache:
    """
    按股票代码缓存预计算指标，每日只算一次。

    缓存 key  : symbol
    缓存 value: (last_date: str, df_with_indicators: pd.DataFrame)
    淘汰策略  : LRU（OrderedDict），超出 max_symbols 时淘汰最久未访问
    线程安全  : threading.Lock（并发扫描场景）
    """

    _instance: 'IncrementalIndicatorCache | None' = None
    _lock_singleton = threading.Lock()

    def __new__(cls, max_symbols: int = 1000):
        with cls._lock_singleton:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._cache: OrderedDict[str, tuple[str, pd.DataFrame]] = OrderedDict()
                inst._lock  = threading.Lock()
                inst._max   = max_symbols
                inst._hits  = 0
                inst._misses = 0
                cls._instance = inst
            return cls._instance

    def get(self, symbol: str, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        获取带指标的 DataFrame。

        - 若 symbol 在缓存且最新 date 一致，直接返回缓存（O(1)）
        - 否则调用 TechnicalIndicators.calculate_all()，写缓存后返回

        Args:
            symbol : 股票代码（作为缓存 key）
            df_raw : 原始 OHLCV DataFrame

        Returns:
            包含 MACD/RSI/KDJ 等列的 DataFrame
        """
        if df_raw.empty or len(df_raw) < 30:
            return df_raw

        # 获取最新 K 线日期
        try:
            last_date = str(df_raw['date'].iloc[-1])
        except Exception:
            return self._compute_and_cache(symbol, df_raw)

        with self._lock:
            if symbol in self._cache:
                cached_date, cached_df = self._cache[symbol]
                if cached_date == last_date and len(cached_df) == len(df_raw):
                    # 命中：移到末尾（LRU）
                    self._cache.move_to_end(symbol)
                    self._hits += 1
                    return cached_df

        # 未命中：重算
        self._misses += 1
        return self._compute_and_cache(symbol, df_raw)

    def _compute_and_cache(self, symbol: str, df_raw: pd.DataFrame) -> pd.DataFrame:
        """计算指标并写入缓存"""
        try:
            from analysis.technical.indicators import TechnicalIndicators
            df_ind = TechnicalIndicators().calculate_all(df_raw)
        except Exception:
            return df_raw

        last_date = str(df_raw['date'].iloc[-1])
        with self._lock:
            self._cache[symbol] = (last_date, df_ind)
            self._cache.move_to_end(symbol)
            # LRU 淘汰
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

        return df_ind

    def invalidate(self, symbol: str) -> None:
        """手动失效某只股票的缓存（数据更新后调用）"""
        with self._lock:
            self._cache.pop(symbol, None)

    def clear(self) -> None:
        """清空全部缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = self._misses = 0

    @property
    def stats(self) -> dict:
        """返回命中率统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            'size':     len(self._cache),
            'max':      self._max,
            'hits':     self._hits,
            'misses':   self._misses,
            'hit_rate': round(hit_rate, 3),
        }


# 模块级单例
_cache_instance: IncrementalIndicatorCache | None = None

def get_indicator_cache(max_symbols: int = 1000) -> IncrementalIndicatorCache:
    """获取全局 IncrementalIndicatorCache 单例"""
    return IncrementalIndicatorCache(max_symbols)
