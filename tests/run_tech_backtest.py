"""
科技板块回测分析 - 移动止盈策略
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from datetime import datetime
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data import get_db_manager

def get_tech_stocks():
    """从数据库获取科技板块股票"""
    db_manager = get_db_manager()
    
    # 科技板块股票列表（与下载脚本一致）
    tech_symbols = [
        # 大盘股
        '000063', '002230', '300750', '600584', '603501', 
        '688981', '688012', '688008', '000938', '600570',
        # 中盘股
        '002371', '300014', '300124', '300433', '300408',
        '603019', '603893', '688111', '688126', '688599',
        '300496', '300661', '300782', '600460', '600703',
        # 小盘股
        '300474', '300223', '300373', '300666', '300724',
        '688002', '688009', '688188', '688256', '688390',
        '688396', '688521', '688561', '688728', '300604',
    ]
    
    # 查询数据库中实际存在的股票
    query = """
    SELECT DISTINCT symbol,
           MIN(date) as start_date,
           MAX(date) as end_date,
           COUNT(*) as records
    FROM marketdata
    WHERE symbol IN %s
    GROUP BY symbol
    ORDER BY records DESC
    """
    
    results = db_manager.pg.execute(query, (tuple(tech_symbols),), fetch=True)
    df = pd.DataFrame(results)
    return df

def run_backtest_for_stock(symbol, analyzer, start_date='2017-01-01', end_date='2024-12-31'):
    """对单只股票运行回测"""
    try:
        db_manager = get_db_manager()
        df = db_manager.get_stock_data(symbol, start_date=start_date, end_date=end_date)

        if df is None or len(df) < 200:
            return None, []

        df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        df['date'] = pd.to_datetime(df['date'])

        # 移动止盈策略
        strategy = WaveStrategy(
            initial_capital=100000,
            position_size=0.2,
            max_positions=3,
            max_total_position=0.8,
            commission_rate=0.0003,
            stamp_tax_rate=0.001,
            slippage_rate=0.001,
            min_holding_days=3,
            use_trend_filter=True,
            trend_ma_period=200,
            stop_loss_pct=0.08,  # 8%止损
            # 移动止盈参数
            use_trailing_stop=True,
            trailing_stop_pct=0.08,
            trailing_stop_activation=1.0,
        )

        backtester = WaveBacktester(analyzer)
        backtester.strategy = strategy
        result = backtester.run(symbol, df, reanalyze_every=5)

        trade_details = [t.to_dict() for t in result.trades if t.status == 'closed']

        return {
            'symbol': symbol,
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'return': result.total_return_pct,
            'avg_return': result.avg_return_pertrade,
            'max_dd': result.max_drawdown_pct,
            'sharpe': result.sharpe_ratio,
            'data_days': len(df)
        }, trade_details
    except Exception as e:
        print(f"  ❌ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None, []

def main():
    print("\n" + "="*70)
    print("🔬 科技板块回测分析 [移动止盈]")
    print("回测区间: 2017-01-01 ~ 2024-12-31")
    print("策略: 8%止损 + 8%移动止盈")
    print("="*70)
    print(f"开始时间: {datetime.now()}")

    # 获取科技板块股票
    print("\n📊 加载股票列表...")
    stocks_df = get_tech_stocks()
    print(f"数据库共有 {len(stocks_df)} 只科技股票")

    if stocks_df.empty:
        print("❌ 没有科技板块数据")
        return

    # 创建回测器
    analyzer = UnifiedWaveAnalyzer()

    results = []
    alltrade_details = []

    for i, row in stocks_df.iterrows():
        symbol = row['symbol']
        print(f"\n[{i+1}/{len(stocks_df)}] {symbol} ...", end=" ", flush=True)

        result, trade_details = run_backtest_for_stock(symbol, analyzer)
        if result:
            print(f"✅ 交易{result['trades']}次 收益{result['return']:.2f}%")
            results.append(result)
            alltrade_details.extend(trade_details)
        else:
            print("❌ 跳过")

    # 汇总报告
    if results:
        print("\n" + "="*70)
        print("📈 汇总报告")
        print("="*70)

        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values('return', ascending=False)

        print(f"\n{'股票':<10} {'交易':<6} {'胜率':<8} {'收益':<10} {'平均':<10} {'回撤':<10} {'Sharpe'}")
        print("-" * 70)

        for _, row in df_results.iterrows():
            print(f"{row['symbol']:<10} {row['trades']:<6} "
                  f"{row['win_rate']:>6.1%} {row['return']:>8.2f}% "
                  f"{row['avg_return']:>8.2f}% {row['max_dd']:>8.2f}% {row['sharpe']:>6.2f}")

        print(f"\n{'='*70}")
        print("📊 统计摘要")
        print(f"{'='*70}")

        print("\n总体表现:")
        print(f"  测试股票: {len(df_results)} 只")
        print(f"  平均胜率: {df_results['win_rate'].mean():.1%}")
        print(f"  平均收益: {df_results['return'].mean():.2f}%")
        print(f"  平均回撤: {df_results['max_dd'].mean():.2f}%")
        print(f"  平均Sharpe: {df_results['sharpe'].mean():.2f}")
        print(f"  平均交易次数: {df_results['trades'].mean():.0f}")

        print("\n收益分布:")
        positive = (df_results['return'] > 0).sum()
        negative = (df_results['return'] <= 0).sum()
        print(f"  盈利: {positive} 只 ({positive/len(df_results):.1%})")
        print(f"  亏损: {negative} 只 ({negative/len(df_results):.1%})")
        print(f"  最好: {df_results['return'].max():.2f}% ({df_results.loc[df_results['return'].idxmax(), 'symbol']})")
        print(f"  最差: {df_results['return'].min():.2f}% ({df_results.loc[df_results['return'].idxmin(), 'symbol']})")

        # 移动止盈效果分析
        if alltrade_details:
            dftrades = pd.DataFrame(alltrade_details)
            trailing_count = dftrades[dftrades['exit_reason'].str.contains('trailing_stop', na=False)].shape[0]
            target_reached = dftrades[dftrades['exit_reason'] == 'target_reached'].shape[0]
            target_proximity = dftrades[dftrades['exit_reason'] == 'target_proximity'].shape[0]
            stop_loss_count = dftrades[dftrades['exit_reason'] == 'stop_loss'].shape[0]
            total_count = len(dftrades)
            
            print("\n卖出原因分布:")
            print(f"  移动止盈: {trailing_count} 笔 ({trailing_count/total_count*100:.1f}%)")
            print(f"  目标价: {target_reached} 笔 ({target_reached/total_count*100:.1f}%)")
            print(f"  接近目标: {target_proximity} 笔 ({target_proximity/total_count*100:.1f}%)")
            print(f"  止损: {stop_loss_count} 笔 ({stop_loss_count/total_count*100:.1f}%)")
            
            # 移动止盈收益分析
            if trailing_count > 0:
                trailingtrades = dftrades[dftrades['exit_reason'].str.contains('trailing_stop', na=False)]
                print("\n移动止盈交易:")
                print(f"  平均收益: {trailingtrades['pnl_pct'].mean():.2f}%")
                print(f"  胜率: {(trailingtrades['pnl_pct'] > 0).mean():.1%}")

        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        output_file = f"tests/results/tech_backtest_{timestamp}.csv"
        df_results.to_csv(output_file, index=False)
        print(f"\n💾 汇总结果: {output_file}")

        if alltrade_details:
            trades_file = f"tests/results/techtrade_details_{timestamp}.csv"
            pd.DataFrame(alltrade_details).to_csv(trades_file, index=False)
            print(f"💾 交易明细: {trades_file} ({len(alltrade_details)} 笔)")

    print(f"\n{'='*70}")
    print(f"✅ 回测完成 | {datetime.now()}")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
