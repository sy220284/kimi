"""
多平台财经数据适配器
支持：搜狐财经、网易财经、新浪财经
作为 THS 同花顺的 fallback 备选方案

注意：已弃用 AKShare/Tushare，统一使用同花顺(THS)作为主要数据源
"""
import json
import time
from datetime import datetime
from typing import Any

import pandas as pd
import requests


class MultiPlatformFinanceAdapter:
    """多平台财经数据适配器"""

    def __init__(self, config: dict[str, Any] = None):
        self.config = config or {}
        self.session = requests.Session()
        
        # 请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://finance.sina.com.cn/stock/',
        }
        
        # 平台优先级（搜狐提供历史，新浪提供实时）
        self.platforms = ['sohu', 'netease', 'sina']
        if self.config.get('prefer'):
            prefer = self.config.get('prefer')
            if prefer in self.platforms:
                self.platforms.remove(prefer)
                self.platforms.insert(0, prefer)

    def _get_sina_code(self, symbol: str) -> str:
        """转换为新浪股票代码格式"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        if symbol.endswith('.SH'):
            return f'sh{code}'
        elif symbol.endswith('.BJ'):
            return f'bj{code}'
        else:
            return f'sz{code}'

    def _get_netease_code(self, symbol: str) -> str:
        """转换为网易股票代码格式"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        if symbol.endswith('.SH'):
            return f'0{code}'
        elif symbol.endswith('.BJ'):
            return f'{code}'
        else:
            return f'1{code}'

    def get_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        ktype: str = 'day',
        adjust: str = 'qfq'
    ) -> pd.DataFrame | None:
        """
        获取历史K线数据（自动切换平台）
        """
        errors = []
        
        for platform in self.platforms:
            try:
                if platform == 'sohu':
                    df = self._fetch_sohu(symbol, start_date, end_date, ktype, adjust)
                elif platform == 'netease':
                    df = self._fetch_netease(symbol, start_date, end_date, ktype, adjust)
                elif platform == 'sina':
                    df = self._fetch_sina(symbol, start_date, end_date, ktype, adjust)
                else:
                    continue
                
                if df is not None and not df.empty:
                    print(f"✅ 从 [{platform}] 获取 {symbol} 成功，共 {len(df)} 条")
                    return df
                    
            except Exception as e:
                error_msg = str(e)
                errors.append(f"{platform}: {error_msg}")
                print(f"⚠️ [{platform}] 获取失败: {error_msg}")
                continue
        
        print(f"❌ 所有平台获取失败: {'; '.join(errors)}")
        return None

    def _fetch_sohu(
        self,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str,
        adjust: str
    ) -> pd.DataFrame | None:
        """从搜狐财经获取数据（替代腾讯）"""
        # 搜狐财经代码格式
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        sohu_code = f'cn_{code}'
        
        # 搜狐API不支持复权参数，获取原始数据
        start = (start_date or '19900101').replace('-', '')
        end = (end_date or datetime.now().strftime('%Y-%m-%d')).replace('-', '')
        
        url = f'http://q.stock.sohu.com/hisHq'
        params = {
            'code': sohu_code,
            'start': start,
            'end': end,
            'stat': '1',
            'order': 'D',  # 降序
            'period': 'd',  # 日线
            'rt': 'json'
        }
        
        # 添加延迟
        time.sleep(self.config.get('delay', 0.1))
        
        response = self.session.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        
        item = data[0]
        if item.get('status') != 0:
            return None
        
        hq = item.get('hq', [])
        if not hq:
            return None
        
        # 解析数据
        # 搜狐格式: [日期, 开盘, 收盘, 涨跌, 涨跌幅, 最低, 最高, 成交量, 成交额, 换手率]
        rows = []
        for row in hq:
            if len(row) >= 9:
                rows.append({
                    'date': row[0],
                    'open': float(row[1]),
                    'close': float(row[2]),
                    'low': float(row[5]),
                    'high': float(row[6]),
                    'volume': float(row[7]) * 100,  # 搜狐是手，转换为股
                    'amount': float(row[8]) * 10000,  # 搜狐是万元，转换为元
                    'pct_change': float(row[4].replace('%', '')) if row[4] else 0,
                })
        
        if not rows:
            return None
            
        df = pd.DataFrame(rows)
        df['symbol'] = symbol
        df['date'] = pd.to_datetime(df['date'])
        
        # 按日期升序排序
        df = df.sort_values('date').reset_index(drop=True)
        
        return df

    def _fetch_netease(
        self,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str,
        adjust: str
    ) -> pd.DataFrame | None:
        """从网易财经获取数据"""
        netease_code = self._get_netease_code(symbol)
        
        # K线类型映射
        ktype_map = {
            'day': 'daily',
            'week': 'weekly',
            'month': 'monthly'
        }
        netease_ktype = ktype_map.get(ktype, 'daily')
        
        url = f'http://quotes.money.163.com/service/chddata.html'
        params = {
            'code': netease_code,
            'start': (start_date or '19900101').replace('-', ''),
            'end': (end_date or datetime.now().strftime('%Y-%m-%d')).replace('-', ''),
            'fields': 'TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;VOTURNOVER;VATURNOVER',
        }
        
        # 添加延迟
        time.sleep(self.config.get('delay', 0.1))
        
        response = self.session.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        
        # 网易返回 CSV 格式
        from io import StringIO
        df = pd.read_csv(StringIO(response.text), encoding='gb2312')
        
        if df.empty:
            return None
        
        # 重命名列
        df.columns = ['date', 'code', 'name', 'close', 'high', 'low', 'open', 
                      'pre_close', 'change', 'pct_change', 'volume', 'amount']
        
        df['symbol'] = symbol
        df['date'] = pd.to_datetime(df['date'])
        
        # 选择需要的列
        df = df[['date', 'symbol', 'open', 'close', 'low', 'high', 'volume', 'amount']]
        
        return df

    def _fetch_sina(
        self,
        symbol: str,
        start_date: str | None,
        end_date: str | None,
        ktype: str,
        adjust: str
    ) -> pd.DataFrame | None:
        """从新浪财经获取数据（通过雪球）"""
        # 雪球需要登录，这里使用新浪的实时接口作为简化版
        # 实际使用时可能需要更复杂的处理
        
        sina_code = self._get_sina_code(symbol)  # 使用新浪代码格式
        
        url = f'http://hq.sinajs.cn/list={sina_code}'
        
        # 添加延迟
        time.sleep(self.config.get('delay', 0.1))
        
        response = self.session.get(url, headers=self.headers, timeout=10)
        response.encoding = 'gb2312'
        
        # 新浪返回的是实时行情，不是历史数据
        # 这个方法主要用于获取实时价格
        # 如果需要历史数据，建议使用腾讯或网易
        
        # 解析实时数据
        data = response.text
        if not data or '=""' in data:
            return None
        
        # 新浪实时数据格式解析
        # var hq_str_sh600000="浦发银行,10.500,10.520,10.480,...";
        import re
        match = re.search(r'="([^"]+)"', data)
        if not match:
            return None
        
        parts = match.group(1).split(',')
        if len(parts) < 8:
            return None
        
        # 只返回实时数据（单条）
        today = datetime.now().strftime('%Y-%m-%d')
        rows = [{
            'date': today,
            'symbol': symbol,
            'open': float(parts[1]),
            'close': float(parts[3]),
            'high': float(parts[4]),
            'low': float(parts[5]),
            'volume': float(parts[8]) if len(parts) > 8 else 0,
        }]
        
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        
        return df

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            df = self.get_history('000001.SZ', start_date='2024-01-01', end_date='2024-01-05')
            return df is not None and not df.empty
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False

    def get_spot(self, symbol: str) -> dict[str, Any] | None:
        """获取实时行情"""
        try:
            # 优先使用新浪实时接口
            code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
            if symbol.endswith('.SH'):
                sina_code = f'sh{code}'
            elif symbol.endswith('.BJ'):
                sina_code = f'bj{code}'
            else:
                sina_code = f'sz{code}'
            
            url = f'http://hq.sinajs.cn/list={sina_code}'
            
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.encoding = 'gb2312'
            
            data = response.text
            import re
            pattern = rf'var hq_str_{sina_code}="([^"]+)"'
            match = re.search(pattern, data)
            if not match:
                return None
            
            parts = match.group(1).split(',')
            if len(parts) < 8:
                return None
            
            return {
                'name': parts[0],
                'open': float(parts[1]),
                'close': float(parts[3]),
                'high': float(parts[4]),
                'low': float(parts[5]),
                'volume': float(parts[8]) if len(parts) > 8 else 0,
            }
            
        except Exception as e:
            print(f"获取实时行情失败: {e}")
            return None
