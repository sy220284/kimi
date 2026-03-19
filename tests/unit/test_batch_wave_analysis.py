#!/usr/bin/env python3
"""
批量波浪分析回测 - 数据库全量数据
分析内容:
1. 浪型识别率统计
2. 买卖点信号识别与后续走势验证
3. 信号准确率回测
"""

from pathlib import Path


import pandas as pd
import psycopg2

from analysis.wave import UnifiedWaveAnalyzer

# 分析配置
LOOKBACK_DAYS = 60      # 分析窗口
STEP_DAYS = 5           # 滑动步长
HOLD_DAYS = [5, 10, 20] # 验证持仓天数
MIN_SIGNAL_CONFIDENCE = 0.5

# 连接数据库
def get_db_connection():
    return psycopg2.connect(
        host='localhost', port=5432, database='quant_analysis',
        user='quant_user', password='quant_password'
    )

# 获取股票列表
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

# 获取单只股票数据
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

# 分析单只股票
def analyze_stock(symbol, analyzer):
    """分析单只股票的所有历史数据"""
    print(f"\n📊 分析 {symbol}...")

    # 获取数据
    df = get_stock_data(symbol, '2020-01-01', '2026-03-16')
    if len(df) < LOOKBACK_DAYS + max(HOLD_DAYS):
        print(f"  ⚠️ 数据不足 ({len(df)}条)，跳过")
        return None

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # 存储结果
    signals = []  # 所有检测到的信号

    # 滑动窗口分析
    for i in range(LOOKBACK_DAYS, len(df) - max(HOLD_DAYS), STEP_DAYS):
        window_df = df.iloc[i-LOOKBACK_DAYS:i+1].copy()
        current_price = window_df['close'].iloc[-1]
        current_date = window_df['date'].iloc[-1]

        # 检测波浪信号
        detected = analyzer.detect(window_df, mode='all')

        for sig in detected:
            if sig.is_valid and sig.confidence >= MIN_SIGNAL_CONFIDENCE:
                # 记录信号
                signal_record = {
                    'symbol': symbol,
                    'date': current_date.strftime('%Y-%m-%d'),
                    'price': current_price,
                    'entry_type': sig.entry_type.value,
                    'confidence': sig.confidence,
                    'resonance_score': sig.resonance_score,
                    'trend_aligned': sig.trend_aligned,
                    'market_condition': sig.market_condition,
                    'target_price': sig.target_price,
                    'stop_loss': sig.stop_loss,
                }

                # 计算后续走势 (未来N天收益率)
                future_idx = i + 1
                for hold_day in HOLD_DAYS:
                    if future_idx + hold_day < len(df):
                        future_price = df.iloc[future_idx + hold_day]['close']
                        future_return = (future_price - current_price) / current_price * 100
                        signal_record[f'return_{hold_day}d'] = future_return
                        signal_record[f'future_price_{hold_day}d'] = future_price
                    else:
                        signal_record[f'return_{hold_day}d'] = None
                        signal_record[f'future_price_{hold_day}d'] = None

                signals.append(signal_record)

    print(f"  ✓ 检测到 {len(signals)} 个信号")
    return signals

