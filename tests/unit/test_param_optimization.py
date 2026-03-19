#!/usr/bin/env python3
"""
波浪分析器参数调优
网格搜索最佳参数组合
"""
import sys

sys.path.insert(0, 'src')

from dataclasses import dataclass

import pandas as pd

from analysis.wave import UnifiedWaveAnalyzer
from data import get_stock_data

# 测试股票 (选择3只代表性股票)
TEST_STOCKS = [
    ('600519', '贵州茅台'),  # 大市值，浪C表现较好
    ('000858', '五粮液'),     # 大市值，浪C表现较差
    ('600600', '青岛啤酒'),   # 小市值
]


@dataclass
class ParamSet:
    """参数组合"""
    name: str
    atr_mult: float
    min_wave_pct: float
    max_wave2_retrace: float
    max_wave4_retrace: float
    min_retrace: float
    min_confidence: float
    use_trend_confirm: bool


# 预定义参数组合 (基于问题分析)
PARAM_SETS = [
    # 基准参数
    ParamSet("baseline", 0.5, 0.015, 0.618, 0.5, 0.30, 0.5, True),

    # 收紧浪2回撤 (针对2浪检测失效问题)
    ParamSet("tight_w2", 0.5, 0.015, 0.50, 0.5, 0.382, 0.5, True),

    # 放宽浪4检测 (针对4浪检测不到问题)
    ParamSet("loose_w4", 0.5, 0.012, 0.618, 0.618, 0.30, 0.5, True),

    # 提高波动门槛 (减少假信号)
    ParamSet("high_vol", 0.5, 0.025, 0.618, 0.5, 0.30, 0.5, True),

    # 降低置信度门槛 (增加信号数量)
    ParamSet("low_conf", 0.5, 0.015, 0.618, 0.5, 0.30, 0.4, True),

    # 关闭趋势确认 (测试影响)
    ParamSet("no_trend", 0.5, 0.015, 0.618, 0.5, 0.30, 0.5, False),

    # ATR乘数调整
    ParamSet("high_atr", 0.8, 0.015, 0.618, 0.5, 0.30, 0.5, True),
    ParamSet("low_atr", 0.3, 0.015, 0.618, 0.5, 0.30, 0.5, True),

    # 综合优化 (收紧2浪+放宽4浪+提高波动)
    ParamSet("optimized", 0.5, 0.02, 0.50, 0.618, 0.382, 0.45, True),
]


def run_backtest_withparams(symbol: str, name: str, param_set: ParamSet) -> dict:
    """使用指定参数运行回测"""
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    if df is None or len(df) == 0:
        return None

    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # 创建分析器
    analyzer = UnifiedWaveAnalyzer(
        atr_mult=param_set.atr_mult,
        min_wave_pct=param_set.min_wave_pct,
        max_wave2_retrace=param_set.max_wave2_retrace,
        max_wave4_retrace=param_set.max_wave4_retrace,
        min_retrace=param_set.min_retrace,
        min_confidence=param_set.min_confidence,
        use_trend_confirm=param_set.use_trend_confirm
    )

    trades = []
    position = None
    entry_idx = 0

    for i in range(60, len(df)):
        row = df.iloc[i]
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']

        if i % 10 == 0 or position is None:
            window_df = df.iloc[max(0, i-60):i+1].copy()

            if not position:
                signals = analyzer.detect(window_df, mode='all')
                for sig in signals:
                    if sig.confidence >= param_set.min_confidence:
                        position = {
                            'entry_date': date_str,
                            'entry_price': price,
                            'entry_type': sig.entry_type.value
                        }
                        entry_idx = i
                        break
            else:
                pnl_pct = (price / position['entry_price'] - 1) * 100
                holding_days = i - entry_idx

                should_sell = False
                if pnl_pct <= -5 or pnl_pct >= 10 or holding_days >= 60:
                    should_sell = True

                if should_sell:
                    trades.append({
                        'entry_type': position['entry_type'],
                        'pnl_pct': pnl_pct,
                        'win': pnl_pct > 0
                    })
                    position = None

    if not trades:
        return {
            'symbol': symbol,
            'name': name,
            'param': param_set.name,
            'trades': 0,
            'win_rate': 0,
            'avg_return': 0,
            'total_return': 0,
            'c_count': 0,
            'w2_count': 0,
            'w4_count': 0
        }

    # 统计
    wins = [t for t in trades if t['win']]
    ctrades = [t for t in trades if t['entry_type'] == 'C']
    w2trades = [t for t in trades if t['entry_type'] == '2']
    w4trades = [t for t in trades if t['entry_type'] == '4']

    return {
        'symbol': symbol,
        'name': name,
        'param': param_set.name,
        'trades': len(trades),
        'win_rate': len(wins) / len(trades),
        'avg_return': sum(t['pnl_pct'] for t in trades) / len(trades),
        'total_return': sum(t['pnl_pct'] for t in trades) / 10,
        'c_count': len(ctrades),
        'w2_count': len(w2trades),
        'w4_count': len(w4trades),
        'c_win_rate': sum(1 for t in ctrades if t['win']) / len(ctrades) if ctrades else 0,
        'w2_win_rate': sum(1 for t in w2trades if t['win']) / len(w2trades) if w2trades else 0,
    }


