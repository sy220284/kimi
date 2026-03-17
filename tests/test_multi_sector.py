#!/usr/bin/env python3
"""
多行业多市值股票波浪策略测试
覆盖: 白酒、乳制品、调味品、啤酒、新能源、银行、科技
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from collections import Counter

print("="*80)
print("🎯 多行业多市值股票波浪策略测试")
print("="*80)

# 按行业分类测试股票
test_stocks = {
    "🍶 白酒 (大市值)": [
        ('600519', '贵州茅台', 'large'),
        ('000858', '五粮液', 'large'),
        ('000568', '泸州老窖', 'mid'),
    ],
    "🥛 乳制品 (中市值)": [
        ('600887', '伊利股份', 'large'),
        ('600597', '光明乳业', 'small'),
    ],
    "🧂 调味品 (中市值)": [
        ('603288', '海天味业', 'large'),
        ('600872', '中炬高新', 'mid'),
    ],
    "🍺 啤酒 (中市值)": [
        ('600600', '青岛啤酒', 'mid'),
        ('000729', '燕京啤酒', 'small'),
    ],
    "🔋 新能源 (大市值)": [
        ('300750', '宁德时代', 'large'),
        ('002594', '比亚迪', 'large'),
    ],
    "🏦 银行 (大市值)": [
        ('000001', '平安银行', 'large'),
        ('600036', '招商银行', 'large'),
    ],
    "💻 科技 (中小市值)": [
        ('600556', '天下秀', 'small'),
        ('002184', '海得控制', 'small'),
    ],
}

results = []

for sector, stocks in test_stocks.items():
    print(f"\n{sector}")
    print("-"*80)
    
    sector_results = []
    
    for symbol, name, size in stocks:
        try:
            df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
            
            analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
            strategy = WaveStrategy(
                initial_capital=1000000,
                position_size=0.2,
                stop_loss_pct=0.05,
                min_confidence=0.35,
                use_resonance=False,
                min_holding_days=3,
                use_trend_filter=False,
                use_dynamic_target=True,
                target_proximity_pct=0.05,
            )
            
            backtester = WaveBacktester(analyzer)
            backtester.strategy = strategy
            
            result = backtester.run(symbol, df, reanalyze_every=30)
            
            # 统计浪号分布
            wave_dist = Counter([t.entry_wave for t in result.trades if t.entry_wave])
            main_wave = max(wave_dist, key=wave_dist.get) if wave_dist else 'None'
            
            print(f"  {symbol} {name:8s} ({size:6s}): "
                  f"{result.total_trades:2d}次 | 胜率{result.win_rate:5.1%} | "
                  f"收益{result.total_return_pct:+6.1f}% | 回撤{result.max_drawdown_pct:5.1f}% | "
                  f"主要浪{main_wave}")
            
            sector_results.append({
                'symbol': symbol,
                'name': name,
                'size': size,
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'drawdown': result.max_drawdown_pct,
                'sharpe': result.sharpe_ratio,
                'main_wave': main_wave
            })
            
        except Exception as e:
            print(f"  {symbol} {name:8s}: 错误 - {str(e)[:30]}")
    
    results.extend(sector_results)

# 汇总统计
print("\n" + "="*80)
print("📊 汇总统计")
print("="*80)

# 按市值分类
size_groups = {'large': '大市值', 'mid': '中市值', 'small': '小市值'}
for size_key, size_name in size_groups.items():
    size_results = [r for r in results if r['size'] == size_key]
    if size_results:
        avg_return = sum(r['return'] for r in size_results) / len(size_results)
        avg_winrate = sum(r['win_rate'] for r in size_results) / len(size_results)
        total_trades = sum(r['trades'] for r in size_results)
        print(f"{size_name}: 平均收益 {avg_return:+.1f}% | 平均胜率 {avg_winrate:.1%} | 总交易 {total_trades}次")

# 按收益排序
print(f"\n{'='*80}")
print("🏆 收益排名 (Top 10)")
print(f"{'='*80}")
print(f"{'排名':<4} {'股票':<8} {'名称':<10} {'收益':<10} {'胜率':<8} {'交易':<6} {'回撤':<8}")
print("-"*60)

sorted_results = sorted(results, key=lambda x: x['return'], reverse=True)
for i, r in enumerate(sorted_results[:10], 1):
    print(f"{i:<4} {r['symbol']:<8} {r['name']:<10} {r['return']:<+10.1f}% {r['win_rate']:<8.1%} {r['trades']:<6} {r['drawdown']:<8.1f}%")

# 统计买入浪号分布
print(f"\n{'='*80}")
print("🌊 买入浪号分布统计")
print(f"{'='*80}")
all_waves = [r['main_wave'] for r in results]
wave_counter = Counter(all_waves)
for wave, count in wave_counter.most_common():
    print(f"  浪{wave}: {count}只股票 ({count/len(results):.1%})")

print("\n✅ 测试完成")
