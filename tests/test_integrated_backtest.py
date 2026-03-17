#!/usr/bin/env python3
"""
集成2/4浪检测的完整回测框架
同时使用原始波浪检测 + 4浪检测器 + 2浪检测器
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer, Wave4Detector, Wave2Detector
from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy, TradeAction, Trade


@dataclass
class IntegratedTrade:
    """集成交易记录"""
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    entry_wave: str = ''
    signal_source: str = ''
    pnl_pct: float = 0.0
    status: str = 'open'


class IntegratedWaveBacktester:
    """集成回测器 - 同时使用多种检测方法"""
    
    def __init__(self, 
                 use_original: bool = True,
                 use_wave4: bool = True,
                 use_wave2: bool = True,
                 wave4_confidence: float = 0.5,
                 wave2_confidence: float = 0.5):
        self.use_original = use_original
        self.use_wave4 = use_wave4
        self.use_wave2 = use_wave2
        self.wave4_confidence = wave4_confidence
        self.wave2_confidence = wave2_confidence
        
        self.analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
        self.wave4_detector = Wave4Detector()
        self.wave2_detector = Wave2Detector()
        self.strategy = None
        
    def set_strategy(self, strategy: WaveStrategy):
        """设置策略"""
        self.strategy = strategy
    
    def run(self, symbol: str, df: pd.DataFrame, reanalyze_every: int = 30) -> Dict:
        """运行集成回测"""
        print(f"\n{'='*80}")
        print(f"📊 集成回测 - {symbol}")
        print(f"  原始检测: {'✓' if self.use_original else '✗'}")
        print(f"  4浪检测: {'✓' if self.use_wave4 else '✗'}")
        print(f"  2浪检测: {'✓' if self.use_wave2 else '✗'}")
        print(f"{'='*80}")
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        trades = []
        position = None
        current_analysis = None
        
        wave_stats = {'C': 0, '4': 0, '2': 0, 'other': 0}
        source_stats = {'original': 0, 'wave4': 0, 'wave2': 0}
        
        for i, row in df.iterrows():
            date = row['date']
            price = row['close']
            date_str = date.strftime('%Y-%m-%d')
            
            # 定期重新分析
            if i % reanalyze_every == 0 or current_analysis is None:
                lookback_start = max(0, i - 60)
                analysis_df = df.iloc[lookback_start:i+1].copy()
                
                current_analysis = None
                wave4_signal = None
                wave2_signal = None
                
                if len(analysis_df) >= 20:
                    if self.use_original:
                        try:
                            current_analysis = self.analyzer.analyze(symbol, analysis_df)
                        except:
                            pass
                    
                    if self.use_wave4:
                        try:
                            wave4_signal = self.wave4_detector.detect(analysis_df)
                        except:
                            pass
                    
                    if self.use_wave2:
                        try:
                            wave2_signal = self.wave2_detector.detect(analysis_df)
                        except:
                            pass
            
            # 生成买入信号 (优先级: 4浪 > 2浪 > 原始检测)
            buy_signal = None
            entry_wave = None
            signal_source = None
            target_price = None
            stop_loss = None
            
            # 优先级1: 4浪信号
            if wave4_signal and wave4_signal.is_valid and wave4_signal.confidence >= self.wave4_confidence:
                if not position:
                    buy_signal = True
                    entry_wave = '4'
                    signal_source = 'wave4'
                    target_price = wave4_signal.target_price
                    stop_loss = wave4_signal.stop_loss
            
            # 优先级2: 2浪信号
            if not buy_signal and wave2_signal and wave2_signal.is_valid and wave2_signal.confidence >= self.wave2_confidence:
                if not position:
                    buy_signal = True
                    entry_wave = '2'
                    signal_source = 'wave2'
                    target_price = wave2_signal.target_price
                    stop_loss = wave2_signal.stop_loss
            
            # 优先级3: 原始检测
            if not buy_signal and current_analysis and current_analysis.primary_pattern:
                pattern = current_analysis.primary_pattern
                latest_wave = pattern.points[-1].wave_num if pattern.points else None
                
                if latest_wave in ['2', '4', 'C', 'A', 'B'] and not position:
                    signal = self.strategy.generate_signal(current_analysis, price)
                    if signal == TradeAction.BUY:
                        buy_signal = True
                        entry_wave = latest_wave if latest_wave else 'C'
                        signal_source = 'original'
                        target_price = pattern.target_price
                        stop_loss = pattern.stop_loss
            
            # 执行买入
            if buy_signal and not position:
                trade = IntegratedTrade(
                    symbol=symbol,
                    entry_date=date_str,
                    entry_price=price,
                    entry_wave=entry_wave,
                    signal_source=signal_source
                )
                position = trade
                
                if entry_wave in wave_stats:
                    wave_stats[entry_wave] += 1
                else:
                    wave_stats['other'] += 1
                
                if signal_source in source_stats:
                    source_stats[signal_source] += 1
            
            # 检查卖出条件
            if position:
                pnl_pct = (price / position.entry_price - 1) * 100
                
                if pnl_pct <= -5:
                    position.exit_date = date_str
                    position.exit_price = price
                    position.pnl_pct = pnl_pct
                    position.status = 'closed'
                    trades.append(position)
                    position = None
                elif pnl_pct >= 10:
                    position.exit_date = date_str
                    position.exit_price = price
                    position.pnl_pct = pnl_pct
                    position.status = 'closed'
                    trades.append(position)
                    position = None
                elif current_analysis and current_analysis.primary_pattern:
                    pattern = current_analysis.primary_pattern
                    latest_wave = pattern.points[-1].wave_num if pattern.points else None
                    if latest_wave in ['5', 'C'] and pnl_pct > 0:
                        position.exit_date = date_str
                        position.exit_price = price
                        position.pnl_pct = pnl_pct
                        position.status = 'closed'
                        trades.append(position)
                        position = None
        
        # 计算结果
        closed_trades = [t for t in trades if t.status == 'closed']
        wins = [t for t in closed_trades if t.pnl_pct > 0]
        
        total_return = sum(t.pnl_pct for t in closed_trades) / 10 if closed_trades else 0
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0
        
        print(f"\n📈 回测结果:")
        print(f"  总交易: {len(closed_trades)} 笔")
        print(f"  胜率: {win_rate:.1%}")
        print(f"  总收益: {total_return:+.2f}%")
        print(f"\n  买入浪号分布:")
        for wave, count in sorted(wave_stats.items()):
            if count > 0:
                print(f"    浪{wave}: {count} 次")
        print(f"\n  信号来源:")
        for source, count in sorted(source_stats.items()):
            if count > 0:
                print(f"    {source}: {count} 次")
        
        return {
            'trades': closed_trades,
            'total_trades': len(closed_trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'wave_distribution': wave_stats,
            'source_distribution': source_stats
        }


def run_comparison(symbol: str, name: str, df: pd.DataFrame):
    """对比原策略 vs 完整集成策略"""
    print(f"\n{'='*80}")
    print(f"🎯 策略对比 - {symbol} {name}")
    print(f"{'='*80}")
    
    strategy = WaveStrategy(
        initial_capital=1000000,
        position_size=0.2,
        stop_loss_pct=0.05,
        min_confidence=0.35,
        use_resonance=True,
        min_holding_days=3,
        use_trend_filter=True,
        trend_ma_period=60,
        use_dynamic_target=True
    )
    
    # 原策略 (仅原始检测)
    print(f"\n[1] 原策略 (仅波浪检测)")
    backtester1 = IntegratedWaveBacktester(use_original=True, use_wave4=False, use_wave2=False)
    backtester1.set_strategy(strategy)
    result1 = backtester1.run(symbol, df, reanalyze_every=30)
    
    # 集成策略 (波浪检测 + 4浪 + 2浪)
    print(f"\n[2] 完整集成策略 (波浪检测 + 4浪 + 2浪)")
    backtester2 = IntegratedWaveBacktester(
        use_original=True, 
        use_wave4=True, 
        use_wave2=True,
        wave4_confidence=0.5,
        wave2_confidence=0.5
    )
    backtester2.set_strategy(strategy)
    result2 = backtester2.run(symbol, df, reanalyze_every=30)
    
    # 对比结果
    print(f"\n{'='*80}")
    print(f"📊 对比结果")
    print(f"{'='*80}")
    print(f"{'指标':<20} {'原策略':<15} {'集成策略':<15} {'改进':<10}")
    sep = "-" * 60
    print(sep)
    
    trades_diff = result2['total_trades'] - result1['total_trades']
    print(f"{'总交易':<20} {result1['total_trades']:<15} {result2['total_trades']:<15} {trades_diff:<+10}")
    
    win_rate_diff = result2['win_rate'] - result1['win_rate']
    print(f"{'胜率':<20} {result1['win_rate']:.1%}{'':<8} {result2['win_rate']:.1%}{'':<8} {win_rate_diff:+.1%}")
    
    return_diff = result2['total_return'] - result1['total_return']
    print(f"{'总收益':<20} {result1['total_return']:+.2f}%{'':<10} {result2['total_return']:+.2f}%{'':<10} {return_diff:+.2f}%")
    
    return {
        'symbol': symbol,
        'name': name,
        'original': result1,
        'integrated': result2
    }


# 主测试
if __name__ == "__main__":
    print("🚀 完整集成回测框架 (2浪 + 4浪 + 共振 + 趋势)")
    print("="*80)
    
    test_stocks = [
        ('600519', '茅台'),
        ('000858', '五粮液'),
        ('600600', '青岛啤酒'),
    ]
    
    results = []
    for symbol, name in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        result = run_comparison(symbol, name, df)
        results.append(result)
    
    # 汇总
    print(f"\n{'='*80}")
    print(f"📈 汇总对比")
    print(f"{'='*80}")
    print(f"{'股票':<10} {'原收益':<12} {'集成收益':<12} {'改进':<10}")
    print("-" * 50)
    for r in results:
        orig = r['original']['total_return']
        integrated = r['integrated']['total_return']
        improvement = integrated - orig
        print(f"{r['symbol']:<10} {orig:>+10.1f}% {integrated:>+10.1f}% {improvement:>+8.1f}%")
    
    avg_orig = sum(r['original']['total_return'] for r in results) / len(results)
    avg_integrated = sum(r['integrated']['total_return'] for r in results) / len(results)
    avg_improvement = avg_integrated - avg_orig
    print("-" * 50)
    print(f"{'平均':<10} {avg_orig:>+10.1f}% {avg_integrated:>+10.1f}% {avg_improvement:>+8.1f}%")
    
    print(f"\n✅ 测试完成")
