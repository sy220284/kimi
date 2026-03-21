import sys
#!/usr/bin/env python3
"""
买卖点准确率分析
用法: python analyze_trades.py [csv_path]
     不传路径时自动选取 tests/results/ 下最新的 techtrade_details_*.csv
"""

from pathlib import Path

import pandas as pd


def find_latest_csv():
    results_dir = Path('tests/results')
    files = sorted(results_dir.glob('techtrade_details_*.csv'))
    if not files:
        raise FileNotFoundError('tests/results/ 下未找到 techtrade_details_*.csv 文件')
    return files[-1]


csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_csv()
print(f'📂 读取文件: {csv_path}')

# 读取交易明细
df = pd.read_csv(csv_path)

print("=" * 70)
print("📊 买卖点准确率分析报告")
print("=" * 70)

# 1. 基础统计
total_trades = len(df)
winning_trades = len(df[df['pnl'] > 0])
losing_trades = len(df[df['pnl'] <= 0])
win_rate = winning_trades / total_trades * 100

print("\n【总体统计】")
print(f"  总交易笔数: {total_trades}")
print(f"  盈利笔数: {winning_trades} ({win_rate:.1f}%)")
print(f"  亏损笔数: {losing_trades} ({100-win_rate:.1f}%)")
print(f"  平均单笔收益: {df['pnl_pct'].mean():.2f}%")
print(f"  单笔收益中位数: {df['pnl_pct'].median():.2f}%")

# 2. 按入场波浪分析
print("\n【按入场波浪分析】")
wave_analysis = df.groupby('entry_wave').agg({
    'pnl_pct': ['count', 'mean', 'median', lambda x: (x > 0).sum() / len(x) * 100],
    'holding_days': 'mean'
}).round(2)
wave_analysis.columns = ['交易次数', '平均收益%', '收益中位数%', '胜率%', '平均持仓天数']
print(wave_analysis)

# 3. 按出场原因分析
print("\n【按出场原因分析】")
exit_analysis = df.groupby('exit_reason').agg({
    'pnl_pct': ['count', 'mean', 'median', lambda x: (x > 0).sum() / len(x) * 100],
    'holding_days': 'mean'
}).round(2)
exit_analysis.columns = ['交易次数', '平均收益%', '收益中位数%', '胜率%', '平均持仓天数']
print(exit_analysis)

# 4. 持仓天数与胜率关系
print("\n【持仓天数 vs 胜率】")
df['holding_bucket'] = pd.cut(df['holding_days'],
                               bins=[0, 10, 20, 40, 80, 200, 2000],
                               labels=['<10天', '10-20天', '20-40天', '40-80天', '80-200天', '>200天'])
holding_analysis = df.groupby('holding_bucket').agg({
    'pnl_pct': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
}).round(2)
holding_analysis.columns = ['交易次数', '平均收益%', '胜率%']
print(holding_analysis)

# 5. 买卖点精准度分析
print("\n【买卖点精准度分析】")

# 买入后短期表现（评估买点）
print("\n  单笔收益分布:")
print(f"    大亏 (<-15%): {len(df[df['pnl_pct'] < -15])}笔 ({len(df[df['pnl_pct'] < -15])/total_trades*100:.1f}%)")
print(f"    小亏 (-15%~0): {len(df[(df['pnl_pct'] >= -15) & (df['pnl_pct'] < 0)])}笔 ({len(df[(df['pnl_pct'] >= -15) & (df['pnl_pct'] < 0)])/total_trades*100:.1f}%)")
print(f"    小盈 (0~10%): {len(df[(df['pnl_pct'] >= 0) & (df['pnl_pct'] < 10)])}笔 ({len(df[(df['pnl_pct'] >= 0) & (df['pnl_pct'] < 10)])/total_trades*100:.1f}%)")
print(f"    中盈 (10%~30%): {len(df[(df['pnl_pct'] >= 10) & (df['pnl_pct'] < 30)])}笔 ({len(df[(df['pnl_pct'] >= 10) & (df['pnl_pct'] < 30)])/total_trades*100:.1f}%)")
print(f"    大盈 (>30%): {len(df[df['pnl_pct'] >= 30])}笔 ({len(df[df['pnl_pct'] >= 30])/total_trades*100:.1f}%)")

