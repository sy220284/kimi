"""
分层参数回测测试 - 科创板10% vs 主板8%
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from datetime import datetime
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data import get_db_manager

def get_stock_tier(symbol):
    """
    股票波动率分层
    - Tier 1 (高波动): 科创板688开头
    - Tier 2 (中波动): 主板60/00开头
    """
    if symbol.startswith('688'):
        return 'high'
    elif symbol.startswith('300'):
        return 'medium'  # 创业板算中波动
    else:
        return 'medium'  # 主板默认中波动

def get_strategy_by_tier(tier, use_tiered=True):
    """根据分层获取策略参数"""
    if not use_tiered:
        # 统一8%参数（基准）
        return WaveStrategy(
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
            stop_loss_pct=0.08,
            use_trailing_stop=True,
            trailing_stop_pct=0.08,
            trailing_stop_activation=1.0,
        )
    
    if tier == 'high':
        # 科创板：10%止损 + 10%移动止盈
        return WaveStrategy(
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
            stop_loss_pct=0.10,  # 10%止损
            use_trailing_stop=True,
            trailing_stop_pct=0.10,  # 10%移动止盈
            trailing_stop_activation=1.0,
        )
    else:
        # 主板/创业板：8%止损 + 8%移动止盈
        return WaveStrategy(
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
            stop_loss_pct=0.08,
            use_trailing_stop=True,
            trailing_stop_pct=0.08,
            trailing_stop_activation=1.0,
        )

def run_tiered_backtest(mode='tiered'):
    """
    跑分层参数回测
    mode: 'tiered' 或 'baseline'(统一8%)
    """
    print(f"\n{'='*70}")
    if mode == 'tiered':
        print("🔬 分层参数回测：科创板10% | 主板8%")
    else:
        print("🔬 基准参数回测：统一8%")
    print(f"{'='*70}")
    print(f"开始时间: {datetime.now()}")
    
    # 获取科技板块股票
    tech_symbols = [
        '000063', '002230', '300750', '600584', '603501', 
        '688981', '688012', '688008', '000938', '600570',
        '002371', '300014', '300124', '300433', '300408',
        '603019', '603893', '688111', '688126', '688599',
        '300496', '300661', '300782', '600460', '600703',
        '300474', '300223', '300373', '300666', '300724',
        '688002', '688009', '688188', '688256', '688390',
        '688396', '688521', '688561', '688728', '300604',
    ]
    
    # 统计分层
    high_tier = [s for s in tech_symbols if s.startswith('688')]
    medium_tier = [s for s in tech_symbols if not s.startswith('688')]
    print(f"\n分层统计:")
    print(f"  科创板(高波动): {len(high_tier)}只")
    print(f"  主板/创业板(中波动): {len(medium_tier)}只")
    
    db_manager = get_db_manager()
    analyzer = UnifiedWaveAnalyzer()
    
    results = []
    all_trade_details = []
    
    for i, symbol in enumerate(tech_symbols, 1):
        tier = get_stock_tier(symbol)
        tier_label = "科创" if tier == 'high' else "主板"
        
        try:
            df = db_manager.get_stock_data(symbol, start_date='2017-01-01', end_date='2024-12-31')
            if df is None or len(df) < 200:
                continue
            
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            df['date'] = pd.to_datetime(df['date'])
            
            # 根据分层获取策略
            strategy = get_strategy_by_tier(tier, use_tiered=(mode=='tiered'))
            
            backtester = WaveBacktester(analyzer)
            backtester.strategy = strategy
            result = backtester.run(symbol, df, reanalyze_every=5)
            
            trade_details = [t.to_dict() for t in result.trades if t.status == 'closed']
            
            results.append({
                'symbol': symbol,
                'tier': tier,
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'avg_return': result.avg_return_per_trade,
                'max_dd': result.max_drawdown_pct,
                'sharpe': result.sharpe_ratio,
            })
            all_trade_details.extend(trade_details)
            
            print(f"[{i}/{len(tech_symbols)}] {symbol}({tier_label}): 收益{result.total_return_pct:+.2f}% 交易{result.total_trades}次")
            
        except Exception as e:
            print(f"[{i}/{len(tech_symbols)}] {symbol}: 错误 - {e}")
    
    # 汇总
    if results:
        df_results = pd.DataFrame(results)
        
        # 按分层统计
        print(f"\n{'='*70}")
        print("📊 分层统计结果")
        print(f"{'='*70}")
        
        high_df = df_results[df_results['tier'] == 'high']
        medium_df = df_results[df_results['tier'] == 'medium']
        
        print(f"\n科创板 ({len(high_df)}只):")
        print(f"  平均收益: {high_df['return'].mean():+.2f}%")
        print(f"  平均胜率: {high_df['win_rate'].mean():.1%}")
        print(f"  盈利比例: {(high_df['return'] > 0).sum()}/{len(high_df)} ({(high_df['return'] > 0).mean():.1%})")
        
        print(f"\n主板/创业板 ({len(medium_df)}只):")
        print(f"  平均收益: {medium_df['return'].mean():+.2f}%")
        print(f"  平均胜率: {medium_df['win_rate'].mean():.1%}")
        print(f"  盈利比例: {(medium_df['return'] > 0).sum()}/{len(medium_df)} ({(medium_df['return'] > 0).mean():.1%})")
        
        print(f"\n总体 ({len(df_results)}只):")
        print(f"  平均收益: {df_results['return'].mean():+.2f}%")
        print(f"  平均胜率: {df_results['win_rate'].mean():.1%}")
        print(f"  盈利比例: {(df_results['return'] > 0).sum()}/{len(df_results)} ({(df_results['return'] > 0).mean():.1%})")
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        mode_str = 'tiered' if mode == 'tiered' else 'baseline'
        output_file = f"tests/results/tech_{mode_str}_{timestamp}.csv"
        df_results.to_csv(output_file, index=False)
        print(f"\n💾 结果保存: {output_file}")
        
        if all_trade_details:
            trades_file = f"tests/results/tech_{mode_str}_trades_{timestamp}.csv"
            pd.DataFrame(all_trade_details).to_csv(trades_file, index=False)
            print(f"💾 交易明细: {trades_file}")
        
        return df_results, all_trade_details
    
    return None, None

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['tiered', 'baseline'], default='tiered')
    args = parser.parse_args()
    
    run_tiered_backtest(mode=args.mode)
