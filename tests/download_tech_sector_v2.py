"""
下载科技板块股票数据 - 备用方案
使用stock_zh_a_spot_em获取全市场股票，再筛选科技板块
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import akshare as ak
from datetime import datetime
import time
from data import get_db_manager

# 科技板块关键词（用于筛选）
TECH_KEYWORDS = [
    '科技', '软件', '信息', '电子', '半导体', '芯片', '集成电路',
    '通信', '网络', '互联网', '智能', '人工智能', 'AI', '大数据',
    '云计算', '物联网', '5G', '区块链', '光伏', '新能源', '电池',
    '计算机', '传媒', '游戏', '光电', '光学', '元件', '器件',
    '精密', '显示', '屏幕', '面板', '存储', '设备', '材料'
]

def is_tech_stock(name, industry=None):
    """判断是否为科技股票"""
    if not name:
        return False
    name = str(name)
    for keyword in TECH_KEYWORDS:
        if keyword in name:
            return True
    if industry and any(k in str(industry) for k in TECH_KEYWORDS):
        return True
    return False

def get_all_stocks_with_industry():
    """获取全市场股票及行业信息"""
    print("获取全市场股票列表...")
    try:
        # 获取实时行情（包含行业信息）
        df = ak.stock_zh_a_spot_em()
        print(f"  获取到 {len(df)} 只股票")
        
        # 标准化列名
        df = df.rename(columns={
            '代码': 'symbol',
            '名称': 'name',
            '总市值': 'total_cap',
            '流通市值': 'float_cap',
            '所属行业': 'industry'
        })
        
        # 筛选科技板块
        df['is_tech'] = df.apply(
            lambda x: is_tech_stock(x.get('name', ''), x.get('industry', '')), 
            axis=1
        )
        
        tech_df = df[df['is_tech']].copy()
        print(f"  筛选出 {len(tech_df)} 只科技股票")
        
        return tech_df[['symbol', 'name', 'total_cap', 'float_cap', 'industry']]
    except Exception as e:
        print(f"获取失败: {e}")
        return pd.DataFrame()

def classify_by_market_cap(df):
    """按市值分类"""
    # 总市值转换为亿元
    df['total_cap_亿'] = df['total_cap'] / 100000000
    
    large_cap = df[df['total_cap_亿'] >= 500].copy()  # 大盘 >=500亿
    mid_cap = df[(df['total_cap_亿'] >= 100) & (df['total_cap_亿'] < 500)].copy()  # 中盘
    small_cap = df[df['total_cap_亿'] < 100].copy()  # 小盘
    
    print("\n市值分布:")
    print(f"  大盘股(≥500亿): {len(large_cap)} 只")
    print(f"  中盘股(100-500亿): {len(mid_cap)} 只")
    print(f"  小盘股(<100亿): {len(small_cap)} 只")
    
    return large_cap, mid_cap, small_cap

def download_stockdata(symbol, start_date='2017-01-01', end_date='2024-12-31'):
    """下载单只股票历史数据"""
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            adjust="qfq"
        )
        
        if df is None or df.empty:
            return None
        
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
    except Exception:
        return None

def main():
    print("\n" + "="*70)
    print("📱 科技板块数据下载 (备用方案)")
    print("="*70)
    print(f"开始时间: {datetime.now()}")
    
    # 1. 获取科技股票
    tech_df = get_all_stocks_with_industry()
    
    if tech_df.empty:
        print("❌ 未获取到科技股票")
        return
    
    # 2. 市值分类
    large_cap, mid_cap, small_cap = classify_by_market_cap(tech_df)
    
    # 3. 选择股票：确保大中小市值都有
    # 大盘股：全部
    # 中盘股：全部或最多100只
    # 小盘股：最多50只
    selected_large = large_cap['symbol'].tolist()
    selected_mid = mid_cap['symbol'].tolist()[:min(len(mid_cap), 100)]
    selected_small = small_cap['symbol'].tolist()[:min(len(small_cap), 50)]
    
    selected_stocks = selected_large + selected_mid + selected_small
    
    print(f"\n选定下载: {len(selected_stocks)} 只")
    print(f"  - 大盘股: {len(selected_large)} 只")
    print(f"  - 中盘股: {len(selected_mid)} 只")
    print(f"  - 小盘股: {len(selected_small)} 只")
    
    # 显示一些示例
    print("\n大盘股示例:")
    for _, row in large_cap.head(5).iterrows():
        print(f"  {row['symbol']} {row['name']} ({row['total_cap_亿']:.0f}亿)")
    
    print("\n中盘股示例:")
    for _, row in mid_cap.head(5).iterrows():
        print(f"  {row['symbol']} {row['name']} ({row['total_cap_亿']:.0f}亿)")
    
    print("\n小盘股示例:")
    for _, row in small_cap.head(5).iterrows():
        print(f"  {row['symbol']} {row['name']} ({row['total_cap_亿']:.0f}亿)")
    
    # 4. 下载数据
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
                db_manager.pg.save_marketdata(df)
                print(f"✅ {len(df)} 条")
                success_count += 1
                total_records += len(df)
            except Exception:
                print("❌ 保存失败")
                fail_count += 1
        else:
            print("❌ 无数据")
            fail_count += 1
        
        # 避免请求过快
        time.sleep(0.1)
    
    # 5. 汇总
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
