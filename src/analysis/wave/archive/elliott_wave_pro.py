"""
波浪分析模块 - 专业版Elliott Wave分析引擎
基于ATR自适应ZigZag、完整规则验证、子波浪嵌套
"""
from typing import List, Dict, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger


# ============================================================================
# SECTION 1 — Domain Models
# ============================================================================

class WaveType(Enum):
    """波浪类型 - 扩展版"""
    # 推动浪
    IMPULSE = "impulse"
    EXTENDED_IMPULSE = "extended_impulse"
    LEADING_DIAGONAL = "leading_diagonal"
    ENDING_DIAGONAL = "ending_diagonal"
    FAILED_FIFTH = "failed_fifth"
    
    # 调整浪 - 简单
    ZIGZAG = "zigzag"
    FLAT_REGULAR = "flat_regular"
    FLAT_EXPANDED = "flat_expanded"
    FLAT_RUNNING = "flat_running"
    
    # 调整浪 - 三角形
    TRIANGLE_CONTRACTING = "triangle_contracting"
    TRIANGLE_EXPANDING = "triangle_expanding"
    TRIANGLE_ASCENDING = "triangle_ascending"
    TRIANGLE_DESCENDING = "triangle_descending"
    
    # 调整浪 - 复杂
    DOUBLE_ZIGZAG = "double_zigzag"
    TRIPLE_ZIGZAG = "triple_zigzag"
    
    UNKNOWN = "unknown"


