#!/usr/bin/env python3
"""
多股票详细操作记录 - 覆盖各种买入浪号
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from collections import Counter, defaultdict

# 扩展测试股票列表 - 不同行业不同特性
test_stocks = [
    # 白酒
    ('600519', '贵州茅台'),
    ('000858', '五粮液'),
    ('000568', '泸州老窖'),
    # 啤酒
    ('600600', '青岛啤酒'),
    ('000729', '燕京啤酒'),
    # 新能源
    ('300750', '宁德时代'),
    ('002594', '比亚迪'),
    ('601012', '隆基绿能'),
    # 银行
    ('600036', '招商银行'),
    ('000001', '平安银行'),
    # 医药
    ('600276', '恒瑞医药'),
    ('000538', '云南白药'),
    # 科技
    ('000063', '中兴通讯'),
    ('002230', '科大讯飞'),
    # 消费
    ('600887', '伊利股份'),
    ('603288', '海天味业'),
    # 地产
    ('000002', '万科A'),
    ('600048', '保利发展'),
    # 汽车
    ('601633', '长城汽车'),
    ('000625', '长安汽车'),
]

print("="*100)
print("🎯 多股票详细操作记录 - 覆盖各种买入浪号")
print("="*100)

all_results = []
wave_distribution = defaultdict(list)  # 按浪号分组的股票

for symbol, name in test_stocks:
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
        
        # 统计买入浪号
        wave_dist = Counter([t.entry_wave for t in result.trades if t.entry_wave])
        main_wave = max(wave_dist, key=wave_dist.get) if wave_dist else 'None'
        
        # 记录到全局分布
        for wave in wave_dist:
            wave_distribution[wave].append({
                'symbol': symbol,
                'name': name,
                'count': wave_dist[wave],
                'return': result.total_return_pct,
                'win_rate': result.win_rate
            })
        
        all_results.append({
            'symbol': symbol,
            'name': name,
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'return': result.total_return_pct,
            'drawdown': result.max_drawdown_pct,
            'main_wave': main_wave,
            'wave_dist': dict(wave_dist)
        })
        
        print(f"✓ {symbol} {name:10s}: {result.total_trades:2d}次 | 胜率{result.win_rate:5.1%} | 收益{result.total_return_pct:+6.1f}% | 主要浪{main_wave}")
        
    except Exception as e:
        print(f"✗ {symbol} {name:10s}: 错误 - {str(e)[:40]}")

# 汇总统计
print(f"\n{'='*100}")
print("📊 汇总统计")
print(f"{'='*100}")

print(f"\n测试股票总数: {len(all_results)}只")
print(f"总交易次数: {sum(r['trades'] for r in all_results)}次")

avg_return = sum(r['return'] for r in all_results) / len(all_results)
avg_winrate = sum(r['win_rate'] for r in all_results) / len(all_results)
print(f"平均收益: {avg_return:+.2f}%")
print(f"平均胜率: {avg_winrate:.1%}")

# 按买入浪号分类统计
print(f"\n{'='*100}")
print("🌊 按买入浪号分类统计")
print(f"{'='*100}")

for wave in sorted(wave_distribution.keys(), key=lambda x: str(x)):
    stocks = wave_distribution[wave]
    avg_ret = sum(s['return'] for s in stocks) / len(stocks)
    avg_wr = sum(s['win_rate'] for s in stocks) / len(stocks)
    
    print(f"\n浪{wave}: {len(stocks)}只股票")
    print(f"  平均收益: {avg_ret:+.2f}% | 平均胜率: {avg_wr:.1%}")
    print(f"  股票列表: ", end="")
    for s in stocks[:5]:
        print(f"{s['symbol']}({s['return']:+.1f}%) ", end="")
    if len(stocks) > 5:
        print(f"...等{len(stocks)-5}只")
    else:
        print()

# 显示每个浪号的典型交易案例
print(f"\n{'='*100}")
print("📝 各浪号典型交易案例")
print(f"{'='*100}")

# 选择几只代表性股票展示详细交易
demo_stocks = ['600519', '600600', '300750', '600036']

for symbol in demo_stocks:
    result_info = next((r for r in all_results if r['symbol'] == symbol), None)
    if not result_info:
        continue
    
    name = result_info['name']
    print(f"\n📈 {symbol} {name} - 浪{result_info['main_wave']}买入案例")
    print(f"{'─'*80}")
    
    # 重新运行回测获取交易详情
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
    
    # 显示前3笔交易
    for i, trade in enumerate(result.trades[:3], 1):
        print(f"  交易#{i}: {trade.entry_date} 浪{trade.entry_wave}→{trade.expected_wave}")
        print(f"         买入¥{trade.entry_price:.2f} → 卖出¥{trade.exit_price:.2f} ({trade.pnl_pct:+.2f}%)")
        if trade.target_price:
            target_pct = (trade.target_price / trade.entry_price - 1) * 100
            print(f"         目标¥{trade.target_price:.2f} (+{target_pct:.1f}%) | 止损¥{trade.stop_loss:.2f}")

# 收益排名
print(f"\n{'='*100}")
print("🏆 收益排名 Top 10")
print(f"{'='*100}")
print(f"{'排名':<4} {'股票':<8} {'名称':<10} {'收益':<10} {'胜率':<8} {'交易':<6} {'主要浪号':<8}")
print("-"*60)

sorted_results = sorted(all_results, key=lambda x: x['return'], reverse=True)
for i, r in enumerate(sorted_results[:10], 1):
    print(f"{i:<4} {r['symbol']:<8} {r['name']:<10} {r['return']:<+10.1f}% {r['win_rate']:<8.1%} {r['trades']:<6} {r['main_wave']:<8}")

print("\n✅ 分析完成")
