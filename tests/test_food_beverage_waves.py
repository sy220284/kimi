#!/usr/bin/env python3
"""
食品饮料板块波浪买卖点回测分析
检查C/2/4浪买点 + 1/3/5浪卖点
评估浪型识别准确度
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from data import get_stock_data
from analysis.wave import EnhancedWaveAnalyzer, Wave4Detector, Wave2Detector


# 食品饮料板块10只不同市值股票
FOOD_BEVERAGE_STOCKS = [
    # 大市值 (>1000亿)
    ('600519', '贵州茅台', 'large'),
    ('000858', '五粮液', 'large'),
    ('002594', '比亚迪', 'large'),  # 包含食品业务
    
    # 中市值 (200-1000亿)
    ('000568', '泸州老窖', 'medium'),
    ('600809', '山西汾酒', 'medium'),
    ('600887', '伊利股份', 'medium'),
    ('603288', '海天味业', 'medium'),
    
    # 小市值 (<200亿)
    ('600600', '青岛啤酒', 'small'),
    ('000729', '燕京啤酒', 'small'),
    ('603589', '口子窖', 'small'),
]


@dataclass
class WaveTrade:
    """波浪交易记录"""
    symbol: str
    name: str
    market_cap: str
    entry_date: str
    entry_price: float
    entry_wave: str  # 'C', '2', '4'
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_wave: Optional[str] = None  # '1', '3', '5'
    pnl_pct: float = 0.0
    holding_days: int = 0
    status: str = 'open'
    # 浪型识别评估
    predictednext_wave: str = ''  # 预期下一浪
    actualnext_wave: str = ''     # 实际走出来的浪
    prediction_correct: bool = False


@dataclass
class WaveAccuracyMetrics:
    """浪型识别准确度指标"""
    totalsignals: int = 0
    correct_predictions: int = 0
    wave_accuracy: Dict[str, Dict] = field(default_factory=dict)
    
    def add_prediction(self, entry_wave: str, predictednext: str, actual_outcome: str):
        """记录预测结果"""
        self.totalsignals += 1
        
        if entry_wave not in self.wave_accuracy:
            self.wave_accuracy[entry_wave] = {
                'total': 0,
                'correct': 0,
                'predictions': defaultdict(int),
                'outcomes': defaultdict(int)
            }
        
        self.wave_accuracy[entry_wave]['total'] += 1
        self.wave_accuracy[entry_wave]['predictions'][predictednext] += 1
        self.wave_accuracy[entry_wave]['outcomes'][actual_outcome] += 1
        
        # 判断是否预测正确
        # C浪买入 -> 预期浪1上涨
        # 2浪买入 -> 预期浪3上涨
        # 4浪买入 -> 预期浪5上涨
        is_correct = False
        if entry_wave == 'C' and actual_outcome in ['1', 'up']:
            is_correct = True
        elif entry_wave == '2' and actual_outcome in ['3', 'up']:
            is_correct = True
        elif entry_wave == '4' and actual_outcome in ['5', 'up']:
            is_correct = True
        
        if is_correct:
            self.correct_predictions += 1
            self.wave_accuracy[entry_wave]['correct'] += 1
        
        return is_correct


class WavePatternBacktester:
    """
    波浪买卖点回测器
    专门分析C/2/4浪买点和1/3/5浪卖点
    """
    
    def __init__(self):
        self.analyzer = EnhancedWaveAnalyzer(use_adaptive=False)
        self.wave4_detector = Wave4Detector()
        self.wave2_detector = Wave2Detector()
        self.accuracymetrics = WaveAccuracyMetrics()
        
    def detect_sellsignal(self, df: pd.DataFrame, entry_wave: str) -> Optional[Dict]:
        """
        检测卖点信号
        C浪买入 -> 等待浪1完成
        2浪买入 -> 等待浪3完成
        4浪买入 -> 等待浪5完成
        """
        if len(df) < 20:
            return None
        
        try:
            result = self.analyzer.analyze(df.iloc[-1]['symbol'] if 'symbol' in df.columns else 'unknown', df)
            if not result or not result.primary_pattern:
                return None
            
            pattern = result.primary_pattern
            if not pattern.points:
                return None
            
            latest_wave = pattern.points[-1].wave_num
            latest_price = pattern.points[-1].price
            
            # 判断是否是预期的卖点
            sellsignal = None
            if entry_wave == 'C' and latest_wave == '1':
                sellsignal = {'wave': '1', 'price': latest_price}
            elif entry_wave == '2' and latest_wave == '3':
                sellsignal = {'wave': '3', 'price': latest_price}
            elif entry_wave == '4' and latest_wave == '5':
                sellsignal = {'wave': '5', 'price': latest_price}
            
            return sellsignal
            
        except Exception:
            return None
    
    def run(self, symbol: str, name: str, market_cap: str, 
            start_date: str = '2023-01-01', end_date: str = '2026-03-16') -> Dict:
        """运行回测"""
        print(f"\n{'='*80}")
        print(f"📊 {symbol} {name} [{market_cap}]")
        print(f"{'='*80}")
        
        df = get_stock_data(symbol, start_date, end_date)
        if df is None or len(df) == 0:
            print("❌ 无数据")
            return {'trades': [], 'metrics': {}}
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        trades = []
        position = None
        entry_idx = 0
        
        # 统计
        wave_counts = {'C': 0, '2': 0, '4': 0}
        
        for i in range(40, len(df)):
            row = df.iloc[i]
            date = row['date']
            price = row['close']
            date_str = date.strftime('%Y-%m-%d')
            
            # 每10天重新分析
            if i % 10 == 0 or position is None:
                lookback_df = df.iloc[max(0, i-60):i+1].copy()
                
                # 检测买入信号
                if not position:
                    # 尝试C浪检测 (通过原始分析器)
                    try:
                        analysis = self.analyzer.analyze(symbol, lookback_df)
                        if analysis and analysis.primary_pattern:
                            pattern = analysis.primary_pattern
                            latest_wave = pattern.points[-1].wave_num if pattern.points else None
                            
                            if latest_wave == 'C':
                                position = WaveTrade(
                                    symbol=symbol, name=name, market_cap=market_cap,
                                    entry_date=date_str, entry_price=price, entry_wave='C',
                                    predictednext_wave='1'
                                )
                                entry_idx = i
                                wave_counts['C'] += 1
                                continue
                    except Exception:
                        pass
                    
                    # 尝试2浪检测
                    wave2_sig = self.wave2_detector.detect(lookback_df)
                    if wave2_sig and wave2_sig.is_valid and wave2_sig.confidence >= 0.5:
                        position = WaveTrade(
                            symbol=symbol, name=name, market_cap=market_cap,
                            entry_date=date_str, entry_price=price, entry_wave='2',
                            predictednext_wave='3'
                        )
                        entry_idx = i
                        wave_counts['2'] += 1
                        continue
                    
                    # 尝试4浪检测
                    wave4_sig = self.wave4_detector.detect(lookback_df)
                    if wave4_sig and wave4_sig.is_valid and wave4_sig.confidence >= 0.5:
                        position = WaveTrade(
                            symbol=symbol, name=name, market_cap=market_cap,
                            entry_date=date_str, entry_price=price, entry_wave='4',
                            predictednext_wave='5'
                        )
                        entry_idx = i
                        wave_counts['4'] += 1
                        continue
                
                # 检测卖出信号
                if position:
                    pnl_pct = (price / position.entry_price - 1) * 100
                    holding_days = i - entry_idx
                    
                    # 检查是否达到预期卖点
                    sellsignal = self.detect_sellsignal(lookback_df, position.entry_wave)
                    
                    # 卖出条件
                    should_sell = False
                    exit_wave = None
                    
                    # 条件1: 达到预期浪型卖点
                    if sellsignal:
                        should_sell = True
                        exit_wave = sellsignal['wave']
                    
                    # 条件2: 止盈 (+10%)
                    elif pnl_pct >= 10:
                        should_sell = True
                        exit_wave = 'profit'
                    
                    # 条件3: 止损 (-5%)
                    elif pnl_pct <= -5:
                        should_sell = True
                        exit_wave = 'stop_loss'
                    
                    # 条件4: 最大持仓60天
                    elif holding_days >= 60:
                        should_sell = True
                        exit_wave = 'timeexit'
                    
                    if should_sell:
                        position.exit_date = date_str
                        position.exit_price = price
                        position.pnl_pct = pnl_pct
                        position.holding_days = holding_days
                        position.exit_wave = exit_wave
                        position.status = 'closed'
                        
                        # 评估预测准确度
                        actual_outcome = 'up' if pnl_pct > 0 else 'down'
                        is_correct = self.accuracymetrics.add_prediction(
                            position.entry_wave,
                            position.predictednext_wave,
                            actual_outcome
                        )
                        position.prediction_correct = is_correct
                        position.actualnext_wave = actual_outcome
                        
                        trades.append(position)
                        position = None
        
        # 计算结果
        closedtrades = [t for t in trades if t.status == 'closed']
        wins = [t for t in closedtrades if t.pnl_pct > 0]
        
        if closedtrades:
            win_rate = len(wins) / len(closedtrades)
            avg_return = sum(t.pnl_pct for t in closedtrades) / len(closedtrades)
            total_return = sum(t.pnl_pct for t in closedtrades) / 10  # 模拟10%仓位
            avg_holding = sum(t.holding_days for t in closedtrades) / len(closedtrades)
        else:
            win_rate = 0
            avg_return = 0
            total_return = 0
            avg_holding = 0
        
        # 按浪型统计
        wavestats = {}
        for wave in ['C', '2', '4']:
            wavetrades = [t for t in closedtrades if t.entry_wave == wave]
            if wavetrades:
                wave_wins = [t for t in wavetrades if t.pnl_pct > 0]
                wavestats[wave] = {
                    'count': len(wavetrades),
                    'win_rate': len(wave_wins) / len(wavetrades),
                    'avg_return': sum(t.pnl_pct for t in wavetrades) / len(wavetrades),
                    'correct_predictions': sum(1 for t in wavetrades if t.prediction_correct)
                }
        
        print("\n📈 回测结果:")
        print(f"  总交易: {len(closedtrades)} 笔 (C:{wave_counts['C']}, 2:{wave_counts['2']}, 4:{wave_counts['4']})")
        print(f"  胜率: {win_rate:.1%}")
        print(f"  平均收益: {avg_return:+.2f}%")
        print(f"  总收益: {total_return:+.2f}%")
        print(f"  平均持仓: {avg_holding:.1f} 天")
        
        if wavestats:
            print("\n  各浪型表现:")
            for wave, stats in wavestats.items():
                print(f"    浪{wave}: {stats['count']}笔 胜率{stats['win_rate']:.1%} 收益{stats['avg_return']:+.2f}% 预测准{stats['correct_predictions']}/{stats['count']}")
        
        return {
            'symbol': symbol,
            'name': name,
            'market_cap': market_cap,
            'trades': closedtrades,
            'totaltrades': len(closedtrades),
            'win_rate': win_rate,
            'total_return': total_return,
            'wavestats': wavestats,
            'wave_counts': wave_counts
        }


def run_sector_backtest():
    """运行食品饮料板块回测"""
    print("🚀 食品饮料板块波浪买卖点回测")
    print("="*80)
    print("目标: C/2/4浪买点 → 1/3/5浪卖点")
    print("评估: 浪型识别准确度、买卖点准确率")
    print("="*80)
    
    backtester = WavePatternBacktester()
    results = []
    
    for symbol, name, market_cap in FOOD_BEVERAGE_STOCKS:
        result = backtester.run(symbol, name, market_cap)
        if result['totaltrades'] > 0:
            results.append(result)
    
    # 汇总统计
    print(f"\n{'='*80}")
    print("📊 板块汇总统计")
    print(f"{'='*80}")
    
    if not results:
        print("❌ 无有效回测结果")
        return
    
    # 按市值分组
    large_cap = [r for r in results if r['market_cap'] == 'large']
    medium_cap = [r for r in results if r['market_cap'] == 'medium']
    small_cap = [r for r in results if r['market_cap'] == 'small']
    
    print("\n按市值分组:")
    for group_name, groupdata in [('大市值', large_cap), ('中市值', medium_cap), ('小市值', small_cap)]:
        if groupdata:
            totaltrades = sum(r['totaltrades'] for r in groupdata)
            avg_win_rate = sum(r['win_rate'] for r in groupdata) / len(groupdata)
            avg_return = sum(r['total_return'] for r in groupdata) / len(groupdata)
            print(f"  {group_name}: {len(groupdata)}只 总交易{totaltrades}笔 胜率{avg_win_rate:.1%} 收益{avg_return:+.2f}%")
    
    # 按浪型汇总
    print("\n按浪型汇总:")
    total_wave_counts = {'C': 0, '2': 0, '4': 0}
    for r in results:
        for wave, count in r['wave_counts'].items():
            total_wave_counts[wave] += count
    
    for wave, count in sorted(total_wave_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            wavetrades = []
            for r in results:
                if wave in r['wavestats']:
                    wavetrades.extend([t for t in r['trades'] if t.entry_wave == wave])
            
            if wavetrades:
                wins = [t for t in wavetrades if t.pnl_pct > 0]
                correct_preds = sum(1 for t in wavetrades if t.prediction_correct)
                avg_return = sum(t.pnl_pct for t in wavetrades) / len(wavetrades)
                print(f"  浪{wave}: {count}次信号 {len(wavetrades)}笔交易 胜率{len(wins)/len(wavetrades):.1%} 预测准{correct_preds}/{len(wavetrades)} 收益{avg_return:+.2f}%")
    
    # 准确度评估
    metrics = backtester.accuracymetrics
    if metrics.totalsignals > 0:
        print("\n浪型预测准确度:")
        print(f"  总预测: {metrics.totalsignals} 次")
        print(f"  正确预测: {metrics.correct_predictions} 次")
        print(f"  整体准确率: {metrics.correct_predictions/metrics.totalsignals:.1%}")
        
        print("\n各浪型预测详情:")
        for wave, data in metrics.wave_accuracy.items():
            if data['total'] > 0:
                acc = data['correct'] / data['total']
                print(f"  浪{wave}: 准确率 {acc:.1%} ({data['correct']}/{data['total']})")
                print(f"    预期走势: {dict(data['predictions'])}")
                print(f"    实际走势: {dict(data['outcomes'])}")
    
    # 详细结果表
    print(f"\n{'='*80}")
    print("📋 个股详细结果")
    print(f"{'='*80}")
    print(f"{'代码':<10} {'名称':<10} {'市值':<8} {'交易':<6} {'胜率':<8} {'收益':<8} {'C/2/4':<10}")
    print("-" * 70)
    for r in results:
        counts = r['wave_counts']
        wave_str = f"{counts['C']}/{counts['2']}/{counts['4']}"
        win_rate_str = f"{r['win_rate']:.1%}"
        ret_str = f"{r['total_return']:+.1f}%"
        print(f"{r['symbol']:<10} {r['name']:<10} {r['market_cap']:<8} {r['totaltrades']:<6} {win_rate_str:<8} {ret_str:<8} {wave_str:<10}")
    
    print("\n✅ 回测完成")
    return results


if __name__ == "__main__":
    results = run_sector_backtest()
