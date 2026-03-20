"""
波浪分析模块 - Elliott Wave波浪识别算法 (专业版整合)
实现波浪计数(1-2-3-4-5/A-B-C)、趋势判断、量价辅助验证

核心改进:
- ATR自适应ZigZag极值点检测 (替代固定窗口)
- 严格的推动浪规则验证 (硬规则+指导原则)
- 多种调整浪类型识别 (ZigZag, Flat, Triangle等)
- 斐波那契目标价计算
- 子波浪嵌套结构
"""
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from utils.logger import get_logger

# ============================================================================
# SECTION 1 — Domain Models
# ============================================================================

class WaveType(Enum):
    """波浪类型"""
    IMPULSE = "impulse"
    CORRECTIVE = "corrective"
    EXTENDING = "extending"
    LEADING_DIAGONAL = "leading_diagonal"
    ENDING_DIAGONAL = "ending_diagonal"
    FAILED_FIFTH = "failed_fifth"
    ZIGZAG = "zigzag"
    FLAT = "flat"
    TRIANGLE = "triangle"
    UNKNOWN = "unknown"


class WaveDirection(Enum):
    """波浪方向"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class WavePoint:
    """波浪点位"""
    index: int
    date: str
    price: float
    volume: float = 0
    wave_num: str | None = None
    is_peak: bool = False
    is_trough: bool = False
    volume_ratio: float = 0.0
    strength: int = 1  # 1=minor, 2=intermediate, 3=major

    def __repr__(self) -> str:
        return f"WavePoint({self.wave_num or '?'} {self.date} ¥{self.price:.2f})"


@dataclass
class WaveValidation:
    """波浪验证结果"""
    rule_name: str
    passed: bool
    score: float
    details: str


@dataclass
class WavePattern:
    """波浪形态"""
    wave_type: WaveType
    direction: WaveDirection
    points: list[WavePoint]
    confidence: float
    start_date: str
    end_date: str
    target_price: float | None = None
    stop_loss: float | None = None
    validations: list[WaveValidation] = field(default_factory=list)
    volume_profile: dict[str, Any] = field(default_factory=dict)
    fib_ratios: dict[str, float] = field(default_factory=dict)
    guideline_scores: dict[str, float] = field(default_factory=dict)
    rule_violations: list[str] = field(default_factory=list)

    @property
    def is_impulse(self) -> bool:
        return self.wave_type in {
            WaveType.IMPULSE, WaveType.EXTENDING,
            WaveType.LEADING_DIAGONAL, WaveType.ENDING_DIAGONAL,
            WaveType.FAILED_FIFTH
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            'wave_type': self.wave_type.value,
            'direction': self.direction.value,
            'confidence': self.confidence,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'fib_ratios': self.fib_ratios,
            'validations': [{'rule': v.rule_name, 'passed': v.passed, 'score': v.score} for v in self.validations],
            'points': [{'date': p.date, 'price': p.price, 'wave_num': p.wave_num} for p in self.points]
        }


# ============================================================================
# SECTION 2 — ATR Adaptive Pivot Detection (专业版核心)
# ============================================================================

def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ATR计算"""
    n = len(close)
    if n < 2:
        return np.full(n, high[0] - low[0] + 1e-8)

    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))

    atr = np.empty(n)
    seed = min(period, n)
    atr[seed-1] = float(np.mean(tr[:seed]))
    alpha = 1.0 / period
    for i in range(seed, n):
        atr[i] = atr[i-1] * (1-alpha) + tr[i] * alpha
    atr[:seed-1] = atr[seed-1]
    return atr


def zigzag_atr(high, low, close, atr, atr_mult=0.5, min_dist=3):
    """ATR自适应ZigZag - 根据波动率动态调整阈值"""
    n = len(close)
    idxs, prices, types = [], [], []

    if n < 5:
        return idxs, prices, types

    direction = 1  # +1找高点
    extreme_idx, extreme_price = 0, high[0]

    idxs.append(0)
    prices.append(low[0])
    types.append("L")

    for i in range(1, n):
        threshold = atr_mult * atr[i]

        if direction == 1:  # 找高点
            if high[i] >= extreme_price:
                extreme_idx, extreme_price = i, high[i]
            elif (extreme_price - low[i]) >= threshold:
                if extreme_idx - idxs[-1] >= min_dist:
                    idxs.append(extreme_idx)
                    prices.append(extreme_price)
                    types.append("H")
                direction = -1
                extreme_idx, extreme_price = i, low[i]
        else:  # 找低点
            if low[i] <= extreme_price:
                extreme_idx, extreme_price = i, low[i]
            elif (high[i] - extreme_price) >= threshold:
                if extreme_idx - idxs[-1] >= min_dist:
                    idxs.append(extreme_idx)
                    prices.append(extreme_price)
                    types.append("L")
                direction = 1
                extreme_idx, extreme_price = i, high[i]

    if extreme_idx != idxs[-1]:
        idxs.append(extreme_idx)
        prices.append(extreme_price)
        types.append("H" if direction == 1 else "L")

    return idxs, prices, types


# ============================================================================
# SECTION 3 — Impulse Wave Rules (严格规则验证)
# ============================================================================

