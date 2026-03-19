#!/usr/bin/env python3
"""
全量数据库回测 - 覆盖所有个股和完整历史周期
验证修复后的B浪和1浪逻辑
"""

from pathlib import Path


import json
import time
from datetime import datetime

import pandas as pd
import psycopg2

from analysis.wave import UnifiedWaveAnalyzer

# 配置
LOOKBACK_DAYS = 60
STEP_DAYS = 5
HOLD_DAYS = [5, 10, 20]
MIN_SIGNAL_CONFIDENCE = 0.5

def get_db_connection():
    return psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )

def get_all_stocks():
    """获取数据库所有股票"""
    conn = get_db_connection()
    sql = '''
    SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as records
    FROM marketdata
    GROUP BY symbol
    ORDER BY records DESC
    '''
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

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

def analyze_stock(symbol, analyzer, df_full=None):
    """分析单只股票完整历史"""
    if df_full is None:
        df_full = get_stock_data(symbol, '1990-01-01', '2026-12-31')

    if len(df_full) < LOOKBACK_DAYS + max(HOLD_DAYS):
        return []

    df_full['date'] = pd.to_datetime(df_full['date'])
    df_full = df_full.sort_values('date').reset_index(drop=True)

    signals = []

    for i in range(LOOKBACK_DAYS, len(df_full) - max(HOLD_DAYS), STEP_DAYS):
        window_df = df_full.iloc[i-LOOKBACK_DAYS:i+1].copy()
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
                    'target_price': sig.target_price,
                    'stop_loss': sig.stop_loss,
                }

                # 获取验证信息
                wave_struct = getattr(sig, 'wave_structure', {})
                if wave_struct:
                    signal_record['wave1_valid'] = wave_struct.get('wave1_valid', False)
                    signal_record['wave1_duration'] = wave_struct.get('wave1_duration', 0)
                    signal_record['b_wave_valid'] = wave_struct.get('b_wave_valid', False)
                    signal_record['b_duration'] = wave_struct.get('b_duration', 0)

                # 后续走势
                future_idx = i + 1
                for hold_day in HOLD_DAYS:
                    if future_idx + hold_day < len(df_full):
                        future_price = df_full.iloc[future_idx + hold_day]['close']
                        future_return = (future_price - current_price) / current_price * 100
                        signal_record[f'return_{hold_day}d'] = future_return
                    else:
                        signal_record[f'return_{hold_day}d'] = None

                signals.append(signal_record)

    return signals

