"""
下载科技板块股票数据 - 直接下载指定股票
大中小市值兼顾的科技龙头股
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import requests
import json
import re
from datetime import datetime
import time
from data import get_db_manager

# 科技股列表 - 大中小市值兼顾
TECH_STOCKS = {
    # 大盘股 (市值 > 1000亿)
    'large_cap': [
        '000063',  # 中兴通讯
        '002230',  # 科大讯飞
        '300750',  # 宁德时代
        '600584',  # 长电科技
        '603501',  # 韦尔股份
        '688981',  # 中芯国际
        '688012',  # 中微公司
        '688008',  # 澜起科技
        '000938',  # 紫光股份
        '600570',  # 恒生电子
    ],
    # 中盘股 (市值 300-1000亿)
    'mid_cap': [
        '002371',  # 北方华创
        '300014',  # 亿纬锂能
        '300124',  # 汇川技术
        '300433',  # 蓝思科技
        '300408',  # 三环集团
        '603019',  # 中科曙光
        '603893',  # 瑞芯微
        '688111',  # 金山办公
        '688126',  # 沪硅产业
        '688599',  # 天合光能
        '300496',  # 中科创达
        '300661',  # 圣邦股份
        '300782',  # 卓胜微
        '600460',  # 士兰微
        '600703',  # 三安光电
    ],
    # 小盘股 (市值 < 300亿) - 科技成长股
    'small_cap': [
        '300474',  # 景嘉微
        '300223',  # 北京君正
        '300373',  # 扬杰科技
        '300666',  # 江丰电子
        '300724',  # 捷佳伟创
        '688002',  # 睿创微纳
        '688009',  # 中国通号
        '688188',  # 柏楚电子
        '688256',  # 寒武纪
        '688390',  # 固德威
        '688396',  # 华润微
        '688521',  # 芯原股份
        '688561',  # 奇安信
        '688599',  # 天合光能 (重复，用其他替换)
        '688728',  # 格科微
    ],
}

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
                except:
                    continue
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        df['symbol'] = symbol
        
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        return None

def main():
    print("\n" + "="*70)
    print("📱 科技板块数据下载 - 指定股票")
    print("="*70)
    print(f"开始时间: {datetime.now()}")
    
    # 合并所有股票
    all_stocks = []
    all_stocks.extend(TECH_STOCKS['large_cap'])
    all_stocks.extend(TECH_STOCKS['mid_cap'])
    all_stocks.extend(TECH_STOCKS['small_cap'])
    
    # 去重
    all_stocks = list(set(all_stocks))
    
    print(f"\n股票列表:")
    print(f"  大盘股: {len(TECH_STOCKS['large_cap'])} 只")
    print(f"  中盘股: {len(TECH_STOCKS['mid_cap'])} 只")
    print(f"  小盘股: {len(TECH_STOCKS['small_cap'])} 只")
    print(f"  总计: {len(all_stocks)} 只")
    
    # 下载数据
    db_manager = get_db_manager()
    start_date = '20170101'
    end_date = '20241231'
    
    success_count = 0
    fail_count = 0
    total_records = 0
    
    large_success = 0
    mid_success = 0
    small_success = 0
    
    print(f"\n开始下载历史数据 ({start_date} ~ {end_date})...")
    print("="*70)
    
    for i, symbol in enumerate(all_stocks, 1):
        print(f"[{i}/{len(all_stocks)}] {symbol} ...", end=" ", flush=True)
        
        df = get_daily_kline_ths(symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            try:
                records = db_manager.pg.save_market_data(df)
                print(f"✅ {len(df)} 条")
                success_count += 1
                total_records += len(df)
                
                # 统计分类
                if symbol in TECH_STOCKS['large_cap']:
                    large_success += 1
                elif symbol in TECH_STOCKS['mid_cap']:
                    mid_success += 1
                else:
                    small_success += 1
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                fail_count += 1
        else:
            print("❌ 无数据")
            fail_count += 1
        
        time.sleep(0.15)  # 控制请求频率
    
    # 汇总
    print("\n" + "="*70)
    print("📊 下载汇总")
    print("="*70)
    print(f"成功: {success_count} 只 | 失败: {fail_count} 只")
    print(f"总记录: {total_records:,} 条")
    print()
    print(f"市值分布:")
    print(f"  大盘股: {large_success}/{len(TECH_STOCKS['large_cap'])} 只")
    print(f"  中盘股: {mid_success}/{len(TECH_STOCKS['mid_cap'])} 只")
    print(f"  小盘股: {small_success}/{len(TECH_STOCKS['small_cap'])} 只")
    
    # 查询数据库中的科技股
    try:
        result = db_manager.pg.execute("""
            SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as records
            FROM market_data 
            WHERE symbol IN %s
            GROUP BY symbol
            ORDER BY records DESC
        """, (tuple(all_stocks),), fetch=True)
        
        if result:
            df_db = pd.DataFrame(result)
            print(f"\n数据库中科技板块股票: {len(df_db)} 只")
            print(f"总记录数: {df_db['records'].sum():,} 条")
    except Exception as e:
        print(f"查询数据库失败: {e}")
    
    print(f"\n结束时间: {datetime.now()}")
    print("="*70)

if __name__ == '__main__':
    main()