class WaveDirection(Enum):
    """波浪方向"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class FibLevel(Enum):
    """斐波那契水平"""
    R_236 = 0.236
    R_382 = 0.382
    R_500 = 0.500
    R_618 = 0.618
    R_786 = 0.786
    E_100 = 1.000
    E_1272 = 1.272
    E_1618 = 1.618
    E_2000 = 2.000
    E_2618 = 2.618


@dataclass
class WavePoint:
    """波浪点位 - 增强版"""
    index: int
    date: str
    price: float
    volume: float = 0.0
    wave_num: Optional[str] = None
    is_peak: bool = False
    is_trough: bool = False
    strength: int = 1  # 1=minor, 2=intermediate, 3=major
    
    # 扩展属性
    sub_waves: List['WavePoint'] = field(default_factory=list)
    fib_targets: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WaveValidation:
    """波浪验证结果"""
    rule_name: str
    passed: bool
    score: float
    details: str


@dataclass
class WavePattern:
    """波浪形态 - 专业版"""
    wave_type: WaveType
    direction: WaveDirection
    points: List[WavePoint]
    confidence: float
    start_date: str
    end_date: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # 扩展属性
    validations: List[WaveValidation] = field(default_factory=list)
    sub_waves: List['WavePattern'] = field(default_factory=list)
    fib_ratios: Dict[str, float] = field(default_factory=dict)
    guideline_scores: Dict[str, float] = field(default_factory=dict)
    rule_violations: List[str] = field(default_factory=list)
    
    # 波浪长度
    wave_lengths: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'wave_type': self.wave_type.value,
            'direction': self.direction.value,
            'confidence': self.confidence,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'fib_ratios': self.fib_ratios,
            'wave_lengths': self.wave_lengths,
            'validations': [{'rule': v.rule_name, 'passed': v.passed, 'score': v.score} for v in self.validations],
            'rule_violations': self.rule_violations,
            'points': [
                {
                    'index': p.index,
                    'date': p.date,
                    'price': p.price,
                    'volume': p.volume,
                    'wave_num': p.wave_num,
                    'is_peak': p.is_peak,
                    'is_trough': p.is_trough,
                    'strength': p.strength
                }
                for p in self.points
            ]
        }
    
    @property
    def is_impulse(self) -> bool:
        return self.wave_type in {
            WaveType.IMPULSE, WaveType.EXTENDED_IMPULSE,
            WaveType.LEADING_DIAGONAL, WaveType.ENDING_DIAGONAL,
            WaveType.FAILED_FIFTH
        }
    
    @property
    def is_corrective(self) -> bool:
        return not self.is_impulse and self.wave_type != WaveType.UNKNOWN


# ============================================================================
# SECTION 2 — ATR Adaptive Pivot Detection
# ============================================================================

def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """计算Wilder ATR"""
    n = len(close)
    if n < 2:
        return np.full(n, high[0] - low[0] + 1e-8)
    
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )
    
    atr = np.empty(n)
    seed_end = min(period, n)
    atr[seed_end - 1] = float(np.mean(tr[:seed_end]))
    
    alpha = 1.0 / period
    for i in range(seed_end, n):
        atr[i] = atr[i - 1] * (1.0 - alpha) + tr[i] * alpha
    atr[:seed_end - 1] = atr[seed_end - 1]
    return atr


def zigzag_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    atr_mult: float = 0.5,
    min_dist: int = 3
) -> Tuple[List[int], List[float], List[str]]:
    """
    ATR自适应ZigZag算法
    
    优势:
    - 根据市场波动率动态调整阈值
    - 比固定百分比更能适应不同波动性的股票
    """
    n = len(close)
    idxs: List[int] = []
    prices: List[float] = []
    types: List[str] = []
    
    if n < 5:
        return idxs, prices, types
    
    direction = 1  # +1找高点, -1找低点
    extreme_idx = 0
    extreme_price = high[0]
    
    # 起点
    idxs.append(0)
    prices.append(low[0])
    types.append("L")
    
    for i in range(1, n):
        threshold = atr_mult * atr[i]
        
        if direction == 1:  # 找高点
            if high[i] >= extreme_price:
                extreme_idx, extreme_price = i, high[i]
            elif (extreme_price - low[i]) >= threshold:
                gap = extreme_idx - idxs[-1]
                if gap >= min_dist:
                    idxs.append(extreme_idx)
                    prices.append(extreme_price)
                    types.append("H")
                direction = -1
                extreme_idx, extreme_price = i, low[i]
        else:  # 找低点
            if low[i] <= extreme_price:
                extreme_idx, extreme_price = i, low[i]
            elif (high[i] - extreme_price) >= threshold:
                gap = extreme_idx - idxs[-1]
                if gap >= min_dist:
                    idxs.append(extreme_idx)
                    prices.append(extreme_price)
                    types.append("L")
                direction = 1
                extreme_idx, extreme_price = i, high[i]
    
    # 添加最后一个极值点
    if extreme_idx != idxs[-1]:
        final_type = "H" if direction == 1 else "L"
        idxs.append(extreme_idx)
        prices.append(extreme_price)
        types.append(final_type)
    
    return idxs, prices, types


# ============================================================================
# SECTION 3 — Wave Metrics & Rules
# ============================================================================

@dataclass
class ImpulseMetrics:
    """推动浪指标"""
    prices: Tuple[float, ...]
    is_bullish: bool
    w1: float
    w2: float
    w3: float
    w4: float
    w5: float
    w2_retrace: float
    w4_retrace: float
    
    @classmethod
    def build(cls, points: List[WavePoint]) -> 'ImpulseMetrics':
        if len(points) != 6:
            raise ValueError(f"需要6个点位, 得到 {len(points)}")
        
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
            w2_retrace=w2/(w1+1e-12),
            w4_retrace=w4/(w3+1e-12),
        )


def validate_impulse_rules(points: List[WavePoint]) -> Tuple[bool, List[str], float, Dict[str, float]]:
    """
    验证推动浪硬规则和指导原则
    
    硬规则:
    1. 波浪方向一致
    2. 浪2不回撤超过浪1起点
    3. 浪3不是最短的
    4. 浪4不与浪1重叠
    
    指导原则评分:
    - 浪2深度0.382-0.618
    - 浪3长度1.618倍浪1
    - 浪3是最长的
    - 浪4回撤0.236-0.5
    - 浪5等于浪1
    """
    if len(points) != 6:
        return False, ["点位数量错误"], 0.0, {}
    
    try:
        m = ImpulseMetrics.build(points)
    except ValueError as e:
        return False, [str(e)], 0.0, {}
    
    violations = []
    
    # 硬规则检查
    if not (m.w1 > 0 and m.w2 > 0 and m.w3 > 0 and m.w4 > 0 and m.w5 > 0):
        violations.append("波浪方向不一致")
    
    if m.w2_retrace >= 1.0:
        violations.append("浪2完全回撤浪1")
    
    if m.w3 < m.w1 and m.w3 < m.w5:
        violations.append("浪3是最短的")
    
    p0, p1, _, _, p4, _ = m.prices
    if m.is_bullish and p4 <= p1:
        violations.append("浪4与浪1重叠")
    elif not m.is_bullish and p4 >= p1:
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
        ("浪5创新高/低", 0.10, (m.prices[5] > m.prices[3]) if m.is_bullish else (m.prices[5] < m.prices[3])),
        ("浪2浪4交替", 0.15, (m.w2_retrace >= 0.50) != (m.w4_retrace >= 0.50)),
    ]
    
    total = sum(w for _, w, _ in checks)
    earned = sum(w for _, w, ok in checks if ok)
    scores = {n: w if ok else 0.0 for n, w, ok in checks}
    
    confidence = earned / (total + 1e-12)
    return True, [], confidence, scores


def validate_zigzag(points: List[WavePoint]) -> Tuple[bool, List[str], float]:
    """验证ZigZag调整浪"""
    if len(points) != 4:
        return False, ["点位数量错误"], 0.0
    
    p0, pA, pB, pC = (p.price for p in points)
    a_len = abs(pA - p0)
    b_len = abs(pB - pA)
    b_ret = b_len / (a_len + 1e-12)
    bearish = pA < p0
    
    violations = []
    if b_ret >= 1.0:
        violations.append("B浪超过A浪起点")
    if b_ret > 0.90:
        violations.append("B浪过深")
    
    if violations:
        return False, violations, 0.0
    
    c_a = abs(pC - pB) / (a_len + 1e-12)
    c_extends = (pC < pA) if bearish else (pC > pA)
    
    score = sum([
        0.25 if 0.382 <= b_ret <= 0.618 else 0.0,
        0.20 if 0.85 <= c_a <= 1.15 else 0.0,
        0.15 if 1.50 <= c_a <= 1.80 else 0.0,
        0.25 if c_extends else 0.0,
        0.15 if 0.50 <= b_ret <= 0.786 else 0.0,
    ])
    
    return True, [], score


def validate_flat(points: List[WavePoint]) -> Tuple[bool, List[str], float, str]:
    """验证Flat调整浪"""
    if len(points) != 4:
        return False, ["点位数量错误"], 0.0, "unknown"
    
    p0, pA, pB, pC = (p.price for p in points)
    a_len = abs(pA - p0)
    b_len = abs(pB - pA)
    c_len = abs(pC - pB)
    b_ret = b_len / (a_len + 1e-12)
    bearish = pA < p0
    c_beyond = (pC < pA) if bearish else (pC > pA)
    
    if b_ret < 0.80 or a_len < 1e-8 or c_len < 1e-8:
        return False, ["B浪不足"], 0.0, "unknown"
    
    if b_ret > 1.05:
        subtype = "expanded" if c_beyond else "running"
    else:
        subtype = "regular"
    
    c_a = c_len / (a_len + 1e-12)
    score = sum([
        0.30 if subtype == "regular" and 0.90 <= b_ret <= 1.05 else 0.0,
        0.30 if subtype == "expanded" else 0.0,
        0.20 if 0.90 <= c_a <= 1.10 else 0.0,
        0.20 if 1.50 <= c_a <= 1.80 else 0.0,
    ])
    
    return True, [], score, subtype


# ============================================================================
# SECTION 4 — Fibonacci Target Calculator
# ============================================================================

class FibTargetCalculator:
    """斐波那契目标价计算器"""
    
    @staticmethod
    def wave3_target(p0: WavePoint, p1: WavePoint, p2: WavePoint) -> List[Dict[str, Any]]:
        """浪3延伸目标"""
        w1_len = abs(p1.price - p0.price)
        direction = 1.0 if p1.price > p0.price else -1.0
        
        targets = []
        for level, prob in [(1.618, 0.45), (2.618, 0.30), (4.236, 0.15), (1.272, 0.10)]:
            price = p2.price + direction * level * w1_len
            targets.append({
                'price': round(price, 4),
                'level': level,
                'probability': prob,
                'type': 'extension'
            })
        return targets
    
    @staticmethod
    def wave4_target(p2: WavePoint, p3: WavePoint) -> List[Dict[str, Any]]:
        """浪4回撤目标"""
        w3_len = abs(p3.price - p2.price)
        direction = -1.0 if p3.price > p2.price else 1.0
        
        targets = []
        for level, prob in [(0.382, 0.45), (0.236, 0.30), (0.500, 0.20), (0.618, 0.05)]:
            price = p3.price + direction * level * w3_len
            targets.append({
                'price': round(price, 4),
                'level': level,
                'probability': prob,
                'type': 'retracement'
            })
        return targets
    
    @staticmethod
    def wave5_target(p0: WavePoint, p1: WavePoint, p4: WavePoint) -> List[Dict[str, Any]]:
        """浪5延伸目标"""
        w1_len = abs(p1.price - p0.price)
        direction = 1.0 if p1.price > p0.price else -1.0
        
        targets = []
        for level, prob in [(1.0, 0.40), (0.618, 0.30), (1.618, 0.20), (0.382, 0.10)]:
            price = p4.price + direction * level * w1_len
            targets.append({
                'price': round(price, 4),
                'level': level,
                'probability': prob,
                'type': 'extension'
            })
        return targets
    
    @staticmethod
    def wave_c_target(p0: WavePoint, pA: WavePoint, pB: WavePoint) -> List[Dict[str, Any]]:
        """C浪延伸目标"""
        a_len = abs(pA.price - p0.price)
        direction = -1.0 if pA.price < p0.price else 1.0
        
        targets = []
        for level, prob in [(1.0, 0.40), (1.618, 0.30), (0.618, 0.20), (2.618, 0.10)]:
            price = pB.price + direction * level * a_len
            targets.append({
                'price': round(price, 4),
                'level': level,
                'probability': prob,
                'type': 'extension'
            })
        return targets


# ============================================================================
# SECTION 5 — Professional Wave Analyzer
# ============================================================================

class ProfessionalWaveAnalyzer:
    """
    专业版Elliott Wave分析器
    
    特性:
    - ATR自适应ZigZag极值点检测
    - 严格的推动浪规则验证
    - 多种调整浪类型识别 (ZigZag, Flat, Triangle)
    - 斐波那契目标价计算
    - 子波浪嵌套结构
    """
    
    def __init__(
        self,
        atr_period: int = 14,
        atr_mult: float = 0.5,
        min_dist: int = 3,
        min_confidence: float = 0.5,
        use_volume: bool = True
    ):
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.min_dist = min_dist
        self.min_confidence = min_confidence
        self.use_volume = use_volume
        self.logger = get_logger('analysis.wave.professional')
        self.fib_calc = FibTargetCalculator()
    
    def detect_pivots(self, df: pd.DataFrame) -> List[WavePoint]:
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
        
        # 计算振幅用于强度分级
        amplitudes = [abs(prices[i+1] - prices[i]) for i in range(len(prices)-1)]
        median_amp = float(np.median(amplitudes)) if amplitudes else 1.0
        
        points = []
        for i, (idx, price, ptype) in enumerate(zip(idxs, prices, types)):
            amp = amplitudes[max(0, i-1)] if i > 0 else amplitudes[0] if amplitudes else 0
            ratio = amp / (median_amp + 1e-12)
            
            if ratio >= 2.0:
                strength = 3
            elif ratio >= 1.0:
                strength = 2
            else:
                strength = 1
            
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
    
    def detect_wave_pattern(self, df: pd.DataFrame) -> Optional[WavePattern]:
        """检测波浪形态"""
        points = self.detect_pivots(df)
        if len(points) < 4:
            return None
        
        # 尝试不同窗口大小
        best_pattern = None
        best_confidence = 0.0
        
        for window_size in [6, 4]:
            for i in range(len(points) - window_size + 1):
                window = points[i:i+window_size]
                pattern = self._classify_pattern(window)
                
                if pattern and pattern.confidence > best_confidence:
                    best_confidence = pattern.confidence
                    best_pattern = pattern
        
        return best_pattern
    
    def _classify_pattern(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """分类波浪形态"""
        n = len(points)
        
        if n == 6:
            # 尝试推动浪
            pattern = self._build_impulse(points)
            if pattern:
                return pattern
            
            # 尝试延长浪
            pattern = self._build_extended_impulse(points)
            if pattern:
                return pattern
            
            # 尝试对角线
            pattern = self._build_diagonal(points)
            if pattern:
                return pattern
            
            # 尝试失败5浪
            pattern = self._build_failed_fifth(points)
            if pattern:
                return pattern
        
        elif n == 4:
            # 尝试ZigZag
            pattern = self._build_zigzag(points)
            if pattern:
                return pattern
            
            # 尝试Flat
            pattern = self._build_flat(points)
            if pattern:
                return pattern
        
        return None
    
    def _build_impulse(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建推动浪"""
        valid, violations, conf, scores = validate_impulse_rules(points)
        if not valid or conf < self.min_confidence:
            return None
        
        p0, p1, p2, p3, p4, p5 = points
        bull = p1.price > p0.price
        
        # 标记子浪
        for i, p in enumerate(points):
            p.wave_num = str(i)
        
        # 计算目标价
        targets = self.fib_calc.wave5_target(p0, p1, p4)
        primary_target = targets[0]['price'] if targets else None
        
        # 止损
        stop_loss = min(p4.price, p2.price) * 0.98 if bull else max(p4.price, p2.price) * 1.02
        
        pattern = WavePattern(
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP if bull else WaveDirection.DOWN,
            points=points,
            confidence=conf,
            start_date=p0.date,
            end_date=p5.date,
            target_price=primary_target,
            stop_loss=round(stop_loss, 4),
            guideline_scores=scores,
            rule_violations=violations
        )
        
        # 计算斐波那契比例
        m = ImpulseMetrics.build(points)
        pattern.fib_ratios = {
            'w2_retracement': round(m.w2_retrace, 4),
            'w3_vs_w1': round(m.w3 / (m.w1 + 1e-12), 4),
            'w4_retracement': round(m.w4_retrace, 4),
            'w5_vs_w1': round(m.w5 / (m.w1 + 1e-12), 4),
        }
        pattern.wave_lengths = {
            'w1': round(m.w1, 4),
            'w2': round(m.w2, 4),
            'w3': round(m.w3, 4),
            'w4': round(m.w4, 4),
            'w5': round(m.w5, 4),
        }
        
        return pattern
    
    def _build_extended_impulse(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建延长浪"""
        pattern = self._build_impulse(points)
        if not pattern:
            return None
        
        # 检查浪3是否延长
        m = ImpulseMetrics.build(points)
        if not (m.w3 >= 1.618 * m.w1 and m.w3 >= m.w5):
            return None
        
        pattern.wave_type = WaveType.EXTENDED_IMPULSE
        pattern.confidence = min(1.0, pattern.confidence + 0.05)
        
        return pattern
    
    def _build_diagonal(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建对角线三角形"""
        if len(points) != 6:
            return None
        
        p0, p1, p2, p3, p4, p5 = points
        bull = p1.price > p0.price
        
        # 检查收敛
        w1 = abs(p1.price - p0.price)
        w3 = abs(p3.price - p2.price)
        w5 = abs(p5.price - p4.price)
        
        converging = w3 < w1 and w5 < w3
        overlap = (p4.price < p1.price) if bull else (p4.price > p1.price)
        
        if not (converging and overlap):
            return None
        
        # 简化评分
        score = 0.5 if converging else 0.0
        score += 0.3 if overlap else 0.0
        
        if score < self.min_confidence:
            return None
        
        for i, p in enumerate(points):
            p.wave_num = str(i)
        
        targets = self.fib_calc.wave5_target(p0, p1, p4)
        primary_target = targets[0]['price'] if targets else None
        
        return WavePattern(
            wave_type=WaveType.ENDING_DIAGONAL,
            direction=WaveDirection.UP if bull else WaveDirection.DOWN,
            points=points,
            confidence=score,
            start_date=p0.date,
            end_date=p5.date,
            target_price=primary_target,
            stop_loss=round(min(p4.price, p2.price) * 0.98 if bull else max(p4.price, p2.price) * 1.02, 4)
        )
    
    def _build_failed_fifth(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建失败5浪"""
        pattern = self._build_impulse(points)
        if not pattern:
            return None
        
        p0, p1, p2, p3, p4, p5 = (p.price for p in points)
        bull = p1 > p0
        
        # 检查浪5是否失败
        if (bull and p5 >= p3) or (not bull and p5 <= p3):
            return None
        
        pattern.wave_type = WaveType.FAILED_FIFTH
        pattern.confidence *= 0.8  # 失败浪降低置信度
        
        return pattern
    
    def _build_zigzag(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建ZigZag调整浪"""
        valid, violations, conf = validate_zigzag(points)
        if not valid or conf < self.min_confidence:
            return None
        
        p0, pA, pB, pC = points
        bear = pA.price < p0.price
        
        for p, label in zip(points, ['A', 'B', 'C']):
            p.wave_num = label
        
        targets = self.fib_calc.wave_c_target(p0, pA, pB)
        primary_target = targets[0]['price'] if targets else None
        
        return WavePattern(
            wave_type=WaveType.ZIGZAG,
            direction=WaveDirection.DOWN if bear else WaveDirection.UP,
            points=points,
            confidence=conf,
            start_date=p0.date,
            end_date=pC.date,
            target_price=primary_target,
            stop_loss=round(pB.price, 4),
            rule_violations=violations
        )
    
    def _build_flat(self, points: List[WavePoint]) -> Optional[WavePattern]:
        """构建Flat调整浪"""
        valid, violations, conf, subtype = validate_flat(points)
        if not valid or conf < self.min_confidence:
            return None
        
        p0, pA, pB, pC = points
        bear = pA.price < p0.price
        
        for p, label in zip(points, ['A', 'B', 'C']):
            p.wave_num = label
        
        wave_type_map = {
            'regular': WaveType.FLAT_REGULAR,
            'expanded': WaveType.FLAT_EXPANDED,
            'running': WaveType.FLAT_RUNNING
        }
        
        targets = self.fib_calc.wave_c_target(p0, pA, pB)
        primary_target = targets[0]['price'] if targets else None
        
        return WavePattern(
            wave_type=wave_type_map.get(subtype, WaveType.FLAT_REGULAR),
            direction=WaveDirection.DOWN if bear else WaveDirection.UP,
            points=points,
            confidence=conf,
            start_date=p0.date,
            end_date=pC.date,
            target_price=primary_target,
            stop_loss=round(pB.price, 4),
            rule_violations=violations
        )
    
    def analyze_trend(self, df: pd.DataFrame, pattern: WavePattern) -> Dict[str, Any]:
        """分析趋势"""
        current_price = df['close'].iloc[-1]
        last_point = pattern.points[-1]
        
        trend_info = {
            'current_price': round(current_price, 4),
            'last_wave_price': round(last_point.price, 4),
            'wave_direction': pattern.direction.value,
            'wave_type': pattern.wave_type.value,
            'confidence': round(pattern.confidence, 4),
            'fib_ratios': pattern.fib_ratios,
            'wave_lengths': pattern.wave_lengths,
        }
        
        # 波浪位置判断
        if pattern.is_impulse:
            if last_point.wave_num == '5':
                trend_info['position'] = 'wave_5_complete'
                trend_info['signal'] = 'watch_for_reversal'
            elif last_point.wave_num in ['2', '4']:
                trend_info['position'] = f"wave_{last_point.wave_num}_complete"
                trend_info['signal'] = 'continuation'
            else:
                trend_info['position'] = f"in_wave_{last_point.wave_num}"
        else:
            if last_point.wave_num == 'C':
                trend_info['position'] = 'wave_C_complete'
                trend_info['signal'] = 'correction_complete'
            else:
                trend_info['position'] = f"in_correction_{last_point.wave_num}"
        
        if pattern.target_price:
            trend_info['target_price'] = pattern.target_price
        if pattern.stop_loss:
            trend_info['stop_loss'] = pattern.stop_loss
        
        return trend_info


# 保持向后兼容
ElliottWaveAnalyzer = ProfessionalWaveAnalyzer
