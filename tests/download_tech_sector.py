"""
下载科技板块股票数据
申万一级行业: 电子、计算机、通信、传媒
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import akshare as ak
from datetime import datetime
from data import get_db_manager

def get_sw_industry_stocks(industry_code, industry_name):
    """获取申万行业成分股"""
    try:
        # 使用akshare获取申万行业成分股
        df = ak.index_stock_sw(industry_name, symbol=industry_code)
        if df is not None and not df.empty:
            return df['股票代码'].tolist()
    except Exception as e:
        print(f"  获取{industry_name}成分股失败: {e}")
    return []

def get_tech_sector_stocks():
    """获取科技板块股票列表（大中小市值兼顾）"""
    
    # 申万一级行业 - 科技相关
    tech_industries = {
        '801080': '电子',      # 半导体、消费电子等
        '801750': '计算机',    # 软件、IT服务等
        '801770': '通信',      # 通信设备、运营商等
        '801760': '传媒',      # 游戏、影视等
    }
    
    all_stocks = []
    
    print("="*60)
    print("获取科技板块股票列表")
    print("="*60)
    
    for code, name in tech_industries.items():
        print(f"\n获取 {name}({code}) 成分股...")
        try:
            # 使用akshare的stock_board_industry_cons_em获取行业成分股
            df = ak.stock_board_industry_cons_em(symbol=name)
            if df is not None and not df.empty:
                stocks = df['代码'].tolist()
                print(f"  获取到 {len(stocks)} 只股票")
                all_stocks.extend([(s, name) for s in stocks])
            else:
                print("  未获取到数据")
        except Exception as e:
            print(f"  获取失败: {e}")
    
    # 去重
    unique_stocks = list(set([s[0] for s in all_stocks]))
    print(f"\n共获取到 {len(unique_stocks)} 只科技板块股票（去重后）")
    
    return unique_stocks

def get_stock_market_cap(symbols):
    """获取股票市值信息，用于分类大中小市值"""
    print("\n获取股票市值信息...")
    try:
        df = ak.stock_zh_a_spot_em()
        df = df[['代码', '名称', '总市值', '流通市值']].copy()
        df = df[df['代码'].isin(symbols)]
        
        # 总市值转换为亿元
        df['总市值_亿'] = df['总市值'] / 100000000
        
        # 分类
        large_cap = df[df['总市值_亿'] >= 500]['代码'].tolist()  # 大盘 >=500亿
        mid_cap = df[(df['总市值_亿'] >= 100) & (df['总市值_亿'] < 500)]['代码'].tolist()  # 中盘 100-500亿
        small_cap = df[df['总市值_亿'] < 100]['代码'].tolist()  # 小盘 <100亿
        
        print(f"  大盘股(≥500亿): {len(large_cap)} 只")
        print(f"  中盘股(100-500亿): {len(mid_cap)} 只")
        print(f"  小盘股(<100亿): {len(small_cap)} 只")
        
        return {
            'large': large_cap,
            'mid': mid_cap,
            'small': small_cap,
            'all': df
        }
    except Exception as e:
        print(f"  获取市值失败: {e}")
        return {'large': [], 'mid': [], 'small': [], 'all': pd.DataFrame()}

def download_stockdata(symbol, start_date='2017-01-01', end_date='2024-12-31'):
    """下载单只股票历史数据"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            adjust="qfq"  # 前复权
        )
        
        if df is None or df.empty:
            return None
        
        # 标准化列名
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount'
        })
        
        df['symbol'] = symbol
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        return df[['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    except Exception as e:
        print(f"    下载失败: {e}")
        return None

def main():
    print("\n" + "="*70)
    print("📱 科技板块数据下载")
    print("="*70)
    print(f"开始时间: {datetime.now()}")
    
    # 1. 获取科技板块股票列表
    tech_stocks = get_tech_sector_stocks()
    
    if not tech_stocks:
        print("❌ 未获取到科技板块股票")
        return
    
    # 2. 获取市值分类
    market_cap = get_stock_market_cap(tech_stocks)
    
    # 选择股票：大中小市值各选一部分
    # 大盘股：全部
    # 中盘股：全部
    # 小盘股：选前50只（避免太多数据）
    selected_stocks = []
    selected_stocks.extend(market_cap['large'])
    selected_stocks.extend(market_cap['mid'])
    selected_stocks.extend(market_cap['small'][:50])  # 小盘取前50
    
    print(f"\n选定下载股票: {len(selected_stocks)} 只")
    print(f"  - 大盘股: {len(market_cap['large'])} 只")
    print(f"  - 中盘股: {len(market_cap['mid'])} 只")
    print(f"  - 小盘股: {min(50, len(market_cap['small']))} 只 (前50)")
    
    # 3. 下载数据
    db_manager = get_db_manager()
    start_date = '2017-01-01'
    end_date = '2024-12-31'
    
    success_count = 0
    fail_count = 0
    total_records = 0
    
    print(f"\n开始下载历史数据 ({start_date} ~ {end_date})...")
    print("="*70)
    
    for i, symbol in enumerate(selected_stocks, 1):
        print(f"[{i}/{len(selected_stocks)}] {symbol} ...", end=" ", flush=True)
        
        df = download_stockdata(symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            try:
                # 保存到数据库
                db_manager.pg.save_marketdata(df)
                print(f"✅ {len(df)} 条记录")
                success_count += 1
                total_records += len(df)
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                fail_count += 1
        else:
            print("❌ 无数据")
            fail_count += 1
    
    # 4. 汇总
    print("\n" + "="*70)
    print("📊 下载汇总")
    print("="*70)
    print(f"成功: {success_count} 只")
    print(f"失败: {fail_count} 只")
    print(f"总记录: {total_records:,} 条")
    
    # 显示数据库中的科技板块股票
    try:
        result = db_manager.pg.execute("""
            SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as records
            FROM marketdata 
            WHERE symbol IN %s
            GROUP BY symbol
        """, (tuple(selected_stocks),), fetch=True)
        
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
