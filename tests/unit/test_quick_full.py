#!/usr/bin/env python3
"""
快速全量回测 - 使用已有数据验证最新修复效果
"""
from pathlib import Path


from datetime import datetime

import numpy as np
import pandas as pd
import psycopg2

from src.analysis.wave import UnifiedWaveAnalyzer
from src.data import get_stock_data

# 配置
LOOKBACK_DAYS = 60
STEP_DAYS = 10  # 增大步长，加快测试
HOLD_DAYS = [5, 10, 20]
MIN_SIGNAL_CONFIDENCE = 0.5

def get_all_stocks():
    conn = psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )
    sql = 'SELECT symbol FROM marketdata GROUP BY symbol ORDER BY COUNT(*) DESC'
    df = pd.read_sql(sql, conn)
    conn.close()
    return df['symbol'].tolist()

def analyze_stock(symbol, analyzer):
    try:
        df = get_stock_data(symbol, start_date='2020-01-01', end_date='2026-03-16')
        if df is None or len(df) < LOOKBACK_DAYS + max(HOLD_DAYS):
            return []

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        signals = []

        for i in range(LOOKBACK_DAYS, len(df) - max(HOLD_DAYS), STEP_DAYS):
            window_df = df.iloc[i-LOOKBACK_DAYS:i+1].copy()
            current_price = window_df['close'].iloc[-1]
            current_date = window_df['date'].iloc[-1]

            detected = analyzer.detect(window_df, mode='all')

            for sig in detected:
                if sig.is_valid and sig.confidence >= MIN_SIGNAL_CONFIDENCE:
                    signal_record = {
                        'symbol': symbol,
                        'date': current_date.strftime('%Y-%m-%d'),
                        'price': current_price,
                        'entry_type': sig.entry_type.value,
                        'confidence': sig.confidence,
                        'resonance_score': getattr(sig, 'resonance_score', 0),
                        'detection_method': getattr(sig, 'detection_method', 'unknown'),
                        'b_wave_valid': getattr(sig, 'wave_structure', {}).get('b_wave_valid', False),
                        'wave1_valid': getattr(sig, 'wave_structure', {}).get('wave1_valid', False),
                    }

                    # 后续走势
                    future_idx = i + 1
                    for hold_day in HOLD_DAYS:
                        if future_idx + hold_day < len(df):
                            future_price = df.iloc[future_idx + hold_day]['close']
                            if current_price != 0 and np.isfinite(current_price):
                                future_return = (future_price - current_price) / current_price * 100
                                if np.isfinite(future_return):
                                    signal_record[f'return_{hold_day}d'] = future_return
                                else:
                                    signal_record[f'return_{hold_day}d'] = None
                            else:
                                signal_record[f'return_{hold_day}d'] = None
                        else:
                            signal_record[f'return_{hold_day}d'] = None

                    signals.append(signal_record)

        return signals
    except Exception as e:
        print(f"  {symbol} 错误: {e}")
        return []

def main():
    print("=" * 80)
    print("快速全量回测 - 验证1浪修复效果")
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
        if (idx + 1) % 10 == 0 or (idx + 1) == len(stocks):
            print(f"  [{idx+1}/{len(stocks)}] 累计信号: {len(allsignals)}")

    # 统计结果
    if allsignals:
        df = pd.DataFrame(allsignals)

        # 清理异常值
        for col in ['return_5d', 'return_10d', 'return_20d']:
            if col in df.columns:
                df[col] = df[col].replace([np.inf, -np.inf], np.nan)

        print("\n" + "=" * 80)
        print("📊 验证统计")
        print("=" * 80)

        print(f"\n总信号数: {len(df)}")

        # 浪型分布
        print("\n浪型分布:")
        for etype, count in df['entry_type'].value_counts().items():
            print(f"  {etype}浪: {count} ({count/len(df)*100:.1f}%)")

        # C浪验证
        c_df = df[df['entry_type'] == 'C']
        if len(c_df) > 0:
            valid_count = c_df['b_wave_valid'].sum()
            print("\nC浪B浪验证:")
            print(f"  总数: {len(c_df)}")
            print(f"  通过验证: {valid_count}")
            print(f"  通过率: {valid_count/len(c_df)*100:.1f}%")

            # 胜率
            c_valid = c_df[c_df['b_wave_valid']]['return_5d'].dropna()
            c_invalid = c_df[~c_df['b_wave_valid']]['return_5d'].dropna()
            if len(c_valid) > 0:
                print(f"  验证通过胜率(5天): {(c_valid > 0).mean()*100:.1f}% (收益: {c_valid.mean():.2f}%)")
            if len(c_invalid) > 0:
                print(f"  验证失败胜率(5天): {(c_invalid > 0).mean()*100:.1f}% (收益: {c_invalid.mean():.2f}%)")

        # 2浪验证
        w2_df = df[df['entry_type'] == '2']
        if len(w2_df) > 0:
            valid_count = w2_df['wave1_valid'].sum()
            print("\n2浪1浪验证:")
            print(f"  总数: {len(w2_df)}")
            print(f"  通过验证: {valid_count}")
            print(f"  通过率: {valid_count/len(w2_df)*100:.1f}%")

            # 胜率
            w2_valid = w2_df[w2_df['wave1_valid']]['return_5d'].dropna()
            w2_invalid = w2_df[~w2_df['wave1_valid']]['return_5d'].dropna()
            if len(w2_valid) > 0:
                print(f"  验证通过胜率(5天): {(w2_valid > 0).mean()*100:.1f}% (收益: {w2_valid.mean():.2f}%)")
            if len(w2_invalid) > 0:
                print(f"  验证失败胜率(5天): {(w2_invalid > 0).mean()*100:.1f}% (收益: {w2_invalid.mean():.2f}%)")

        # 整体胜率
        print("\n整体胜率:")
        for d in [5, 10, 20]:
            col = f'return_{d}d'
            if col in df.columns:
                validreturns = df[col].dropna()
                if len(validreturns) > 0:
                    win_rate = (validreturns > 0).mean() * 100
                    avg_return = validreturns.mean()
                    print(f"  {d}天后: {win_rate:.1f}% (平均收益: {avg_return:.2f}%)")

        # 保存结果
        output_dir = Path('tests/results')
        output_dir.mkdir(exist_ok=True)
        df.to_csv(output_dir / 'fulldatabase_v3.csv', index=False, encoding='utf-8-sig')
        print("\n💾 结果保存: tests/results/fulldatabase_v3.csv")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == '__main__':
    main()
