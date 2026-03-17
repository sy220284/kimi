"""
波浪检测优化模块 - 增强版高低点识别和浪型验证
"""
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class PivotPoint:
    """极值点"""
    idx: int
    date: str
    price: float
    is_peak: bool  # True=峰值, False=谷值
    strength: int  # 强度1-5
    volume: float = 0
    wave_num: Optional[str] = None  # 浪号标注


def enhanced_pivot_detection(
    df: pd.DataFrame,
    atr_period: int = 14,
    atr_mult: float = 0.5,
    min_pivots: int = 4,
    trend_confirmation: bool = True
) -> List[PivotPoint]:
    """
    增强版极值点检测
    
    改进点:
    1. 双阶段过滤 - 先粗筛再精筛
    2. 趋势确认 - 确保极值点确实是局部高低点
    3. 强度分级 - 根据波动幅度和成交量评分
    4. 噪声过滤 - 剔除小幅震荡产生的假信号
    """
    if len(df) < atr_period * 2:
        return []
    
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
    dates = df['date'].values if 'date' in df.columns else [str(i) for i in range(len(df))]
    
    # 计算ATR
    atr = _calculate_atr(highs, lows, closes, atr_period)
    min_move = atr * atr_mult
    
    # 第一阶段: 检测所有候选极值点
    candidates = _find_candidate_pivots(highs, lows, closes, min_move)
    
    # 第二阶段: 趋势确认和精筛
    if trend_confirmation:
        candidates = _confirm_pivots(candidates, highs, lows, closes, min_move)
    
    # 第三阶段: 计算强度
    pivots = _calculate_pivot_strength(candidates, highs, lows, volumes, atr)
    
    return pivots


def _calculate_atr(highs, lows, closes, period=14):
    """计算ATR"""
    tr1 = highs[1:] - lows[1:]
    tr2 = np.abs(highs[1:] - closes[:-1])
    tr3 = np.abs(lows[1:] - closes[:-1])
    tr = np.maximum(np.maximum(tr1, tr2), tr3)
    atr = np.zeros_like(closes)
    atr[period] = np.mean(tr[:period])
    for i in range(period + 1, len(closes)):
        atr[i] = (atr[i-1] * (period-1) + tr[i-1]) / period
    return atr


def _find_candidate_pivots(highs, lows, closes, min_move):
    """第一阶段: 找出所有候选极值点"""
    candidates = []
    n = len(closes)
    
    i = 0
    while i < n - 1:
        # 找下一个显著的高点或低点
        start_price = closes[i]
        
        # 向上找高点
        j = i + 1
        max_idx = i
        max_price = highs[i]
        while j < n and (closes[j] - start_price) > -min_move[j]:
            if highs[j] > max_price:
                max_price = highs[j]
                max_idx = j
            j += 1
        
        if max_idx > i and (max_price - start_price) >= min_move[max_idx]:
            candidates.append((max_idx, max_price, True))  # (idx, price, is_peak)
            i = max_idx
            continue
        
        # 向下找低点
        j = i + 1
        min_idx = i
        min_price = lows[i]
        while j < n and (start_price - closes[j]) > -min_move[j]:
            if lows[j] < min_price:
                min_price = lows[j]
                min_idx = j
            j += 1
        
        if min_idx > i and (start_price - min_price) >= min_move[min_idx]:
            candidates.append((min_idx, min_price, False))  # (idx, price, is_peak=False)
            i = min_idx
            continue
        
        i += 1
    
    return candidates


def _confirm_pivots(candidates, highs, lows, closes, min_move):
    """第二阶段: 趋势确认 - 确保极值点是真正的局部高低点"""
    if len(candidates) < 2:
        return candidates
    
    confirmed = []
    n = len(candidates)
    
    for i, (idx, price, is_peak) in enumerate(candidates):
        # 检查前后趋势
        lookback = min(3, idx)
        lookahead = min(3, len(closes) - idx - 1)
        
        if is_peak:
            # 峰值前应该上升，峰值后应该下降
            before_trend = closes[idx] > closes[max(0, idx-lookback)]
            after_trend = closes[min(len(closes)-1, idx+lookahead)] < closes[idx]
            if before_trend and after_trend:
                confirmed.append((idx, price, is_peak))
            elif i > 0 and i < n - 1:  # 中间点检查相对高低
                prev_price = candidates[i-1][1]
                next_price = candidates[i+1][1]
                if price > prev_price and price > next_price:
                    confirmed.append((idx, price, is_peak))
        else:
            # 谷值前应该下降，谷值后应该上升
            before_trend = closes[idx] < closes[max(0, idx-lookback)]
            after_trend = closes[min(len(closes)-1, idx+lookahead)] > closes[idx]
            if before_trend and after_trend:
                confirmed.append((idx, price, is_peak))
            elif i > 0 and i < n - 1:
                prev_price = candidates[i-1][1]
                next_price = candidates[i+1][1]
                if price < prev_price and price < next_price:
                    confirmed.append((idx, price, is_peak))
    
    return confirmed


