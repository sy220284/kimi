"""
数据采集模块 - 同花顺(THS)网页版API适配器
基于同花顺网页版内部API，无需token，直接HTTP获取
支持多次请求拼接获取完整历史数据
"""
from typing import Any, Dict, Optional
import pandas as pd
import requests
import json
import re
from datetime import datetime
from .data_collector import DataSourceAdapter, DataSourceType, DataFetchError


class ThsAdapter(DataSourceAdapter):
    """同花顺(THS)数据源适配器 - 基于网页版内部API"""
    
    # 同花顺API基础配置
    BASE_URL = "http://d.10jqka.com.cn/v4/line"
    STOCK_PAGE_URL = "http://stockpage.10jqka.com.cn"
    REFERER_URL = "http://stockpage.10jqka.com.cn"
    
    # K线类型映射
    KTYPE_MAP = {
        '1min': '00',    # 1分钟
        '5min': '01',    # 5分钟  
        '15min': '02',   # 15分钟
        '30min': '03',   # 30分钟
        '60min': '04',   # 60分钟
        'day': '01',     # 日线
        'week': '11',    # 周线
        'month': '12',   # 月线
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化同花顺适配器
        
        Args:
            config: 配置字典（同花顺不需要token，但可配置headers等）
        """
        super().__init__(config)
        self.session = requests.Session()
        self.timeout = config.get('timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        self._setup_headers()
    
    def _setup_headers(self) -> None:
        """设置请求头，模拟浏览器访问"""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        # 允许通过配置覆盖默认headers
        custom_headers = self.config.get('headers', {})
        self.session.headers.update({**default_headers, **custom_headers})
    
    @property
    def source_type(self) -> DataSourceType:
        """返回数据源类型"""
        return DataSourceType.THS
    
    def connect(self) -> bool:
        """
        测试同花顺API连接
        
        Returns:
            是否连接成功
        """
        try:
            # 用茅台测试连接
            test_symbol = "hs_600519"
            url = f"{self.BASE_URL}/{test_symbol}/01/last.js"
            
            headers = {
                'Referer': f"{self.REFERER_URL}/600519/"
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                self.logger.info("同花顺API连接成功")
                return True
            else:
                self.logger.error(f"同花顺API连接失败，状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"同花顺连接失败: {e}")
            return False
    
    def _standardize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码为同花顺格式
        
        Args:
            symbol: 股票代码 (如: 600519.SH, 000001.SZ, 600519)
            
        Returns:
            同花顺格式代码 (如: hs_600519, hs_000001)
        """
        # 移除后缀
        symbol = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        symbol = symbol.replace('.sh', '').replace('.sz', '').replace('.bj', '')
        
        # 同花顺格式: hs_ + 代码
        return f"hs_{symbol}"
    
    def _parse_js_data(self, js_text: str, symbol: str) -> pd.DataFrame:
        """
        解析同花顺返回的JavaScript格式数据
        
        Args:
            js_text: JavaScript文本
            symbol: 股票代码
            
        Returns:
            DataFrame格式数据
        """
        try:
            # 提取JSON数据部分
            # 格式: quotebridge_v4_line_hs_600519_01({"data": "..."})
            pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
            match = re.search(pattern, js_text)
            
            if not match:
                raise DataFetchError("无法解析同花顺返回数据格式")
            
            json_str = match.group(1)
            data = json.loads(json_str)
            
            if 'data' not in data:
                raise DataFetchError("同花顺返回数据不包含data字段")
            
            # 解析数据字符串
            # 格式: 日期,开盘价,最高价,最低价,收盘价,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
            lines = data['data'].split(';')
            records = []
            
            for line in lines:
                if not line.strip():
                    continue
                
                parts = line.split(',')
                if len(parts) >= 6:
                    try:
                        record = {
                            'date': parts[0],
                            'open': float(parts[1]),
                            'high': float(parts[2]),
                            'low': float(parts[3]),
                            'close': float(parts[4]),
                            'volume': float(parts[5]) if parts[5] else 0,
                        }
                        if len(parts) > 6 and parts[6]:
                            record['amount'] = float(parts[6])
                        if len(parts) > 7 and parts[7]:
                            record['amplitude'] = float(parts[7])
                        if len(parts) > 8 and parts[8]:
                            record['change_pct'] = float(parts[8])
                        if len(parts) > 9 and parts[9]:
                            record['change'] = float(parts[9])
                        if len(parts) > 10 and parts[10]:
                            record['turnover'] = float(parts[10])
                        records.append(record)
                    except ValueError:
                        continue
            
            if not records:
                raise DataFetchError("解析后无有效数据")
            
            df = pd.DataFrame(records)
            df['symbol'] = symbol.replace('hs_', '')
            
            # 转换日期格式
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            
            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            raise DataFetchError(f"同花顺数据JSON解析失败: {e}")
        except Exception as e:
            self.logger.error(f"数据解析失败: {e}")
            raise DataFetchError(f"同花顺数据解析失败: {e}")
    
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
            symbol: 股票代码 (如: 600519 或 600519.SH)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            adjust: 复权类型 ('' 不复权, 'qfq' 前复权, 'hfq' 后复权)
            **kwargs: 额外参数
                - ktype: K线类型 ('day', 'week', 'month')
                
        Returns:
            DataFrame包含日K线数据
        """
        try:
            ths_symbol = self._standardize_symbol(symbol)
            ktype = kwargs.get('ktype', 'day')
            ktype_code = self.KTYPE_MAP.get(ktype, '01')
            
            # 构建URL
            url = f"{self.BASE_URL}/{ths_symbol}/{ktype_code}/last.js"
            
            # 设置Referer
            stock_code = ths_symbol.replace('hs_', '')
            headers = {
                'Referer': f"{self.REFERER_URL}/{stock_code}/"
            }
            
            self.logger.debug(f"请求同花顺API: {url}")
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise DataFetchError(f"同花顺API返回错误: HTTP {response.status_code}")
            
            # 解析数据
            df = self._parse_js_data(response.text, ths_symbol)
            
            if df.empty:
                self.logger.warning(f"{symbol} 返回数据为空")
                return pd.DataFrame()
            
            # 按日期过滤
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            
            # 处理复权（同花顺默认返回前复权数据）
            if adjust == 'hfq':
                self.logger.warning("同花顺API默认返回前复权，后复权需要额外计算")
            
            return self.normalize_kline_data(df)
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} 日K线数据失败: {e}")
            raise DataFetchError(f"同花顺获取日K线失败: {e}")
    
    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        """
        获取实时行情数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据字典
        """
        try:
            ths_symbol = self._standardize_symbol(symbol)
            
            # 使用line接口获取最新数据
            url = f"{self.BASE_URL}/{ths_symbol}/01/last.js"
            
            stock_code = ths_symbol.replace('hs_', '')
            headers = {
                'Referer': f"{self.REFERER_URL}/{stock_code}/"
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise DataFetchError(f"获取实时行情失败: HTTP {response.status_code}")
            
            df = self._parse_js_data(response.text, ths_symbol)
            
            if df.empty:
                raise DataFetchError("无实时行情数据")
            
            # 返回最新一条数据
            latest = df.iloc[-1].to_dict()
            latest['symbol'] = stock_code
            
            return latest
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} 实时行情失败: {e}")
            raise DataFetchError(f"同花顺获取实时行情失败: {e}")
    
    def get_stock_list(self, **kwargs) -> pd.DataFrame:
        """
        获取股票列表
        
        注：同花顺网页API不直接提供股票列表，使用备用方案
        
        Returns:
            DataFrame包含股票列表
        """
        try:
            # 使用同花顺的stockpick接口获取A股列表
            url = "http://data.10jqka.com.cn/rank/yield/"
            
            headers = {
                'Referer': 'http://data.10jqka.com.cn/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            _response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            # 提取股票代码和名称
            # 这里简化处理，实际可能需要解析HTML或使用其他接口
            self.logger.warning("同花顺股票列表获取需要额外解析，建议配合其他数据源使用")
            
            # 返回空DataFrame，带有标准列
            return pd.DataFrame(columns=['symbol', 'stock_name', 'exchange'])
            
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            raise DataFetchError(f"同花顺获取股票列表失败: {e}")
    
    def get_industry_index(
        self,
        industry_code: Optional[str] = None,
        start_date: str = '',
        end_date: str = '',
        **kwargs
    ) -> pd.DataFrame:
        """
        获取行业指数数据
        
        注：同花顺行业指数代码格式不同，需要特殊处理
        
        Args:
            industry_code: 行业代码 (同花顺格式，如: 881001)
            start_date: 开始日期
            end_date: 结束日期
            **kwargs: 额外参数
            
        Returns:
            DataFrame包含行业指数数据
        """
        try:
            if not industry_code:
                raise DataFetchError("同花顺行业数据需要提供行业代码")
            
            # 行业指数格式: hs_ + 行业代码
            ths_symbol = f"hs_{industry_code}"
            url = f"{self.BASE_URL}/{ths_symbol}/01/last.js"
            
            headers = {
                'Referer': f"{self.REFERER_URL}/{industry_code}/"
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise DataFetchError(f"获取行业指数失败: HTTP {response.status_code}")
            
            df = self._parse_js_data(response.text, ths_symbol)
            
            if df.empty:
                return pd.DataFrame()
            
            # 按日期过滤
            if start_date and end_date:
                df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
            
            df['industry_code'] = industry_code
            
            return df
            
        except Exception as e:
            self.logger.error(f"获取行业指数数据失败: {e}")
            raise DataFetchError(f"同花顺获取行业指数失败: {e}")
    
    def get_industry_list(self) -> pd.DataFrame:
        """
        获取行业板块列表
        
        Returns:
            DataFrame包含行业列表
        """
        try:
            # 同花顺行业板块数据
            url = "http://data.10jqka.com.cn/rank/industry/"
            
            headers = {
                'Referer': 'http://data.10jqka.com.cn/',
            }
            
            _response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            self.logger.warning("同花顺行业列表需要HTML解析，建议使用备用数据源")
            
            return pd.DataFrame(columns=['industry_code', 'industry_name'])
            
        except Exception as e:
            self.logger.error(f"获取行业列表失败: {e}")
            raise DataFetchError(f"同花顺获取行业列表失败: {e}")
    
    def get_index_list(self) -> pd.DataFrame:
        """
        获取指数列表
        
        Returns:
            DataFrame包含指数列表
        """
        # 同花顺常见指数代码映射
        common_indices = [
            {'symbol': 'hs_000001', 'name': '上证指数', 'code': '000001'},
            {'symbol': 'hs_399001', 'name': '深证成指', 'code': '399001'},
            {'symbol': 'hs_399006', 'name': '创业板指', 'code': '399006'},
            {'symbol': 'hs_000300', 'name': '沪深300', 'code': '000300'},
            {'symbol': 'hs_000016', 'name': '上证50', 'code': '000016'},
            {'symbol': 'hs_000905', 'name': '中证500', 'code': '000905'},
            {'symbol': 'hs_000688', 'name': '科创50', 'code': '000688'},
        ]
        
        return pd.DataFrame(common_indices)
    
    def get_kline_data(
        self,
        symbol: str,
        period: str = 'day',
        count: int = 500,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取指定数量的K线数据
        
        Args:
            symbol: 股票代码
            period: 周期 ('1min', '5min', '15min', '30min', '60min', 'day', 'week', 'month')
            count: 获取条数
            **kwargs: 额外参数
            
        Returns:
            DataFrame包含K线数据
        """
        try:
            ths_symbol = self._standardize_symbol(symbol)
            ktype_code = self.KTYPE_MAP.get(period, '01')
            
            url = f"{self.BASE_URL}/{ths_symbol}/{ktype_code}/last.js"
            
            stock_code = ths_symbol.replace('hs_', '')
            headers = {
                'Referer': f"{self.REFERER_URL}/{stock_code}/"
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code != 200:
                raise DataFetchError(f"获取K线数据失败: HTTP {response.status_code}")
            
            df = self._parse_js_data(response.text, ths_symbol)
            
            if df.empty:
                return pd.DataFrame()
            
            # 取最后N条
            if count > 0 and len(df) > count:
                df = df.tail(count)
            
            return self.normalize_kline_data(df)
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} K线数据失败: {e}")
            raise DataFetchError(f"同花顺获取K线数据失败: {e}")
    
    def get_concept_list(self) -> pd.DataFrame:
        """
        获取概念板块列表
        
        Returns:
            DataFrame包含概念列表
        """
        try:
            url = "http://data.10jqka.com.cn/rank/concept/"
            
            headers = {
                'Referer': 'http://data.10jqka.com.cn/',
            }
            
            _response = self.session.get(url, headers=headers, timeout=self.timeout)
            
            self.logger.warning("同花顺概念列表需要HTML解析，建议使用备用数据源")
            
            return pd.DataFrame(columns=['concept_code', 'concept_name'])
            
        except Exception as e:
            self.logger.error(f"获取概念列表失败: {e}")
            raise DataFetchError(f"同花顺获取概念列表失败: {e}")
    
    def _parse_year_data(self, js_text: str) -> pd.DataFrame:
        """解析年份接口返回的数据"""
        pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
        match = re.search(pattern, js_text)
        if not match:
            raise ValueError("无法解析数据格式")
        
        data = json.loads(match.group(1))
        lines = data.get('data', '').split(';')
        
        records = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 6:
                try:
                    record = {
                        'date': parts[0],
                        'open': float(parts[1]),
                        'high': float(parts[2]),
                        'low': float(parts[3]),
                        'close': float(parts[4]),
                        'volume': float(parts[5]) if parts[5] else 0,
                    }
                    if len(parts) > 6 and parts[6]:
                        record['amount'] = float(parts[6])
                    if len(parts) > 7 and parts[7]:
                        record['amplitude'] = float(parts[7])
                    if len(parts) > 8 and parts[8]:
                        record['change_pct'] = float(parts[8])
                    if len(parts) > 9 and parts[9]:
                        record['change'] = float(parts[9])
                    if len(parts) > 10 and parts[10]:
                        record['turnover'] = float(parts[10])
                    records.append(record)
                except ValueError:
                    continue
        
        df = pd.DataFrame(records)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            df = df.sort_values('date').reset_index(drop=True)
        return df
    
    def get_full_history(
        self,
        symbol: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        获取完整历史数据（按年份多次请求拼接）
        
        Args:
            symbol: 股票代码
            start_year: 开始年份（默认从上市年份）
            end_year: 结束年份（默认今年）
            **kwargs: 额外参数
                - show_progress: 是否显示进度
                
        Returns:
            DataFrame包含完整历史数据
        """
        try:
            ths_symbol = self._standardize_symbol(symbol)
            show_progress = kwargs.get('show_progress', True)
            
            # 获取数据信息
            info_url = f"{self.BASE_URL}/{ths_symbol}/01/last.js"
            stock_code = ths_symbol.replace('hs_', '')
            
            resp = self.session.get(info_url, headers={'Referer': f'{self.REFERER_URL}/{stock_code}/'}, timeout=self.timeout)
            
            if resp.status_code != 200:
                raise DataFetchError(f"获取数据信息失败: HTTP {resp.status_code}")
            
            # 直接解析JSON获取信息
            pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
            match = re.search(pattern, resp.text)
            if not match:
                raise DataFetchError("无法解析数据信息")
            
            info_json = json.loads(match.group(1))
            total_records = int(info_json.get('total', 0))
            listing_date = info_json.get('start', '')
            listing_year = int(listing_date[:4]) if listing_date else 1990
            
            # 确定年份范围
            start = start_year if start_year else listing_year
            end = end_year if end_year else datetime.now().year
            
            self.logger.info(f"{symbol} 共有 {total_records} 条历史数据，从 {start} 年到 {end} 年")
            
            all_data = []
            
            for year in range(end, start - 1, -1):
                try:
                    url = f"{self.BASE_URL}/{ths_symbol}/01/{year}.js"
                    year_resp = self.session.get(url, headers={'Referer': f'{self.REFERER_URL}/{stock_code}/'}, timeout=self.timeout)
                    
                    if year_resp.status_code == 200:
                        df = self._parse_year_data(year_resp.text)
                        if not df.empty:
                            all_data.append(df)
                            if show_progress:
                                self.logger.debug(f"  ✓ {year}年: {len(df)} 条")
                        else:
                            if show_progress:
                                self.logger.debug(f"  - {year}年: 无数据")
                    else:
                        if show_progress:
                            self.logger.debug(f"  - {year}年: HTTP {year_resp.status_code}")
                            
                except Exception as e:
                    self.logger.warning(f"  - {year}年: 错误 {str(e)[:40]}")
            
            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined = combined.drop_duplicates(subset=['date'], keep='first')
                combined['symbol'] = stock_code
                combined = combined.sort_values('date').reset_index(drop=True)
                self.logger.info(f"{symbol} 完整数据获取完成: {len(combined)} 条")
                return self.normalize_kline_data(combined)
            
            return pd.DataFrame()
            
        except Exception as e:
            self.logger.error(f"获取 {symbol} 完整历史数据失败: {e}")
            raise DataFetchError(f"同花顺获取完整历史数据失败: {e}")
