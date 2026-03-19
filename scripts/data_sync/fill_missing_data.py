"""
补全昨日数据 - 使用同花顺接口
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import json
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from data import get_db_manager


def get_daily_kline_ths(symbol, start_date, end_date):
    """从同花顺获取日线数据"""
    try:
        url = f'http://d.10jqka.com.cn/v4/line/hs_{symbol}/01/{start_date}/{end_date}/last.js'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': f'http://stockpage.10jqka.com.cn/{symbol}/'
        }

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            return None

        # 解析JSONP格式: quotebridge_v4_line_xxx({"data":"..."})
        text = response.text
        pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
        match = re.search(pattern, text)

        if not match:
            return None

        data = json.loads(match.group(1))

        if 'data' not in data or not data['data']:
            return None

        # 解析数据
        lines = data['data'].split(';')
        records = []

        for line in lines:
            if not line:
                continue
            parts = line.split(',')
            if len(parts) >= 5:
                records.append({
                    'date': f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]}",
                    'open': float(parts[1]),
                    'high': float(parts[2]),
                    'low': float(parts[3]),
                    'close': float(parts[4]),
                    'volume': int(parts[5]) if len(parts) > 5 else 0,
                    'amount': float(parts[6]) if len(parts) > 6 else 0
                })

        return pd.DataFrame(records)

    except Exception as e:
        return None


def fill_missing_date(target_date='2026-03-18'):
    """
    补全指定日期的缺失数据
    """
    db = get_db_manager()

    print(f'📊 补全 {target_date} 的数据...\n')

    # 1. 找出缺失该日期的股票
    all_stocks = db.pg.execute('SELECT DISTINCT symbol FROM market_data', fetch=True)
    all_symbols = [r['symbol'] for r in all_stocks]

    existing = db.pg.execute(
        "SELECT symbol FROM market_data WHERE date = %s",
        (target_date,), fetch=True
    )
    existing_symbols = {r['symbol'] for r in existing}

    missing_symbols = [s for s in all_symbols if s not in existing_symbols]

    print(f'数据库总股票: {len(all_symbols)} 只')
    print(f'{target_date} 已有数据: {len(existing_symbols)} 只')
    print(f'需要补全: {len(missing_symbols)} 只\n')

    if not missing_symbols:
        print('✅ 无需补全')
        return {'filled': 0, 'failed': []}

    # 2. 逐只补全
    filled_count = 0
    failed_symbols = []

    # 日期范围：前一天到后一天，确保能抓到目标日期
    start_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y%m%d')
    end_date = (datetime.strptime(target_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y%m%d')

    for i, symbol in enumerate(missing_symbols, 1):
        print(f'[{i}/{len(missing_symbols)}] {symbol} ...', end=' ', flush=True)

        try:
            df = get_daily_kline_ths(symbol, start_date, end_date)

            if df is None or df.empty:
                print('❌ 无数据')
                failed_symbols.append(symbol)
                time.sleep(0.3)
                continue

            # 筛选目标日期的数据
            target_data = df[df['date'] == target_date]

            if target_data.empty:
                print('❌ 无该日期数据')
                failed_symbols.append(symbol)
                time.sleep(0.3)
                continue

            # 插入数据库
            row = target_data.iloc[0]
            sql = """INSERT INTO market_data (symbol, date, open, high, low, close, volume, amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, date) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                    close = EXCLUDED.close, volume = EXCLUDED.volume, amount = EXCLUDED.amount"""

            db.pg.execute(sql, (
                symbol, row['date'], row['open'], row['high'],
                row['low'], row['close'], row['volume'], row['amount']
            ))

            filled_count += 1
            print(f'✅ 收盘{row["close"]:.2f}')

            # 进度汇报
            if i % 50 == 0:
                progress = int((i / len(missing_symbols)) * 100)
                print(f'\n📈 进度: {progress}% ({i}/{len(missing_symbols)})\n')

            time.sleep(0.3)

        except Exception as e:
            print(f'❌ 失败: {e}')
            failed_symbols.append(symbol)
            time.sleep(1)

    # 汇总
    print(f'\n{"="*60}')
    print(f'✅ 补全完成: {target_date}')
    print(f'{"="*60}')
    print(f'成功补全: {filled_count}/{len(missing_symbols)} 只')
    print(f'失败: {len(failed_symbols)} 只')

    if failed_symbols:
        print(f'\n失败列表前20: {failed_symbols[:20]}')

    return {
        'filled': filled_count,
        'total': len(missing_symbols),
        'failed': failed_symbols
    }


if __name__ == '__main__':
    # 默认补昨天
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    fill_missing_date(yesterday)
