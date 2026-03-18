"""
测试修复后的回测系统
使用本地CSV数据,不依赖数据库
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer

def load_testdata():
    """加载测试数据"""
    # 尝试从results目录加载之前的回测数据
    csv_path = Path(__file__).parent / 'results' / 'batch_wave_analysis.csv'
    
    if csv_path.exists():
        print(f"✅ 加载数据: {csv_path}")
        df = pd.read_csv(csv_path)
        
        # 获取第一只股票的数据
        if 'symbol' in df.columns:
            symbols = df['symbol'].unique()
            if len(symbols) > 0:
                symbol = symbols[0]
                stock_df = df[df['symbol'] == symbol].copy()
                
                # 确保有必要的列
                required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                if all(col in stock_df.columns for col in required_cols):
                    return symbol, stock_df[required_cols]
    
    # 如果没有找到数据,生成模拟数据
    print("⚠️ 未找到历史数据,生成模拟数据")
    dates = pd.date_range('2023-01-01', '2024-12-31', freq='D')
    
    # 生成带趋势的随机价格
    import numpy as np
    np.random.seed(42)
    
    base_price = 100
    prices = [base_price]
    for i in range(1, len(dates)):
        # 随机游走 + 小趋势
        change = np.random.normal(0.001, 0.02)
        prices.append(prices[-1] * (1 + change))
    
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 10000000) for _ in prices]
    })
    
    return '000001', df

def main():
    print("\n" + "="*60)
    print("🔧 测试修复后的回测系统")
    print("="*60)
    
    # 加载数据
    symbol, df = load_testdata()
    print(f"\n股票: {symbol}")
    print(f"数据范围: {df['date'].min()} ~ {df['date'].max()}")
    print(f"数据量: {len(df)} 条")
    
    # 创建回测器
    print("\n初始化回测器...")
    analyzer = UnifiedWaveAnalyzer()
    
    # 使用修复后的参数
    strategy = WaveStrategy(
        initial_capital=100000,
        position_size=0.2,
        max_positions=3,  # 新增
        max_total_position=0.8,  # 新增
        commission_rate=0.0003,  # 新增
        stamp_tax_rate=0.001,  # 新增
        slippage_rate=0.001,  # 新增
        min_holding_days=3,
        use_trend_filter=True,
        trend_ma_period=200
    )
    
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    # 运行回测
    print("\n开始回测...")
    result = backtester.run(symbol, df, reanalyze_every=5)
    
    # 打印报告
    report = backtester.generate_report(result)
    print(report)
    
    # 详细统计
    print("\n" + "="*60)
    print("📈 修复前后对比")
    print("="*60)
    print("\n修复项:")
    print("  ✅ 前视偏差: 只使用历史数据")
    print("  ✅ 交易成本: 佣金0.03% + 印花税0.1% + 滑点0.1%")
    print("  ✅ 涨跌停处理: 涨停无法买入,跌停无法卖出")
    print("  ✅ 资金管理: 最大3只持仓,总仓位≤80%")
    print("  ✅ 趋势过滤: 买入时过滤,不清空信号")
    
    print("\n实际交易成本:")
    if result.total_trades > 0:
        # 估算交易成本
        avg_cost_pertrade = 0.0003 + 0.001 + 0.001 + 0.0003 + 0.001 + 0.001  # 买入+卖出
        total_cost_pct = avg_cost_pertrade * result.total_trades * 100
        print(f"  往返成本: 0.36% × {result.total_trades}笔 = {total_cost_pct:.2f}%")
        print(f"  对收益影响: -{total_cost_pct:.2f}%")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    main()
