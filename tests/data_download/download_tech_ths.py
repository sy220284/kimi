"""
下载科技板块股票数据 - 使用同花顺接口
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import json
import re
import time
from datetime import datetime

import pandas as pd
import requests

from data import get_db_manager

# 同花顺科技板块代码
# 可通过 http://q.10jqka.com.cn/gn/detail/code/xxx 查看板块成分股

# 科技相关板块代码（同花顺概念板块）
TECH_SECTORS = {
    '半导体': 'http://q.10jqka.com.cn/gn/detail/code/300199/',
    '芯片概念': 'http://q.10jqka.com.cn/gn/detail/code/300218/',
    '国产软件': 'http://q.10jqka.com.cn/gn/detail/code/300387/',
    '人工智能': 'http://q.10jqka.com.cn/gn/detail/code/300751/',
    '5G概念': 'http://q.10jqka.com.cn/gn/detail/code/300327/',
    '云计算': 'http://q.10jqka.com.cn/gn/detail/code/300377/',
    '大数据': 'http://q.10jqka.com.cn/gn/detail/code/300373/',
    '物联网': 'http://q.10jqka.com.cn/gn/detail/code/300322/',
    '光伏概念': 'http://q.10jqka.com.cn/gn/detail/code/300194/',
    '新能源': 'http://q.10jqka.com.cn/gn/detail/code/300250/',
}

def get_sector_stocks_from_ths(sector_name, sector_url):
    """从同花顺获取板块成分股"""
    try:
        # 从URL中提取code
        code = sector_url.split('/code/')[1].rstrip('/')

        # 同花顺板块成分股API
        api_url = f'http://q.10jqka.com.cn/gn/detail/field/264648/order/desc/page/1/ajax/1/code/{code}'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': sector_url,
            'X-Requested-With': 'XMLHttpRequest'
        }

        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code != 200:
            return []

        # 解析HTML提取股票代码
        html = response.text
        # 股票代码格式: target="_blank">600519</a>
        pattern = r'target="_blank">(\d{6})</a>'
        stocks = list(set(re.findall(pattern, html)))

        return stocks
    except Exception as e:
        print(f"    获取失败: {e}")
        return []

def get_daily_kline_ths(symbol, start_date='20170101', end_date='20241231'):
    """从同花顺获取日线数据"""
    try:
        url = f'http://d.10jqka.com.cn/v4/line/hs_{symbol}/01/{start_date}/{end_date}/last.js'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'http://stockpage.10jqka.com.cn/{symbol}/'
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        # 解析JS数据
        text = response.text
        pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
        match = re.search(pattern, text)

        if not match:
            return None

        data = json.loads(match.group(1))

        if 'data' not in data:
            return None

        # 解析数据
        lines = data['data'].split(';')
        records = []

        for line in lines:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 6:
                try:
                    record = {
                        'date': datetime.strptime(parts[0], '%Y%m%d').strftime('%Y-%m-%d'),
                        'open': float(parts[1]),
                        'high': float(parts[2]),
                        'low': float(parts[3]),
                        'close': float(parts[4]),
                        'volume': int(parts[5]),
                    }
                    if len(parts) >= 7:
                        record['amount'] = float(parts[6])
                    else:
                        record['amount'] = 0
                    records.append(record)
                except Exception:
                    continue

        if not records:
            return None

        df = pd.DataFrame(records)
        df['symbol'] = symbol

        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception:
        return None

def main():
    print("\n" + "="*70)
    print("📱 科技板块数据下载 (同花顺接口)")
    print("="*70)
    print(f"开始时间: {datetime.now()}")

    # 1. 获取科技板块股票列表
    print("\n获取科技板块股票列表...")
    all_stocks = set()

    for sector_name, sector_url in TECH_SECTORS.items():
        print(f"  {sector_name} ...", end=" ", flush=True)
        stocks = get_sector_stocks_from_ths(sector_name, sector_url)
        print(f"{len(stocks)} 只")
        all_stocks.update(stocks)
        time.sleep(0.5)  # 避免请求过快

    print(f"\n共获取到 {len(all_stocks)} 只科技股票（去重后）")

    if not all_stocks:
        print("❌ 未获取到股票列表")
        return

    # 转换为列表并排序
    stock_list = sorted(all_stocks)

    # 2. 下载历史数据
    db_manager = get_db_manager()
    start_date = '20170101'
    end_date = '20241231'

    success_count = 0
    fail_count = 0
    total_records = 0

    print(f"\n开始下载历史数据 ({start_date} ~ {end_date})...")
    print("="*70)

    # 限制下载数量，优先大市值（按代码排序，主板股票在前）
    # 60开头是沪市主板，00开头是深市主板，30开头是创业板，68开头是科创板
    priority_order = [s for s in stock_list if s.startswith('6') or s.startswith('0')]
    priority_order += [s for s in stock_list if s.startswith('3') or s.startswith('68')]

    # 最多下载100只（大中小市值兼顾）
    download_list = priority_order[:100]

    print(f"选定下载: {len(download_list)} 只")

    for i, symbol in enumerate(download_list, 1):
        print(f"[{i}/{len(download_list)}] {symbol} ...", end=" ", flush=True)

        df = get_daily_kline_ths(symbol, start_date, end_date)

        if df is not None and not df.empty:
            try:
                db_manager.pg.save_marketdata(df)
                print(f"✅ {len(df)} 条")
                success_count += 1
                total_records += len(df)
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                fail_count += 1
        else:
            print("❌ 无数据")
            fail_count += 1

        time.sleep(0.2)  # 控制请求频率

    # 3. 汇总
    print("\n" + "="*70)
    print("📊 下载汇总")
    print("="*70)
    print(f"成功: {success_count} 只")
    print(f"失败: {fail_count} 只")
    print(f"总记录: {total_records:,} 条")

    print(f"\n结束时间: {datetime.now()}")
    print("="*70)

if __name__ == '__main__':
    main()
