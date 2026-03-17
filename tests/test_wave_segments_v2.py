#!/usr/bin/env python3
"""
深度分析: B浪和1浪的真实表现 (修复版)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
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
    FROM market_data
    WHERE symbol = %s AND date >= %s AND date <= %s
    ORDER BY date
    '''
    df = pd.read_sql(sql, conn, params=(symbol, start_date, end_date))
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df

def analyze_stock_waves(symbol):
    """分析单只股票的波浪段落"""
    df = get_stock_data(symbol, '2018-01-01', '2026-03-16')
    if len(df) < 100:
        return []
    
    all_segments = []
    
    # 滑动窗口分析
    for start_idx in range(0, len(df) - 120, 60):
        window_df = df.iloc[start_idx:start_idx+120].copy().reset_index(drop=True)
        
        # 检测极值点
        pivots = enhanced_pivot_detection(window_df, atr_period=10, atr_mult=0.5, min_pivots=4)
        
        if len(pivots) < 4:
            continue
        
        for i in range(len(pivots) - 2):
            p1 = pivots[i]
            p2 = pivots[i+1]
            
            # 获取实际日期
            p1_date = window_df.iloc[p1.idx]['date'] if p1.idx < len(window_df) else None
            p2_date = window_df.iloc[p2.idx]['date'] if p2.idx < len(window_df) else None
            
            if p1_date is None or p2_date is None:
                continue
            
            price_change = abs(p2.price - p1.price)
            price_change_pct = price_change / p1.price * 100
            duration = (p2_date - p1_date).days
            direction_up = p2.price > p1.price
            
            # 判断可能的浪型
            possible_waves = []
            
            # A浪: 调整开始，幅度>5%
            if price_change_pct > 5:
                possible_waves.append('A')
            
            # B浪: 反弹，幅度为前一段的20%-100%
            if i > 0:
                prev_change = abs(p1.price - pivots[i-1].price)
                if prev_change > 0:
                    bounce_ratio = price_change / prev_change
                    if 0.2 <= bounce_ratio <= 1.0 and price_change_pct > 2:
                        possible_waves.append('B')
            
            # 1浪: 推动开始，幅度>3%，持续时间≥2天
            if price_change_pct > 3 and duration >= 2:
                possible_waves.append('1')
            
            # 2浪: 回撤，幅度为前一段的30%-70%
            if i > 0 and price_change_pct < 10:
                prev_change = abs(p1.price - pivots[i-1].price)
                if prev_change > 0:
                    retrace_ratio = price_change / prev_change
                    if 0.3 <= retrace_ratio <= 0.7:
                        possible_waves.append('2')
            
            # 计算后续走势
            future_returns = {}
            if p2.idx + 20 < len(window_df):
                p2_price = p2.price
                for days in [5, 10, 20]:
                    future_price = window_df.iloc[p2.idx + days]['close']
                    future_ret = (future_price - p2_price) / p2_price * 100
                    future_returns[f'future_{days}d'] = future_ret
            
            segment = {
                'symbol': symbol,
                'start_date': p1_date.strftime('%Y-%m-%d'),
                'end_date': p2_date.strftime('%Y-%m-%d'),
                'start_price': p1.price,
                'end_price': p2.price,
                'price_change_pct': price_change_pct if direction_up else -price_change_pct,
                'abs_change_pct': price_change_pct,
                'duration': duration,
                'direction': 'up' if direction_up else 'down',
                'possible_waves': ','.join(possible_waves) if possible_waves else '',
                **future_returns
            }
            
            all_segments.append(segment)
    
    return all_segments

def print_wave_stats(name, df, wave_type):
    """打印浪型统计"""
    wave_df = df[df['possible_waves'].str.contains(wave_type, na=False)]
    
    print(f"\n【{name}】样本数: {len(wave_df)}")
    if len(wave_df) == 0:
        return wave_df
    
    print(f"  平均持续时间: {wave_df['duration'].mean():.1f}天 (中位数{wave_df['duration'].median():.1f})")
    print(f"  平均价格变动: {wave_df['abs_change_pct'].mean():.2f}%")
    print(f"  价格变动范围: {wave_df['abs_change_pct'].min():.1f}% ~ {wave_df['abs_change_pct'].max():.1f}%")
    
    # 持续时间分布
    print(f"  持续时间分布:")
    print(f"    <3天: {(wave_df['duration'] < 3).sum()} ({(wave_df['duration'] < 3).mean()*100:.1f}%)")
    print(f"    3-7天: {((wave_df['duration'] >= 3) & (wave_df['duration'] < 7)).sum()}")
    print(f"    7-15天: {((wave_df['duration'] >= 7) & (wave_df['duration'] < 15)).sum()}")
    print(f"    15-30天: {((wave_df['duration'] >= 15) & (wave_df['duration'] < 30)).sum()}")
    print(f"    >30天: {(wave_df['duration'] >= 30).sum()}")
    
    # 后续表现
    for days in [5, 10, 20]:
        col = f'future_{days}d'
        if col in wave_df.columns:
            valid = wave_df[col].dropna()
            if len(valid) > 0:
                win_rate = (valid > 0).mean() * 100
                avg_ret = valid.mean()
                print(f"  {days}天后: 胜率{win_rate:.1f}%, 平均收益{avg_ret:+.2f}% (n={len(valid)})")
    
    return wave_df

def main():
    print("=" * 90)
    print("B浪和1浪深度分析 (修复版)")
    print("=" * 90)
    
    # 获取股票列表
    conn = get_db_connection()
    sql = '''
    SELECT symbol, COUNT(*) as records
    FROM market_data 
    WHERE date >= '2018-01-01'
    GROUP BY symbol
    HAVING COUNT(*) >= 500
    ORDER BY COUNT(*) DESC
    LIMIT 30
    '''
    stock_df = pd.read_sql(sql, conn)
    conn.close()
    
    symbols = stock_df['symbol'].tolist()
    print(f"分析股票: {len(symbols)} 只\n")
    
    all_segments = []
    
    for idx, symbol in enumerate(symbols, 1):
        segments = analyze_stock_waves(symbol)
        all_segments.extend(segments)
        if idx % 5 == 0:
            print(f"  已完成 {idx}/{len(symbols)} 只, 累计 {len(all_segments)} 个段落")
    
    print(f"\n✓ 共分析 {len(all_segments)} 个波浪段落")
    
    # 转换为DataFrame
    df = pd.DataFrame(all_segments)
    
    print("\n" + "=" * 90)
    print("分析结果")
    print("=" * 90)
    
    # 各浪型分析
    b_df = print_wave_stats("B浪", df, 'B')
    w1_df = print_wave_stats("1浪", df, '1')
    a_df = print_wave_stats("A浪", df, 'A')
    w2_df = print_wave_stats("2浪", df, '2')
    
    # 保存数据
    output_file = 'tests/results/wave_segments_v2.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n💾 详细数据已保存: {output_file}")
    
    # 关键发现
    print("\n" + "=" * 90)
    print("关键发现")
    print("=" * 90)
    
    if len(b_df) > 0:
        print(f"\nB浪特征:")
        print(f"  - 平均持续{b_df['duration'].mean():.1f}天，但分布很散")
        print(f"  - 反弹幅度{b_df['abs_change_pct'].mean():.1f}%±{b_df['abs_change_pct'].std():.1f}%")
        short_b = (b_df['duration'] < 3).sum()
        print(f"  - 有{short_b}个B浪(<3天)占比{short_b/len(b_df)*100:.1f}%，原验证条件(≥3天)会过滤掉")
    
    if len(w1_df) > 0:
        print(f"\n1浪特征:")
        print(f"  - 平均持续{w1_df['duration'].mean():.1f}天")
        short_1 = (w1_df['duration'] < 3).sum()
        print(f"  - 有{short_1}个1浪(<3天)占比{short_1/len(w1_df)*100:.1f}%")
    
    print("\n" + "=" * 90)
    print("分析完成")
    print("=" * 90)

if __name__ == '__main__':
    main()
