"""
数据采集模块 - Tushare数据源适配器
"""
from typing import Any, Dict, Optional
import pandas as pd
import tushare as ts
from .data_collector import DataSourceAdapter, DataSourceType, DataFetchError


class TushareAdapter(DataSourceAdapter):
    """Tushare数据源适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Tushare适配器
        
        Args:
            config: 配置字典，需要包含token
        """
        super().__init__(config)
        self.token = config.get('token', '')
        self._pro: Optional[ts.pro_api] = None
    
    @property
    def source_type(self) -> DataSourceType:
        """返回数据源类型"""
        return DataSourceType.TUSHARE
    
    def connect(self) -> bool:
        """
        连接Tushare数据源
        
        Returns:
            是否连接成功
        """
        try:
            if not self.token:
                raise DataFetchError("Tushare token未配置")
            
            ts.set_token(self.token)
            self._pro = ts.pro_api()
            
            # 测试连接
            self._pro.query('stock_basic', limit=1)
            self.logger.info("Tushare连接成功")
            return True
            
        except Exception as e:
            self.logger.error(f"Tushare连接失败: {e}")
            return False
    
    def _get_pro(self):
        """获取Tushare Pro API实例"""
        if self._pro is None:
            self.connect()
        return self._pro
    
    def _convert_date_format(self, date_str: str) -> str:
        """
        转换日期格式从YYYY-MM-DD到YYYYMMDD
        
        Args:
            date_str: 日期字符串 (YYYY-MM-DD)
            
        Returns:
            转换后的日期字符串 (YYYYMMDD)
        """
        return date_str.replace('-', '')
    
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
            symbol: 股票代码 (如: 000001.SZ)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            **kwargs: 额外参数
            
        Returns:
            DataFrame包含日K线数据
        """
        try:
            pro = self._get_pro()
            
            # 转换日期格式
            start = self._convert_date_format(start_date)
            end = self._convert_date_format(end_date)
            
            # 获取日线数据
            df = pro.daily(
                ts_code=symbol,
                start_date=start,
                end_date=end
            )
            
            if df.empty:
                self.logger.warning(f"{symbol} 在指定日期范围内无数据")
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                'ts_code': 'symbol',
                'trade_date': 'date',
                'vol': 'volume',
                'amount': 'amount'
            })
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)
            
            return self.normalize_kline_data(df)
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} 日K线数据失败: {e}")
            raise DataFetchError(f"Tushare获取日K线失败: {e}")
    
    def get_industry_index(
        self,
        industry_code: Optional[str] = None,
        start_date: str = '',
        end_date: str = '',
        **kwargs
    ) -> pd.DataFrame:
        """
        获取行业指数数据
        
        Args:
            industry_code: 行业代码 (可选)
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 额外参数
            
        Returns:
            DataFrame包含行业指数数据
        """
        try:
            pro = self._get_pro()
            
            # 转换日期格式
            start = self._convert_date_format(start_date) if start_date else None
            end = self._convert_date_format(end_date) if end_date else None
            
            # 获取申万行业指数日线
            if industry_code:
                df = pro.sw_daily(
                    ts_code=industry_code,
                    start_date=start,
                    end_date=end
                )
            else:
                # 获取所有行业指数
                df = pro.sw_daily(start_date=start, end_date=end)
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                'ts_code': 'industry_code',
                'trade_date': 'date',
                'name': 'industry_name'
            })
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            return df.sort_values(['industry_code', 'date']).reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取行业指数数据失败: {e}")
            raise DataFetchError(f"Tushare获取行业指数失败: {e}")
    
    def get_stock_list(self, **kwargs) -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            **kwargs: 额外参数
                - exchange: 交易所 (SSE/SZSE)
                - list_status: 上市状态 (L-上市/D-退市/P-暂停)
                
        Returns:
            DataFrame包含股票列表
        """
        try:
            pro = self._get_pro()
            
            exchange = kwargs.get('exchange', None)
            list_status = kwargs.get('list_status', 'L')
            
            df = pro.stock_basic(
                exchange=exchange,
                list_status=list_status
            )
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                'ts_code': 'symbol',
                'name': 'stock_name'
            })
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            raise DataFetchError(f"Tushare获取股票列表失败: {e}")
    
    def get_industry_list(self, level: str = 'L1') -> pd.DataFrame:
        """
        获取申万行业列表
        
        Args:
            level: 行业级别 (L1-一级/L2-二级/L3-三级)
            
        Returns:
            DataFrame包含行业列表
        """
        try:
            pro = self._get_pro()
            
            df = pro.sw_classify(level=level)
            
            if df.empty:
                return pd.DataFrame()
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取行业列表失败: {e}")
            raise DataFetchError(f"Tushare获取行业列表失败: {e}")
