"""
东方财富直连适配器
直接调用东财API，不通过 akshare 中间层
"""
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests


class EastMoneyDirectAdapter:
    """东方财富直连适配器"""

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}
        self.session = requests.Session()
        
        # 请求头模拟浏览器
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://quote.eastmoney.com/',
        }
        
        # 基础URL
        self.base_url = 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
        self.spot_url = 'http://push2.eastmoney.com/api/qt/stock/get'
        
    def _get_secid(self, symbol: str) -> str:
        """
        获取东财的 secid 格式
        
        Args:
            symbol: 股票代码如 '000001.SZ'
            
        Returns:
            secid 如 '0.000001' (深市) 或 '1.600000' (沪市)
        """
        # 移除后缀
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        # 判断市场
        if symbol.endswith('.SH'):
            return f'1.{code}'  # 沪市
        elif symbol.endswith('.BJ'):
            return f'0.{code}'  # 北交所也用0
        else:
            return f'0.{code}'  # 深市默认

    def get_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        ktype: str = 'day',
        adjust: str = 'qfq'
    ) -> pd.DataFrame | None:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            ktype: K线类型 (day/week/month)
            adjust: 复权类型 (qfq/bfq)
            
        Returns:
            DataFrame 或 None
        """
        # 转换日期格式
        if start_date:
            start_date = start_date.replace('-', '')
        if end_date:
            end_date = end_date.replace('-', '')
        
        # 默认取全部历史
        if not start_date:
            start_date = '19900101'
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # K线类型映射
        ktype_map = {
            'day': '101',
            'week': '102',
            'month': '103',
            '1min': '1',
            '5min': '5',
            '15min': '15',
            '30min': '30',
            '60min': '60'
        }
        ktype_code = ktype_map.get(ktype, '101')
        
        # 构建参数
        secid = self._get_secid(symbol)
        fields = 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
        
        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': fields,
            'klt': ktype_code,
            'fqt': '0' if adjust == 'bfq' else '1',  # 0=不复权, 1=前复权
            'beg': start_date,
            'end': end_date,
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'iscr': '0'
        }
        
        try:
            # 添加随机延迟防封
            time.sleep(self.config.get('delay', 0.1))
            
            response = self.session.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 解析数据
            klines = data.get('data', {}).get('klines', [])
            
            if not klines:
                return None
            
            # 解析K线数据
            rows = []
            for line in klines:
                # 格式: 日期,开盘,收盘,最低,最高,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
                parts = line.split(',')
                if len(parts) >= 6:
                    rows.append({
                        'date': parts[0],
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'low': float(parts[3]),
                        'high': float(parts[4]),
                        'volume': float(parts[5]),
                        'amount': float(parts[6]) if len(parts) > 6 else None,
                        'amplitude': float(parts[7]) if len(parts) > 7 else None,
                        'pct_change': float(parts[8]) if len(parts) > 8 else None,
                        'change': float(parts[9]) if len(parts) > 9 else None,
                        'turnover': float(parts[10]) if len(parts) > 10 else None,
                    })
            
            df = pd.DataFrame(rows)
            df['symbol'] = symbol
            df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"东财直连获取数据失败 {symbol}: {e}")
            return None

    def get_spot(self, symbol: str) -> dict[str, Any] | None:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情字典或 None
        """
        secid = self._get_secid(symbol)
        
        params = {
            'secid': secid,
            'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60,f107',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        }
        
        try:
            response = self.session.get(
                self.spot_url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('data')
            
        except Exception as e:
            print(f"东财直连获取实时行情失败 {symbol}: {e}")
            return None

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            # 测试获取平安银行数据
            df = self.get_history('000001.SZ', start_date='2024-01-01', end_date='2024-01-05')
            return df is not None and not df.empty
        except Exception:
            return False
