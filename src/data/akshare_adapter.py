"""
数据采集模块 - Akshare数据源适配器
"""
from typing import Any, Dict, List, Optional
import pandas as pd
import akshare as ak
from datetime import datetime
from .data_collector import DataSourceAdapter, DataSourceType, DataFetchError


class AkshareAdapter(DataSourceAdapter):
    """Akshare数据源适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Akshare适配器
        
        Args:
            config: 配置字典
        """
        super().__init__(config)
    
    @property
    def source_type(self) -> DataSourceType:
        """返回数据源类型"""
        return DataSourceType.AKSHARE
    
    def connect(self) -> bool:
        """
        连接Akshare数据源
        
        Returns:
            是否连接成功（Akshare不需要显式连接）
        """
        try:
            # 测试连接 - 获取一次股票列表
            ak.stock_zh_a_spot_em()
            self.logger.info("Akshare连接成功")
            return True
        except Exception as e:
            self.logger.error(f"Akshare连接失败: {e}")
            return False
    
    def _standardize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码格式
        
        Args:
            symbol: 股票代码
            
        Returns:
            标准化的股票代码
        """
        # 移除可能的后缀
        symbol = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        return symbol
    
    def _convert_period(self, start_date: str, end_date: str) -> tuple:
        """
        转换日期格式
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            转换后的日期元组 (YYYYMMDD, YYYYMMDD)
        """
        start = start_date.replace('-', '')
        end = end_date.replace('-', '')
        return start, end
    
    def get_daily_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = 'qfq',
        **kwargs
    ) -> pd.DataFrame:
        """
        获取日K线数据
        
        Args:
            symbol: 股票代码 (如: 000001 或 000001.SZ)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            adjust: 复权类型 ('' 不复权, 'qfq' 前复权, 'hfq' 后复权)
            **kwargs: 额外参数
            
        Returns:
            DataFrame包含日K线数据
        """
        try:
            symbol = self._standardize_symbol(symbol)
            start, end = self._convert_period(start_date, end_date)
            
            # 使用akshare获取日线数据
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=adjust
            )
            
            if df.empty:
                self.logger.warning(f"{symbol} 在指定日期范围内无数据")
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })
            
            # 添加symbol列
            df['symbol'] = symbol
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)
            
            return self.normalize_kline_data(df)
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} 日K线数据失败: {e}")
            raise DataFetchError(f"Akshare获取日K线失败: {e}")
    
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
            # 获取申万行业指数
            if industry_code:
                # 获取特定行业历史行情
                df = ak.index_zh_a_hist(
                    symbol=industry_code,
                    period="daily",
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', '')
                )
                df['industry_code'] = industry_code
            else:
                # 获取行业板块实时行情作为快照
                df = ak.stock_board_industry_name_em()
                df = df.rename(columns={
                    '板块名称': 'industry_name',
                    '板块代码': 'industry_code'
                })
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名（如果是历史数据）
            if '日期' in df.columns:
                df = df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                })
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取行业指数数据失败: {e}")
            raise DataFetchError(f"Akshare获取行业指数失败: {e}")
    
    def get_stock_list(self, **kwargs) -> pd.DataFrame:
        """
        获取A股股票列表
        
        Args:
            **kwargs: 额外参数
                
        Returns:
            DataFrame包含股票列表
        """
        try:
            # 使用东方财富数据源获取A股列表
            df = ak.stock_zh_a_spot_em()
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            column_mapping = {
                '代码': 'symbol',
                '名称': 'stock_name',
                '最新价': 'latest_price',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'prev_close',
                '量比': 'volume_ratio',
                '换手率': 'turnover',
                '市盈率-动态': 'pe_ratio',
                '市净率': 'pb_ratio',
                '总市值': 'total_market_cap',
                '流通市值': 'float_market_cap',
                '涨速': 'rise_speed',
                '5分钟涨跌': 'change_5min',
                '60日涨跌幅': 'change_60d',
                '年初至今涨跌幅': 'change_ytd'
            }
            
            df = df.rename(columns=column_mapping)
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            raise DataFetchError(f"Akshare获取股票列表失败: {e}")
    
    def get_industry_list(self) -> pd.DataFrame:
        """
        获取行业板块列表
        
        Returns:
            DataFrame包含行业列表
        """
        try:
            df = ak.stock_board_industry_name_em()
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                '板块名称': 'industry_name',
                '板块代码': 'industry_code',
                '最新价': 'latest_price',
                '涨跌额': 'change',
                '涨跌幅': 'change_pct',
                '总市值': 'total_market_cap',
                '换手率': 'turnover',
                '上涨家数': 'rising_count',
                '下跌家数': 'falling_count',
                '领涨股票': 'leading_stock',
                '领涨股票-涨跌幅': 'leading_stock_change'
            })
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取行业列表失败: {e}")
            raise DataFetchError(f"Akshare获取行业列表失败: {e}")
    
    def get_concept_list(self) -> pd.DataFrame:
        """
        获取概念板块列表
        
        Returns:
            DataFrame包含概念列表
        """
        try:
            df = ak.stock_board_concept_name_em()
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df = df.rename(columns={
                '板块名称': 'concept_name',
                '板块代码': 'concept_code',
                '最新价': 'latest_price',
                '涨跌额': 'change',
                '涨跌幅': 'change_pct',
                '总市值': 'total_market_cap',
                '换手率': 'turnover',
                '上涨家数': 'rising_count',
                '下跌家数': 'falling_count',
                '领涨股票': 'leading_stock',
                '领涨股票-涨跌幅': 'leading_stock_change'
            })
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取概念列表失败: {e}")
            raise DataFetchError(f"Akshare获取概念列表失败: {e}")
    
    def get_index_list(self) -> pd.DataFrame:
        """
        获取指数列表
        
        Returns:
            DataFrame包含指数列表
        """
        try:
            # 获取沪深指数列表
            df = ak.index_stock_info()
            
            if df.empty:
                return pd.DataFrame()
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            self.logger.error(f"获取指数列表失败: {e}")
            raise DataFetchError(f"Akshare获取指数列表失败: {e}")