def _calculate_pivot_strength(candidates, highs, lows, volumes, atr):
    """第三阶段: 计算极值点强度"""
    if not candidates:
        return []
    
    pivots = []
    amplitudes = []
    
    # 计算相邻极值点的幅度
    for i in range(len(candidates) - 1):
        amp = abs(candidates[i+1][1] - candidates[i][1])
        amplitudes.append(amp)
    
    median_amp = np.median(amplitudes) if amplitudes else 1.0
    
    for i, (idx, price, is_peak) in enumerate(candidates):
        # 基于波动幅度评分
        if i < len(amplitudes):
            amp_ratio = amplitudes[i] / (median_amp + 1e-12)
        else:
            amp_ratio = 1.0
        
        # 基于成交量评分（如果有）
        vol_ratio = 1.0
        if idx < len(volumes) and volumes[idx] > 0:
            # 峰值放量、谷值缩量是正常形态
            avg_vol = np.mean(volumes[max(0, idx-5):min(len(volumes), idx+1)])
            vol_ratio = volumes[idx] / (avg_vol + 1e-12)
        
        # 综合强度 1-5
        if amp_ratio >= 2.0 and vol_ratio >= 1.5:
            strength = 5
        elif amp_ratio >= 1.5 or vol_ratio >= 1.3:
            strength = 4
        elif amp_ratio >= 1.0 or vol_ratio >= 1.0:
            strength = 3
        elif amp_ratio >= 0.7:
            strength = 2
        else:
            strength = 1
        
        pivots.append(PivotPoint(
            idx=idx,
            date=str(idx),  # 简化处理
            price=price,
            is_peak=is_peak,
            strength=strength,
            volume=volumes[idx] if idx < len(volumes) else 0
        ))
    
    return pivots


def label_wave_numbers(pivots: List[PivotPoint], pattern_type: str = "auto") -> List[PivotPoint]:
    """
    智能浪号标注
    
    即使不完全符合标准浪型，也根据位置关系尝试标注浪号
    
    Args:
        pivots: 极值点列表
        pattern_type: 预设浪型类型 ("impulse", "zigzag", "auto")
    
    Returns:
        标注了浪号的极值点列表
    """
    if len(pivots) < 4:
        return pivots
    
    # 自动判断浪型
    if pattern_type == "auto":
        pattern_type = _infer_pattern_type(pivots)
    
    if pattern_type == "impulse":
        return _label_impulse(pivots)
    elif pattern_type == "zigzag":
        return _label_zigzag(pivots)
    else:
        return _label_generic(pivots)


def _infer_pattern_type(pivots: List[PivotPoint]) -> str:
    """根据极值点特征推断浪型"""
    if len(pivots) < 4:
        return "generic"
    
    # 获取价格序列
    prices = [p.price for p in pivots]
    
    # 检查是否有6个点且符合推动浪特征
    if len(pivots) >= 6:
        # 简单的推动浪判断: 0-1-2-3-4-5 波浪式上升/下降
        p0, p1, p2, p3, p4, p5 = prices[:6]
        
        # 检查是否是5浪推动结构
        w1 = abs(p1 - p0)
        w2 = abs(p2 - p1)
        w3 = abs(p3 - p2)
        w4 = abs(p4 - p3)
        w5 = abs(p5 - p4)
        
        # 推动浪特征: 1,3,5同向且3通常是最大的
        if w1 > 0 and w2 > 0 and w3 > w1 and w3 > w5 and w4 < w3:
            return "impulse"
    
    # 检查是否是ZigZag (ABC)
    if len(pivots) >= 4:
        p0, pA, pB, pC = prices[:4]
        
        a_len = abs(pA - p0)
        b_len = abs(pB - pA)
        c_len = abs(pC - pB)
        
        # ZigZag特征: A浪和C浪同向，B浪反向且B浪回撤小于A浪
        if b_len < a_len and c_len > b_len:
            return "zigzag"
    
    return "generic"