# 6. 最佳/最差交易
print("\n【TOP 5 最佳交易】")
top5 = df.nlargest(5, 'pnl_pct')[['symbol', 'entry_date', 'exit_date', 'pnl_pct', 'holding_days', 'entry_wave', 'exit_reason']]
print(top5.to_string(index=False))

print("\n【TOP 5 最差交易】")
bottom5 = df.nsmallest(5, 'pnl_pct')[['symbol', 'entry_date', 'exit_date', 'pnl_pct', 'holding_days', 'entry_wave', 'exit_reason']]
print(bottom5.to_string(index=False))

# 7. 移动止盈效果分析
print("\n【移动止盈效果分析】")
trailing_trades = df[df['exit_reason'].str.contains('trailing_stop', na=False)]
stop_loss_trades = df[df['exit_reason'] == 'stop_loss']

print("  移动止盈交易:")
print(f"    笔数: {len(trailing_trades)}")
print(f"    平均收益: {trailing_trades['pnl_pct'].mean():.2f}%")
print(f"    胜率: {(trailing_trades['pnl_pct'] > 0).sum() / len(trailing_trades) * 100:.1f}%")
print(f"    平均持仓: {trailing_trades['holding_days'].mean():.1f}天")

print("\n  止损交易:")
print(f"    笔数: {len(stop_loss_trades)}")
print(f"    平均收益: {stop_loss_trades['pnl_pct'].mean():.2f}%")
print(f"    胜率: {(stop_loss_trades['pnl_pct'] > 0).sum() / len(stop_loss_trades) * 100:.1f}%")
print(f"    平均持仓: {stop_loss_trades['holding_days'].mean():.1f}天")

# 8. 关键发现
print("\n" + "=" * 70)
print("【关键发现】")
print("=" * 70)

# Wave C vs Wave 2
c_wave = df[df['entry_wave'] == 'C']
wave2 = df[df['entry_wave'] == '2']

if len(c_wave) > 0 and len(wave2) > 0:
    c_win_rate = (c_wave['pnl_pct'] > 0).sum() / len(c_wave) * 100
    w2_win_rate = (wave2['pnl_pct'] > 0).sum() / len(wave2) * 100
    print("\n1. 入场波浪对比:")
    print(f"   Wave C: {len(c_wave)}笔, 胜率{c_win_rate:.1f}%, 平均收益{c_wave['pnl_pct'].mean():.2f}%")
    print(f"   Wave 2: {len(wave2)}笔, 胜率{w2_win_rate:.1f}%, 平均收益{wave2['pnl_pct'].mean():.2f}%")

print("\n2. 持仓时间影响:")
short_term = df[df['holding_days'] <= 20]
long_term = df[df['holding_days'] > 60]
if len(short_term) > 0 and len(long_term) > 0:
    print(f"   短期(≤20天): {len(short_term)}笔, 胜率{(short_term['pnl_pct'] > 0).sum()/len(short_term)*100:.1f}%")
    print(f"   长期(>60天): {len(long_term)}笔, 胜率{(long_term['pnl_pct'] > 0).sum()/len(long_term)*100:.1f}%")

print("\n3. 移动止盈贡献:")
trailing_pnl = trailing_trades['pnl_pct'].sum()
total_pnl = df['pnl_pct'].sum()
print(f"   移动止盈交易贡献: {trailing_pnl:.1f}% (占总收益 {trailing_pnl/total_pnl*100:.1f}%)")
print(f"   止损交易贡献: {stop_loss_trades['pnl_pct'].sum():.1f}%")

print("\n" + "=" * 70)