def main():
    """主函数 - 参数调优"""
    print("🔧 波浪分析器参数调优")
    print("=" * 80)

    all_results = []

    for param_set in PARAM_SETS:
        print(f"\n{'='*80}")
        print(f"测试参数: {param_set.name}")
        print(f"{'='*80}")
        print(f"  atr_mult={param_set.atr_mult}, min_wave_pct={param_set.min_wave_pct}")
        print(f"  max_w2={param_set.max_wave2_retrace}, max_w4={param_set.max_wave4_retrace}")
        print(f"  min_retrace={param_set.min_retrace}, min_conf={param_set.min_confidence}")
        print(f"  trend_confirm={param_set.use_trend_confirm}")

        param_results = []
        for symbol, name in TEST_STOCKS:
            result = run_backtest_withparams(symbol, name, param_set)
            if result:
                param_results.append(result)
                print(f"  {symbol}: {result['trades']}笔 胜率{result['win_rate']:.1%} 收益{result['total_return']:+.2f}% (C:{result['c_count']}/2:{result['w2_count']}/4:{result['w4_count']})")

        if param_results:
            avgtrades = sum(r['trades'] for r in param_results) / len(param_results)
            avg_win_rate = sum(r['win_rate'] for r in param_results) / len(param_results)
            avg_return = sum(r['total_return'] for r in param_results) / len(param_results)
            total_c = sum(r['c_count'] for r in param_results)
            total_w2 = sum(r['w2_count'] for r in param_results)
            total_w4 = sum(r['w4_count'] for r in param_results)

            all_results.append({
                'param': param_set.name,
                'avgtrades': avgtrades,
                'avg_win_rate': avg_win_rate,
                'avg_return': avg_return,
                'total_c': total_c,
                'total_w2': total_w2,
                'total_w4': total_w4,
                'score': avg_win_rate * 0.5 + (avg_return / 10) * 0.5  # 综合评分
            })

            print(f"\n  平均: {avgtrades:.0f}笔 胜率{avg_win_rate:.1%} 收益{avg_return:+.2f}%")

    # 汇总对比
    print(f"\n{'='*80}")
    print("📊 参数对比汇总")
    print(f"{'='*80}")
    print(f"{'参数':<15} {'交易':<8} {'胜率':<10} {'收益':<10} {'C/2/4':<12} {'评分':<8}")
    print("-" * 80)

    # 按评分排序
    all_results.sort(key=lambda x: -x['score'])

    for r in all_results:
        wave_str = f"{r['total_c']}/{r['total_w2']}/{r['total_w4']}"
        print(f"{r['param']:<15} {r['avgtrades']:<8.0f} {r['avg_win_rate']:<10.1%} {r['avg_return']:<+10.1f}% {wave_str:<12} {r['score']:<8.3f}")

    # 最佳参数
    if all_results:
        best = all_results[0]
        print(f"\n{'='*80}")
        print(f"🏆 最佳参数: {best['param']}")
        print(f"  平均交易: {best['avgtrades']:.0f}笔")
        print(f"  平均胜率: {best['avg_win_rate']:.1%}")
        print(f"  平均收益: {best['avg_return']:+.2f}%")
        print(f"{'='*80}")

    print("\n✅ 参数调优完成")


if __name__ == "__main__":
    main()