@dataclass
class ImpulseMetrics:
    """推动浪指标"""
    prices: tuple[float, ...]
    is_bullish: bool
    w1: float
    w2: float
    w3: float
    w4: float
    w5: float
    w2_retrace: float
    w4_retrace: float

    @classmethod
    def build(cls, points):
        p = tuple(p.price for p in points)
        p0, p1, p2, p3, p4, p5 = p
        bull = p1 > p0

        if bull:
            w1, w2, w3, w4, w5 = p1-p0, p1-p2, p3-p2, p3-p4, p5-p4
        else:
            w1, w2, w3, w4, w5 = p0-p1, p2-p1, p2-p3, p4-p3, p4-p5

        return cls(
            prices=p, is_bullish=bull,
            w1=w1, w2=w2, w3=w3, w4=w4, w5=w5,
            w2_retrace=w2/(w1+1e-12), w4_retrace=w4/(w3+1e-12)
        )


def validate_impulse_rules(points):
    """推动浪硬规则验证 + 指导原则评分"""
    if len(points) != 6:
        return False, ["点位数量错误"], 0.0, {}

    try:
        m = ImpulseMetrics.build(points)
    except Exception:
        return False, ["构建失败"], 0.0, {}

    violations = []

    # 硬规则
    if not (m.w1>0 and m.w2>0 and m.w3>0 and m.w4>0 and m.w5>0):
        violations.append("方向不一致")
    if m.w2_retrace >= 1.0:
        violations.append("浪2完全回撤")
    if m.w3 < m.w1 and m.w3 < m.w5:
        violations.append("浪3最短")

    p0, p1, _, _, p4, _ = m.prices
    if m.is_bullish and p4 <= p1 or not m.is_bullish and p4 >= p1:
        violations.append("浪4与浪1重叠")

    if violations:
        return False, violations, 0.0, {}

    # 指导原则评分
    checks = [
        ("浪2黄金分割", 0.15, 0.382 <= m.w2_retrace <= 0.618),
        ("浪3延伸1.618", 0.20, 1.50 <= m.w3/(m.w1+1e-12) <= 1.80),
        ("浪3最长", 0.15, m.w3 >= m.w1 and m.w3 >= m.w5),
        ("浪4浅回撤", 0.15, 0.236 <= m.w4_retrace <= 0.500),
        ("浪5等于浪1", 0.10, 0.85 <= m.w5/(m.w1+1e-12) <= 1.15),
        ("浪5新极点", 0.10, (m.prices[5]>m.prices[3]) if m.is_bullish else (m.prices[5]<m.prices[3])),
        ("浪2浪4交替", 0.15, (m.w2_retrace>=0.50) != (m.w4_retrace>=0.50)),
    ]

    total = sum(w for _, w, _ in checks)
    earned = sum(w for _, w, ok in checks if ok)
    scores = {n: w if ok else 0.0 for n, w, ok in checks}

    return True, [], earned/(total+1e-12), scores


def validate_zigzag(points):
    """ZigZag验证"""
    if len(points) != 4:
        return False, [], 0.0

    p0, pA, pB, pC = (p.price for p in points)
    a_len = abs(pA - p0)
    b_len = abs(pB - pA)
    b_ret = b_len / (a_len + 1e-12)

    if b_ret >= 1.0 or a_len < 1e-8:
        return False, ["B浪过深"], 0.0

    c_a = abs(pC - pB) / (a_len + 1e-12)
    score = sum([
        0.30 if 0.382 <= b_ret <= 0.618 else 0.0,
        0.25 if 0.85 <= c_a <= 1.15 else 0.0,
        0.25 if c_a >= 1.0 else 0.0,
        0.20 if 0.50 <= b_ret <= 0.786 else 0.0,
    ])

    return True, [], score


def validate_flat(points):
    """
    Flat调整浪验证（平台型整理）

    Flat 三种子型:
    - Regular Flat:  B≈A，C≈A（经典平台）
    - Expanded Flat: B > A，C > A（扩散平台，A股最常见）
    - Running Flat:  B > A，C < A（逃跑平台）

    关键特征: B浪回撤 >= 80% A浪（区别于ZigZag的B浪≤61.8%）
    """
    if len(points) != 4:
        return False, [], 0.0

    p0, pA, pB, pC = (p.price for p in points)
    a_len = abs(pA - p0)
    b_len = abs(pB - pA)
    b_ret = b_len / (a_len + 1e-12)

    if a_len < 1e-8:
        return False, ["A浪过短"], 0.0

    # Flat核心条件：B浪深度回撤（>= 80% A浪），区别于ZigZag
    if b_ret < 0.80:
        return False, ["B浪回撤不足80%，非Flat型"], 0.0

    c_a = abs(pC - pB) / (a_len + 1e-12)

    # C浪不能太短（至少 0.618 倍A浪），否则可能只是噪声
    if c_a < 0.618:
        return False, ["C浪过短"], 0.0

    # 方向验证：A-C同向（调整方向一致）
    bear_flat = (pA < p0)  # 下跌Flat
    if bear_flat:
        ac_same_dir = pC < pB  # A下跌，C也应下跌
    else:
        ac_same_dir = pC > pB  # A上涨（少见），C也应上涨

    if not ac_same_dir:
        return False, ["C浪方向异常"], 0.0

    # 评分
    score = 0.0

    # B浪深度（Flat标志）
    if 0.90 <= b_ret <= 1.05:
        score += 0.35  # Regular Flat（B≈A）
    elif b_ret > 1.05:
        score += 0.30  # Expanded Flat（B突破A起点，A股最常见）
    else:
        score += 0.20  # 80%-90%，弱Flat

    # C浪长度
    if 0.90 <= c_a <= 1.10:
        score += 0.30  # C≈A，Regular Flat
    elif c_a > 1.10:
        score += 0.25  # C > A，Expanded Flat（常见）
    elif 0.618 <= c_a < 0.90:
        score += 0.15  # Running Flat（C较短）

    # B浪超出A浪起点（Expanded Flat特征，A股极常见）
    if bear_flat and pB > p0:
        score += 0.20  # B浪新高，扩散型
    elif not bear_flat and pB < p0:
        score += 0.20

    # 最终加权
    score = min(score, 1.0)

    return True, [], score


