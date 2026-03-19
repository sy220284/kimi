#!/usr/bin/env python3
"""
波浪识别事后验证分析

思路：
1. 找完整波浪周期（如A浪起点→C浪终点，或1浪起点→5浪终点）
2. 用完整数据事后分析"真实浪型"
3. 对比实时识别的信号点
4. 统计准确率并建立特征库
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import psycopg2

from src.analysis.wave import UnifiedWaveAnalyzer


@dataclass
class WaveSegment:
    """波浪段落（事后验证用）"""
    start_date: str
    end_date: str
    start_price: float
    end_price: float
    wave_type: str  # 'A', 'B', 'C', '1', '2', '3', '4', '5'
    is_corrective: bool  # 是否是调整浪
    duration_days: int
    price_change_pct: float
    volume_profile: str  # '扩张', '收缩', '平稳'

@dataclass
class WaveCycle:
    """完整波浪周期"""
    symbol: str
    start_date: str
    end_date: str
    pattern_type: str  # 'impulse', 'corrective', 'complex'
    segments: list[WaveSegment]
    total_return_pct: float
    max_drawdown_pct: float

class WavePostValidator:
    """波浪事后验证器"""

    def __init__(self):
        self.analyzer = UnifiedWaveAnalyzer(
            use_resonance=False,  # 事后验证不需要共振
            use_trend_filter=False,  # 事后验证不需要趋势过滤
            trend_ma_period=20,
        )

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据库获取股票数据"""
        conn = psycopg2.connect(
            host='localhost', port=5432, database='quant_analysis',
            user='quant_user', password='quant_password'
        )
        sql = '''
        SELECT date, open, high, low, close, volume, amount
        FROM marketdata
        WHERE symbol = %s AND date >= %s AND date <= %s
        ORDER BY date
        '''
        df = pd.read_sql(sql, conn, params=(symbol, start_date, end_date))
        conn.close()
        return df

    def detectpivots_with_future(self, df: pd.DataFrame,
                                   confirmation_bars: int = 5) -> pd.DataFrame:
        """
        用未来数据确认高低点（事后视角）

        规则：
        - 一个高点要确认为真正高点，需要后续N天都不再创新高
        - 一个低点要确认为真正低点，需要后续N天都不再创新低
        """
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        n = confirmation_bars
        highs = df['high'].values
        lows = df['low'].values

        # 标记潜在高低点
        df['ispeak'] = False
        df['is_trough'] = False
        df['is_confirmedpeak'] = False
        df['is_confirmed_trough'] = False

        for i in range(n, len(df) - n):
            # 潜在高点：比前后n天都高
            if highs[i] == max(highs[i-n:i+n+1]):
                df.loc[i, 'ispeak'] = True
                # 确认：后续不再创新高
                if i + n < len(df):
                    future_max = max(highs[i+1:min(i+n+1, len(df))])
                    if highs[i] >= future_max:
                        df.loc[i, 'is_confirmedpeak'] = True

            # 潜在低点：比前后n天都低
            if lows[i] == min(lows[i-n:i+n+1]):
                df.loc[i, 'is_trough'] = True
                # 确认：后续不再创新低
                if i + n < len(df):
                    future_min = min(lows[i+1:min(i+n+1, len(df))])
                    if lows[i] <= future_min:
                        df.loc[i, 'is_confirmed_trough'] = True

        return df

    def identify_wave_pattern(self, df: pd.DataFrame) -> WaveCycle | None:
        """
        识别完整波浪模式（事后视角）
        """
        df = self.detectpivots_with_future(df)

        # 提取确认的极值点
        peaks = df[df['is_confirmedpeak']].copy()
        troughs = df[df['is_confirmed_trough']].copy()

        if len(peaks) < 2 or len(troughs) < 2:
            return None

        # 合并并按时间排序
        extremes = []
        for _, row in peaks.iterrows():
            extremes.append({
                'date': row['date'],
                'price': row['high'],
                'type': 'peak',
                'idx': row.name
            })
        for _, row in troughs.iterrows():
            extremes.append({
                'date': row['date'],
                'price': row['low'],
                'type': 'trough',
                'idx': row.name
            })

        extremes.sort(key=lambda x: x['date'])

        # 确保极值点交替出现（高低高低...）
        cleaned = []
        last_type = None
        for ext in extremes:
            if ext['type'] != last_type:
                cleaned.append(ext)
                last_type = ext['type']

        if len(cleaned) < 4:
            return None

        # 尝试识别波浪模式
        segments = []
        symbol = df.iloc[0]['date'].strftime('%Y%m%d')[:6]  # 简化处理

        for i in range(len(cleaned) - 1):
            start = cleaned[i]
            end = cleaned[i+1]

            duration = (end['date'] - start['date']).days
            price_change = (end['price'] - start['price']) / start['price'] * 100

            # 判断浪型
            if i == 0:
                wave_type = 'A' if start['type'] == 'peak' else '1'
            elif i == 1:
                wave_type = 'B' if segments[0].wave_type == 'A' else '2'
            elif i == 2:
                wave_type = 'C' if segments[0].wave_type == 'A' else '3'
            elif i == 3:
                wave_type = '4' if segments[0].wave_type == '1' else '?'  # 推动浪才有4浪
            elif i == 4:
                wave_type = '5' if segments[0].wave_type == '1' else '?'
            else:
                wave_type = '?'

            is_corrective = wave_type in ['A', 'B', 'C', '2', '4']

            # 成交量特征
            start_idx = start['idx']
            end_idx = end['idx']
            vol_start = df.iloc[start_idx:start_idx+5]['volume'].mean() if start_idx + 5 < len(df) else 0
            vol_end = df.iloc[end_idx-5:end_idx]['volume'].mean() if end_idx - 5 >= 0 else 0

            if vol_end > vol_start * 1.3:
                vol_profile = '扩张'
            elif vol_end < vol_start * 0.7:
                vol_profile = '收缩'
            else:
                vol_profile = '平稳'

            segment = WaveSegment(
                start_date=start['date'].strftime('%Y-%m-%d'),
                end_date=end['date'].strftime('%Y-%m-%d'),
                start_price=start['price'],
                end_price=end['price'],
                wave_type=wave_type,
                is_corrective=is_corrective,
                duration_days=duration,
                price_change_pct=price_change,
                volume_profile=vol_profile
            )
            segments.append(segment)

        # 判断整体模式
        if len(segments) >= 3 and segments[0].wave_type == '1':
            pattern_type = 'impulse'
        elif len(segments) >= 3 and segments[0].wave_type == 'A':
            pattern_type = 'corrective'
        else:
            pattern_type = 'complex'

        total_return = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100

        # 计算最大回撤
        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax * 100
        max_drawdown = drawdown.min()

        return WaveCycle(
            symbol=symbol,
            start_date=df['date'].iloc[0].strftime('%Y-%m-%d'),
            end_date=df['date'].iloc[-1].strftime('%Y-%m-%d'),
            pattern_type=pattern_type,
            segments=segments,
            total_return_pct=total_return,
            max_drawdown_pct=max_drawdown
        )

    def build_feature_library(self, symbols: list[str],
                              start_date: str = '2020-01-01',
                              end_date: str = '2026-03-16') -> dict:
        """
        建立浪型特征库
        """
        print("\n📚 建立浪型特征库...")

        features = {
            'C浪': {'durations': [], 'pricechanges': [], 'volume_profiles': []},
            '2浪': {'durations': [], 'pricechanges': [], 'volume_profiles': []},
            'A浪': {'durations': [], 'pricechanges': [], 'volume_profiles': []},
            'B浪': {'durations': [], 'pricechanges': [], 'volume_profiles': []},
        }

        all_cycles = []

        for symbol in symbols[:10]:  # 先分析10只
            print(f"  分析 {symbol}...")
            df = self.get_stock_data(symbol, start_date, end_date)

            if len(df) < 200:
                continue

            # 分段分析（每段约120天）
            for i in range(0, len(df) - 120, 60):
                segment_df = df.iloc[i:i+120].copy()
                cycle = self.identify_wave_pattern(segment_df)

                if cycle and len(cycle.segments) >= 3:
                    all_cycles.append(cycle)

                    for seg in cycle.segments:
                        wave_key = seg.wave_type + '浪' if seg.wave_type in ['C', '2', 'A', 'B'] else seg.wave_type
                        if wave_key in features:
                            features[wave_key]['durations'].append(seg.duration_days)
                            features[wave_key]['pricechanges'].append(abs(seg.price_change_pct))
                            features[wave_key]['volume_profiles'].append(seg.volume_profile)

        # 统计特征
        featurestats = {}
        for wave_type, data in features.items():
            if data['durations']:
                featurestats[wave_type] = {
                    'sample_count': len(data['durations']),
                    'avg_duration': np.mean(data['durations']),
                    'duration_std': np.std(data['durations']),
                    'avg_price_change': np.mean(data['pricechanges']),
                    'price_change_std': np.std(data['pricechanges']),
                    'volume_expansion_pct': data['volume_profiles'].count('扩张') / len(data['volume_profiles']) * 100,
                    'volume_contraction_pct': data['volume_profiles'].count('收缩') / len(data['volume_profiles']) * 100,
                }

        print(f"\n✓ 分析了 {len(all_cycles)} 个完整周期")
        return featurestats, all_cycles

    def validate_realtimesignals(self, symbol: str,
                                   realtimesignals: list[dict],
                                   true_cycle: WaveCycle) -> dict:
        """
        验证实时识别信号 vs 事后真实浪型
        """
        validations = []

        for signal in realtimesignals:
            signal_date = signal['date']
            signal_type = signal['entry_type']

            # 找到信号日期所在的真实的浪
            true_wave = None
            for seg in true_cycle.segments:
                if seg.start_date <= signal_date <= seg.end_date:
                    true_wave = seg
                    break

            if true_wave:
                is_correct = (signal_type == true_wave.wave_type)
                validations.append({
                    'signal_date': signal_date,
                    'signal_type': signal_type,
                    'true_type': true_wave.wave_type,
                    'is_correct': is_correct,
                    'date_diff_days': 0,  # 在同一浪内
                })
            else:
                # 信号点不在任何已识别的浪中（可能提前或滞后）
                validations.append({
                    'signal_date': signal_date,
                    'signal_type': signal_type,
                    'true_type': 'unknown',
                    'is_correct': False,
                    'date_diff_days': -1,
                })

        if validations:
            accuracy = sum(v['is_correct'] for v in validations) / len(validations)
        else:
            accuracy = 0

        return {
            'symbol': symbol,
            'totalsignals': len(validations),
            'correctsignals': sum(v['is_correct'] for v in validations),
            'accuracy': accuracy,
            'details': validations
        }

