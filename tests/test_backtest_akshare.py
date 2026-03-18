"""
使用akshare获取实时数据进行回测
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer

def get_stock_data_akshare(symbol, start_date, end_date):
    """使用akshare获取股票数据"""
    try:
        print(f"  获取 {symbol} 数据...")
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df is None or len(df) == 0:
            return None
        
        # 重命名列
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume'
        })
        
        df['date'] = pd.to_datetime(df['date'])
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("🔧 修复后回测系统 - 真实数据验证")
    print("="*60)
    
    # 测试股票
    test_stocks = [
        ('600519', '贵州茅台'),
        ('000858', '五粮液'),
        ('600702', '舍得酒业')
    ]
    
    # 回测参数
    start_date = "20200101"
    end_date = datetime.now().strftime("%Y%m%d")
    
    print(f"\n回测周期: {start_date} ~ {end_date}")
    print(f"测试股票: {len(test_stocks)}只")
    
    results = []
    
    for symbol, name in test_stocks:
        print(f"\n{'='*60}")
        print(f"📊 {symbol} {name}")
        print('='*60)
        
        # 获取数据
        df = get_stock_data_akshare(symbol, start_date, end_date)
        
        if df is None or len(df) < 200:
            print(f"  ⚠️ 数据不足,跳过")
            continue
        
        print(f"  数据量: {len(df)}条")
        print(f"  范围: {df['date'].min()} ~ {df['date'].max()}")
        
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
        
        # 运行回测
        try:
            result = backtester.run(symbol, df, reanalyze_every=5)
            
            print(f"\n【结果】")
            print(f"  交易次数: {result.total_trades}")
            print(f"  胜率: {result.win_rate:.1%}")
            print(f"  总收益: {result.total_return_pct:.2f}%")
            print(f"  平均每笔: {result.avg_return_per_trade:.2f}%")
            print(f"  最大回撤: {result.max_drawdown_pct:.2f}%")
            print(f"  Sharpe: {result.sharpe_ratio:.2f}")
            
            results.append({
                'symbol': symbol,
                'name': name,
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'avg': result.avg_return_per_trade,
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
        
        print(f"\n{'股票':<12} {'交易':<6} {'胜率':<8} {'收益':<10} {'平均':<10} {'回撤':<10} {'Sharpe'}")
        print("-" * 75)
        
        for _, row in df_results.iterrows():
            print(f"{row['symbol']} {row['name']:<6} {row['trades']:<6} "
                  f"{row['win_rate']:>6.1%} {row['return']:>8.2f}% "
                  f"{row['avg']:>8.2f}% {row['dd']:>8.2f}% {row['sharpe']:>6.2f}")
        
        print(f"\n平均:")
        print(f"  胜率: {df_results['win_rate'].mean():.1%}")
        print(f"  收益: {df_results['return'].mean():.2f}%")
        print(f"  Sharpe: {df_results['sharpe'].mean():.2f}")
        
        print(f"\n{'='*60}")
        print("✅ 修复验证完成")
        print('='*60)

if __name__ == '__main__':
    main()