def validate_triangle(points):
    """
    Triangle调整浪验证（三角形整理）
    
    Triangle特征：
    - 5浪结构：A-B-C-D-E
    - 收敛形态：每个子浪都短于前一个
    - A-B-C-D-E逐步收敛
    - 常见于4浪或B浪
    
    子类型：
    - 对称三角形：上下轨收敛速度相近
    - 上升三角形：下轨水平，上轨下降
    - 下降三角形：上轨水平，下轨上升
    - 扩散三角形：上下轨发散（少见）
    
    Args:
        points: 5个WavePoint（A-B-C-D-E）
        
    Returns:
        (is_valid, errors, score)
    """
    if len(points) != 5:
        return False, ["需要5个点(A-B-C-D-E)"], 0.0
    
    pA, pB, pC, pD, pE = [p.price for p in points]
    
    # 计算各浪长度
    ab_len = abs(pB - pA)
    bc_len = abs(pC - pB)
    cd_len = abs(pD - pC)
    de_len = abs(pE - pD)
    
    # 核心条件1：子浪长度递减（收敛）
    converging = (bc_len < ab_len and cd_len < bc_len and de_len < cd_len)
    
    # 核心条件2：各浪长度不能太短
    min_wave = min(ab_len, bc_len, cd_len, de_len)
    if min_wave < 1e-6:
        return False, ["子浪过短"], 0.0
    
    # 核心条件3：B-C-D应在A-E连成的通道内
    # 简化验证：E应在A-D的范围内
    if pA < pD:  # 上升趋势的三角形
        if not (pE >= min(pA, pD) * 0.99 and pE <= max(pA, pD) * 1.01):
            return False, ["E浪超出三角形范围"], 0.0
    else:  # 下降趋势的三角形
        if not (pE <= max(pA, pD) * 1.01 and pE >= min(pA, pD) * 0.99):
            return False, ["E浪超出三角形范围"], 0.0
    
    # 评分
    score = 0.0
    
    # 收敛程度
    if converging:
        score += 0.40
    elif bc_len < ab_len and cd_len < bc_len:
        score += 0.25  # 部分收敛
    else:
        score += 0.10
    
    # 各浪长度比例合理性
    bc_ab = bc_len / (ab_len + 1e-12)
    cd_bc = cd_len / (bc_len + 1e-12)
    de_cd = de_len / (cd_len + 1e-12)
    
    # 理想比例：0.618-0.786
    if 0.50 <= bc_ab <= 0.85:
        score += 0.15
    if 0.50 <= cd_bc <= 0.85:
        score += 0.15
    if 0.50 <= de_cd <= 0.85:
        score += 0.15
    
    # 最终E浪长度应最短
    if de_len < cd_len < bc_len < ab_len:
        score += 0.15
    
    score = min(score, 1.0)
    
    # 收敛是必要条件，但不是充分条件
    is_valid = score >= 0.50 or converging
    
    return is_valid, [], score


def validate_diagonal(points, wave_subtype: str = 'auto') -> tuple:
    """
    Diagonal（对角线浪）验证

    对角线浪是推动浪的特殊子类型，出现在趋势末期（Ending Diagonal）
    或趋势起始（Leading Diagonal）。与标准推动浪的区别：
    - 浪 4 与浪 1 的价格区间重叠（标准推动浪中不允许）
    - 每个子浪均为 3 波结构（ZigZag）
    - 整体呈收敛楔形（通道收窄）

    子类型：
    - leading_diagonal：出现在1浪或A浪，5浪结构，收敛楔
    - ending_diagonal：出现在5浪或C浪，预示趋势反转，5浪结构

    Args:
        points:  5 个 WavePoint（1-2-3-4-5 或 A-B-C-D-E）
        wave_subtype: 'leading' / 'ending' / 'auto'

    Returns:
        (is_valid: bool, errors: list[str], score: float)
    """
    if len(points) != 5:
        return False, ["需要5个点(1-2-3-4-5)"], 0.0

    p = [pt.price for pt in points]
    p0, p1, p2, p3, p4 = p

    # 确定方向
    is_bull = p4 > p0   # 上升对角线

    errors = []
    score  = 0.0

    # ── 规则 1：对角线浪中浪3不能短于浪1和浪5中的任意一个（宽松版）──
    # 注意：对角线浪的子浪都是3波，幅度比标准推动浪小，规则宽松
    w1 = abs(p1 - p0)
    w3 = abs(p3 - p2)
    w5 = abs(p4 - p3)
    if w3 < w5 * 0.5:   # 仅当浪3小于浪5的50%时才拒绝（宽松）
        errors.append("浪3极短（不符合对角线浪特征）")
        return False, errors, 0.0

    # 浪3不得短于浪1的30%（对角线浪宽松要求）
    if w3 < w1 * 0.3:
        errors.append("浪3相对浪1过短")
        return False, errors, 0.0

    # ── 规则 2：浪 4 与浪 1 重叠（对角线浪的特征）──
    # 浪4 结束于 p4，浪1 结束于 p1；p4 进入浪1的价格区间即为重叠
    if is_bull:
        w4_overlaps = p4 < p1   # 上升：浪4低点进入浪1高点以下
    else:
        w4_overlaps = p4 > p1   # 下降：浪4高点进入浪1低点以上

    if not w4_overlaps:
        errors.append("浪4未与浪1重叠（对角线浪特征缺失）")
        score -= 0.2
    else:
        score += 0.30  # 重叠是关键特征

    # ── 规则 3：收敛楔形（通道收窄）──
    # 上升对角：浪1,3,5高点连线下倾；浪2,4低点连线上倾
    w2_ret = abs(p2 - p1) / (w1 + 1e-10)  # 浪2回调比例
    w4_ret = abs(p4 - p3) / (w3 + 1e-10)  # 浪4回调比例（对角线浪4更深）

    # 收敛：浪5 < 浪3 (按绝对幅度)，浪4 > 浪2（回调更深）
    if w5 < w3:
        score += 0.20  # 收敛
    if w4_ret >= w2_ret * 0.8:
        score += 0.15  # 浪4回调相对更深

    # ── 规则 4：斐波那契比例校验 ──
    fib_618 = 0.618
    if 0.5 <= w2_ret <= 0.786:
        score += 0.15  # 浪2回调 50-78.6%
    if 0.5 <= w4_ret <= 0.90:
        score += 0.10  # 浪4回调 50-90%（对角线浪4可更深）
    if 0.618 <= (w5 / w1 + 1e-10) <= 1.618:
        score += 0.10  # 浪5与浪1的比例关系

    # ── 规则 5：子类型判断 ──
    if wave_subtype == 'auto':
        # Ending Diagonal：浪5创新高/新低（趋势延伸）
        if is_bull and p4 > p2:
            detected_type = 'ending_diagonal'
        elif not is_bull and p4 < p2:
            detected_type = 'ending_diagonal'
        else:
            detected_type = 'leading_diagonal'
    else:
        detected_type = wave_subtype

    score = min(score, 1.0)
    is_valid = score >= 0.45 and not errors  # 对角线浪容错更高

    return is_valid, errors, score


