#!/usr/bin/env python3
"""
优化版回测 - 集成2/4浪买卖点
"""



import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from analysis.backtest.wave_backtester import Trade, TradeAction, WaveBacktester, WaveStrategy
from analysis.wave import UnifiedWaveAnalyzer
from data import get_stock_data


class ImpulseWaveOptimizer:
    """
    推动浪优化器 - 专门识别2浪和4浪买入点
    """

    def __init__(self,
                 min_wave_change: float = 0.02,
                 max_wave2_retrace: float = 0.618,
                 max_wave4_retrace: float = 0.5):
        self.min_wave_change = min_wave_change
        self.max_wave2_retrace = max_wave2_retrace
        self.max_wave4_retrace = max_wave4_retrace

    def find_buysignals(self, df: pd.DataFrame) -> list[dict]:
        """
        寻找推动浪2浪和4浪买入信号

        Returns:
            信号列表，每个信号包含:
            - entry_wave: '2' 或 '4'
            - entry_price: 买入价格
            - entry_date: 买入日期
            - target_price: 目标价格
            - stop_loss: 止损价格
            - confidence: 置信度
            - direction: 'up' 或 'down'
        """
        prices = df['close'].values
        dates = df['date'].values

        # 找极值点
        pivots = self._findpivots(prices, dates, window=3)
        if len(pivots) < 4:
            return []

        signals = []

        # 遍历寻找12345模式
        for i in range(len(pivots) - 3):
            # 尝试以pivots[i]作为浪1起点
            p1_idx, p1_price, p1_date = pivots[i]

            for j in range(i+1, min(i+4, len(pivots)-2)):
                p2_idx, p2_price, p2_date = pivots[j]

                # 检查浪1幅度
                wave1 = abs(p2_price - p1_price)
                if wave1 < p1_price * self.min_wave_change:
                    continue

                direction_up = p2_price > p1_price

                for k in range(j+1, min(j+4, len(pivots)-1)):
                    p3_idx, p3_price, p3_date = pivots[k]

                    # 浪3应该在浪1方向延伸
                    if direction_up and p3_price <= p2_price:
                        continue
                    if not direction_up and p3_price >= p2_price:
                        continue

                    wave2 = abs(p3_price - p2_price)
                    w2_retrace = wave2 / wave1

                    # 浪2回撤检查
                    if w2_retrace > self.max_wave2_retrace:
                        continue

                    # 检查浪3幅度
                    wave3 = abs(p3_price - p2_price)
                    if wave3 < wave1 * 0.8:
                        continue

                    # 寻找浪4
                    for m in range(k+1, min(k+5, len(pivots))):
                        p4_idx, p4_price, p4_date = pivots[m]

                        wave4 = abs(p4_price - p3_price)
                        w4_retrace = wave4 / wave3

                        # 浪4回撤检查
                        if w4_retrace > self.max_wave4_retrace:
                            continue

                        # 检查是否有第5点
                        if m + 1 < len(pivots):
                            p5_idx, p5_price, p5_date = pivots[m+1]
                            # 完整12345，不买入
                            continue

                        # 当前在4浪！这是一个买入信号
                        confidence = self._calc_confidence(w2_retrace, w4_retrace, wave3/wave1)

                        # 计算目标价 = 4浪低点 + 浪1幅度
                        if direction_up:
                            target = p4_price + wave1
                            stop_loss = min(p4_price * 0.98, p2_price * 0.99)
                        else:
                            target = p4_price - wave1
                            stop_loss = max(p4_price * 1.02, p2_price * 1.01)

                        signals.append({
                            'entry_wave': '4',
                            'entry_price': p4_price,
                            'entry_date': p4_date,
                            'target_price': target,
                            'stop_loss': stop_loss,
                            'confidence': confidence,
                            'direction': 'up' if direction_up else 'down',
                            'wave1_price': p1_price,
                            'wave2_price': p2_price,
                            'wave3_price': p3_price,
                            'wave2_retrace': w2_retrace,
                            'wave4_retrace': w4_retrace
                        })

        return signals

    def _findpivots(self, prices: np.ndarray, dates: np.ndarray, window: int = 3) -> list[tuple]:
        """寻找极值点"""
        pivots = []
        for i in range(window, len(prices) - window):
            ispeak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                     all(prices[i] >= prices[i+j] for j in range(1, window+1))

            is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                       all(prices[i] <= prices[i+j] for j in range(1, window+1))

            if ispeak or is_trough:
                pivots.append((i, prices[i], dates[i]))

        return pivots

    def _calc_confidence(self, w2_ret: float, w4_ret: float, w3_ratio: float) -> float:
        """计算置信度"""
        score = 0.5

        # 浪2回撤合理 (30%-50%)
        if 0.3 <= w2_ret <= 0.5:
            score += 0.15
        elif w2_ret <= 0.618:
            score += 0.1

        # 浪4回撤合理 (20%-40%)
        if 0.2 <= w4_ret <= 0.4:
            score += 0.15
        elif w4_ret <= 0.5:
            score += 0.1

        # 浪3强劲
        if w3_ratio > 1.5:
            score += 0.1

        return min(score, 0.9)