def main():
    print("=" * 80)
    print("波浪识别事后验证分析")
    print("=" * 80)

    validator = WavePostValidator()

    # 获取股票列表
    conn = psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )
    sql = '''
    SELECT symbol, COUNT(*) as records
    FROM marketdata
    WHERE date >= '2020-01-01'
    GROUP BY symbol
    HAVING COUNT(*) >= 1000
    ORDER BY COUNT(*) DESC
    LIMIT 20
    '''
    stock_df = pd.read_sql(sql, conn)
    conn.close()

    symbols = stock_df['symbol'].tolist()
    print(f"\n选择 {len(symbols)} 只股票进行分析")

    # 建立特征库
    featurestats, cycles = validator.build_feature_library(symbols)

    # 打印特征库
    print("\n" + "=" * 80)
    print("📊 浪型特征库")
    print("=" * 80)

    for wave_type, stats in featurestats.items():
        print(f"\n【{wave_type}浪特征】 (样本{stats['sample_count']}个)")
        print(f"  平均持续时间: {stats['avg_duration']:.1f} ± {stats['duration_std']:.1f} 天")
        print(f"  平均价格变动: {stats['avg_price_change']:.2f}% ± {stats['price_change_std']:.2f}%")
        print(f"  成交量扩张比例: {stats['volume_expansion_pct']:.1f}%")
        print(f"  成交量收缩比例: {stats['volume_contraction_pct']:.1f}%")

    # 保存特征库
    output_dir = Path('tests/results')
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / 'wave_feature_library.json', 'w', encoding='utf-8') as f:
        json.dump(featurestats, f, ensure_ascii=False, indent=2)

    print("\n💾 特征库已保存: tests/results/wave_feature_library.json")

    # 示例：分析一只股票的实时识别 vs 事后真实浪型
    print("\n" + "=" * 80)
    print("🔍 实时识别 vs 事后验证示例")
    print("=" * 80)

    test_symbol = '600519'
    df = validator.get_stock_data(test_symbol, '2024-01-01', '2024-12-31')

    if len(df) > 120:
        cycle = validator.identify_wave_pattern(df.iloc[:120])
        if cycle:
            print(f"\n{test_symbol} 2024年前120天真实浪型结构:")
            print(f"  模式类型: {cycle.pattern_type}")
            print(f"  总收益: {cycle.total_return_pct:.2f}%")
            print(f"  最大回撤: {cycle.max_drawdown_pct:.2f}%")
            print("\n  分段详情:")
            for seg in cycle.segments:
                direction = "上涨" if seg.price_change_pct > 0 else "下跌"
                print(f"    {seg.wave_type}浪: {seg.start_date} ~ {seg.end_date}")
                print(f"         {direction} {abs(seg.price_change_pct):.2f}%, {seg.duration_days}天, 成交量{seg.volume_profile}")

    print("\n" + "=" * 80)
    print("✅ 事后验证分析完成")
    print("=" * 80)

if __name__ == '__main__':
    main()
