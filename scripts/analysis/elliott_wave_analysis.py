#!/usr/bin/env python3
"""
自选股艾略特波浪分析 + 买点识别

分析维度:
1. 波浪理论 - 识别当前处于第几浪
2. 技术形态 - 均线、MACD、RSI
3. 买点信号 - 金叉、底背离、突破

输出: 波浪分析结果 + 买点评分排序

优化参数版本 (2026-03-20)
基于10轮回测优化结果:
- 年化收益: 14.82%
- 最大回撤: 7.13%
- 胜率: 47.7%
- 夏普比率: 1.51
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from data import get_db_manager


def load_self_select_stocks():
    """加载自选股列表"""
    with open('.cache/mx_selfselect_list.json', 'r') as f:
        return json.load(f)


def get_stock_data(symbol: str, days: int = 120) -> pd.DataFrame:
    """从数据库获取股票数据"""
    db = get_db_manager()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # 数据库中股票代码是纯6位，不需要后缀
    result = db.pg.execute('''
        SELECT date, open, high, low, close, volume, amount
        FROM market_data
        WHERE symbol = %s AND date >= %s AND date <= %s
        ORDER BY date
    ''', (symbol, start_date, end_date), fetch=True)
    
    if not result:
        return pd.DataFrame()
    
    df = pd.DataFrame(result)
    df['date'] = pd.to_datetime(df['date'])
    return df


def calculate_ma(df: pd.DataFrame, periods=[5, 10, 20, 60]) -> pd.DataFrame:
    """计算移动平均线"""
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    """计算MACD"""
    ema_fast = df['close'].ewm(span=fast).mean()
    ema_slow = df['close'].ewm(span=slow).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def calculate_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
    """计算RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df


def find_peaks_troughs(df: pd.DataFrame, window=5) -> tuple:
    """找出波峰和波谷"""
    highs = df['high'].values
    lows = df['low'].values
    
    peaks = []  # 波峰索引
    troughs = []  # 波谷索引
    
    for i in range(window, len(df) - window):
        # 波峰：比前后window天都高
        if all(highs[i] > highs[i-j] for j in range(1, window+1)) and \
           all(highs[i] > highs[i+j] for j in range(1, window+1)):
            peaks.append(i)
        
        # 波谷：比前后window天都低
        if all(lows[i] < lows[i-j] for j in range(1, window+1)) and \
           all(lows[i] < lows[i+j] for j in range(1, window+1)):
            troughs.append(i)
    
    return peaks, troughs


def identify_elliott_wave(df: pd.DataFrame, peaks: list, troughs: list) -> dict:
    """
    简化的艾略特波浪识别
    
    基本思路:
    - 1浪：从底部开始的上涨
    - 2浪：1浪后的回调（不跌破1浪起点）
    - 3浪：最长的一浪，突破1浪高点
    - 4浪：3浪后的回调
    - 5浪：最后的上涨，通常短于3浪
    - A浪：下跌开始
    - B浪：反弹
    - C浪：最后一跌
    """
    if len(peaks) < 2 or len(troughs) < 2:
        return {'wave': 'Unknown', 'confidence': 0}
    
    close = df['close'].astype(float).values
    recent_peaks = peaks[-3:] if len(peaks) >= 3 else peaks
    recent_troughs = troughs[-3:] if len(troughs) >= 3 else troughs
    
    # 获取最近的价格极值
    last_peak_idx = peaks[-1]
    last_trough_idx = troughs[-1] if troughs else 0
    
    last_peak_price = close[last_peak_idx]
    last_trough_price = close[last_trough_idx] if troughs else close[0]
    
    current_price = close[-1]
    
    # 简单判断当前处于什么阶段
    wave_info = {
        'current_price': current_price,
        'last_peak': last_peak_price,
        'last_trough': last_trough_price,
        'peak_count': len(peaks),
        'trough_count': len(troughs)
    }
    
    # 判断波浪阶段
    if current_price > last_peak_price * 0.98:  # 接近或创新高
        if len(peaks) % 5 == 1:
            wave_info['wave'] = '可能处于3浪或5浪'
            wave_info['signal'] = 'bullish'
        else:
            wave_info['wave'] = '可能处于上涨延续'
            wave_info['signal'] = 'bullish'
    elif current_price < last_trough_price * 1.02:  # 接近或创新低
        if len(troughs) % 3 == 0:
            wave_info['wave'] = '可能处于C浪末端'
            wave_info['signal'] = 'oversold'
        else:
            wave_info['wave'] = '可能处于回调阶段'
            wave_info['signal'] = 'bearish'
    else:  # 中间位置
        wave_info['wave'] = '震荡整理中'
        wave_info['signal'] = 'neutral'
    
    return wave_info