def main():
    print("=" * 90)
    print("全量数据库回测 - 修复后的B浪/1浪验证")
    print("=" * 90)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取所有股票
    stock_list = get_all_stocks()
    print(f"\n数据库股票总数: {len(stock_list)}")
    print(f"数据时间范围: {stock_list['start_date'].min()} ~ {stock_list['end_date'].max()}")
    print(f"总记录数: {stock_list['records'].sum():,}")

    # 统计信息
    print("\n数据分布:")
    print(f"  10年以上数据: {(stock_list['records'] > 2000).sum()} 只")
    print(f"  5-10年数据: {((stock_list['records'] >= 1000) & (stock_list['records'] <= 2000)).sum()} 只")
    print(f"  5年以下数据: {(stock_list['records'] < 1000).sum()} 只")

    # 创建分析器
    analyzer = UnifiedWaveAnalyzer(
        use_resonance=True,
        min_resonance_score=0.3,
        trend_ma_period=200,
        use_adaptive_params=False,
    )

    # 批量分析所有股票
    allsignals = []
    start_time = time.time()

    print("\n开始全量分析...")
    for idx, row in stock_list.iterrows():
        symbol = row['symbol']
        signals = analyze_stock(symbol, analyzer)
        if signals:
            allsignals.extend(signals)

        if (idx + 1) % 10 == 0 or (idx + 1) == len(stock_list):
            elapsed = time.time() - start_time
            progress = (idx + 1) / len(stock_list) * 100
            eta = (elapsed / (idx + 1)) * (len(stock_list) - idx - 1) if idx > 0 else 0
            print(f"  [{idx+1}/{len(stock_list)} {progress:.1f}%] {symbol} | "
                  f"信号:{len(allsignals)} | 已用:{elapsed/60:.1f}分 | 预计:{eta/60:.1f}分")

    # 保存结果
    output_dir = Path('tests/results')
    output_dir.mkdir(exist_ok=True)

    if allsignals:
        df = pd.DataFrame(allsignals)
        output_file = output_dir / 'fulldatabase_v2.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')

        # 生成详细报告
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(stock_list),
            'totalsignals': len(allsignals),
            'by_type': df['entry_type'].value_counts().to_dict(),
            'by_method': df['detection_method'].value_counts().to_dict(),
            'avg_confidence': df['confidence'].mean(),
            'confidence_distribution': {
                '0.5-0.6': ((df['confidence'] >= 0.5) & (df['confidence'] < 0.6)).sum(),
                '0.6-0.7': ((df['confidence'] >= 0.6) & (df['confidence'] < 0.7)).sum(),
                '0.7-0.8': ((df['confidence'] >= 0.7) & (df['confidence'] < 0.8)).sum(),
                '0.8+': (df['confidence'] >= 0.8).sum(),
            },
            'win_rate_5d': (df['return_5d'] > 0).mean() * 100,
            'win_rate_10d': (df['return_10d'] > 0).mean() * 100,
            'win_rate_20d': (df['return_20d'] > 0).mean() * 100,
        }

        # B浪和1浪验证统计
        if 'b_wave_valid' in df.columns:
            b_df = df[df['entry_type'] == 'C']
            if len(b_df) > 0:
                report['b_wavestats'] = {
                    'total': len(b_df),
                    'valid': b_df['b_wave_valid'].sum(),
                    'valid_rate': b_df['b_wave_valid'].mean() * 100,
                    'valid_win_rate_5d': b_df[b_df['b_wave_valid']]['return_5d'].mean() * 100 if b_df['b_wave_valid'].sum() > 0 else 0,
                }

        if 'wave1_valid' in df.columns:
            w1_df = df[df['entry_type'] == '2']
            if len(w1_df) > 0:
                report['wave1stats'] = {
                    'total': len(w1_df),
                    'valid': w1_df['wave1_valid'].sum(),
                    'valid_rate': w1_df['wave1_valid'].mean() * 100,
                }

        with open(output_dir / 'fulldatabase_v2summary.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # 打印报告
        print("\n" + "=" * 90)
        print("📊 全量回测结果")
        print("=" * 90)
        print(f"总信号数: {report['totalsignals']:,}")
        print("\n浪型分布:")
        for wave_type, count in report['by_type'].items():
            print(f"  {wave_type}浪: {count} ({count/report['totalsignals']*100:.1f}%)")
        print("\n置信度分布:")
        for rng, count in report['confidence_distribution'].items():
            print(f"  {rng}: {count} ({count/report['totalsignals']*100:.1f}%)")
        print("\n胜率:")
        print(f"  5天后: {report['win_rate_5d']:.1f}%")
        print(f"  10天后: {report['win_rate_10d']:.1f}%")
        print(f"  20天后: {report['win_rate_20d']:.1f}%")

        if 'b_wavestats' in report:
            print("\nB浪验证:")
            print(f"  总数: {report['b_wavestats']['total']}")
            print(f"  通过验证: {report['b_wavestats']['valid']} ({report['b_wavestats']['valid_rate']:.1f}%)")

        if 'wave1stats' in report:
            print("\n1浪验证:")
            print(f"  总数: {report['wave1stats']['total']}")
            print(f"  通过验证: {report['wave1stats']['valid']} ({report['wave1stats']['valid_rate']:.1f}%)")

        print(f"\n💾 详细结果: {output_file}")

    elapsed_total = time.time() - start_time
    print("\n" + "=" * 90)
    print("✅ 全量回测完成")
    print(f"总用时: {elapsed_total/60:.1f}分钟")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

if __name__ == '__main__':
    main()
