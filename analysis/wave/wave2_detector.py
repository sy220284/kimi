#!/usr/bin/env python3
"""
2浪买入点检测器 - 推动浪回调买入
"""


from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Wave2Signal:
    """2浪买入信号"""
    is_valid: bool
    entry_price: float
    target_price: float
    stop_loss: float
    confidence: float
    direction: str
    wave2_retrace: float
    entry_wave: str = '2'


class Wave2Detector:
    """
    2浪买入点检测器

    检测逻辑:
    1. 找到浪1 (明显的上升/下降)
    2. 浪2回撤浪1的30%-61.8%
    3. 在回撤区域内买入，预期浪3
    """

    def __init__(self,
                 min_wave_pct: float = 0.015,
                 min_retrace: float = 0.30,
                 max_retrace: float = 0.618,
                 lookback: int = 30):
        self.min_wave_pct = min_wave_pct
        self.min_retrace = min_retrace
        self.max_retrace = max_retrace
        self.lookback = lookback

    def detect(self, df: pd.DataFrame) -> Wave2Signal | None:
        """检测当前是否处于2浪买入点"""
        if len(df) < self.lookback:
            return None

        df_window = df.iloc[-self.lookback:].copy().reset_index(drop=True)
        prices = df_window['close'].values

        # 找极值点
        pivots = self._find_pivots(prices, window=2)
        if len(pivots) < 3:
            return None

        # 取最后3个极值点 (浪1起点, 浪1终点/浪2起点, 浪2终点)
        p1_idx, p1_price = pivots[-3]
        p2_idx, p2_price = pivots[-2]
        p3_idx, p3_price = pivots[-1]

        # 计算浪1幅度
        wave1_amp = abs(p2_price - p1_price)
        if wave1_amp < p1_price * self.min_wave_pct:
            return None

        # 确定方向
        direction_up = p2_price > p1_price

        # 验证浪1结构
        if direction_up:
            # 上升浪1: p1 < p2
            if not (p2_price > p1_price):
                return None
            # 浪2回撤: p3在p1和p2之间
            if not (p1_price < p3_price < p2_price):
                return None
        else:
            # 下降浪1: p1 > p2
            if not (p2_price < p1_price):
                return None
            # 浪2回撤: p3在p1和p2之间
            if not (p1_price > p3_price > p2_price):
                return None

        # 计算浪2回撤比例
        wave2_amp = abs(p3_price - p2_price)
        retrace_ratio = wave2_amp / wave1_amp

        if not (self.min_retrace <= retrace_ratio <= self.max_retrace):
            return None

        # 当前价格应该在浪2回撤区域内
        current_price = prices[-1]

        if direction_up:
            # 当前价格应该在p3附近或之上
            if current_price < p3_price * 0.98:  # 不能低于浪2低点太多
                return None
            # 目标价: 浪1等长 (保守) 或1.618倍 (激进)
            target = current_price + wave1_amp * 1.0
            # 止损: 浪1起点下方
            stop_loss = p1_price * 0.99
        else:
            if current_price > p3_price * 1.02:
                return None
            target = current_price - wave1_amp * 1.0
            stop_loss = p1_price * 1.01

        # 置信度
        confidence = 0.5
        # 理想回撤区间 38.2%-50% 置信度更高
        if 0.382 <= retrace_ratio <= 0.5:
            confidence += 0.2
        # 回撤在50%-61.8% 中等置信度
        elif 0.5 < retrace_ratio <= 0.618:
            confidence += 0.1

        return Wave2Signal(
            is_valid=True,
            entry_price=current_price,
            target_price=target,
            stop_loss=stop_loss,
            confidence=min(confidence, 0.8),
            direction='up' if direction_up else 'down',
            wave2_retrace=retrace_ratio
        )

    def _find_pivots(self, prices: np.ndarray, window: int = 2) -> list[tuple[int, float]]:
        """寻找极值点"""
        pivots = []
        for i in range(window, len(prices) - window):
            is_peak = all(prices[i] >= prices[i-j] for j in range(1, window+1)) and \
                     all(prices[i] >= prices[i+j] for j in range(1, window+1))
            is_trough = all(prices[i] <= prices[i-j] for j in range(1, window+1)) and \
                       all(prices[i] <= prices[i+j] for j in range(1, window+1))
            if is_peak or is_trough:
                pivots.append((i, prices[i]))
        return pivots


# 便捷函数
def detect_wave2(df: pd.DataFrame,
                 min_wave_pct: float = 0.015,
                 min_retrace: float = 0.30,
                 max_retrace: float = 0.618,
                 lookback: int = 30) -> Wave2Signal | None:
    """便捷函数 - 检测2浪买入点"""
    detector = Wave2Detector(
        min_wave_pct=min_wave_pct,
        min_retrace=min_retrace,
        max_retrace=max_retrace,
        lookback=lookback
    )
    return detector.detect(df)


if __name__ == "__main__":
    # 测试
    from data import get_stock_data

    print("🧪 Wave2Detector 测试")
    print("="*70)

    test_stocks = [
        ('600519', '茅台'),
        ('000858', '五粮液'),
        ('300750', '宁德时代'),
    ]

    for symbol, name in test_stocks:
        df = get_stock_data(symbol, '2023-01-01', '2026-03-16')
        df['date'] = pd.to_datetime(df['date'])

        signals = []
        for i in range(40, len(df), 10):
            window_df = df.iloc[i-40:i].copy()
            result = detect_wave2(window_df)
            if result and result.is_valid and result.confidence >= 0.5:
                signals.append({
                    'date': df.iloc[i]['date'],
                    'price': result.entry_price,
                    'target': result.target_price,
                    'retrace': result.wave2_retrace,
                    'confidence': result.confidence
                })

        print(f"\n{symbol} {name}:")
        print(f"  找到 {len(signals)} 个2浪信号")
        for sig in signals[:2]:
            target_pct = (sig['target'] / sig['price'] - 1) * 100
            print(f"  {sig['date'].strftime('%Y-%m-%d')}: ¥{sig['price']:.2f} -> ¥{sig['target']:.2f} ({target_pct:+.1f}%) 回撤{sig['retrace']:.1%} 置信{sig['confidence']:.2f}")

    print("\n✅ 测试完成")