def check_buy_signals(df: pd.DataFrame) -> dict:
    """
    检查买点信号 - 优化参数版本 (2026-03-20)
    
    基于10轮回测优化结果:
    - RSI超卖权重: 20 (优化后)
    - MACD底背离权重: 20
    - 锤子线权重: 10
    - 缩量止跌权重: 10
    - 接近前低权重: 10
    - MACD金叉权重: 15
    - 买点评分阈值: 40
    - 强买入阈值: 50
    """
    signals = {
        'score': 0,
        'max_score': 100,
        'signals': []
    }
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    # 辅助函数：安全转换为float
    def to_float(val):
        try:
            return float(val)
        except:
            return 0.0
    
    # 获取最新和前一日的关键值
    close_now = to_float(latest['close'])
    close_prev = to_float(prev['close'])
    macd_now = to_float(latest['macd'])
    macd_signal_now = to_float(latest['macd_signal'])
    macd_prev = to_float(prev['macd'])
    macd_signal_prev = to_float(prev['macd_signal'])
    macd_hist_now = to_float(latest['macd_hist'])
    macd_hist_prev = to_float(prev['macd_hist'])
    ma5_now = to_float(latest['ma5'])
    ma10_now = to_float(latest['ma10'])
    ma20_now = to_float(latest['ma20'])
    ma5_prev = to_float(prev['ma5'])
    rsi_now = to_float(latest['rsi'])
    rsi_prev = to_float(prev['rsi'])
    vol_now = to_float(latest['volume'])
    low_now = to_float(latest['low'])
    open_now = to_float(latest['open'])
    
    # ========== C浪/2浪/4浪回调买点信号 (优化权重) ==========
    
    # 1. MACD底背离 (20分) - 关键信号
    # 价格创新低但MACD未创新低
    recent_low = to_float(df['low'].tail(20).min())
    price_making_lower_low = close_now < recent_low * 1.02
    macd_not_lower = macd_hist_now > macd_hist_prev * 0.9 and macd_hist_now < 0
    if price_making_lower_low and macd_not_lower:
        signals['score'] += 20
        signals['signals'].append('MACD底背离 +20')
    
    # 2. RSI超卖 (20分) - 优化后权重翻倍
    if rsi_now < 35:
        signals['score'] += 20
        signals['signals'].append('RSI超卖 +20')
    elif rsi_now < 40:
        signals['score'] += 10
        signals['signals'].append('RSI偏弱 +10')
    
    # 3. 锤子线形态 (10分)
    body = abs(close_now - open_now)
    lower_shadow = min(close_now, open_now) - low_now
    upper_shadow = to_float(latest['high']) - max(close_now, open_now)
    if lower_shadow > body * 2 and upper_shadow < body and body > 0:
        signals['score'] += 10
        signals['signals'].append('锤子线止跌 +10')
    
    # 4. 缩量止跌 (10分)
    vol_avg_20 = to_float(df['volume'].tail(20).mean())
    if vol_now < vol_avg_20 * 0.7:
        signals['score'] += 10
        signals['signals'].append('缩量止跌 +10')
    
    # 5. 接近前低支撑 (10分)
    if close_now <= recent_low * 1.03:
        signals['score'] += 10
        signals['signals'].append('接近前低 +10')
    
    # 6. MACD金叉 (15分)
    if macd_now > macd_signal_now and macd_prev <= macd_signal_prev:
        signals['score'] += 15
        signals['signals'].append('MACD金叉 +15')
    
    # 7. RSI脱离超卖区 (10分)
    if rsi_prev < 35 and rsi_now >= 35:
        signals['score'] += 10
        signals['signals'].append('RSI脱离超卖 +10')
    
    # 8. 站上5日线 (5分)
    if close_now > ma5_now and close_prev <= ma5_prev:
        signals['score'] += 5
        signals['signals'].append('站上5日线 +5')
    
    # ========== 评级标准 (优化阈值) ==========
    # 强买入: ≥50分
    # 买入: ≥40分
    # 关注: ≥25分
    # 观望: <25分
    
    if signals['score'] >= 50:
        signals['rating'] = '强买入'
    elif signals['score'] >= 40:
        signals['rating'] = '买入'
    elif signals['score'] >= 25:
        signals['rating'] = '关注'
    else:
        signals['rating'] = '观望'
    
    signals['price'] = close_now
    signals['change_pct'] = (close_now / close_prev - 1) * 100 if close_prev else 0
    
    return signals
    
    signals['price'] = close_now
    signals['change_pct'] = (close_now / close_prev - 1) * 100 if close_prev else 0
    
    return signals
    
    # 1. MACD金叉 (15分)
    if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
        signals['score'] += 15
        signals['signals'].append('MACD金叉 +15')
    
    # 2. 5日线上穿10日线 (15分)
    if latest['ma5'] > latest['ma10'] and prev['ma5'] <= prev['ma10']:
        signals['score'] += 15
        signals['signals'].append('均线金叉(5/10) +15')
    
    # 3. RSI从超卖区回升 (10分)
    if latest['rsi'] > 30 and prev['rsi'] <= 30:
        signals['score'] += 10
        signals['signals'].append('RSI脱离超卖 +10')
    
    # 4. 价格在20日线上方 (10分)
    if latest['close'] > latest['ma20']:
        signals['score'] += 10
        signals['signals'].append('站上20日线 +10')
    
    # 5. 放量上涨 (10分)
    if latest['volume'] > df['volume'].rolling(20).mean().iloc[-1] * 1.2 and \
       latest['close'] > prev['close']:
        signals['score'] += 10
        signals['signals'].append('放量上涨 +10')
    
    # 6. RSI处于健康区间 40-60 (5分)
    if 40 <= latest['rsi'] <= 60:
        signals['score'] += 5
        signals['signals'].append('RSI健康 +5')
    
    # 7. 短期趋势向上 (10分)
    if latest['ma5'] > latest['ma10'] > latest['ma20']:
        signals['score'] += 10
        signals['signals'].append('多头排列 +10')
    
    # 8. 突破近期高点 (15分)
    recent_high = df['high'].tail(20).max()
    if latest['close'] > recent_high * 0.98:
        signals['score'] += 15
        signals['signals'].append('突破前高 +15')
    
    # 评级
    if signals['score'] >= 70:
        signals['rating'] = '强买入'
    elif signals['score'] >= 50:
        signals['rating'] = '买入'
    elif signals['score'] >= 30:
        signals['rating'] = '观望'
    else:
        signals['rating'] = '观望/卖出'
    
    signals['price'] = latest['close']
    signals['change_pct'] = (latest['close'] / prev['close'] - 1) * 100 if prev['close'] else 0
    
    return signals


