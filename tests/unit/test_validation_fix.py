#!/usr/bin/env python3
"""
快速验证B浪修复效果 - 测试5只股票
"""
from pathlib import Path


from datetime import datetime

import pandas as pd
import psycopg2

from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data

# 配置
LOOKBACK_DAYS = 60
STEP_DAYS = 5
HOLD_DAYS = [5, 10, 20]
MIN_SIGNAL_CONFIDENCE = 0.5

def get_all_stocks():
    conn = psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )
    sql = 'SELECT symbol FROM marketdata GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 10'
    df = pd.read_sql(sql, conn)
    conn.close()
    return df['symbol'].tolist()

def analyze_stock(symbol, analyzer):
    df = get_stock_data(symbol, start_date='2020-01-01', end_date='2026-03-16')
    if df is None or len(df) < LOOKBACK_DAYS + max(HOLD_DAYS):
        return []

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    signals = []

    for i in range(LOOKBACK_DAYS, len(df) - max(HOLD_DAYS), STEP_DAYS):
        window_df = df.iloc[i-LOOKBACK_DAYS:i+1].copy()
        current_price = window_df['close'].iloc[-1]

        detected = analyzer.detect(window_df, mode='all')

        for sig in detected:
            if sig.is_valid and sig.confidence >= MIN_SIGNAL_CONFIDENCE:
                signal_record = {
                    'symbol': symbol,
                    'entry_type': sig.entry_type.value,
                    'confidence': sig.confidence,
                    'b_wave_valid': getattr(sig, 'wave_structure', {}).get('b_wave_valid', False),
                    'wave1_valid': getattr(sig, 'wave_structure', {}).get('wave1_valid', False),
                }
                signals.append(signal_record)

    return signals

def main():
    print("=" * 80)
    print("B浪验证修复效果快速测试 (10只股票)")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    stocks = get_all_stocks()
    print(f"\n测试股票: {len(stocks)} 只")

    analyzer = UnifiedWaveAnalyzer(
        use_resonance=True,
        min_resonance_score=0.3,
        trend_ma_period=200,
        use_adaptive_params=False,
    )

    allsignals = []

    for idx, symbol in enumerate(stocks):
        signals = analyze_stock(symbol, analyzer)
        if signals:
            allsignals.extend(signals)
        print(f"  [{idx+1}/{len(stocks)}] {symbol}: {len(signals)} 个信号")

    # 统计结果
    if allsignals:
        df = pd.DataFrame(allsignals)

        print("\n" + "=" * 80)
        print("📊 验证统计")
        print("=" * 80)

        # C浪验证
        c_df = df[df['entry_type'] == 'C']
        if len(c_df) > 0:
            valid_count = c_df['b_wave_valid'].sum()
            print("\nC浪信号:")
            print(f"  总数: {len(c_df)}")
            print(f"  通过B浪验证: {valid_count}")
            print(f"  通过率: {valid_count/len(c_df)*100:.1f}%")

        # 2浪验证
        w2_df = df[df['entry_type'] == '2']
        if len(w2_df) > 0:
            valid_count = w2_df['wave1_valid'].sum()
            print("\n2浪信号:")
            print(f"  总数: {len(w2_df)}")
            print(f"  通过1浪验证: {valid_count}")
            print(f"  通过率: {valid_count/len(w2_df)*100:.1f}%")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == '__main__':
    main()