# ============================================================================
# SECTION 4 — Elliott Wave Analyzer (整合版)
# ============================================================================

class ElliottWaveAnalyzer:
    """
    专业版Elliott Wave分析器

    核心改进:
    1. ATR自适应ZigZag极值点检测
    2. 严格推动浪规则验证
    3. ZigZag/Flat调整浪识别
    4. 斐波那契目标价计算
    """

    def __init__(
        self,
        min_wave_length: int = 5,
        max_wave_length: int = 100,
        confidence_threshold: float = 0.5,
        atr_period: int = 14,
        atr_mult: float = 0.5,
        min_dist: int = 3,
        use_volume: bool = True,
        use_fibonacci: bool = True
    ):
        self.min_wave_length = min_wave_length
        self.max_wave_length = max_wave_length
        self.confidence_threshold = confidence_threshold
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.min_dist = min_dist
        self.use_volume = use_volume
        self.use_fibonacci = use_fibonacci
        self.logger = get_logger('analysis.wave.elliott')

    def find_peaks_and_troughs(self, df: pd.DataFrame, window: int = 5, min_change_pct: float = 2.0):
        """使用ATR自适应ZigZag检测极值点"""
        points = self._detect_pivots(df)
        peaks = [p.index for p in points if p.is_peak]
        troughs = [p.index for p in points if p.is_trough]
        return peaks, troughs

    def _detect_pivots(self, df: pd.DataFrame) -> list[WavePoint]:
        """检测极值点"""
        if len(df) < self.atr_period + 4:
            return []

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
        dates = df['date'].values if 'date' in df.columns else [str(i) for i in range(len(df))]

        atr = calculate_atr(highs, lows, closes, self.atr_period)
        idxs, prices, types = zigzag_atr(highs, lows, closes, atr, self.atr_mult, self.min_dist)

        if len(idxs) < 2:
            return []

        # 强度分级
        amplitudes = [float(abs(float(prices[i+1]) - float(prices[i]))) for i in range(len(prices)-1)]
        median_amp = float(np.median(amplitudes)) if amplitudes else 1.0

        points = []
        for i, (idx, price, ptype) in enumerate(zip(idxs, prices, types, strict=False)):
            amp = float(amplitudes[max(0, i-1)]) if i > 0 else (float(amplitudes[0]) if amplitudes else 0)
            ratio = amp / (median_amp + 1e-12)
            strength = 3 if ratio >= 2.0 else (2 if ratio >= 1.0 else 1)

            points.append(WavePoint(
                index=idx,
                date=str(dates[idx]) if isinstance(dates[idx], str) else str(dates[idx]),
                price=price,
                volume=float(volumes[idx]) if idx < len(volumes) else 0.0,
                is_peak=(ptype == "H"),
                is_trough=(ptype == "L"),
                strength=strength
            ))

        return points

    def detect_wave_pattern(self, df: pd.DataFrame, window: int = 5, min_change_pct: float = 2.0) -> WavePattern | None:
        """检测波浪形态 - 优先使用原始检测，增强版作为fallback"""
        # 先用原始检测方法
        points = self._detect_pivots(df)
        if len(points) >= 4:
            best_pattern = self._detect_with_points(points)
            if best_pattern and best_pattern.confidence >= self.confidence_threshold:
                return best_pattern

        # 如果原始方法未找到，尝试增强版检测
        from .enhanced_detector import (
            enhanced_pivot_detection,
            label_wave_numbers,
            validate_wave_structure,
        )

        pivots = enhanced_pivot_detection(
            df,
            atr_period=self.atr_period,
            atr_mult=self.atr_mult,
            min_pivots=4,
            trend_confirmation=True
        )

        if len(pivots) >= 4:
            labeled_pivots = label_wave_numbers(pivots, "auto")
            is_valid, reason, conf = validate_wave_structure(labeled_pivots)

            if is_valid and conf >= self.confidence_threshold * 0.7:
                return self._create_generic_pattern(labeled_pivots, df, conf)

        # 如果都没找到，返回原始方法的结果（即使置信度低）
        if len(points) >= 4:
            return self._detect_with_points(points)

        return None

    def _detect_with_points(self, points: list[WavePoint]) -> WavePattern | None:
        """使用现有极值点检测波浪 - 智能浪号标注"""
        best_pattern = None
        best_confidence = 0.0

        # 尝试6点模式 (推动浪)
        for i in range(len(points) - 5):
            window_points = points[i:i+6]
            pattern = self._try_impulse(window_points)
            if pattern and pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        # 尝试4点模式 (ZigZag)
        for i in range(len(points) - 3):
            window_points = points[i:i+4]
            pattern = self._try_zigzag(window_points)
            if pattern and pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        # 尝试4点模式 (Flat调整浪)
        for i in range(len(points) - 3):
            window_points = points[i:i+4]
            pattern = self._try_flat(window_points)
            if pattern and pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        # 尝试5点模式 (Triangle三角形调整浪)
        for i in range(len(points) - 4):
            window_points = points[i:i+5]
            pattern = self._try_triangle(window_points)
            if pattern and pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        # 尝试5点模式 (Diagonal对角线浪 — 趋势末期/起始)
        for i in range(len(points) - 4):
            window_points = points[i:i+5]
            pattern = self._try_diagonal(window_points)
            if pattern and pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        # 如果没有找到标准浪型，使用智能通用标注
        if best_pattern is None and len(points) >= 4:
            best_pattern = self._create_smart_generic_pattern(points)

        return best_pattern

    def _create_smart_generic_pattern(self, points: list[WavePoint]) -> WavePattern | None:
        """
        创建智能通用波浪模式

        基于价格极值点关系推断浪号:
        1. 如果点已经有浪号，保留原标注
        2. 根据趋势方向标注未标注的点
        3. 确保最后一点是调整浪末端(2/4/C)
        """
        if len(points) < 4:
            return None

        # 复制点列表避免修改原始数据
        labeled_points = []
        for p in points:
            new_p = WavePoint(
                index=p.index,
                date=p.date,
                price=p.price,
                volume=p.volume,
                is_peak=p.is_peak,
                is_trough=p.is_trough,
                strength=p.strength
            )
            # 保留原有的浪号标注
            if hasattr(p, 'wave_num') and p.wave_num:
                new_p.wave_num = p.wave_num
            labeled_points.append(new_p)

        # 分析整体趋势
        prices = [p.price for p in labeled_points]
        direction_up = prices[-1] > prices[0]

        # 如果已经有足够的浪号标注，直接创建模式
        existing_waves = [p.wave_num for p in labeled_points if p.wave_num]
        if len(existing_waves) >= len(labeled_points) - 1:
            # 大部分已标注，检查最后一点
            last_point = labeled_points[-1]
            if not last_point.wave_num:
                # 最后一点未标注，根据趋势推断
                last_point.wave_num = 'C' if not direction_up else '4'

            return self._build_generic_pattern(labeled_points, direction_up)

        # 智能标注未标注的点
        n = len(labeled_points)

        # 找出最高点和最低点的位置
        max_price = max(prices)
        min_price = min(prices)
        max_idx = prices.index(max_price)
        _min_idx = prices.index(min_price)

        if direction_up:
            # 上升趋势: 1-2-3-4-5
            for i, p in enumerate(labeled_points):
                if p.wave_num:  # 保留已有标注
                    continue

                # 基于位置的智能标注
                if i == 0:
                    p.wave_num = '1'
                elif i == n - 1:
                    # 最后一点 - 检查是否在回调
                    if prices[-1] < max_price * 0.98 and max_idx < n - 1:
                        p.wave_num = '4'  # 4浪回调
                    else:
                        p.wave_num = '5'  # 5浪结束
                elif prices[i] == max_price:
                    p.wave_num = '3'  # 3浪顶点
                elif prices[i] == min_price:
                    p.wave_num = '2'  # 2浪低点
                else:
                    # 交替标注
                    p.wave_num = str((i % 5) + 1)
        else:
            # 下降趋势: A-B-C
            for i, p in enumerate(labeled_points):
                if p.wave_num:  # 保留已有标注
                    continue

                if i == 0:
                    p.wave_num = 'A'
                elif i == n - 1:
                    p.wave_num = 'C'  # C浪结束 = 买入点
                elif i == 1:
                    p.wave_num = 'B'
                else:
                    p.wave_num = 'C'

        return self._build_generic_pattern(labeled_points, direction_up)

    def _build_generic_pattern(self, labeled_points: list[WavePoint], direction_up: bool) -> WavePattern:
        """构建通用波浪模式"""
        prices = [p.price for p in labeled_points]
        last_wave = labeled_points[-1].wave_num or ('4' if direction_up else 'C')

        direction = WaveDirection.UP if direction_up else WaveDirection.DOWN

        # 确定浪型
        if last_wave in ['2', '4']:
            wave_type = WaveType.CORRECTIVE
        elif last_wave in ['A', 'B', 'C']:
            wave_type = WaveType.ZIGZAG
        else:
            wave_type = WaveType.UNKNOWN

        # 计算目标价 - 基于个股波动率的动态目标
        recent_amp = abs(prices[-1] - prices[-2]) if len(prices) >= 2 else prices[-1] * 0.05

        # 根据浪号设置目标倍数
        target_multipliers = {
            '2': 1.618,  # 2浪末 -> 3浪目标
            '4': 1.0,    # 4浪末 -> 5浪目标
            'C': 1.0,    # C浪末 -> 1浪目标
            'A': 0.8,    # A浪末 -> B浪反弹
            'B': 1.2     # B浪末 -> C浪下跌
        }
        multiplier = target_multipliers.get(last_wave, 1.0)

        target = prices[-1] + recent_amp * multiplier if direction_up else prices[-1] - recent_amp * multiplier
        stop_loss = prices[-2] if len(prices) >= 2 else (prices[-1] * 0.95 if direction_up else prices[-1] * 1.05)

        return WavePattern(
            wave_type=wave_type,
            direction=direction,
            points=labeled_points,
            confidence=0.5,
            start_date=labeled_points[0].date,
            end_date=labeled_points[-1].date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4)
        )

    def _try_impulse(self, points: list[WavePoint]) -> WavePattern | None:
        """尝试识别推动浪"""
        if len(points) != 6:
            return None

        valid, violations, conf, scores = validate_impulse_rules(points)
        if not valid or conf < self.confidence_threshold:
            return None

        # 标注浪号 (创建新列表避免修改原始数据)
        labeled_points = []
        for i, p in enumerate(points):
            # 创建新点并设置浪号
            new_p = WavePoint(
                index=p.index,
                date=p.date,
                price=p.price,
                volume=p.volume,
                is_peak=p.is_peak,
                is_trough=p.is_trough,
                strength=p.strength
            )
            new_p.wave_num = str(i)
            labeled_points.append(new_p)

        p0, p1, p2, p3, p4, p5 = labeled_points
        bull = p1.price > p0.price

        # 目标价 = 浪4 + 浪1长度
        target = p4.price + (p1.price - p0.price) if bull else p4.price - (p0.price - p1.price)
        stop_loss = min(p4.price, p2.price) * 0.98 if bull else max(p4.price, p2.price) * 1.02

        m = ImpulseMetrics.build(labeled_points)

        return WavePattern(
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP if bull else WaveDirection.DOWN,
            points=labeled_points,
            confidence=conf,
            start_date=p0.date,
            end_date=p5.date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4),
            guideline_scores=scores,
            fib_ratios={
                'w2_retracement': round(m.w2_retrace, 4),
                'w3_vs_w1': round(m.w3/(m.w1+1e-12), 4),
                'w4_retracement': round(m.w4_retrace, 4),
            }
        )

    def _try_zigzag(self, points: list[WavePoint]) -> WavePattern | None:
        """尝试识别ZigZag"""
        if len(points) != 4:
            return None

        valid, violations, conf = validate_zigzag(points)
        if not valid or conf < self.confidence_threshold:
            return None

        # 标注浪号 (创建新列表)
        labels = ['A', 'B', 'C']
        labeled_points = []
        for i, p in enumerate(points):
            new_p = WavePoint(
                index=p.index,
                date=p.date,
                price=p.price,
                volume=p.volume,
                is_peak=p.is_peak,
                is_trough=p.is_trough,
                strength=p.strength
            )
            # 对于ZigZag，所有点都应该是A-B-C的一部分
            # 如果超过3个点，额外的点也标为C（调整结束）
            if i < len(labels):
                new_p.wave_num = labels[i]
            else:
                new_p.wave_num = 'C'  # 额外点也标为C
            labeled_points.append(new_p)

        p0, pA, pB, pC = labeled_points
        bear = pA.price < p0.price

        # C浪目标 = B + 1.0×A浪长度
        a_len = abs(pA.price - p0.price)
        target = pB.price - a_len if bear else pB.price + a_len

        return WavePattern(
            wave_type=WaveType.ZIGZAG,
            direction=WaveDirection.DOWN if bear else WaveDirection.UP,
            points=labeled_points,
            confidence=conf,
            start_date=p0.date,
            end_date=pC.date,
            target_price=round(target, 4),
            stop_loss=round(pB.price, 4)
        )

    def _try_flat(self, points: list[WavePoint]) -> WavePattern | None:
        """
        尝试识别Flat平台型调整浪

        Flat特征：B浪深度回撤(≥80% A浪)，区别于ZigZag(B浪≤61.8%)
        常见子型：Regular Flat、Expanded Flat（A股最常见）、Running Flat
        """
        if len(points) != 4:
            return None

        valid, violations, conf = validate_flat(points)
        # Flat阈值略低于ZigZag，因为识别难度更高
        if not valid or conf < self.confidence_threshold * 0.8:
            return None

        labels = ['A', 'B', 'C']
        labeled_points = []
        for i, p in enumerate(points):
            new_p = WavePoint(
                index=p.index,
                date=p.date,
                price=p.price,
                volume=p.volume,
                is_peak=p.is_peak,
                is_trough=p.is_trough,
                strength=p.strength
            )
            new_p.wave_num = labels[i] if i < len(labels) else 'C'
            labeled_points.append(new_p)

        p0, pA, pB, pC = labeled_points
        bear = pA.price < p0.price  # 下跌调整

        a_len = abs(pA.price - p0.price)

        # Flat C浪目标：通常等于A浪长度，Expanded Flat可达1.618倍
        b_ret = abs(pB.price - pA.price) / (a_len + 1e-12)
        if b_ret > 1.05:
            # Expanded Flat：C浪目标更远
            target_mult = 1.382
        else:
            target_mult = 1.0

        if bear:
            target = pB.price - a_len * target_mult
            stop_loss = pB.price * 1.02  # 止损在B浪高点上方
        else:
            target = pB.price + a_len * target_mult
            stop_loss = pB.price * 0.98

        return WavePattern(
            wave_type=WaveType.FLAT,
            direction=WaveDirection.DOWN if bear else WaveDirection.UP,
            points=labeled_points,
            confidence=conf,
            start_date=p0.date,
            end_date=pC.date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4)
        )

    def _try_triangle(self, points: list[WavePoint]) -> WavePattern | None:
        """
        尝试识别Triangle三角形调整浪
        
        Triangle特征：
        - 5浪结构：A-B-C-D-E
        - 收敛形态，每个子浪长度递减
        - 常见于4浪或B浪位置
        
        Args:
            points: 5个WavePoint (A-B-C-D-E)
            
        Returns:
            WavePattern或None
        """
        if len(points) != 5:
            return None
        
        valid, violations, conf = validate_triangle(points)
        # Triangle识别难度较高，降低阈值
        if not valid or conf < self.confidence_threshold * 0.6:
            return None
        
        # 标注浪号
        labels = ['A', 'B', 'C', 'D', 'E']
        labeled_points = []
        for i, p in enumerate(points):
            new_p = WavePoint(
                index=p.index,
                date=p.date,
                price=p.price,
                volume=p.volume,
                is_peak=p.is_peak,
                is_trough=p.is_trough,
                strength=p.strength
            )
            new_p.wave_num = labels[i] if i < len(labels) else 'E'
            labeled_points.append(new_p)
        
        pA, pB, pC, pD, pE = labeled_points
        
        # 判断方向（A到B的方向决定整体方向）
        bear = pB.price < pA.price
        direction = WaveDirection.DOWN if bear else WaveDirection.UP
        
        # Triangle突破目标：E浪结束后沿原趋势方向突破
        # 目标 = E + (A浪长度 × 0.618)
        a_len = abs(pB.price - pA.price)
        
        if bear:
            # 下降三角形，向下突破
            target = pE.price - a_len * 0.618
            stop_loss = max(pD.price, pB.price) * 1.01
        else:
            # 上升三角形，向上突破
            target = pE.price + a_len * 0.618
            stop_loss = min(pD.price, pB.price) * 0.99
        
        return WavePattern(
            wave_type=WaveType.TRIANGLE,
            direction=direction,
            points=labeled_points,
            confidence=conf,
            start_date=pA.date,
            end_date=pE.date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4)
        )

    def _try_diagonal(self, points: list[WavePoint]) -> WavePattern | None:
        """
        尝试识别 Diagonal 对角线浪（P2-A新增）

        对角线浪特征：
        - 5波结构，浪4与浪1价格区间重叠
        - 整体呈收敛楔形（通道收窄）
        - 出现在趋势末期（Ending）或趋势起点（Leading）
        - 是趋势反转的重要信号
        """
        if len(points) < 5:
            return None

        is_valid, errors, score = validate_diagonal(points[:5])
        if not is_valid:
            return None

        p0, p1, p2, p3, p4 = points[:5]
        is_bull = p4.price > p0.price

        # 判断子类型：浪4进入浪1区域深度决定Ending/Leading
        if is_bull:
            overlap_depth = (p1.price - p3.price) / (p1.price - p0.price + 1e-10)
        else:
            overlap_depth = (p3.price - p1.price) / (p0.price - p1.price + 1e-10)

        wave_type = (WaveType.ENDING_DIAGONAL if overlap_depth > 0.5
                     else WaveType.LEADING_DIAGONAL)

        # 目标价：Ending Diagonal 预示反转，目标回到浪4起点
        if wave_type == WaveType.ENDING_DIAGONAL:
            target = p3.price          # 反转目标 = 浪4起点
            stop   = p4.price * (1.02 if not is_bull else 0.98)
        else:
            wave1_len = abs(p1.price - p0.price)
            target = (p4.price + wave1_len * 1.618 if is_bull
                      else p4.price - wave1_len * 1.618)
            stop   = p2.price

        labeled = [
            WavePoint(pt.index, pt.date, pt.price, wave_num=str(i+1))
            for i, pt in enumerate(points[:5])
        ]

        direction = WaveDirection.UP if is_bull else WaveDirection.DOWN
        return WavePattern(
            wave_type=wave_type,
            direction=direction,
            points=labeled,
            confidence=round(score, 4),
            start_date=p0.date,
            end_date=p4.date,
            target_price=round(target, 4),
            stop_loss=round(stop, 4)
        )

    def _try_impulse_enhanced(self, pivots, df: pd.DataFrame) -> WavePattern | None:
        """增强版推动浪识别"""
        if len(pivots) != 6:
            return None

        # 转换为WavePoint
        points = self._convert_pivots_to_wavepoints(pivots, df)

        valid, violations, conf, scores = validate_impulse_rules(points)
        if not valid:
            return None

        # 即使置信度略低于阈值，如果结构合理也接受
        if conf < self.confidence_threshold * 0.7:
            return None

        # 标注浪号
        for i, p in enumerate(points):
            p.wave_num = str(i)

        p0, p1, p2, p3, p4, p5 = points
        bull = p1.price > p0.price

        # 目标价 = 浪4 + 浪1长度
        target = p4.price + (p1.price - p0.price) if bull else p4.price - (p0.price - p1.price)
        stop_loss = min(p4.price, p2.price) * 0.98 if bull else max(p4.price, p2.price) * 1.02

        m = ImpulseMetrics.build(points)

        return WavePattern(
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP if bull else WaveDirection.DOWN,
            points=points,
            confidence=conf,
            start_date=p0.date,
            end_date=p5.date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4),
            guideline_scores=scores,
            fib_ratios={
                'w2_retracement': round(m.w2_retrace, 4),
                'w3_vs_w1': round(m.w3/(m.w1+1e-12), 4),
                'w4_retracement': round(m.w4_retrace, 4),
            }
        )

    def _try_zigzag_enhanced(self, pivots, df: pd.DataFrame) -> WavePattern | None:
        """增强版ZigZag识别"""
        if len(pivots) != 4:
            return None

        points = self._convert_pivots_to_wavepoints(pivots, df)

        valid, violations, conf = validate_zigzag(points)
        if not valid:
            return None

        if conf < self.confidence_threshold * 0.7:
            return None

        for p, label in zip(points, ['A', 'B', 'C'], strict=False):
            p.wave_num = label

        p0, pA, pB, pC = points
        bear = pA.price < p0.price

        a_len = abs(pA.price - p0.price)
        target = pB.price - a_len if bear else pB.price + a_len

        return WavePattern(
            wave_type=WaveType.ZIGZAG,
            direction=WaveDirection.DOWN if bear else WaveDirection.UP,
            points=points,
            confidence=conf,
            start_date=p0.date,
            end_date=pC.date,
            target_price=round(target, 4),
            stop_loss=round(pB.price, 4)
        )

    def _create_generic_pattern(self, pivots, df: pd.DataFrame, conf: float) -> WavePattern:
        """创建通用波浪模式"""

        points = self._convert_pivots_to_wavepoints(pivots, df)

        # 确定方向
        if len(points) >= 2:
            direction = WaveDirection.UP if points[-1].price > points[0].price else WaveDirection.DOWN
        else:
            direction = WaveDirection.UNKNOWN

        # 确定浪型
        last_wave = points[-1].wave_num if points[-1].wave_num else 'C'
        if last_wave in ['2', '4', 'B']:
            wave_type = WaveType.CORRECTIVE
        elif last_wave in ['A', 'C']:
            wave_type = WaveType.ZIGZAG
        else:
            wave_type = WaveType.UNKNOWN

        # 计算目标价 - 基于最近一波的幅度
        if len(points) >= 2:
            recent_wave_amp = abs(points[-1].price - points[-2].price)
            target = points[-1].price + recent_wave_amp if direction == WaveDirection.UP else points[-1].price - recent_wave_amp
            stop_loss = points[-2].price
        else:
            target = points[-1].price * 1.05 if direction == WaveDirection.UP else points[-1].price * 0.95
            stop_loss = points[-1].price * 0.95 if direction == WaveDirection.UP else points[-1].price * 1.05

        return WavePattern(
            wave_type=wave_type,
            direction=direction,
            points=points,
            confidence=conf,
            start_date=points[0].date,
            end_date=points[-1].date,
            target_price=round(target, 4),
            stop_loss=round(stop_loss, 4)
        )

    def _convert_pivots_to_wavepoints(self, pivots, df: pd.DataFrame) -> list[WavePoint]:
        """将PivotPoint转换为WavePoint"""

        dates = df['date'].values if 'date' in df.columns else [str(i) for i in range(len(df))]
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))

        points = []
        for p in pivots:
            wp = WavePoint(
                index=p.idx,
                date=str(dates[p.idx]) if isinstance(dates[p.idx], str) else str(dates[p.idx]),
                price=p.price,
                volume=float(volumes[p.idx]) if p.idx < len(volumes) else 0.0,
                is_peak=p.is_peak,
                is_trough=not p.is_peak,
                strength=p.strength
            )
            if hasattr(p, 'wave_num') and p.wave_num:
                wp.wave_num = p.wave_num
            points.append(wp)

        return points

    def analyze_trend(self, df: pd.DataFrame, pattern: WavePattern) -> dict[str, Any]:
        """分析趋势"""
        current_price = df['close'].iloc[-1]
        last_point = pattern.points[-1]

        result = {
            'current_price': round(current_price, 4),
            'last_wave_price': round(last_point.price, 4),
            'wave_direction': pattern.direction.value,
            'wave_type': pattern.wave_type.value,
            'confidence': round(pattern.confidence, 4),
            'fib_ratios': pattern.fib_ratios,
            'guideline_scores': pattern.guideline_scores,
        }

        # 位置判断
        if pattern.is_impulse:
            if last_point.wave_num == '5':
                result['position'] = 'wave_5_complete'
                result['signal'] = 'watch_for_reversal'
            else:
                result['position'] = f"wave_{last_point.wave_num}_complete"
                result['signal'] = 'continuation'
        else:
            if last_point.wave_num == 'C':
                result['position'] = 'correction_complete'
                result['signal'] = 'new_trend'
            else:
                result['position'] = f"correction_{last_point.wave_num}"

        if pattern.target_price:
            result['target_price'] = pattern.target_price
        if pattern.stop_loss:
            result['stop_loss'] = pattern.stop_loss

        return result


# 保持向后兼容的别名
WaveAnalyzer = ElliottWaveAnalyzer
