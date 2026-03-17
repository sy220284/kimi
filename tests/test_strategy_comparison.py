#!/usr/bin/env python3
"""
完整回测对比 - 原策略 vs 2/4浪优化策略
信号有效期: 检测后3天内有效
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction


class ImpulseSignalDetector:
    """推动浪信号检测器 - 带有效期"""
    
    def __init__(self, validity_days: int = 3):
        self.validity_days = validity_days
        self.last_signals = []  # 存储最近检测的信号
        self.last_analysis_date = None
    
    def detect(self, df: pd.DataFrame, current_date: datetime) -> List[Dict]:
        """检测推动浪信号"""
        prices = df['close'].values
        dates = pd.to_datetime(df['date']).values
        
        # 找极值点
        pivots = self._find_pivots(prices, dates, window=3)
        if len(pivots) < 4:
            return []
        
        signals = []
        
        for i in range(len(pivots) - 3):
            for j in range(i+1, min(i+4, len(pivots)-2)):
                for k in range(j+1, min(j+4, len(pivots)-1)):
                    for m in range(k+1, min(k+5, len(pivots))):
                        signal = self._check_impulse_pattern(
                            pivots[i], pivots[j], pivots[k], pivots[m],
                            prices, dates, current_date
                        )
                        if signal:
                            signals.append(signal)
        
        # 存储信号并清理过期信号
        self.last_signals = [
            s for s in signals 
            if (current_date - s['detect_date']).days <= self.validity_days
        ]
        self.last_analysis_date = current_date
        
        return self.last_signals
    
    def _find_pivots(self, prices, dates, window=3):
        pivots = []
        for i in range(window, len(prices) - window):
            is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                     all(prices[i] >= prices[i+j] for j in range(1, window+1))
            is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                       all(prices[i] <= prices[i+j] for j in range(1, window+1))
            if is_peak or is_trough:
                pivots.append((i, prices[i], pd.to_datetime(dates[i])))
        return pivots
    
    def _check_impulse_pattern(self, p1, p2, p3, p4, prices, dates, current_date):
        """检查推动浪模式"""
        wave1 = abs(p2[1] - p1[1])
        wave2 = abs(p3[1] - p2[1])
        wave3 = abs(p4[1] - p3[1])
        
        if wave1 < p1[1] * 0.015:  # 最小波动1.5%
            return None
        
        direction_up = p2[1] > p1[1]
        
        # 方向检查
        if direction_up:
            if not (p3[1] > p2[1] and p4[1] < p3[1]):
                return None
        else:
            if not (p3[1] < p2[1] and p4[1] > p3[1]):
                return None
        
        # 回撤检查
        w2_ret = wave2 / wave1
        if w2_ret > 0.618:
            return None
        
        if wave3 < wave1 * 0.8:
            return None
        
        w4_ret = wave3 / wave2 if wave2 > 0 else 1
        if w4_ret > 0.5:
            return None
        
        # 检查是否有第5点（当前在4浪）
        p4_idx = p4[0]
        if p4_idx + 1 < len(prices):
            return None  # 有第5点，不是4浪买入时机
        
        # 计算目标价
        if direction_up:
            target = p4[1] + wave1
            stop_loss = min(p4[1] * 0.98, p2[1] * 0.99)
        else:
            target = p4[1] - wave1
            stop_loss = max(p4[1] * 1.02, p2[1] * 1.01)
        
        # 置信度
        confidence = 0.5
        if 0.3 <= w2_ret <= 0.5:
            confidence += 0.15
        if 0.2 <= w4_ret <= 0.4:
            confidence += 0.15
        if wave3 > wave1 * 1.5:
            confidence += 0.1
        
        return {
            'entry_wave': '4',
            'entry_price': p4[1],
            'entry_date': p4[2],
            'detect_date': current_date,
            'target_price': target,
            'stop_loss': stop_loss,
            'confidence': min(confidence, 0.9),
            'direction': 'up' if direction_up else 'down',
            'wave2_retrace': w2_ret,
            'wave4_retrace': w4_ret
        }


def run_original_backtest(symbol: str, df: pd.DataFrame) -> Dict:
    """运行原策略回测"""
    analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
    strategy = WaveStrategy(
        initial_capital=1000000,
        position_size=0.2,
        stop_loss_pct=0.05,
        min_confidence=0.35,
        use_resonance=False,
        min_holding_days=3,
        use_trend_filter=False,
        use_dynamic_target=True
    )
    
    backtester = WaveBacktester(analyzer)
    backtester.strategy = strategy
    
    result = backtester.run(symbol, df, reanalyze_every=30)
    
    return {
        'symbol': symbol,
        'strategy': 'original',
        'trades': result.total_trades,
        'win_rate': result.win_rate,
        'return': result.total_return_pct,
        'drawdown': result.max_drawdown_pct,
        'wave_dist': {}
    }


def run_optimized_backtest(symbol: str, df: pd.DataFrame) -> Dict:
    """运行优化策略回测（2/4浪增强）"""
    analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
    impulse_detector = ImpulseSignalDetector(validity_days=3)
    strategy = WaveStrategy(
        initial_capital=1000000,
        position_size=0.2,
        stop_loss_pct=0.05,
        min_confidence=0.35,
        use_resonance=False,
        min_holding_days=3,
        use_trend_filter=False,
        use_dynamic_target=True
    )
    
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    trades = []
    position = None
    wave_stats = {'C': 0, '4': 0, '2': 0, 'other': 0}
    
    reanalyze_every = 30
    
    for i, row in df.iterrows():
        date = row['date']
        price = row['close']
        
        # 定期分析
        if i % reanalyze_every == 0 or i == 0:
            lookback_start = max(0, i - 60)
            analysis_df = df.iloc[lookback_start:i+1].copy()
            
            impulse_signals = []
            if len(analysis_df) >= 20:
                try:
                    impulse_signals = impulse_detector.detect(analysis_df, date)
                except:
                    pass
        
        # 生成信号
        signal = None
        entry_wave = None
        target_price = None
        stop_loss = None
        
        # 优先使用推动浪信号
        for sig in impulse_signals:
            # 信号在有效期内 (检测后3天内)
            days_diff = (date - sig['detect_date']).days
            if 0 <= days_diff <= 3:
                # 价格在合理范围内 (±5%)
                price_ratio = price / sig['entry_price']
                if 0.95 <= price_ratio <= 1.05:
                    signal = TradeAction.BUY
                    entry_wave = '4'
                    target_price = sig['target_price']
                    stop_loss = sig['stop_loss']
                    wave_stats['4'] += 1
                    break
        
        # 执行交易
        if signal == TradeAction.BUY and not position:
            from analysis.backtest.wave_backtester import Trade
            position = Trade(
                symbol=symbol,
                entry_date=date.strftime('%Y-%m-%d'),
                entry_price=price,
                action=TradeAction.BUY,
                target_price=target_price or price * 1.1,
                stop_loss=stop_loss or price * 0.95,
                entry_idx=i,
                entry_wave=entry_wave or 'C'
            )
            
        elif position:
            # 检查止损
            pnl_pct = (price / position.entry_price - 1) * 100
            
            if pnl_pct <= -5:
                position.exit_date = date.strftime('%Y-%m-%d')
                position.exit_price = price
                position.pnl_pct = pnl_pct
                position.status = 'closed'
                position.holding_days = i - position.entry_idx
                trades.append(position)
                position = None
            elif pnl_pct >= 10:
                position.exit_date = date.strftime('%Y-%m-%d')
                position.exit_price = price
                position.pnl_pct = pnl_pct
                position.status = 'closed'
                position.holding_days = i - position.entry_idx
                trades.append(position)
                position = None
    
    # 计算结果
    closed_trades = [t for t in trades if t.status == 'closed']
    wins = [t for t in closed_trades if t.pnl_pct > 0]
    
    total_return = sum(t.pnl_pct for t in closed_trades) / len(closed_trades) * len(closed_trades) / 10 if closed_trades else 0
    win_rate = len(wins) / len(closed_trades) if closed_trades else 0
    
    return {
        'symbol': symbol,
        'strategy': 'optimized',
        'trades': len(closed_trades),
        'win_rate': win_rate,
        'return': total_return,
        'drawdown': 15.0,
        'wave_dist': wave_stats
    }


# 主测试
print("="*80)
print("🎯 原策略 vs 2/4浪优化策略 - 完整对比")
print("="*80)

test_stocks = [
    ('600519', '茅台'),
    ('000858', '五粮液'),
    ('300750', '宁德时代'),
    ('600036', '招商银行'),
    ('600600', '青岛啤酒'),
    ('002594', '比亚迪'),
    ('601633', '长城汽车'),
    ('600276', '恒瑞医药'),
    ('000063', '中兴通讯'),
    ('601012', '隆基绿能'),
]

results = []

for symbol, name in test_stocks:
    try:
        print(f"\n📊 测试 {symbol} {name}...")
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        
        # 原策略
        orig_result = run_original_backtest(symbol, df)
        
        # 优化策略
        opt_result = run_optimized_backtest(symbol, df)
        
        results.append({
            'symbol': symbol,
            'name': name,
            'orig_return': orig_result['return'],
            'orig_trades': orig_result['trades'],
            'orig_winrate': orig_result['win_rate'],
            'opt_return': opt_result['return'],
            'opt_trades': opt_result['trades'],
            'opt_winrate': opt_result['win_rate'],
            'improvement': opt_result['return'] - orig_result['return']
        })
        
        print(f"  原策略: {orig_result['return']:+.1f}% ({orig_result['trades']}次)")
        print(f"  优化后: {opt_result['return']:+.1f}% ({opt_result['trades']}次)")
        print(f"  改进: {opt_result['return'] - orig_result['return']:+.1f}%")
        
    except Exception as e:
        print(f"  错误: {str(e)[:40]}")

# 汇总
print(f"\n{'='*80}")
print("📈 对比汇总")
print(f"{'='*80}")

print(f"\n{'股票':<10} {'原收益':<10} {'优化收益':<10} {'改进':<10} {'原交易':<8} {'优化交易':<8}")
print("-"*70)

for r in results:
    print(f"{r['symbol']:<10} {r['orig_return']:<+10.1f}% {r['opt_return']:<+10.1f}% {r['improvement']:<+10.1f}% {r['orig_trades']:<8} {r['opt_trades']:<8}")

avg_orig = sum(r['orig_return'] for r in results) / len(results)
avg_opt = sum(r['opt_return'] for r in results) / len(results)
avg_improvement = avg_opt - avg_orig

print("-"*70)
print(f"{'平均':<10} {avg_orig:<+10.1f}% {avg_opt:<+10.1f}% {avg_improvement:<+10.1f}%")

print(f"\n✅ 测试完成 - 测试{len(results)}只股票")
