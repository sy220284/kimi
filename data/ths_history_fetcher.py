#!/usr/bin/env python3
"""
同花顺(THS)API - 完整历史数据获取模块
支持多次请求拼接获取全部历史数据
"""
import json
import re
from datetime import datetime

import pandas as pd
import requests


class ThsHistoryFetcher:
    """同花顺历史数据获取器"""

    BASE_URL = "http://d.10jqka.com.cn/v4/line"

    def __init__(self, timeout: int = 30):
        self.session = requests.Session()
        self.timeout = timeout
        self._setup_headers()

    def _setup_headers(self):
        """设置请求头"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })

    def _get_referer(self, code: str) -> str:
        """获取Referer"""
        stock_code = code.replace('hs_', '')
        return f'http://stockpage.10jqka.com.cn/{stock_code}/'

    def _parse_js_data(self, js_text: str) -> dict:
        """解析同花顺JS数据"""
        pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
        match = re.search(pattern, js_text)
        if not match:
            raise ValueError("无法解析数据格式")
        return json.loads(match.group(1))

    def _parse_kline_data(self, data: dict) -> pd.DataFrame:
        """解析K线数据"""
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
                    # 跳过格式错误的行
                    continue

        df = pd.DataFrame(records)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
            df = df.sort_values('date').reset_index(drop=True)
        return df

    def get_data_info(self, code: str) -> dict:
        """获取数据信息（总条数、起始日期等）"""
        url = f"{self.BASE_URL}/{code}/01/last.js"

        resp = self.session.get(url, headers={'Referer': self._get_referer(code)}, timeout=self.timeout)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        data = self._parse_js_data(resp.text)

        return {
            'total': int(data.get('total', 0)),
            'start_date': data.get('start', ''),
            'years': data.get('year', {}),
        }

    def get_recent_data(self, code: str, days: int = 140) -> pd.DataFrame:
        """获取最近N天的数据（单次请求）"""
        url = f"{self.BASE_URL}/{code}/01/last.js"

        resp = self.session.get(url, headers={'Referer': self._get_referer(code)}, timeout=self.timeout)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        data = self._parse_js_data(resp.text)
        df = self._parse_kline_data(data)

        if days > 0 and len(df) > days:
            df = df.tail(days).reset_index(drop=True)

        return df

    def _parse_year_data(self, js_text: str) -> pd.DataFrame:
        """解析年份接口返回的数据"""
        pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
        match = re.search(pattern, js_text)
        if not match:
            raise ValueError("无法解析数据格式")

        data = json.loads(match.group(1))

        # 年份接口的数据在 'data' 字段
        if 'data' in data:
            lines = data['data'].split(';')
        else:
            # 尝试按 last.js 格式解析
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

    def get_all_data(self, code: str, progress_callback=None) -> pd.DataFrame:
        """
        获取全部历史数据（多次请求拼接）

        策略：通过获取不同年份的数据来拼接完整历史
        """
        # 首先获取数据信息
        info = self.get_data_info(code)
        total = info['total']
        start_year = int(info['start_date'][:4])
        end_year = datetime.now().year

        print(f"[INFO] {code} 共有 {total} 条历史数据，从 {start_year} 年到 {end_year} 年")

        all_data = []

        # 使用 year 参数按年份获取
        for year in range(end_year, start_year - 1, -1):
            try:
                if progress_callback:
                    progress_callback(year, start_year, end_year)

                url = f"{self.BASE_URL}/{code}/01/{year}.js"
                resp = self.session.get(url, headers={'Referer': self._get_referer(code)}, timeout=self.timeout)

                if resp.status_code == 200:
                    try:
                        df = self._parse_year_data(resp.text)
                        if not df.empty:
                            all_data.append(df)
                            print(f"  ✓ {year}年: {len(df)} 条")
                        else:
                            print(f"  - {year}年: 无数据")
                    except Exception as e:
                        print(f"  - {year}年: 解析失败 - {str(e)[:40]}")
                else:
                    print(f"  - {year}年: HTTP {resp.status_code}")

            except Exception as e:
                print(f"  - {year}年: 错误 {str(e)[:40]}")

        if all_data:
            # 合并所有数据
            combined = pd.concat(all_data, ignore_index=True)
            # 去重并按日期排序
            combined = combined.drop_duplicates(subset=['date'], keep='first')
            combined = combined.sort_values('date').reset_index(drop=True)
            return combined

        return pd.DataFrame()

    def get_data_by_date_range(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指定日期范围的数据

        Args:
            code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        # 先获取全部数据，然后过滤
        df = self.get_all_data(code)

        if df.empty:
            return df

        # 过滤日期范围
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        return df.reset_index(drop=True)


def main():
    """测试完整历史数据获取"""
    print("=" * 70)
    print("同花顺(THS)API - 完整历史数据获取测试")
    print("=" * 70)

    fetcher = ThsHistoryFetcher()

    # 测试股票
    test_stocks = [
        ("hs_600519", "贵州茅台"),
        ("hs_000001", "平安银行"),
    ]

    for code, name in test_stocks:
        print(f"\n📊 {name}({code.replace('hs_', '')})")
        print("-" * 70)

        # 获取数据信息
        try:
            info = fetcher.get_data_info(code)
            print(f"总数据条数: {info['total']}")
            print(f"起始日期: {info['start_date']}")
        except Exception as e:
            print(f"获取信息失败: {e}")
            continue

        # 获取最近数据
        print("\n获取最近140天数据...")
        try:
            recent_df = fetcher.get_recent_data(code, days=140)
            print(f"✓ 获取 {len(recent_df)} 条")
            print(f"  范围: {recent_df['date'].min()} ~ {recent_df['date'].max()}")
        except Exception as e:
            print(f"✗ 失败: {e}")

        # 尝试获取全部数据（按年份）
        print("\n尝试按年份获取完整历史数据...")
        try:
            all_df = fetcher.get_all_data(code)
            if not all_df.empty:
                print(f"\n✓ 总计获取 {len(all_df)} 条数据")
                print(f"  完整范围: {all_df['date'].min()} ~ {all_df['date'].max()}")
                print("\n  数据预览 (前5条):")
                print(all_df.head().to_string(index=False))
                print("\n  数据预览 (后5条):")
                print(all_df.tail().to_string(index=False))
            else:
                print("✗ 未获取到数据")
        except Exception as e:
            print(f"✗ 获取完整数据失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
