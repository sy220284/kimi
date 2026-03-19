#!/usr/bin/env python3
"""
批量波浪分析回测 - 带进度跟踪
对比增强版 vs 上一版本
"""

from pathlib import Path


import json
import time
from datetime import datetime

import pandas as pd
import psycopg2

from src.analysis.wave import UnifiedWaveAnalyzer

# 分析配置
LOOKBACK_DAYS = 60
STEP_DAYS = 5
HOLD_DAYS = [5, 10, 20]
MIN_SIGNAL_CONFIDENCE = 0.5

class ProgressTracker:
    """进度跟踪器"""
    def __init__(self, total_stocks):
        self.total = total_stocks
        self.current = 0
        self.start_time = time.time()
        self.signals_found = 0

    def update(self, signals_count):
        self.current += 1
        self.signals_found += signals_count
        elapsed = time.time() - self.start_time
        progress = self.current / self.total * 100
        eta = (elapsed / self.current) * (self.total - self.current) if self.current > 0 else 0

        print(f"\n[PROGRESS] {self.current}/{self.total} ({progress:.1f}%) | "
              f"信号:{self.signals_found} | 已用:{elapsed/60:.1f}分 | 预计剩余:{eta/60:.1f}分")

        return {
            'current': self.current,
            'total': self.total,
            'progress': progress,
            'signals': self.signals_found,
            'elapsed_min': elapsed/60,
            'eta_min': eta/60
        }

def get_db_connection():
    return psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )

def get_stock_list(min_records=1000):
    conn = get_db_connection()
    sql = '''
    SELECT symbol, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as records
    FROM marketdata
    GROUP BY symbol
    HAVING COUNT(*) >= %s
    ORDER BY COUNT(*) DESC
    '''
    df = pd.read_sql(sql, conn, params=(min_records,))
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

def analyze_stock(symbol, analyzer, tracker):
    """分析单只股票"""
    df = get_stock_data(symbol, '2020-01-01', '2026-03-16')
    if len(df) < LOOKBACK_DAYS + max(HOLD_DAYS):
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
                    'trend_aligned': getattr(sig, 'trend_aligned', False),
                    'market_condition': getattr(sig, 'market_condition', 'unknown'),
                    'target_price': sig.target_price,
                    'stop_loss': sig.stop_loss,
                    'detection_method': getattr(sig, 'detection_method', 'unknown'),
                }

                # 获取验证信息
                wave_struct = getattr(sig, 'wave_structure', {})
                if wave_struct:
                    signal_record['wave1_valid'] = wave_struct.get('wave1_valid', False)
                    signal_record['wave123_valid'] = wave_struct.get('wave123_valid', False)
                    signal_record['b_wave_valid'] = wave_struct.get('b_wave_valid', False)

                # 后续走势
                future_idx = i + 1
                for hold_day in HOLD_DAYS:
                    if future_idx + hold_day < len(df):
                        future_price = df.iloc[future_idx + hold_day]['close']
                        future_return = (future_price - current_price) / current_price * 100
                        signal_record[f'return_{hold_day}d'] = future_return
                    else:
                        signal_record[f'return_{hold_day}d'] = None

                signals.append(signal_record)

    # 更新进度
    progress = tracker.update(len(signals))
    print(f"  {symbol}: {len(signals)}个信号")

    return signals

def main():
    print("=" * 80)
    print("批量波浪分析回测 - 增强版")
    print("=" * 80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 获取股票列表
    stock_list = get_stock_list(min_records=2000)
    print(f"\n待分析股票: {len(stock_list)} 只")
    print("前10只:", ', '.join(stock_list['symbol'].head(10).tolist()))

    # 创建分析器
    analyzer = UnifiedWaveAnalyzer(
        use_resonance=True,
        min_resonance_score=0.3,
        trend_ma_period=200,
        use_adaptive_params=False,
    )

    # 进度跟踪
    selected_stocks = stock_list['symbol'].head(20).tolist()
    tracker = ProgressTracker(len(selected_stocks))

    # 批量分析
    allsignals = []
    print(f"\n开始分析前{len(selected_stocks)}只股票...")

    for symbol in selected_stocks:
        signals = analyze_stock(symbol, analyzer, tracker)
        if signals:
            allsignals.extend(signals)

    # 保存结果
    output_dir = Path('tests/results')
    output_dir.mkdir(exist_ok=True)

    if allsignals:
        df = pd.DataFrame(allsignals)
        df.to_csv(output_dir / 'batch_enhanced_v2.csv', index=False, encoding='utf-8-sig')

        # 生成摘要
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(selected_stocks),
            'totalsignals': len(allsignals),
            'by_type': df['entry_type'].value_counts().to_dict(),
            'by_method': df['detection_method'].value_counts().to_dict() if 'detection_method' in df.columns else {},
            'avg_confidence': df['confidence'].mean(),
            'win_rate_5d': (df['return_5d'] > 0).mean() * 100 if 'return_5d' in df.columns else 0,
            'win_rate_20d': (df['return_20d'] > 0).mean() * 100 if 'return_20d' in df.columns else 0,
        }

        with open(output_dir / 'batch_enhanced_v2summary.json', 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        print("\n" + "=" * 80)
        print("📊 结果摘要")
        print("=" * 80)
        print(f"总信号数: {summary['totalsignals']}")
        print(f"浪型分布: {summary['by_type']}")
        print(f"检测方法: {summary['by_method']}")
        print(f"平均置信度: {summary['avg_confidence']:.2f}")
        print(f"5天胜率: {summary['win_rate_5d']:.1f}%")
        print(f"20天胜率: {summary['win_rate_20d']:.1f}%")
        print("\n💾 结果保存: tests/results/batch_enhanced_v2.csv")

    print("\n" + "=" * 80)
    print("✅ 批量分析完成")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == '__main__':
    main()
