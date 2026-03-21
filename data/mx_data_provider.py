"""
本地基本面数据提供者 (LocalFundamentalProvider)

保留但不主动使用，仅在需要时手动调用
"""
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FundamentalData:
    """基本面数据结构"""
    symbol: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    recent_news: Optional[List[str]] = None
    sector: Optional[str] = None


class LocalFundamentalProvider:
    """本地基本面数据提供者（按需使用）"""
    
    def __init__(self):
        self._cache: Dict[str, FundamentalData] = {}
    
    def set_data(self, symbol: str, data: FundamentalData) -> None:
        """设置股票基本面数据"""
        self._cache[symbol] = data
    
    def get_data(self, symbol: str) -> Optional[FundamentalData]:
        """获取股票基本面数据"""
        return self._cache.get(symbol)


# 便捷函数
def get_fundamental_provider() -> LocalFundamentalProvider:
    """获取默认数据提供者实例"""
    return LocalFundamentalProvider()