def _label_impulse(pivots: List[PivotPoint]) -> List[PivotPoint]:
    """标注推动浪浪号 (0-1-2-3-4-5)"""
    labeled = []
    
    # 获取最后6个点标注为推动浪
    wave_nums = ['0', '1', '2', '3', '4', '5']
    
    for i, p in enumerate(pivots):
        if i < len(wave_nums):
            p.wave_num = wave_nums[i]
        else:
            # 超出6个点后，根据趋势延续标注
            last_wave = int(wave_nums[-1]) if wave_nums[-1].isdigit() else 5
            p.wave_num = str(last_wave + 1)
        labeled.append(p)
    
    return labeled


def _label_zigzag(pivots: List[PivotPoint]) -> List[PivotPoint]:
    """标注ZigZag浪号 (A-B-C)"""
    labeled = []
    
    wave_nums = ['A', 'B', 'C']
    
    for i, p in enumerate(pivots):
        if i < len(wave_nums):
            p.wave_num = wave_nums[i]
        else:
            # 超出3个点，可能是复杂调整浪
            if i == 3:
                p.wave_num = 'A'  # 新的调整浪开始
            elif i == 4:
                p.wave_num = 'B'
            else:
                p.wave_num = 'C'
        labeled.append(p)
    
    return labeled


def _label_generic(pivots: List[PivotPoint]) -> List[PivotPoint]:
    """通用浪号标注 - 基于趋势方向"""
    if len(pivots) < 2:
        return pivots
    
    labeled = []
    
    # 确定整体趋势
    overall_trend = "up" if pivots[-1].price > pivots[0].price else "down"
    
    # 根据趋势标注浪号
    for i, p in enumerate(pivots):
        if overall_trend == "up":
            # 上升趋势: 1-2-3-4-5 或 A-B-C
            if i % 2 == 0:  # 峰值或起点
                if i == 0:
                    p.wave_num = '1'
                elif i == 2:
                    p.wave_num = '3'
                elif i == 4:
                    p.wave_num = '5'
                else:
                    p.wave_num = str(i + 1)
            else:  # 谷值
                if i == 1:
                    p.wave_num = '2'
                elif i == 3:
                    p.wave_num = '4'
                else:
                    p.wave_num = str(i + 1)
        else:
            # 下降趋势: A-B-C
            if i == 0:
                p.wave_num = 'A'
            elif i == 1:
                p.wave_num = 'B'
            elif i == 2:
                p.wave_num = 'C'
            else:
                p.wave_num = chr(ord('A') + (i % 3))
        
        labeled.append(p)
    
    return labeled


def validate_wave_structure(
    pivots: List[PivotPoint],
    min_wave_amplitude: float = 0.02,
    max_retracement: float = 1.0
) -> Tuple[bool, str, float]:
    """
    验证波浪结构合理性
    
    Returns:
        (是否有效, 原因, 置信度得分)
    """
    if len(pivots) < 4:
        return False, "极值点不足", 0.0
    
    scores = []
    reasons = []
    
    prices = [p.price for p in pivots]
    
    # 1. 检查波浪幅度
    for i in range(len(prices) - 1):
        amp = abs(prices[i+1] - prices[i]) / prices[i]
        if amp < min_wave_amplitude:
            return False, f"浪{i}幅度过小", 0.0
        scores.append(min(amp / min_wave_amplitude, 1.0))
    
    # 2. 检查回撤是否合理
    for i in range(2, len(prices)):
        prev_wave = abs(prices[i-1] - prices[i-2])
        curr_wave = abs(prices[i] - prices[i-1])
        
        if prev_wave > 0:
            retracement = curr_wave / prev_wave
            if retracement > max_retracement:
                reasons.append(f"浪{i}回撤过大")
                scores.append(0.5)
            else:
                scores.append(1.0 - retracement * 0.5)
    
    # 3. 检查交替原则
    if len(pivots) >= 6:
        w2_amp = abs(prices[2] - prices[1])
        w4_amp = abs(prices[4] - prices[3])
        
        # 浪2和浪4幅度应该不同 (交替)
        if abs(w2_amp - w4_amp) / max(w2_amp, w4_amp) > 0.3:
            scores.append(1.0)
        else:
            scores.append(0.7)
    
    avg_score = np.mean(scores) if scores else 0.0
    
    if avg_score >= 0.7:
        return True, "结构合理", avg_score
    elif avg_score >= 0.5:
        return True, "结构一般", avg_score
    else:
        return False, ";".join(reasons) if reasons else "结构弱", avg_score