def analyze_stock(symbol: str) -> dict:
    """分析单只股票"""
    df = get_stock_data(symbol)
    
    if df.empty or len(df) < 60:
        return {'symbol': symbol, 'error': '数据不足'}
    
    # 计算指标
    df = calculate_ma(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    
    # 找出波峰波谷
    peaks, troughs = find_peaks_troughs(df)
    
    # 波浪分析
    wave_info = identify_elliott_wave(df, peaks, troughs)
    
    # 买点信号
    buy_signals = check_buy_signals(df)
    
    return {
        'symbol': symbol,
        'wave': wave_info,
        'buy': buy_signals,
        'data_days': len(df)
    }


def main():
    """主函数"""
    print("=" * 70)
    print("自选股艾略特波浪分析 + 买点识别")
    print("=" * 70)
    
    # 加载自选股
    stocks = load_self_select_stocks()
    print(f"\n自选股数量: {len(stocks)} 只")
    print("\n开始分析...")
    print("-" * 70)
    
    results = []
    
    for i, symbol in enumerate(stocks, 1):
        print(f"\n[{i}/{len(stocks)}] 分析 {symbol}...", end=' ')
        
        try:
            result = analyze_stock(symbol)
            results.append(result)
            
            if 'error' in result:
                print(f"❌ {result['error']}")
            else:
                buy = result['buy']
                print(f"✅ 评分{buy['score']} - {buy['rating']}")
                
        except Exception as e:
            print(f"❌ 错误: {str(e)[:30]}")
            results.append({'symbol': symbol, 'error': str(e)})
    
    # 排序：按买点评分降序
    valid_results = [r for r in results if 'error' not in r]
    valid_results.sort(key=lambda x: x['buy']['score'], reverse=True)
    
    # 输出报告
    print("\n" + "=" * 70)
    print("📊 分析结果汇总")
    print("=" * 70)
    
    print(f"\n成功分析: {len(valid_results)}/{len(stocks)} 只股票")
    
    # 强买入
    strong_buy = [r for r in valid_results if r['buy']['rating'] == '强买入']
    if strong_buy:
        print(f"\n🔥 强买入信号 ({len(strong_buy)}只):")
        for r in strong_buy[:5]:
            buy = r['buy']
            print(f"  {r['symbol']:8s} 评分:{buy['score']:2d} 价格:{buy['price']:.2f} "
                  f"涨幅:{buy['change_pct']:+.2f}%")
            print(f"           信号: {', '.join(buy['signals'][:3])}")
    
    # 买入
    buy_list = [r for r in valid_results if r['buy']['rating'] == '买入']
    if buy_list:
        print(f"\n✅ 买入信号 ({len(buy_list)}只):")
        for r in buy_list[:8]:
            buy = r['buy']
            print(f"  {r['symbol']:8s} 评分:{buy['score']:2d} 价格:{buy['price']:.2f}")
    
    # 观望
    watch_list = [r for r in valid_results if r['buy']['rating'] == '观望']
    if watch_list:
        print(f"\n👀 观望 ({len(watch_list)}只):")
        symbols = [r['symbol'] for r in watch_list[:10]]
        print(f"  {', '.join(symbols)}")
    
    # 波浪分析
    print("\n" + "=" * 70)
    print("🌊 波浪分析 (评分前10)")
    print("=" * 70)
    
    for r in valid_results[:10]:
        wave = r['wave']
        buy = r['buy']
        print(f"\n{r['symbol']:8s} | 评分:{buy['score']:2d} | {wave.get('wave', 'Unknown')}")
        print(f"         当前:{wave.get('current_price', 0):.2f} "
              f"前高:{wave.get('last_peak', 0):.2f} "
              f"前低:{wave.get('last_trough', 0):.2f}")
    
    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
