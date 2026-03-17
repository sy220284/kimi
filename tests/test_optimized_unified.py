#!/usr/bin/env python3
"""
优化版统一分析器回测
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass

from data import get_stock_data
from analysis.wave import UnifiedWaveAnalyzer, WaveEntryType


TEST_STOCKS = [
    ('600519', '贵州茅台', 'large'),
    ('000858', '五粮液', 'large'),
    ('002594', '比亚迪', 'large'),
    ('000568', '泸州老窖', 'medium'),
    ('600809', '山西汾酒', 'medium'),
]


def run_optimized_backtest(symbol: str, name: str, market_cap: str) -> Dict:
    """使用优化版分析器回测"""
    print(f"\n{'='*60}")
    print(f"📊 {symbol} {name}")
    print(f"{'='*60}")
    
    df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
    if df is None or len(df) == 0:
        return {}
    
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # 优化版分析器
    analyzer = UnifiedWaveAnalyzer(
        atr_period=10,          # 优化: 更短周期
        min_pivots=3,           # 优化: 降低门槛
        min_retrace=0.382,      # 优化: 收紧至38.2%
        max_wave2_retrace=0.50, # 优化: 收紧至50%
        use_trend_filter=True,  # 优化: 后置趋势过滤
        atr_stop_mult=2.0       # 新增: ATR动态止损
    )
    
    trades = []
    position = None
    entry_idx = 0
    signal_counts = {'C': 0, '2': 0, '4': 0, '4_inferred': 0}
    
    for i in range(60, len(df)):
        row = df.iloc[i]
        date_str = row['date'].strftime('%Y-%m-%d')
        price = row['close']
        
        if i % 10 == 0 or position is None:
            window_df = df.iloc[max(0, i-60):i+1].copy()
            
            if not position:
                signals = analyzer.detect(window_df, mode='all')
                
                for sig in signals:
                    if sig.confidence >= 0.5:
                        position = {
                            'entry_date': date_str,
                            'entry_price': price,
                            'entry_type': sig.entry_type.value,
                            'stop_loss': sig.stop_loss,
                            'target': sig.target_price,
                            'direction': sig.direction
                        }
                        entry_idx = i
                        
                        signal_counts[sig.entry_type.value] += 1
                        if sig.entry_type.value == '4' and sig.detection_method == 'inferred':
                            signal_counts['4_inferred'] += 1
                        break
            
            else:
                pnl_pct = (price / position['entry_price'] - 1) * 100
                holding_days = i - entry_idx
                
                # ATR动态止损
                stop_triggered = price <= position['stop_loss'] if position['direction'] == 'up' else price >= position['stop_loss']
                target_hit = price >= position['target'] * 0.98 if position['direction'] == 'up' else price <= position['target'] * 1.02
                
                should_sell = False
                if stop_triggered:
                    should_sell = True
                    exit_reason = 'stop_loss'
                elif target_hit:
                    should_sell = True
                    exit_reason = 'target'
                elif holding_days >= 60:
                    should_sell = True
                    exit_reason = 'timeout'
                
                if should_sell:
                    trades.append({
                        'entry_type': position['entry_type'],
                        'pnl_pct': pnl_pct,
                        'win': pnl_pct > 0,
                        'exit_reason': exit_reason,
                        'holding_days': holding_days
                    })
                    position = None
    
    if not trades:
        return {'symbol': symbol, 'name': name, 'trades': 0}
    
    wins = [t for t in trades if t['win']]
    win_rate = len(wins) / len(trades)
    avg_return = sum(t['pnl_pct'] for t in trades) / len(trades)
    total_return = sum(t['pnl_pct'] for t in trades) / 10
    
    print(f"总交易: {len(trades)} 笔")
    print(f"胜率: {win_rate:.1%}")
    print(f"总收益: {total_return:+.2f}%")
    print(f"信号分布: C:{signal_counts['C']} 2:{signal_counts['2']} 4:{signal_counts['4']}(推断:{signal_counts['4_inferred']})")
    
    # 各浪型统计
    for wave in ['C', '2', '4']:
        wave_trades = [t for t in trades if t['entry_type'] == wave]
        if wave_trades:
            w_wins = [t for t in wave_trades if t['win']]
            w_ret = sum(t['pnl_pct'] for t in wave_trades) / len(wave_trades)
            print(f"  浪{wave}: {len(wave_trades)}笔 胜率{len(w_wins)/len(wave_trades):.1%} 收益{w_ret:+.2f}%")
    
    return {
        'symbol': symbol,
        'name': name,
        'trades': len(trades),
        'win_rate': win_rate,
        'total_return': total_return,
        'signal_counts': signal_counts
    }


def main():
    print("🚀 优化版统一分析器回测")
    print("="*60)
    print("优化内容:")
    print("  • ATR周期: 14→10")
    print("  • min_pivots: 4→3")
    print("  • min_retrace: 30%→38.2%")
    print("  • max_wave2_retrace: 61.8%→50%")
    print("  • 趋势过滤后置")
    print("  • ATR动态止损")
    print("="*60)
    
    results = []
    for symbol, name, cap in TEST_STOCKS:
        result = run_optimized_backtest(symbol, name, cap)
        if result.get('trades', 0) > 0:
            results.append(result)
    
    if results:
        print(f"\n{'='*60}")
        print("📈 汇总")
        print(f"{'='*60}")
        avg_trades = sum(r['trades'] for r in results) / len(results)
        avg_win = sum(r['win_rate'] for r in results) / len(results)
        avg_ret = sum(r['total_return'] for r in results) / len(results)
        print(f"平均交易: {avg_trades:.0f}笔")
        print(f"平均胜率: {avg_win:.1%}")
        print(f"平均收益: {avg_ret:+.2f}%")
    
    print("\n✅ 完成")


if __name__ == "__main__":
    main()
