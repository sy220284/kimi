#!/usr/bin/env python3
"""
深度分析: B浪和1浪的真实表现
扩大样本范围，分析历史数据中B浪和1浪的特征
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import psycopg2
from datetime import datetime

from src.analysis.wave.enhanced_detector import enhanced_pivot_detection

def get_db_connection():
    return psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )

def get_stock_data(symbol, start_date, end_date):
    conn = get_db_connection()
    sql = '''
    SELECT date, open, high, low, close, volume, amount
    FROM marketdata
    WHERE symbol = %s AND date >= %s AND date <= %s
    ORDER BY date
    '''
    df = pd.read_sql(sql, conn, params=(symbol, start_date, end_date))
    conn.close()
    return df

def analyze_wave_segments(df):
    """
    分析完整的波浪段落
    返回识别出的A/B/C和1/2/3/4/5浪段
    """
    # 检测极值点
    pivots = enhanced_pivot_detection(df, atr_period=10, atr_mult=0.5, minpivots=4)
    
    if len(pivots) < 4:
        return []
    
    segments = []
    
    for i in range(len(pivots) - 2):
        p1 = pivots[i]
        p2 = pivots[i+1]
        p3 = pivots[i+2]
        
        price_change = abs(p2.price - p1.price)
        price_change_pct = price_change / p1.price * 100
        
        try:
            d1 = datetime.strptime(str(p1.date)[:10], '%Y-%m-%d')
            d2 = datetime.strptime(str(p2.date)[:10], '%Y-%m-%d')
            duration = (d2 - d1).days
        except Exception:
            duration = 0
        
        # 判断方向
        direction_up = p2.price > p1.price
        
        # 判断可能的浪型
        possible_waves = []
        
        # A浪特征: 调整开始，幅度较大
        if price_change_pct > 5:
            possible_waves.append('A')
        
        # B浪特征: 反弹，幅度为前一段的30%-80%
        if i > 0:
            prev_change = abs(p1.price - pivots[i-1].price)
            if prev_change > 0:
                bounce_ratio = price_change / prev_change
                if 0.2 <= bounce_ratio <= 1.0:
                    possible_waves.append('B')
        
        # 1浪特征: 推动开始，从低位启动
        if price_change_pct > 3 and duration >= 2:
            if i == 0 or (direction_up and p1.price > pivots[i-1].price) or (not direction_up and p1.price < pivots[i-1].price):
                possible_waves.append('1')
        
        # 2浪特征: 回撤，幅度为前一段的30%-70%
        if i > 0 and price_change_pct < 10:
            prev_change = abs(p1.price - pivots[i-1].price)
            if prev_change > 0:
                retrace_ratio = price_change / prev_change
                if 0.3 <= retrace_ratio <= 0.7:
                    possible_waves.append('2')
        
        segment = {
            'start_date': p1.date,
            'end_date': p2.date,
            'start_price': p1.price,
            'end_price': p2.price,
            'price_change_pct': price_change_pct if direction_up else -price_change_pct,
            'abs_change_pct': price_change_pct,
            'duration': duration,
            'direction': 'up' if direction_up else 'down',
            'possible_waves': possible_waves,
        }
        
        # 计算后续走势
        p2_idx = df[df['date'] == p2.date].index[0] if len(df[df['date'] == p2.date]) > 0 else -1
        if p2_idx >= 0 and p2_idx + 20 < len(df):
            future_5d = (df.iloc[p2_idx + 5]['close'] - p2.price) / p2.price * 100
            future_10d = (df.iloc[p2_idx + 10]['close'] - p2.price) / p2.price * 100
            future_20d = (df.iloc[p2_idx + 20]['close'] - p2.price) / p2.price * 100
            segment['future_5d'] = future_5d
            segment['future_10d'] = future_10d
            segment['future_20d'] = future_20d
        
        segments.append(segment)
    
    return segments

def main():
    print("=" * 90)
    print("B浪和1浪深度分析")
    print("=" * 90)
    
    # 扩大样本 - 分析更多股票和更长时间
    conn = get_db_connection()
    sql = '''
    SELECT symbol, COUNT(*) as records
    FROM marketdata 
    WHERE date >= '2018-01-01'
    GROUP BY symbol
    HAVING COUNT(*) >= 500
    ORDER BY COUNT(*) DESC
    LIMIT 30
    '''
    stock_df = pd.read_sql(sql, conn)
    conn.close()
    
    symbols = stock_df['symbol'].tolist()
    print(f"分析股票: {len(symbols)} 只")
    print(f"股票列表: {', '.join(symbols[:10])}...")
    
    all_b_waves = []
    all_wave1 = []
    all_segments = []
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}] 分析 {symbol}...")
        
        df = get_stock_data(symbol, '2018-01-01', '2026-03-16')
        if len(df) < 100:
            continue
        
        # 分段分析
        for i in range(0, len(df) - 120, 60):
            window_df = df.iloc[i:i+120].copy()
            segments = analyze_wave_segments(window_df)
            
            for seg in segments:
                seg['symbol'] = symbol
                all_segments.append(seg)
                
                if 'B' in seg['possible_waves']:
                    all_b_waves.append(seg)
                if '1' in seg['possible_waves']:
                    all_wave1.append(seg)
    
    print("\n" + "=" * 90)
    print("分析结果")
    print("=" * 90)
    
    # B浪分析
    print(f"\n【B浪分析】样本数: {len(all_b_waves)}")
    if all_b_waves:
        b_df = pd.DataFrame(all_b_waves)
        print(f"  平均持续时间: {b_df['duration'].mean():.1f}天")
        print(f"  平均价格变动: {b_df['abs_change_pct'].mean():.2f}%")
        print("  持续时间分布:")
        print(f"    <5天: {(b_df['duration'] < 5).sum()} ({(b_df['duration'] < 5).mean()*100:.1f}%)")
        print(f"    5-10天: {((b_df['duration'] >= 5) & (b_df['duration'] < 10)).sum()}")
        print(f"    10-20天: {((b_df['duration'] >= 10) & (b_df['duration'] < 20)).sum()}")
        print(f"    >20天: {(b_df['duration'] >= 20).sum()}")
        
        # B浪后续表现
        if 'future_5d' in b_df.columns:
            valid = b_df['future_5d'].dropna()
            if len(valid) > 0:
                print("\n  B浪结束后5天:")
                print(f"    胜率: {(valid > 0).mean()*100:.1f}%")
                print(f"    平均收益: {valid.mean():.2f}%")
    
    # 1浪分析
    print(f"\n【1浪分析】样本数: {len(all_wave1)}")
    if all_wave1:
        w1_df = pd.DataFrame(all_wave1)
        print(f"  平均持续时间: {w1_df['duration'].mean():.1f}天")
        print(f"  平均价格变动: {w1_df['abs_change_pct'].mean():.2f}%")
        print("  持续时间分布:")
        print(f"    <3天: {(w1_df['duration'] < 3).sum()} ({(w1_df['duration'] < 3).mean()*100:.1f}%)")
        print(f"    3-5天: {((w1_df['duration'] >= 3) & (w1_df['duration'] < 5)).sum()}")
        print(f"    5-10天: {((w1_df['duration'] >= 5) & (w1_df['duration'] < 10)).sum()}")
        print(f"    >10天: {(w1_df['duration'] >= 10).sum()}")
        
        # 1浪后续表现
        if 'future_5d' in w1_df.columns:
            valid = w1_df['future_5d'].dropna()
            if len(valid) > 0:
                print("\n  1浪结束后5天:")
                print(f"    胜率: {(valid > 0).mean()*100:.1f}%")
                print(f"    平均收益: {valid.mean():.2f}%")
    
    # 保存详细数据
    if all_segments:
        segments_df = pd.DataFrame(all_segments)
        output_file = 'tests/results/wave_segments_deep_analysis.csv'
        segments_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 详细数据已保存: {output_file}")
    
    print("\n" + "=" * 90)
    print("分析完成")
    print("=" * 90)

if __name__ == '__main__':
    main()
