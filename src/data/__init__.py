"""
数据采集模块初始化文件

优化后的数据层 - 提供统一、稳定、高质量的数据获取接口
"""
from .data_collector import (
    DataCollector,
    DataSourceAdapter,
    DataSourceType,
    DataSourceError,
    DataFetchError
)
from .ths_adapter import ThsAdapter
from .ths_history_fetcher import ThsHistoryFetcher

# 新增优化模块
from .cache import DataCache, get_cache
from .multi_source import MultiSourceDataManager, get_data_manager
from .quality_monitor import DataQualityMonitor, DataQualityReport
from .data_api import DataAPI, get_stock_data
from .db_manager import DatabaseDataManager, get_db_manager

__all__ = [
    # 基础模块
    'DataCollector',
    'DataSourceAdapter',
    'DataSourceType',
    'DataSourceError',
    'DataFetchError',
    'ThsAdapter',
    'ThsHistoryFetcher',
    # 优化模块 - Phase 1
    'DataCache',
    'get_cache',
    'MultiSourceDataManager',
    'get_data_manager',
    'DataQualityMonitor',
    'DataQualityReport',
    'DataAPI',
    'get_stock_data',
    # 数据库优先模块
    'DatabaseDataManager',
    'get_db_manager',
]
