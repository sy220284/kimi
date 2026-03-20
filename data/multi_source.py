"""
多源数据管理器 - 主备切换 + 数据聚合
主源: THS (同花顺)
备源: AKShare / Tushare / 本地缓存
"""
import sys
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


class DataSourcePriority(Enum):
    """数据源优先级"""
    PRIMARY = 1    # 主源
    SECONDARY = 2  # 备源
    FALLBACK = 3   # 最后备选


class DataSourceStatus:
    """数据源状态"""
    def __init__(self, name: str):
        self.name = name
        self.available = True
        self.last_error = None
        self.last_used = None
        self.success_count = 0
        self.fail_count = 0
        self.avg_response_time = 0.0

    def record_success(self, response_time: float):
        """记录成功"""
        self.available = True
        self.last_used = datetime.now()
        self.success_count += 1
        # 移动平均
        self.avg_response_time = 0.7 * self.avg_response_time + 0.3 * response_time

    def record_fail(self, error: str):
        """记录失败"""
        self.available = False
        self.last_error = error
        self.last_used = datetime.now()
        self.fail_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'available': self.available,
            'last_error': self.last_error,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'avg_response_time_ms': round(self.avg_response_time * 1000, 2)
        }


class MultiSourceDataManager:
    """多源数据管理器"""

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}
        self.sources: dict[str, Any] = {}
        self.source_status: dict[str, DataSourceStatus] = {}

        # 初始化数据源
        self._init_sources()

    def _init_sources(self):
        """初始化所有数据源"""
        # THS (主源)
        try:
            from data.ths_adapter import ThsAdapter
            ths_config = self.config.get('ths', {'enabled': True})
            if ths_config.get('enabled', True):
                self.sources['ths'] = ThsAdapter(ths_config)
                self.source_status['ths'] = DataSourceStatus('ths')
        except Exception as e:
            print(f"THS初始化失败: {e}")

        # AKShare (备源) - 已弃用
        # try:
        #     from data.akshare_adapter import AkshareAdapter
        #     ak_config = self.config.get('akshare', {'enabled': False})
        #     if ak_config.get('enabled', False):
        #         self.sources['akshare'] = AkshareAdapter(ak_config)
        #         self.source_status['akshare'] = DataSourceStatus('akshare')
        # except Exception as e:
        #     print(f"AKShare初始化失败: {e}")

        # 东财直连 (AKShare的fallback)
        try:
            from data.eastmoney_direct import EastMoneyDirectAdapter
            em_config = self.config.get('eastmoney', {'enabled': True, 'delay': 0.1})
            if em_config.get('enabled', True):
                self.sources['eastmoney'] = EastMoneyDirectAdapter(em_config)
                self.source_status['eastmoney'] = DataSourceStatus('eastmoney')
                print("✅ 东财直连适配器已加载")
        except Exception as e:
            print(f"东财直连初始化失败: {e}")

        # 多平台财经 (腾讯/网易/新浪) 作为最终fallback
        try:
            from data.multi_platform_finance import MultiPlatformFinanceAdapter
            mp_config = self.config.get('multi_platform', {'enabled': True, 'delay': 0.1, 'prefer': 'tencent'})
            if mp_config.get('enabled', True):
                self.sources['multi_platform'] = MultiPlatformFinanceAdapter(mp_config)
                self.source_status['multi_platform'] = DataSourceStatus('multi_platform')
                print("✅ 多平台财经适配器已加载 (腾讯/网易/新浪)")
        except Exception as e:
            print(f"多平台财经初始化失败: {e}")

        # 本地缓存 (最后备选)
        try:
            from data.cache import get_cache
            self.sources['cache'] = get_cache()
            self.source_status['cache'] = DataSourceStatus('cache')
        except Exception as e:
            print(f"缓存初始化失败: {e}")

    def get_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        ktype: str = "day",
        prefer_source: str | None = None
    ) -> pd.DataFrame:
        """
        获取历史数据（自动 failover）

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            ktype: K线类型
            prefer_source: 优先使用指定源

        Returns:
            DataFrame
        """
        import time

        # 确定查询顺序: THS -> AKShare -> 东财直连 -> 多平台(腾讯/网易/新浪) -> 缓存
        source_order = ['ths', 'akshare', 'eastmoney', 'multi_platform', 'cache']
        if prefer_source and prefer_source in source_order:
            source_order.remove(prefer_source)
            source_order.insert(0, prefer_source)

        errors = []

        for source_name in source_order:
            if source_name not in self.sources:
                continue

            source = self.sources[source_name]
            status = self.source_status[source_name]

            try:
                start_time = time.time()

                # 调用数据源
                if source_name == 'ths':
                    df = self._fetch_from_ths(source, symbol, start_date, end_date, ktype)
                elif source_name == 'akshare':
                    df = self._fetch_from_akshare(source, symbol, start_date, end_date, ktype)
                elif source_name == 'eastmoney':
                    df = self._fetch_from_eastmoney(source, symbol, start_date, end_date, ktype)
                elif source_name == 'multi_platform':
                    df = self._fetch_from_multi_platform(source, symbol, start_date, end_date, ktype)
                elif source_name == 'cache':
                    df = self._fetch_from_cache(source, symbol, start_date, end_date, ktype)
                else:
                    continue

                elapsed = time.time() - start_time

                if df is not None and not df.empty:
                    status.record_success(elapsed)
                    print(f"✅ 从 [{source_name}] 获取 {symbol} 数据成功，共 {len(df)} 条")

                    # 如果是从主源或备源获取，保存到缓存
                    if source_name in ['ths', 'akshare', 'eastmoney', 'multi_platform'] and 'cache' in self.sources:
                        self.sources['cache'].set(
                            df, symbol,
                            start_date or df['date'].min().strftime('%Y-%m-%d'),
                            end_date or df['date'].max().strftime('%Y-%m-%d'),
                            ktype
                        )

                    return df
                else:
                    errors.append(f"{source_name}: 返回空数据")

            except Exception as e:
                error_msg = str(e)
                status.record_fail(error_msg)
                errors.append(f"{source_name}: {error_msg}")
                print(f"⚠️ [{source_name}] 获取失败: {error_msg}")

        # 所有源都失败
        raise DataFetchError(f"所有数据源获取失败: {'; '.join(errors)}")

    def _fetch_from_ths(
        self,
        adapter,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str
    ) -> pd.DataFrame:
        """从THS获取数据"""
        # 解析年份用于 get_full_history
        start_year = 2020
        end_year = datetime.now().year

        if start_date:
            start_year = int(start_date[:4])
        if end_date:
            end_year = int(end_date[:4])

        df = adapter.get_full_history(symbol, start_year=start_year, end_year=end_year)

        # 按日期过滤
        if start_date:
            df = df[df['date'] >= start_date]
        if end_date:
            df = df[df['date'] <= end_date]

        return df

    def _fetch_from_akshare(
        self,
        adapter,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str
    ) -> pd.DataFrame:
        """从AKShare获取数据"""
        return adapter.get_daily_kline(symbol, start_date, end_date, adjust='qfq')

    def _fetch_from_eastmoney(
        self,
        adapter,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str
    ) -> pd.DataFrame:
        """从东财直连获取数据"""
        return adapter.get_history(symbol, start_date, end_date, ktype)

    def _fetch_from_multi_platform(
        self,
        adapter,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str
    ) -> pd.DataFrame:
        """从多平台财经获取数据"""
        return adapter.get_history(symbol, start_date, end_date, ktype)

    def _fetch_from_cache(
        self,
        cache,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str
    ) -> pd.DataFrame:
        """从缓存获取数据"""
        return cache.get(symbol, start_date or "", end_date or "", ktype)

    def get_source_status(self) -> list[dict[str, Any]]:
        """获取所有数据源状态"""
        return [status.to_dict() for status in self.source_status.values()]

    def get_best_source(self) -> str:
        """获取当前最佳可用数据源"""
        available = [
            (name, status)
            for name, status in self.source_status.items()
            if status.available
        ]

        if not available:
            return 'cache'  # 默认返回缓存

        # 按成功率+响应时间排序
        def score(item):
            name, status = item
            total = status.success_count + status.fail_count
            if total == 0:
                return (1, 0)  # 新源优先
            success_rate = status.success_count / total
            return (success_rate, -status.avg_response_time)

        available.sort(key=score, reverse=True)
        return available[0][0]


class DataFetchError(Exception):
    """数据获取异常"""
    pass


# 全局实例
_global_manager = None

def get_data_manager(config: dict[str, Any] = None) -> MultiSourceDataManager:
    """获取全局数据管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = MultiSourceDataManager(config)
    return _global_manager
