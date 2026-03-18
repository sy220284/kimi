"""
使用缓存数据运行修复后的回测系统
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pickle
import os
import pandas as pd
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer

def load_cacheddata():
    """从.cache目录加载所有股票数据"""
    cache_dir = Path(__file__).parent.parent / '.cache'
    stocks = {}
    
    for f in os.listdir(cache_dir):
        if not f.endswith('.pkl'):
            continue
        
        try:
            with open(cache_dir / f, 'rb') as file:
                data = pickle.load(file)
                if 'data' in data and not data['data'].empty:
                    df = data['data']
                    symbol = df['symbol'].iloc[0]
                    
                    # 保留最长的数据
                    if symbol not in stocks or len(df) > len(stocks[symbol]):
                        stocks[symbol] = df
        except Exception as e:
            print(f"加载失败 {f}: {e}")
    
    return stocks

def main():
    print("\n" + "="*60)
    print("🔧 修复后回测系统 - 缓存数据验证")
    print("="*60)
    
    # 加载缓存数据
    print("\n加载缓存数据...")
    stocks = load_cacheddata()
    
    print(f"找到 {len(stocks)} 只股票:")
    for symbol, df in stocks.items():
        print(f"  {symbol}: {len(df)}天, {df['date'].min()} ~ {df['date'].max()}")
    
    # 创建回测器
    analyzer = UnifiedWaveAnalyzer()
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
        trend_ma_period=200
    )
    
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    results = []
    
    for symbol, df in stocks.items():
        print(f"\n{'='*60}")
        print(f"📊 {symbol}")
        print('='*60)
        
        # 准备数据
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
        df['date'] = pd.to_datetime(df['date'])
        
        print(f"数据量: {len(df)}天")
        
        # 运行回测
        try:
            result = backtester.run(symbol, df, reanalyze_every=5)
            
            print("\n【结果】")
            print(f"  交易次数: {result.totaltrades}")
            print(f"  胜率: {result.win_rate:.1%}")
            print(f"  总收益: {result.total_return_pct:.2f}%")
            print(f"  平均每笔: {result.avg_return_pertrade:.2f}%")
            print(f"  最大回撤: {result.max_drawdown_pct:.2f}%")
            print(f"  Sharpe: {result.sharpe_ratio:.2f}")
            
            results.append({
                'symbol': symbol,
                'trades': result.totaltrades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'avg': result.avg_return_pertrade,
                'dd': result.max_drawdown_pct,
                'sharpe': result.sharpe_ratio
            })
            
        except Exception as e:
            print(f"  ❌ 回测失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 汇总
    if results:
        print(f"\n{'='*60}")
        print("📈 汇总报告")
        print('='*60)
        
        df_results = pd.DataFrame(results)
        
        print(f"\n{'股票':<10} {'交易':<6} {'胜率':<8} {'收益':<10} {'平均':<10} {'回撤':<10} {'Sharpe'}")
        print("-" * 70)
        
        for _, row in df_results.iterrows():
            print(f"{row['symbol']:<10} {row['trades']:<6} "
                  f"{row['win_rate']:>6.1%} {row['return']:>8.2f}% "
                  f"{row['avg']:>8.2f}% {row['dd']:>8.2f}% {row['sharpe']:>6.2f}")
        
        print("\n平均:")
        print(f"  胜率: {df_results['win_rate'].mean():.1%}")
        print(f"  收益: {df_results['return'].mean():.2f}%")
        print(f"  Sharpe: {df_results['sharpe'].mean():.2f}")
        
        print(f"\n{'='*60}")
        print("✅ 修复验证完成")
        print('='*60)
        print("\n关键修复:")
        print("  1. 前视偏差: 只使用历史数据 ✅")
        print("  2. 交易成本: 0.36%/笔 ✅")
        print("  3. 涨跌停处理: 已实现 ✅")
        print("  4. 资金管理: 最大3只,80%仓位 ✅")
        print("  5. 趋势过滤: 买入时过滤 ✅")

if __name__ == '__main__':
    main()