class OptimizedWaveBacktester(WaveBacktester):
    """优化版回测器 - 集成推动浪识别"""

    def __init__(self, analyzer, impulse_optimizer=None):
        super().__init__(analyzer)
        self.impulse_optimizer = impulse_optimizer or ImpulseWaveOptimizer()

    def run_with_impulse(self, symbol: str, df: pd.DataFrame, reanalyze_every: int = 30):
        """运行回测 - 同时使用原始检测和推动浪优化"""
        print(f"\n{'='*80}")
        print(f"📊 优化版回测 - {symbol}")
        print(f"{'='*80}")

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        trades = []
        equity = [self.strategy.initial_capital]
        current_analysis = None
        position = None

        wavestats = {'C': 0, '4': 0, '2': 0, 'other': 0}

        for i, (_idx, row) in enumerate(df.iterrows()):
            date = row['date'].strftime('%Y-%m-%d')
            price = row['close']

            # 定期重新分析
            if i % reanalyze_every == 0 or current_analysis is None:
                lookback_start = max(0, i - 60)
                analysis_df = df.iloc[lookback_start:i+1].copy()

                current_analysis = None
                impulsesignals = []

                if len(analysis_df) >= 20:
                    try:
                        # 1. 原始检测
                        current_analysis = self.analyzer.analyze(symbol, analysis_df)

                        # 2. 推动浪优化检测
                        impulsesignals = self.impulse_optimizer.find_buysignals(analysis_df)

                    except Exception:
                        pass

            # 生成信号
            signal = None
            entry_wave = None
            target_price = None
            stop_loss = None

            # 优先使用推动浪信号（如果找到4浪买入点）
            if impulsesignals and not position:
                bestsignal = max(impulsesignals, key=lambda x: x['confidence'])
                if bestsignal['confidence'] >= self.strategy.min_confidence:
                    # 检查日期匹配
                    signal_date = pd.to_datetime(bestsignal['entry_date']).strftime('%Y-%m-%d')
                    if signal_date == date:
                        signal = TradeAction.BUY
                        entry_wave = '4'
                        target_price = bestsignal['target_price']
                        stop_loss = bestsignal['stop_loss']
                        wavestats['4'] += 1

            # 如果没有推动浪信号，使用原始信号
            if signal is None and current_analysis and current_analysis.primary_pattern:
                pattern = current_analysis.primary_pattern

                # 检查是否是买入点
                latest_wave = pattern.points[-1].wave_num if pattern.points else None

                if latest_wave in ['2', '4', 'C', 'A', 'B'] and not position:
                    signal = self.strategy.generatesignal(current_analysis, price)
                    if signal == TradeAction.BUY:
                        entry_wave = latest_wave
                        target_price = pattern.target_price
                        stop_loss = pattern.stop_loss
                        wavestats[latest_wave if latest_wave in ['2', '4', 'C'] else 'other'] += 1
                elif position:
                    signal = self.strategy.generatesignal(current_analysis, price)

            # 执行交易
            if signal == TradeAction.BUY and not position:
                # 买入
                target = target_price or price * 1.1
                stop = stop_loss or price * 0.95

                trade = Trade(
                    symbol=symbol,
                    entry_date=date,
                    entry_price=price,
                    action=TradeAction.BUY,
                    target_price=target,
                    stop_loss=stop,
                    entry_idx=i,
                    entry_wave=entry_wave or 'C'
                )
                position = trade

            elif signal == TradeAction.CLOSE and position:
                # 卖出
                position.exit_date = date
                position.exit_price = price
                position.pnl = (price - position.entry_price) * position.quantity
                position.pnl_pct = (price / position.entry_price - 1) * 100
                position.status = 'closed'
                position.holding_days = i - position.entry_idx
                trades.append(position)
                position = None

            # 检查止损止盈
            if position:
                pnl_pct = (price / position.entry_price - 1) * 100

                if pnl_pct <= -5:  # 止损
                    position.exit_date = date
                    position.exit_price = price
                    position.pnl_pct = pnl_pct
                    position.status = 'closed'
                    position.holding_days = i - position.entry_idx
                    trades.append(position)
                    position = None

            # 更新权益
            if position:
                current_equity = self.strategy.initial_capital * (1 + (price - position.entry_price) / position.entry_price * 0.2)
            else:
                current_equity = equity[-1]
            equity.append(current_equity)

        # 计算结果
        closedtrades = [t for t in trades if t.status == 'closed']
        wins = [t for t in closedtrades if t.pnl_pct > 0]

        total_return = (equity[-1] / self.strategy.initial_capital - 1) * 100
        win_rate = len(wins) / len(closedtrades) if closedtrades else 0

        print("\n📈 结果统计:")
        print(f"  总交易: {len(closedtrades)} 笔")
        print(f"  胜率: {win_rate:.1%}")
        print(f"  总收益: {total_return:+.2f}%")
        print("\n  买入浪号分布:")
        for wave, count in sorted(wavestats.items()):
            if count > 0:
                print(f"    浪{wave}: {count} 次")

        return {
            'trades': closedtrades,
            'total_return': total_return,
            'win_rate': win_rate,
            'wavestats': wavestats
        }


# 测试
if __name__ == "__main__":
    print("🧪 优化版回测测试 (2/4浪买卖点增强)")
    print("="*80)

    test_stocks = [
        ('600519', '茅台'),
        ('000858', '五粮液'),
        ('600600', '青岛啤酒'),
    ]

    for symbol, _name in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')

        analyzer = UnifiedWaveAnalyzer(use_adaptive_params=False)
        optimizer = ImpulseWaveOptimizer()
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

        backtester = OptimizedWaveBacktester(analyzer, optimizer)
        backtester.strategy = strategy

        result = backtester.run_with_impulse(symbol, df, reanalyze_every=30)

    print("\n✅ 测试完成")
