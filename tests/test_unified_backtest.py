#!/usr/bin/env python3
"""
使用统一波浪分析器的回测
简化版 - 单一入口
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass

from data import get_stock_data
from analysis.wave import UnifiedWaveAnalyzer


# 食品饮料板块10只股票
FOOD_BEVERAGE_STOCKS = [
    ('600519', '贵州茅台', 'large'),
    ('000858', '五粮液', 'large'),
    ('002594', '比亚迪', 'large'),
    ('000568', '泸州老窖', 'medium'),
    ('600809', '山西汾酒', 'medium'),
    ('600887', '伊利股份', 'medium'),
    ('603288', '海天味业', 'medium'),
    ('600600', '青岛啤酒', 'small'),
    ('000729', '燕京啤酒', 'small'),
    ('603589', '口子窖', 'small'),
]


@dataclass
class SimpleTrade:
    """简化交易记录"""
    symbol: str
    name: str
    entry_date: str
    entry_price: float
    entry_type: str  # 'C', '2', '4'
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_pct: float = 0.0
    status: str = 'open'


def run_unified_backtest(symbol: str, name: str, market_cap: str,
                         start_date: str = '2023-01-01', 
                         end_date: str = '2026-03-16') -> Dict:
    """使用统一分析器回测"""
    print(f"\n{'='*60}")
    print(f"📊 {symbol} {name} [{market_cap}]")
    print(f"{'='*60}")
    
    df = get_stock_data(symbol, start_date, end_date)
    if df is None or len(df) == 0:
        return {'trades': [], 'stats': {}}
    
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # 统一分析器
    analyzer = UnifiedWaveAnalyzer(
        atr_period=14,
        atr_mult=0.5,
        min_confidence=0.5,
        use_trend_confirm=True
    )
    
    trades = []
    position = None
    entry_idx = 0
    
    # 统计信号
    signal_counts = {'C': 0, '2': 0, '4': 0}
    
    for i in range(60, len(df)):
        row = df.iloc[i]
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        # 每10天检测一次
        if i % 10 == 0 or position is None:
            window_df = df.iloc[max(0, i-60):i+1].copy()
            
            if not position:
                # 检测买入信号
                signals = analyzer.detect(window_df, mode='all')
                
                for sig in signals:
                    if sig.confidence >= 0.5:
                        position = SimpleTrade(
                            symbol=symbol, name=name,
                            entry_date=date_str,
                            entry_price=price,
                            entry_type=sig.entry_type.value
                        )
                        entry_idx = i
                        signal_counts[sig.entry_type.value] += 1
                        break
            
            else:
                # 检测卖出
                pnl_pct = (price / position.entry_price - 1) * 100
                holding_days = i - entry_idx
                
                should_sell = False
                
                # 止损 -5%
                if pnl_pct <= -5:
                    should_sell = True
                # 止盈 +10%
                elif pnl_pct >= 10:
                    should_sell = True
                # 最大持仓60天
                elif holding_days >= 60:
                    should_sell = True
                
                if should_sell:
                    position.exit_date = date_str
                    position.exit_price = price
                    position.pnl_pct = pnl_pct
                    position.status = 'closed'
                    trades.append(position)
                    position = None
    
    # 计算结果
    closedtrades = [t for t in trades if t.status == 'closed']
    wins = [t for t in closedtrades if t.pnl_pct > 0]
    
    if closedtrades:
        win_rate = len(wins) / len(closedtrades)
        avg_return = sum(t.pnl_pct for t in closedtrades) / len(closedtrades)
        total_return = sum(t.pnl_pct for t in closedtrades) / 10
    else:
        win_rate = 0
        avg_return = 0
        total_return = 0
    
    # 按浪型统计
    wavestats = {}
    for wave in ['C', '2', '4']:
        wavetrades = [t for t in closedtrades if t.entry_type == wave]
        if wavetrades:
            wave_wins = [t for t in wavetrades if t.pnl_pct > 0]
            wavestats[wave] = {
                'count': len(wavetrades),
                'win_rate': len(wave_wins) / len(wavetrades),
                'avg_return': sum(t.pnl_pct for t in wavetrades) / len(wavetrades)
            }
    
    print(f"总交易: {len(closedtrades)} 笔 (C:{signal_counts['C']}, 2:{signal_counts['2']}, 4:{signal_counts['4']})")
    print(f"胜率: {win_rate:.1%}")
    print(f"总收益: {total_return:+.2f}%")
    
    if wavestats:
        print("\n各浪型表现:")
        for wave, stats in wavestats.items():
            print(f"  浪{wave}: {stats['count']}笔 胜率{stats['win_rate']:.1%} 收益{stats['avg_return']:+.2f}%")
    
    return {
        'symbol': symbol,
        'name': name,
        'market_cap': market_cap,
        'totaltrades': len(closedtrades),
        'win_rate': win_rate,
        'total_return': total_return,
        'signal_counts': signal_counts,
        'wavestats': wavestats,
        'trades': closedtrades
    }


def main():
    """主函数"""
    print("🚀 统一波浪分析器回测")
    print("="*60)
    print("使用单一入口: UnifiedWaveAnalyzer")
    print("统一极值点检测: enhanced_pivot_detection")
    print("="*60)
    
    results = []
    for symbol, name, cap in FOOD_BEVERAGE_STOCKS:
        result = run_unified_backtest(symbol, name, cap)
        if result['totaltrades'] > 0:
            results.append(result)
    
    # 汇总
    print(f"\n{'='*60}")
    print("📈 汇总统计")
    print(f"{'='*60}")
    
    # 按市值
    print("\n按市值分组:")
    for cap_name, cap_code in [('大市值', 'large'), ('中市值', 'medium'), ('小市值', 'small')]:
        cap_results = [r for r in results if r['market_cap'] == cap_code]
        if cap_results:
            totaltrades = sum(r['totaltrades'] for r in cap_results)
            avg_win = sum(r['win_rate'] for r in cap_results) / len(cap_results)
            avg_ret = sum(r['total_return'] for r in cap_results) / len(cap_results)
            print(f"  {cap_name}: {len(cap_results)}只 {totaltrades}笔 胜率{avg_win:.1%} 收益{avg_ret:+.2f}%")
    
    # 按浪型
    print("\n按浪型汇总:")
    totalsignals = {'C': 0, '2': 0, '4': 0}
    for r in results:
        for wave, count in r['signal_counts'].items():
            totalsignals[wave] += count
    
    for wave, count in sorted(totalsignals.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  浪{wave}: {count}次信号")
    
    # 详细结果
    print(f"\n{'='*60}")
    print("📋 个股详细结果")
    print(f"{'='*60}")
    print(f"{'代码':<10} {'名称':<10} {'交易':<6} {'胜率':<8} {'收益':<8} {'C/2/4':<10}")
    print("-" * 60)
    for r in results:
        c = r['signal_counts']
        win_rate_str = f"{r['win_rate']:.1%}"
        ret_str = f"{r['total_return']:+.1f}%"
        wave_str = f"{c['C']}/{c['2']}/{c['4']}"
        print(f"{r['symbol']:<10} {r['name']:<10} {r['totaltrades']:<6} {win_rate_str:<8} {ret_str:<8} {wave_str:<10}")
    
    print("\n✅ 回测完成")


if __name__ == "__main__":
    main()
