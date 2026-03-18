"""
多源数据管理器 - 主备切换 + 数据聚合
主源: THS (同花顺)
备源: AKShare / Tushare / 本地缓存
"""
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pathlib import Path
import sys

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
    
    def to_dict(self) -> Dict[str, Any]:
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
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.sources: Dict[str, Any] = {}
        self.source_status: Dict[str, DataSourceStatus] = {}
        
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
        
        # 本地缓存 (备选)
        try:
            from data.cache import get_cache
            self.sources['cache'] = get_cache()
            self.source_status['cache'] = DataSourceStatus('cache')
        except Exception as e:
            print(f"缓存初始化失败: {e}")
    
    def get_history(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ktype: str = "day",
        prefer_source: Optional[str] = None
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
        
        # 确定查询顺序
        source_order = ['ths', 'cache']
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
                elif source_name == 'cache':
                    df = self._fetch_from_cache(source, symbol, start_date, end_date, ktype)
                else:
                    continue
                
                elapsed = time.time() - start_time
                
                if df is not None and not df.empty:
                    status.record_success(elapsed)
                    
                    # 如果是从主源获取，保存到缓存
                    if source_name == 'ths' and 'cache' in self.sources:
                        self.sources['cache'].set(
                            df, symbol, 
                            start_date or df['date'].min(),
                            end_date or df['date'].max(),
                            ktype
                        )
                    
                    return df
                
            except Exception as e:
                error_msg = str(e)
                status.record_fail(error_msg)
                errors.append(f"{source_name}: {error_msg}")
        
        # 所有源都失败
        raise DataFetchError(f"所有数据源获取失败: {'; '.join(errors)}")
    
    def _fetch_from_ths(
        self, 
        adapter, 
        symbol: str, 
        start_date: Optional[str],
        end_date: Optional[str],
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
    
    def _fetch_from_cache(
        self,
        cache,
        symbol: str,
        start_date: Optional[str],
        end_date: Optional[str],
        ktype: str
    ) -> pd.DataFrame:
        """从缓存获取数据"""
        return cache.get(symbol, start_date or "", end_date or "", ktype)
    
    def get_source_status(self) -> List[Dict[str, Any]]:
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

def get_data_manager(config: Dict[str, Any] = None) -> MultiSourceDataManager:
    """获取全局数据管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = MultiSourceDataManager(config)
    return _global_manager