# 统计分析结果
def analyze_results(allsignals):
    """分析所有信号统计结果"""
    if not allsignals:
        print("⚠️ 没有检测到信号")
        return

    df = pd.DataFrame(allsignals)

    print("\n" + "=" * 80)
    print("📈 浪型识别统计分析")
    print("=" * 80)

    # 1. 信号类型分布
    print("\n【信号类型分布】")
    type_dist = df['entry_type'].value_counts()
    print(type_dist)

    # 2. 置信度分布
    print("\n【置信度分布】")
    print(f"  平均置信度: {df['confidence'].mean():.2f}")
    print(f"  高置信度(≥0.7): {(df['confidence'] >= 0.7).sum()} ({(df['confidence'] >= 0.7).mean()*100:.1f}%)")
    print(f"  中等置信度(0.5-0.7): {((df['confidence'] >= 0.5) & (df['confidence'] < 0.7)).sum()}")

    # 3. 共振分数分布
    print("\n【共振分数分布】")
    print(f"  平均共振分数: {df['resonance_score'].mean():.2f}")
    print(f"  强共振(≥0.5): {(df['resonance_score'] >= 0.5).sum()}")

    # 4. 趋势对齐情况
    print("\n【趋势对齐情况】")
    aligned_dist = df['trend_aligned'].value_counts()
    print(aligned_dist)

    # 5. 市场状态分布
    print("\n【市场状态分布】")
    market_dist = df['market_condition'].value_counts()
    print(market_dist)

    # 6. 后续走势验证
    print("\n【后续走势验证】")
    for hold_day in HOLD_DAYS:
        col = f'return_{hold_day}d'
        validreturns = df[col].dropna()
        if len(validreturns) > 0:
            win_rate = (validreturns > 0).mean() * 100
            avg_return = validreturns.mean()
            median_return = validreturns.median()

            print(f"\n  {hold_day}天后:")
            print(f"    样本数: {len(validreturns)}")
            print(f"    胜率: {win_rate:.1f}%")
            print(f"    平均收益: {avg_return:+.2f}%")
            print(f"    中位数收益: {median_return:+.2f}%")
            print(f"    最大收益: {validreturns.max():+.2f}%")
            print(f"    最大亏损: {validreturns.min():+.2f}%")

            # 按信号类型分组
            print("    按浪型分组胜率:")
            for wave_type in df['entry_type'].unique():
                wavedata = df[df['entry_type'] == wave_type][col].dropna()
                if len(wavedata) > 0:
                    wave_win_rate = (wavedata > 0).mean() * 100
                    wave_avg = wavedata.mean()
                    print(f"      {wave_type}浪: 胜率{wave_win_rate:.1f}%, 平均{wave_avg:+.2f}% (n={len(wavedata)})")

    # 7. 目标价达成率
    print("\n【目标价达成分析】")
    df['target_diff'] = (df['target_price'] - df['price']) / df['price'] * 100
    print(f"  平均目标涨幅: {df['target_diff'].mean():.2f}%")

    for hold_day in HOLD_DAYS:
        col = f'return_{hold_day}d'
        validdata = df[df[col].notna()].copy()
        if len(validdata) > 0:
            # 目标达成: 收益 > 0 (简化判断)
            target_hit = (validdata[col] > 0).sum()
            print(f"  {hold_day}天目标达成率: {target_hit}/{len(validdata)} ({target_hit/len(validdata)*100:.1f}%)")

    return df

def main():
    print("=" * 80)
    print("批量波浪分析回测")
    print("=" * 80)

    # 获取股票列表 (选择数据量较大的股票)
    stock_list = get_stock_list(min_records=2000)
    print(f"\n待分析股票: {len(stock_list)} 只")
    print(stock_list[['symbol', 'records']].head(20).to_string(index=False))

    # 创建分析器
    analyzer = UnifiedWaveAnalyzer(
        use_resonance=True,
        min_resonance_score=0.3,
        trend_ma_period=200,
        use_adaptive_params=False,
    )

    # 批量分析 (选择前20只股票)
    allsignals = []
    selected_stocks = stock_list['symbol'].head(20).tolist()

    print("\n开始分析前20只股票...")
    for symbol in selected_stocks:
        signals = analyze_stock(symbol, analyzer)
        if signals:
            allsignals.extend(signals)

    # 统计分析
    results_df = analyze_results(allsignals)

    # 保存结果
    if results_df is not None and len(results_df) > 0:
        output_file = 'tests/results/batch_wave_analysis.json'
        Path(output_file).parent.mkdir(exist_ok=True)
        results_df.to_json(output_file, orient='records', force_ascii=False, indent=2)
        print(f"\n💾 详细结果已保存: {output_file}")

        # CSV格式也保存一份
        csv_file = 'tests/results/batch_wave_analysis.csv'
        results_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"💾 CSV结果已保存: {csv_file}")

    print("\n" + "=" * 80)
    print("✅ 批量分析完成")
    print("=" * 80)

if __name__ == '__main__':
    main()
