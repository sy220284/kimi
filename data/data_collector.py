"""
数据采集模块 - 统一数据采集接口
"""
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.config_loader import load_config
from utils.logger import get_logger


class DataSourceError(Exception):
    """数据源错误"""
    pass


class DataFetchError(Exception):
    """数据获取错误"""
    pass


class DataSourceType(Enum):
    """数据源类型"""
    # 已弃用数据源 (保留枚举值供兼容性使用)
    TUSHARE = "tushare"  # 已弃用 - 数据不复权
    AKSHARE = "akshare"  # 已弃用 - 网络不稳定
    BAOSTOCK = "baostock"
    
    # 当前默认数据源
    THS = "ths"  # 同花顺 - 前复权数据 (默认)


class DataSourceAdapter(ABC):
    """数据源适配器抽象基类"""

    def __init__(self, config: dict[str, Any]):
        """
        初始化适配器

        Args:
            config: 数据源配置
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.logger = get_logger(f'data.{self.source_type.value}')

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """返回数据源类型"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        连接数据源

        Returns:
            是否连接成功
        """
        pass

    @abstractmethod
    def get_daily_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取日K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            **kwargs: 额外参数

        Returns:
            DataFrame包含日K线数据
        """
        pass

    @abstractmethod
    def get_industry_index(
        self,
        industry_code: str | None = None,
        start_date: str = '',
        end_date: str = '',
        **kwargs
    ) -> pd.DataFrame:
        """
        获取行业指数数据

        Args:
            industry_code: 行业代码
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 额外参数

        Returns:
            DataFrame包含行业指数数据
        """
        pass

    @abstractmethod
    def get_stock_list(self, **kwargs) -> pd.DataFrame:
        """
        获取股票列表

        Args:
            **kwargs: 额外参数

        Returns:
            DataFrame包含股票列表
        """
        pass

    def normalize_kline_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化K线数据格式

        Args:
            df: 原始K线数据

        Returns:
            标准化的DataFrame
        """
        # 确保必要的列存在
        _required_cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']

        # 列名映射（不同数据源可能有不同的列名）
        column_mapping = {
            'ts_code': 'symbol',
            'trade_date': 'date',
            'stk_code': 'symbol',
        }

        df = df.rename(columns=column_mapping)

        # 统一日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        # 确保数值列为float类型
        numeric_cols = ['open', 'high', 'low', 'close', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 确保volume为整数
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').astype('int64')

        return df


class DataCollector:
    """统一数据采集器"""

    def __init__(self, config_path: Path | None = None):
        """
        初始化数据采集器

        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(config_path)
        self.logger = get_logger('data.collector')
        self._adapters: dict[DataSourceType, DataSourceAdapter] = {}
        self._load_adapters()

    def _load_adapters(self) -> None:
        """加载所有启用的数据源适配器
        
        注意: 已统一使用同花顺(THS)作为默认数据源
        Tushare和AKShare已弃用
        """
        from .ths_adapter import ThsAdapter

        # 加载同花顺(THS) - 默认数据源
        ths_config = self.config.get('data_sources', {}).get('ths', {})
        # 如果配置中没有明确禁用，则默认启用
        if ths_config.get('enabled', True):
            try:
                adapter = ThsAdapter(ths_config)
                self._adapters[DataSourceType.THS] = adapter
                self.logger.info("同花顺(THS)适配器已加载 (默认数据源)")
            except Exception as e:
                self.logger.error(f"同花顺(THS)适配器加载失败: {e}")

    def register_adapter(
        self,
        source_type: DataSourceType,
        adapter: DataSourceAdapter
    ) -> None:
        """
        注册数据源适配器

        Args:
            source_type: 数据源类型
            adapter: 适配器实例
        """
        self._adapters[source_type] = adapter
        self.logger.info(f"{source_type.value}适配器已注册")

    def get_adapter(
        self,
        source_type: DataSourceType
    ) -> DataSourceAdapter | None:
        """
        获取数据源适配器

        Args:
            source_type: 数据源类型

        Returns:
            适配器实例或None
        """
        return self._adapters.get(source_type)

    def get_daily_kline(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        source: DataSourceType = DataSourceType.THS,  # 默认改为THS
        **kwargs
    ) -> pd.DataFrame:
        """
        获取日K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期，默认为一年前
            end_date: 结束日期，默认为今天
            source: 数据源类型
            **kwargs: 额外参数

        Returns:
            DataFrame包含日K线数据

        Raises:
            DataFetchError: 获取数据失败
        """
        # 设置默认日期
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        adapter = self.get_adapter(source)
        if not adapter:
            raise DataSourceError(f"数据源 {source.value} 未启用或未加载")

        try:
            df = adapter.get_daily_kline(symbol, start_date, end_date, **kwargs)
            self.logger.info(f"获取 {symbol} 日K线数据成功: {len(df)}条记录")
            return df
        except Exception as e:
            self.logger.error(f"获取 {symbol} 日K线数据失败: {e}")
            raise DataFetchError(f"获取日K线数据失败: {e}")

    def get_industry_index(
        self,
        industry_code: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        source: DataSourceType = DataSourceType.THS,  # 默认改为THS
        **kwargs
    ) -> pd.DataFrame:
        """
        获取行业指数数据

        Args:
            industry_code: 行业代码
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源类型
            **kwargs: 额外参数

        Returns:
            DataFrame包含行业指数数据

        Raises:
            DataFetchError: 获取数据失败
        """
        # 设置默认日期
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        adapter = self.get_adapter(source)
        if not adapter:
            raise DataSourceError(f"数据源 {source.value} 未启用或未加载")

        try:
            df = adapter.get_industry_index(industry_code, start_date, end_date, **kwargs)
            self.logger.info(f"获取行业指数数据成功: {len(df)}条记录")
            return df
        except Exception as e:
            self.logger.error(f"获取行业指数数据失败: {e}")
            raise DataFetchError(f"获取行业指数数据失败: {e}")

    def get_stock_list(
        self,
        source: DataSourceType = DataSourceType.AKSHARE,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取股票列表

        Args:
            source: 数据源类型
            **kwargs: 额外参数

        Returns:
            DataFrame包含股票列表
        """
        adapter = self.get_adapter(source)
        if not adapter:
            raise DataSourceError(f"数据源 {source.value} 未启用或未加载")

        try:
            df = adapter.get_stock_list(**kwargs)
            self.logger.info(f"获取股票列表成功: {len(df)}只股票")
            return df
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            raise DataFetchError(f"获取股票列表失败: {e}")

    def fetch_multi_symbols(
        self,
        symbols: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
        source: DataSourceType = DataSourceType.AKSHARE
    ) -> dict[str, pd.DataFrame]:
        """
        批量获取多只股票数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源类型

        Returns:
            股票代码到DataFrame的字典
        """
        results = {}
        for symbol in symbols:
            try:
                df = self.get_daily_kline(symbol, start_date, end_date, source)
                results[symbol] = df
            except Exception as e:
                self.logger.warning(f"获取 {symbol} 数据失败: {e}")
                results[symbol] = pd.DataFrame()

        return results
