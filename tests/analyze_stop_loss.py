"""
分析止损后的股价走势
判断是趋势走坏还是被洗盘
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data import get_db_manager


def analyze_stop_loss_stocks():
    """分析所有发生止损的股票，统计止损后走势"""
    print("\n" + "="*70)
    print("🔍 止损后股价走势分析")
    print("="*70)
    
    # 读取交易明细
    df_trades = pd.read_csv('tests/results/trade_details_20260318_0921.csv')
    stop_loss_trades = df_trades[df_trades['exit_reason'] == 'stop_loss'].copy()
    
    print(f"\n总止损交易: {len(stop_loss_trades)} 笔")
    
    # 获取数据库连接
    db_manager = get_db_manager()
    
    # 统计止损后走势
    results = []
    
    for idx, trade in stop_loss_trades.iterrows():
        symbol = trade['symbol']
        exit_date = trade['exit_date']
        exit_price = trade['exit_price']
        
        # 获取后续数据
        try:
            df = db_manager.get_stock_data(symbol)
            if df is None or len(df) < 10:
                continue
            
            df['date'] = pd.to_datetime(df['date'])
            exit_dt = pd.to_datetime(exit_date)
            
            # 找到止损日之后的走势
            future_data = df[df['date'] > exit_dt].copy()
            if len(future_data) < 5:
                continue
            
            # 计算后续各时间点的价格变化
            future_prices = {}
            for days in [1, 3, 5, 10, 20, 60]:
                if len(future_data) >= days:
                    future_price = future_data.iloc[days-1]['close']
                    change_pct = (future_price - exit_price) / exit_price * 100
                    future_prices[f'{days}d'] = round(change_pct, 2)
                else:
                    future_prices[f'{days}d'] = None
            
            # 判断后续走势
            if future_prices.get('20d') is not None:
                if future_prices['20d'] > 5:
                    trend = '继续上涨'
                elif future_prices['20d'] < -5:
                    trend = '趋势走坏'
                else:
                    trend = '震荡整理'
            else:
                trend = '数据不足'
            
            # 找后续最高点
            if len(future_data) > 0:
                max_future_price = future_data.head(60)['close'].max() if len(future_data) >= 60 else future_data['close'].max()
                max_gain = (max_future_price - exit_price) / exit_price * 100
            else:
                max_gain = 0
            
            results.append({
                'symbol': symbol,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'pnl_pct': trade['pnl_pct'],
                'holding_days': trade['holding_days'],
                'entry_wave': trade['entry_wave'],
                **future_prices,
                'max_60d_gain': round(max_gain, 2),
                'trend_judgment': trend
            })
            
        except Exception as e:
            continue
    
    # 汇总分析
    df_results = pd.DataFrame(results)
    
    print(f"\n成功分析: {len(df_results)} 笔止损交易")
    
    # 后续走势统计
    print("\n" + "-"*70)
    print("📊 止损后平均走势")
    print("-"*70)
    
    for col in ['1d', '3d', '5d', '10d', '20d', '60d']:
        if col in df_results.columns:
            avg_change = df_results[col].mean()
            positive_pct = (df_results[col] > 0).mean()
            print(f"  止损后{col:>3}: 平均{avg_change:>+6.2f}% | 上涨比例{positive_pct:>5.1%}")
    
    # 趋势判断分布
    print("\n" + "-"*70)
    print("🎯 止损后20天趋势判断")
    print("-"*70)
    
    trend_dist = df_results['trend_judgment'].value_counts()
    for trend, count in trend_dist.items():
        pct = count / len(df_results)
        print(f"  {trend}: {count} 笔 ({pct:.1%})")
    
    # 被洗盘 vs 真走坏分析
    print("\n" + "-"*70)
    print("💡 洗盘 vs 真走坏分析")
    print("-"*70)
    
    # 如果止损后20天上涨超过5%，认为是被洗盘
    washed_out = df_results[df_results['20d'] > 5]
    real_drop = df_results[df_results['20d'] < -5]
    
    print(f"\n被洗盘（止损后20天涨>5%）:")
    print(f"  笔数: {len(washed_out)} ({len(washed_out)/len(df_results):.1%})")
    print(f"  平均止损亏损: {washed_out['pnl_pct'].mean():.2f}%")
    print(f"  止损后平均涨幅: {washed_out['20d'].mean():.2f}%")
    print(f"  60天内最高涨幅: {washed_out['max_60d_gain'].mean():.2f}%")
    
    print(f"\n真走坏（止损后20天跌>5%）:")
    print(f"  笔数: {len(real_drop)} ({len(real_drop)/len(df_results):.1%})")
    print(f"  平均止损亏损: {real_drop['pnl_pct'].mean():.2f}%")
    print(f"  止损后平均跌幅: {real_drop['20d'].mean():.2f}%")
    
    # 按浪型分析
    print("\n" + "-"*70)
    print("🌊 按买入浪型分析止损效果")
    print("-"*70)
    
    wave_analysis = df_results.groupby('entry_wave').agg({
        '20d': 'mean',
        'max_60d_gain': 'mean',
        'symbol': 'count'
    }).round(2)
    print(wave_analysis)
    
    # 典型案例
    print("\n" + "-"*70)
    print("📌 典型案例 - 被洗盘（止损后大涨）")
    print("-"*70)
    
    top_washed = washed_out.nlargest(5, '20d')
    for _, row in top_washed.iterrows():
        print(f"\n{row['symbol']} @ {row['exit_date']}")
        print(f"  止损价: {row['exit_price']:.2f}, 止损亏损: {row['pnl_pct']:.2f}%")
        print(f"  止损后20天: {row['20d']:+.2f}%")
        print(f"  60天最高: {row['max_60d_gain']:+.2f}%")
    
    print("\n" + "-"*70)
    print("📌 典型案例 - 真走坏（止损后继续跌）")
    print("-"*70)
    
    top_drops = real_drop.nsmallest(5, '20d')
    for _, row in top_drops.iterrows():
        print(f"\n{row['symbol']} @ {row['exit_date']}")
        print(f"  止损价: {row['exit_price']:.2f}, 止损亏损: {row['pnl_pct']:.2f}%")
        print(f"  止损后20天: {row['20d']:+.2f}%")
    
    # 保存详细分析
    output_file = f"tests/results/stop_loss_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df_results.to_csv(output_file, index=False)
    print(f"\n💾 详细分析已保存: {output_file}")
    
    print("\n" + "="*70)
    print("✅ 分析完成")
    print("="*70)


if __name__ == '__main__':
    analyze_stop_loss_stocks()
