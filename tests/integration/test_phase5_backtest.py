#!/usr/bin/env python3
"""
Phase 5 测试 - 回测验证
验证波浪策略的历史表现
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


from analysis.backtest.wave_backtester import WaveBacktester
from analysis.wave import UnifiedWaveAnalyzer
from data import get_stock_data

print("="*80)
print("📈 Phase 5 测试 - 回测验证")
print("="*80)

# 初始化
analyzer = UnifiedWaveAnalyzer()
backtester = WaveBacktester(analyzer)

# 测试股票
symbols = [
    ("600138", "中青旅"),
    ("002184", "海得控制"),
    ("600556", "天下秀"),
    ("002358", "森源电气"),
]

all_results = []

for symbol, name in symbols:
    print(f"\n{'='*80}")
    print(f"📊 {name} ({symbol})")
    print('='*80)

    try:
        # 获取2年历史数据
        df = get_stock_data(symbol, '2023-01-01', '2025-12-31')

        # 运行回测
        result = backtester.run(symbol, df, reanalyze_every=5)

        # 生成报告
        report = backtester.generate_report(result)
        print(report)

        all_results.append({
            'symbol': symbol,
            'name': name,
            'result': result
        })

    except Exception as e:
        print(f"❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()

# 汇总对比
print(f"\n\n{'='*80}")
print("📋 四只股票回测汇总")
print("="*80)

print(f"\n{'股票':<10} {'交易次数':>8} {'胜率':>8} {'总收益':>10} {'最大回撤':>10} {'Sharpe':>8}")
print("-"*60)

for item in all_results:
    r = item['result']
    print(f"{item['name']:<8} {r.total_trades:>8} {r.win_rate:>7.1%} "
          f"{r.total_return_pct:>9.1f}% {r.max_drawdown_pct:>9.1f}% {r.sharpe_ratio:>7.2f}")

# 计算组合表现
if all_results:
    total_trades = sum(r['result'].total_trades for r in all_results)
    avg_win_rate = sum(r['result'].win_rate for r in all_results) / len(all_results)
    avg_return = sum(r['result'].total_return_pct for r in all_results) / len(all_results)

    print(f"\n{'组合平均':<8} {total_trades:>8} {avg_win_rate:>7.1%} "
          f"{avg_return:>9.1f}%")

print("\n" + "="*80)
print("Phase 5 回测完成!")
print("="*80)
