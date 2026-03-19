#!/usr/bin/env python3
"""
大盘扫描分析
获取并分析今日大盘指数
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


from data.ths_history_fetcher import ThsHistoryFetcher

# 主要大盘指数
INDICES = {
    '000001': '上证指数',
    '000016': '上证50',
    '000300': '沪深300',
    '000905': '中证500',
    '399001': '深证成指',
    '399006': '创业板指',
    '883957': '科创50',
}


def fetch_index_data(symbol, name):
    """获取指数数据"""
    print(f"  📥 下载 {symbol} {name}...", end=" ")

    fetcher = ThsHistoryFetcher()

    try:
        # 获取最近30天数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)

        df = fetcher.get_data_by_date_range(
            f'hs_{symbol}',
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if df is not None and not df.empty:
            print(f"✅ {len(df)}条")
            return df
        else:
            print("❌ 无数据")
            return None

    except Exception as e:
        print(f"❌ 失败: {e}")
        return None


def analyze_index(symbol, name, df):
    """分析指数"""
    if df is None or df.empty:
        return None

    # 确保数据排序
    df = df.sort_values('date')

    # 最新数据
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    # 计算指标
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()

    # 波动率 (20日)
    df['returns'] = df['close'].pct_change()
    volatility = df['returns'].rolling(20).std() * np.sqrt(252) * 100

    # 最新指标
    latest_ma5 = df['ma5'].iloc[-1]
    latest_ma20 = df['ma20'].iloc[-1]
    latest_ma60 = df['ma60'].iloc[-1]
    latest_vol = volatility.iloc[-1] if not pd.isna(volatility.iloc[-1]) else 0

    # 涨跌幅
    change_pct = (latest['close'] - prev['close']) / prev['close'] * 100

    # 趋势判断
    trend = "未知"
    if latest['close'] > latest_ma5 > latest_ma20:
        trend = "强势上涨 📈📈"
    elif latest['close'] > latest_ma20:
        trend = "多头趋势 📈"
    elif latest['close'] < latest_ma5 < latest_ma20:
        trend = "弱势下跌 📉📉"
    elif latest['close'] < latest_ma20:
        trend = "空头趋势 📉"
    else:
        trend = "震荡整理 ➡️"

    return {
        'symbol': symbol,
        'name': name,
        'date': latest['date'],
        'close': latest['close'],
        'open': latest['open'],
        'high': latest['high'],
        'low': latest['low'],
        'volume': latest['volume'],
        'change_pct': change_pct,
        'ma5': latest_ma5,
        'ma20': latest_ma20,
        'ma60': latest_ma60,
        'volatility': latest_vol,
        'trend': trend,
        'above_ma20': latest['close'] > latest_ma20,
        'above_ma60': latest['close'] > latest_ma60,
    }


def print_market_report(results):
    """打印市场报告"""
    print("\n" + "="*80)
    print("📊 今日大盘扫描报告")
    print("="*80)
    print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 分类统计
    rising = [r for r in results if r['change_pct'] > 0]
    falling = [r for r in results if r['change_pct'] <= 0]

    print("\n📈 市场概况:")
    print(f"  上涨指数: {len(rising)} 个")
    print(f"  下跌指数: {len(falling)} 个")

    if rising:
        avg_gain = sum(r['change_pct'] for r in rising) / len(rising)
        print(f"  平均涨幅: {avg_gain:+.2f}%")

    if falling:
        avg_drop = sum(r['change_pct'] for r in falling) / len(falling)
        print(f"  平均跌幅: {avg_drop:+.2f}%")

    # 详细数据
    print("\n📋 指数详情:")
    print("-"*80)
    print(f"{'指数':<12} {'名称':<12} {'最新价':<10} {'涨跌':<10} {'趋势':<12} {'波动率':<8}")
    print("-"*80)

    for r in sorted(results, key=lambda x: x['change_pct'], reverse=True):
        change_str = f"{r['change_pct']:+.2f}%"
        print(f"{r['symbol']:<12} {r['name']:<12} {r['close']:<10.2f} {change_str:<10} {r['trend']:<12} {r['volatility']:<8.1f}%")

    # 技术分析
    print("\n🔍 技术分析:")
    print("-"*80)

    for r in results:
        print(f"\n{r['name']} ({r['symbol']}):")
        print(f"  最新价: {r['close']:.2f} ({r['change_pct']:+.2f}%)")
        print(f"  区间: {r['low']:.2f} - {r['high']:.2f}")
        print(f"  成交量: {r['volume']:,}")
        print(f"  MA5: {r['ma5']:.2f} {'✅' if r['close'] > r['ma5'] else '❌'}")
        print(f"  MA20: {r['ma20']:.2f} {'✅' if r['close'] > r['ma20'] else '❌'}")
        print(f"  MA60: {r['ma60']:.2f} {'✅' if r['close'] > r['ma60'] else '❌'}")
        print(f"  波动率: {r['volatility']:.1f}%")
        print(f"  趋势: {r['trend']}")

    # 市场判断
    print("\n📊 市场综合判断:")
    print("-"*80)

    # 计算平均分
    avg_change = sum(r['change_pct'] for r in results) / len(results)
    above_ma20_count = sum(1 for r in results if r['above_ma20'])
    above_ma60_count = sum(1 for r in results if r['above_ma60'])

    print(f"  平均涨跌幅: {avg_change:+.2f}%")
    print(f"  站上MA20: {above_ma20_count}/{len(results)} ({above_ma20_count/len(results)*100:.0f}%)")
    print(f"  站上MA60: {above_ma60_count}/{len(results)} ({above_ma60_count/len(results)*100:.0f}%)")

    if avg_change > 1 and above_ma20_count >= len(results) * 0.6:
        sentiment = "🟢 强势市场 - 积极做多"
    elif avg_change > 0:
        sentiment = "🟡 偏强市场 - 谨慎做多"
    elif avg_change > -1:
        sentiment = "🟠 偏弱市场 - 谨慎观望"
    else:
        sentiment = "🔴 弱势市场 - 控制风险"

    print(f"  市场情绪: {sentiment}")

    print("\n" + "="*80)


def main():
    """主函数"""
    print("="*80)
    print("🤖 智能体大盘扫描系统")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    print("\n📥 正在下载大盘指数数据...")
    print("-"*80)

    results = []
    for symbol, name in INDICES.items():
        df = fetch_index_data(symbol, name)
        if df is not None:
            result = analyze_index(symbol, name, df)
            if result:
                results.append(result)
        time.sleep(0.5)  # 避免请求过快

    if results:
        print_market_report(results)
    else:
        print("\n❌ 未能获取任何指数数据")

    print("\n✅ 大盘扫描完成!")


if __name__ == '__main__':
    main()
