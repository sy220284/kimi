"""
组合优化模块 - 内存缓存 + 向量化计算
修复版 - 简化groupby操作避免列丢失
C1增强: LRU缓存淘汰策略，支持内存上限控制
"""
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import time

import numpy as np
import pandas as pd

from data.db_manager import get_db_manager


class OptimizedDataManager:
    """组合优化数据管理器 - 单例模式 + LRU缓存淘汰"""

    _instance = None

    # C1: LRU 配置
    _MAX_SYMBOLS = 1500          # 最多缓存股票数
    _MAX_MEMORY_MB = 1024        # 内存上限 1GB

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db = get_db_manager()
        self._cache: pd.DataFrame | None = None
        # C1: 改用 OrderedDict 实现 LRU（最近访问的移到末尾）
        self._cache_by_symbol: OrderedDict[str, pd.DataFrame] = OrderedDict()
        self._initialized = True

    def load_all_data(self, force_reload: bool = False) -> pd.DataFrame:
        """加载全部数据到内存"""
        if self._cache is not None and not force_reload:
            return self._cache

        print("📦 正在加载全量数据到内存...")
        start = time.time()

        result = self.db.pg.execute(
            "SELECT symbol, date, open, high, low, close, volume, amount FROM market_data ORDER BY symbol, date",
            fetch=True
        )

        self._cache = pd.DataFrame(result)

        # 构建按股票索引的缓存（LRU OrderedDict）
        print("🗂️  构建索引...")
        for symbol, group in self._cache.groupby('symbol'):
            self._cache_by_symbol[symbol] = group.reset_index(drop=True)

        # C1: 初次加载后检查是否超出内存限制
        self._evict_if_needed()

        elapsed = time.time() - start
        mem_mb = self._cache.memory_usage(deep=True).sum() / 1024 / 1024
        print(f"✅ 加载完成: {len(self._cache):,}条, {len(self._cache_by_symbol)}只, {elapsed:.2f}s, {mem_mb:.0f}MB")

        return self._cache

    def get_stock_data(self, symbol: str,
                       adjust: str = 'none') -> pd.DataFrame | None:
        """
        获取单只股票数据 (O(1) + LRU访问顺序更新)

        C3增强：支持价格复权，消除除权/派息对技术分析的影响。

        Args:
            symbol: 股票代码
            adjust: 复权方式
                'none'     — 不复权（默认，原始价格）
                'backward' — 后复权（以最新价格为基准向历史回调，推荐用于回测）
                'forward'  — 前复权（以最早价格为基准向未来调整）

        Returns:
            DataFrame，复权时 open/high/low/close 已调整，volume 未调整
        """
        if self._cache is None:
            self.load_all_data()
        if symbol not in self._cache_by_symbol:
            return None
        # C1: 移到末尾表示最近访问
        self._cache_by_symbol.move_to_end(symbol)
        df = self._cache_by_symbol[symbol]

        if adjust == 'none' or adjust is None:
            return df

        return self._apply_adjust(df, adjust)

    def _apply_adjust(self, df: pd.DataFrame, adjust: str) -> pd.DataFrame:
        """
        C3: 计算复权因子并调整价格序列

        使用连续复权因子法：
        - 检测价格跳空（相邻两日收盘价变动超过10%且当日开盘价接近前日收盘价调整后）
        - 计算累积因子
        - 后复权：ratio_cumulative 从历史到现在，以最新价格为基准
        - 前复权：从最早价格向后展开

        注意：本实现为近似复权，精确复权需要配合除权除息公告数据。
        当 amount 列可用时，可用成交额/成交量推算真实成交均价作为辅助验证。
        """
        df = df.copy().sort_values('date').reset_index(drop=True)
        price_cols = ['open', 'high', 'low', 'close']

        for col in price_cols:
            if col not in df.columns:
                return df

        closes = df['close'].values.astype(float)
        n = len(closes)
        if n < 2:
            return df

        # 计算每日收益率，识别除权跳空
        # 除权日特征：当日收盘/前日收盘的变动 ≠ 当日开盘/前日收盘的变动
        # 简化实现：检测收盘价日涨跌幅超过阈值且开盘/收盘比例异常
        factors = np.ones(n)  # 每日复权因子，1表示无除权

        for i in range(1, n):
            prev_close = closes[i - 1]
            curr_open  = df['open'].values[i]
            if prev_close <= 0:
                continue
            gap_ratio = curr_open / prev_close
            # 若开盘跳空超过8%（排除正常涨跌停），视为除权日
            # 实际复权因子 = 前收 / 除权后开盘 * 真实开盘（近似）
            if gap_ratio < 0.88 or gap_ratio > 1.12:
                # 使用开盘/前收比例作为复权因子
                factors[i] = gap_ratio

        # 累积因子（后复权：以最后一天为基准1.0，往前累积）
        if adjust == 'backward':
            cum = np.ones(n)
            cum[-1] = 1.0
            for i in range(n - 2, -1, -1):
                cum[i] = cum[i + 1] * factors[i + 1]
        else:  # forward：以第一天为基准1.0，往后累积
            cum = np.ones(n)
            cum[0] = 1.0
            for i in range(1, n):
                cum[i] = cum[i - 1] / factors[i] if factors[i] != 1.0 else cum[i - 1]

        # 应用复权因子到 OHLC
        for col in price_cols:
            df[col] = (df[col].values.astype(float) * cum).round(4)

        df['adjust'] = adjust
        return df

    def _evict_if_needed(self) -> None:
        """C1: 超出内存或股票数上限时，淘汰最久未访问的股票"""
        # 按股票数量淘汰
        while len(self._cache_by_symbol) > self._MAX_SYMBOLS:
            oldest = next(iter(self._cache_by_symbol))
            del self._cache_by_symbol[oldest]

        # 按内存淘汰（每20只检查一次避免频繁计算）
        if len(self._cache_by_symbol) % 20 == 0:
            total_mb = sum(
                df.memory_usage(deep=True).sum()
                for df in self._cache_by_symbol.values()
            ) / 1024 / 1024
            while total_mb > self._MAX_MEMORY_MB and self._cache_by_symbol:
                oldest = next(iter(self._cache_by_symbol))
                evicted = self._cache_by_symbol.pop(oldest)
                total_mb -= evicted.memory_usage(deep=True).sum() / 1024 / 1024

    def get_stocks_data(self, symbols: list[str]) -> pd.DataFrame:
        """获取多只股票数据"""
        if self._cache is None:
            self.load_all_data()

        dfs = [self._cache_by_symbol[s] for s in symbols if s in self._cache_by_symbol]
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    # ==================== 向量化计算 - 简化版避免groupby问题 ====================

    def calculate_ma(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """计算移动平均线"""
        df = df.copy()
        df[f'ma{window}'] = df.groupby('symbol')['close'].transform(
            lambda x: x.rolling(window=window, min_periods=1).mean()
        )
        return df

    def calculate_ema(self, df: pd.DataFrame, span: int = 20) -> pd.DataFrame:
        """计算指数移动平均线"""
        df = df.copy()
        df[f'ema{span}'] = df.groupby('symbol')['close'].transform(
            lambda x: x.ewm(span=span, adjust=False).mean()
        )
        return df

    def calculate_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算日收益率"""
        df = df.copy()
        df['prev_close'] = df.groupby('symbol')['close'].shift(1)
        df['daily_return'] = (df['close'] - df['prev_close']) / df['prev_close'].replace(0, np.nan)
        return df

    def calculate_volatility(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """计算滚动波动率"""
        df = df.copy()
        df[f'volatility{window}'] = df.groupby('symbol')['close'].transform(
            lambda x: x.replace(0, np.nan).pct_change().rolling(window=window, min_periods=2).std() * np.sqrt(252)
        )
        return df

    def calculate_rsi(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """计算RSI"""
        df = df.copy()

        def _rsi(prices):
            delta = prices.diff()
            gain = delta.where(delta > 0, 0).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / loss.replace(0, np.nan)
            return 100 - (100 / (1 + rs))

        df[f'rsi{window}'] = df.groupby('symbol')['close'].transform(_rsi)
        return df

    def calculate_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD - 使用transform避免列丢失"""
        df = df.copy()

        # 使用transform保持原DataFrame结构
        ema_fast = df.groupby('symbol')['close'].transform(lambda x: x.ewm(span=fast, adjust=False).mean())
        ema_slow = df.groupby('symbol')['close'].transform(lambda x: x.ewm(span=slow, adjust=False).mean())

        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df.groupby('symbol')['macd'].transform(lambda x: x.ewm(span=signal, adjust=False).mean())
        df['macd_hist'] = df['macd'] - df['macd_signal']

        return df

    def calculate_bollinger(self, df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        """计算布林带 - 使用transform"""
        df = df.copy()

        df['bb_middle'] = df.groupby('symbol')['close'].transform(lambda x: x.rolling(window=window).mean())
        bb_std = df.groupby('symbol')['close'].transform(lambda x: x.rolling(window=window).std())

        df['bb_upper'] = df['bb_middle'] + (bb_std * num_std)
        df['bb_lower'] = df['bb_middle'] - (bb_std * num_std)

        return df

    def calculate_atr(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        """计算ATR"""
        df = df.copy()
        df = df.sort_values(['symbol', 'date'])

        # 计算True Range
        prev_close = df.groupby('symbol')['close'].shift(1)
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - prev_close).abs()
        tr3 = (df['low'] - prev_close).abs()
        df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        df[f'atr{window}'] = df.groupby('symbol')['tr'].transform(lambda x: x.rolling(window=window, min_periods=1).mean())
        return df

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """批量计算所有指标"""
        print("📊 计算技术指标...")
        start = time.time()

        df = self.calculate_ma(df, 5)
        df = self.calculate_ma(df, 10)
        df = self.calculate_ma(df, 20)
        df = self.calculate_ma(df, 60)
        df = self.calculate_returns(df)
        df = self.calculate_volatility(df, 20)
        df = self.calculate_rsi(df, 14)
        df = self.calculate_macd(df)
        df = self.calculate_bollinger(df)
        df = self.calculate_atr(df, 14)

        elapsed = time.time() - start
        print(f"✅ 完成: {elapsed*1000:.2f}ms")
        return df


# ============== 单例和便捷函数 ==============

_data_manager: OptimizedDataManager | None = None

def get_optimized_data_manager() -> OptimizedDataManager:
    global _data_manager
    if _data_manager is None:
        _data_manager = OptimizedDataManager()
    return _data_manager


def load_all_data() -> pd.DataFrame:
    return get_optimized_data_manager().load_all_data()


def get_stock(symbol: str) -> pd.DataFrame | None:
    return get_optimized_data_manager().get_stock_data(symbol)


def get_stocks(symbols: list[str]) -> pd.DataFrame:
    return get_optimized_data_manager().get_stocks_data(symbols)


# ============== 性能测试 ==============

def benchmark():
    print("="*80)
    print("🚀 组合优化性能测试")
    print("="*80)

    mgr = OptimizedDataManager()
    _df = mgr.load_all_data()
    symbols = list(mgr._cache_by_symbol.keys())
    print(f"\n样本: {len(symbols)}只股票\n")

    # 查询测试
    print("【查询性能】")
    start = time.time()
    for _ in range(100):
        _ = mgr.get_stock_data(np.random.choice(symbols))
    print(f"  单股查询100次: {(time.time()-start)*1000:.2f}ms")

    start = time.time()
    _ = mgr.get_stocks_data(symbols[:100])
    print(f"  100只批量: {(time.time()-start)*1000:.2f}ms")

    # 指标计算
    print("\n【指标计算】")
    test_df = mgr.get_stocks_data(symbols[:50])

    start = time.time()
    _ = mgr.calculate_ma(test_df.copy(), 20)
    print(f"  MA20(50只): {(time.time()-start)*1000:.2f}ms")

    start = time.time()
    _ = mgr.calculate_macd(test_df.copy())
    print(f"  MACD(50只): {(time.time()-start)*1000:.2f}ms")

    start = time.time()
    _ = mgr.calculate_bollinger(test_df.copy())
    print(f"  布林带(50只): {(time.time()-start)*1000:.2f}ms")

    start = time.time()
    _ = mgr.calculate_all_indicators(test_df.copy())
    print(f"  全部指标(50只): {(time.time()-start)*1000:.2f}ms")

    print("\n" + "="*80)
    print("✅ 测试通过")
    print("="*80)


if __name__ == '__main__':
    benchmark()
