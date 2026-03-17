"""
统一数据接口 - 整合缓存、多源、质量监控
简化调用，一行代码获取高质量数据
"""
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.multi_source import get_data_manager
from data.quality_monitor import DataQualityMonitor, DataQualityReport
from data.cache import get_cache
from data.db_manager import DatabaseDataManager, get_db_manager


class DataAPI:
    """
    统一数据API - 一站式数据获取
    
    功能:
    1. 数据库优先 (PostgreSQL)
    2. 自动多源failover (THS备用)
    3. 智能缓存 (Redis)
    4. 质量监控
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # 数据库优先管理器
        self.db_manager = get_db_manager()
        self.quality_monitor = DataQualityMonitor()
        self.cache = get_cache()
    
    def get_stock_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ktype: str = "day",
        check_quality: bool = True,
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """
        获取股票数据（数据库优先）
        """
        result = {
            'data': None,
            'quality_report': None,
            'source': None,
            'cached': False
        }
        
        # 1. 数据库优先获取
        try:
            df = self.db_manager.get_stock_data(symbol, start_date, end_date)
            if not df.empty:
                result['source'] = 'database'
            else:
                df = None
        except Exception as e:
            df = None
        
        if df is None or df.empty:
            result['error'] = "无数据"
            return result
        
        # 2. 数据质量检查
        if check_quality:
            quality_report = self.quality_monitor.check(df, symbol)
            result['quality_report'] = quality_report
            
            # 3. 自动修复
            if auto_fix and not quality_report.is_valid:
                df = self.quality_monitor.auto_fix(df)
                result['fixed'] = True
                result['quality_report'] = self.quality_monitor.check(df, symbol)
        
        result['data'] = df
        return result
    
    def get_batch_data(
        self,
        symbols: list,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ktype: str = "day"
    ) -> Dict[str, Dict[str, Any]]:
        """批量获取多只股票数据"""
        results = {}
        
        for symbol in symbols:
            try:
                result = self.get_stock_data(symbol, start_date, end_date, ktype)
                results[symbol] = result
            except Exception as e:
                results[symbol] = {'error': str(e)}
        
        return results
    
    def get_source_status(self) -> list:
        """获取数据源状态"""
        return self.manager.get_source_status()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()
    
    def clear_cache(self):
        """清理缓存"""
        self.cache.clear_expired()


# 便捷函数
def get_stock_data(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    ktype: str = "day"
) -> pd.DataFrame:
    """
    快速获取股票数据（只返回DataFrame）
    
    Example:
        df = get_stock_data('600138', '2024-01-01', '2024-12-31')
    """
    api = DataAPI()
    result = api.get_stock_data(symbol, start_date, end_date, ktype)
    
    if 'error' in result:
        raise Exception(result['error'])
    
    return result['data']
