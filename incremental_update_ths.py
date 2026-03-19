"""
同花顺增量更新 - 每日收盘后更新数据库
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from data import get_db_manager


def get_last_trading_day():
    """获取最近交易日（考虑周末）"""
    today = datetime.now()
    # 如果今天是周末，回退到周五
    if today.weekday() == 5:  # 周六
        return today - timedelta(days=1)
    elif today.weekday() == 6:  # 周日
        return today - timedelta(days=2)
    return today


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

        # 解析JSONP格式: quote_xxxx({"data":"..."})
        text = response.text
        match = re.search(r'quote_\w+\(({.+})\);?$', text, re.DOTALL)

        if not match:
            return None

        data = match.group(1)
        json_data = eval(data.replace('null', 'None').replace('true', 'True').replace('false', 'False'))

        if 'data' not in json_data or not json_data['data']:
            return None

        # 解析数据: "日期,开盘价,最高价,最低价,收盘价,成交量,成交额"
        lines = json_data['data'].split(';')
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
        print(f"  获取 {symbol} 失败: {e}")
        return None


def incremental_update(symbols=None, days_back=5):
    """
    增量更新数据库

    Args:
        symbols: 股票列表，None则更新数据库中所有已有股票
        days_back: 往回检查多少天
    """
    db = get_db_manager()

    # 1. 检查数据库最后日期
    result = db.pg.execute('SELECT MAX(date) as last_date FROM market_data', fetch=True)
    last_date = result[0]['last_date']
    print(f"📊 数据库最后日期: {last_date}")

    # 2. 确定更新范围
    today = get_last_trading_day().date()

    if last_date >= today:
        print(f"✅ 数据已是最新 (今天: {today})")
        return {'updated': 0, 'symbols': 0}

    start_date = (last_date + timedelta(days=1)).strftime('%Y%m%d')
    end_date = today.strftime('%Y%m%d')

    print(f"📅 更新范围: {start_date} ~ {end_date}")

    # 3. 获取股票列表
    if symbols is None:
        result = db.pg.execute('SELECT DISTINCT symbol FROM market_data', fetch=True)
        symbols = [r['symbol'] for r in result]

    print(f"🔄 准备更新 {len(symbols)} 只股票")

    # 4. 逐只更新
    updated_count = 0
    new_records = 0
    failed_symbols = []

    for i, symbol in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}] {symbol} ...", end=" ", flush=True)

        try:
            # 获取数据
            df = get_daily_kline_ths(symbol, start_date, end_date)

            if df is None or df.empty:
                print("无新数据")
                time.sleep(0.3)  # 防封
                continue

            # 添加到数据库
            df['symbol'] = symbol

            for _, row in df.iterrows():
                sql = """INSERT INTO market_data (symbol, date, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        amount = EXCLUDED.amount"""
                db.pg.execute(sql, (
                    row['symbol'], row['date'], row['open'], row['high'],
                    row['low'], row['close'], row['volume'], row['amount']
                ))

            new_records += len(df)
            updated_count += 1
            print(f"✅ +{len(df)}条")

            # 进度更新
            if i % 10 == 0:
                progress = int((i / len(symbols)) * 100)
                print(f"\n📈 进度: {progress}% ({i}/{len(symbols)})")

            time.sleep(0.3)  # 防封

        except Exception as e:
            print(f"❌ 失败: {e}")
            failed_symbols.append(symbol)
            time.sleep(1)  # 出错后多等一下

    # 5. 汇总
    print(f"\\n{'='*50}")
    print("✅ 增量更新完成")
    print(f"{'='*50}")
    print(f"更新股票: {updated_count}/{len(symbols)}")
    print(f"新增记录: {new_records} 条")
    print(f"失败: {len(failed_symbols)} 只")

    if failed_symbols:
        print(f"失败列表: {', '.join(failed_symbols[:10])}{'...' if len(failed_symbols) > 10 else ''}")

    return {
        'updated': updated_count,
        'symbols': len(symbols),
        'new_records': new_records,
        'failed': failed_symbols
    }


def test_update():
    """测试更新 - 只更新几只股票"""
    db = get_db_manager()
    result = db.pg.execute("""
        SELECT symbol FROM (
            SELECT DISTINCT symbol FROM market_data
        ) t
        ORDER BY RANDOM()
        LIMIT 5
    """, fetch=True)
    test_symbols = [r['symbol'] for r in result]

    print("🧪 测试模式 - 更新5只股票")
    return incremental_update(test_symbols)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='同花顺增量更新')
    parser.add_argument('--test', action='store_true', help='测试模式（只更新5只）')
    parser.add_argument('--symbols', nargs='+', help='指定股票代码')
    args = parser.parse_args()

    if args.test:
        test_update()
    elif args.symbols:
        incremental_update(args.symbols)
    else:
        # 完整更新
        incremental_update()
