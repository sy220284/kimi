#!/usr/bin/env python3
"""
回测问题诊断
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.data import get_stock_data
from src.analysis.wave import UnifiedWaveAnalyzer

SYMBOL = '600519'
START = '2024-01-01'
END = '2026-03-16'

print("回测问题诊断")
print("=" * 70)

df = get_stock_data(SYMBOL, START, END)
df['date'] = pd.to_datetime(df['date'])
df['ma200'] = df['close'].rolling(200).mean()

analyzer = UnifiedWaveAnalyzer(
    use_resonance=True,
    min_resonance_score=0.3,
    trend_ma_period=200
)

# 模拟回测流程
print("\n逐日诊断 (最近20个交易日):")
print("-" * 70)
print(f"{'日期':<12} {'价格':>10} {'MA200':>10} {'趋势':>6} {'信号数':>6}")
print("-" * 70)

for i in range(len(df)-20, len(df)):
    row = df.iloc[i]
    date = row['date'].strftime('%m-%d')
    price = row['close']
    ma200 = row['ma200']
    
    # 趋势判断
    if pd.notna(ma200):
        if price > ma200 * 1.05:
            trend = 'UP'
        elif price < ma200 * 0.95:
            trend = 'DOWN'
        else:
            trend = 'SIDE'
    else:
        trend = 'N/A'
    
    # 检测信号 (使用最近60天数据)
    lookback = max(0, i - 60)
    window_df = df.iloc[lookback:i+1].copy()
    signals = analyzer.detect(window_df, mode='all') if len(window_df) >= 30 else []
    
    # 统计有效信号
    valid_signals = [s for s in signals if s.is_valid and s.confidence >= 0.5]
    
    print(f"{date:<12} {price:>10.2f} {ma200:>10.2f} {trend:>6} {len(valid_signals):>6}")
    
    if valid_signals:
        for sig in valid_signals:
            aligned = "✓" if sig.trend_aligned else "✗"
            print(f"    → {sig.entry_type.value}浪 ¥{sig.entry_price:.2f} 置信{sig.confidence:.2f} 趋势{aligned}")

print("-" * 70)
print("\n诊断结论:")
print("1. 价格vs MA200: 当前价格在MA200上方/下方?")
print("2. 信号趋势对齐: 信号是否与200日均线趋势一致?")
print("3. 共振分数: 是否满足min_resonance_score阈值?")
