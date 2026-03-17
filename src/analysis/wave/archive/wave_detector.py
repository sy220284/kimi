"""
波浪分析模块 - 增强版波浪形态检测器
集成ATR自适应极值点、严格规则验证、多维度信号生成
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger
from .elliott_wave import (
    ElliottWaveAnalyzer, WavePattern, WavePoint,
    WaveType, WaveDirection, WaveValidation
)


@dataclass
class WaveSignal:
    """波浪信号"""
    symbol: str
    signal_type: str
    confidence: float
    wave_pattern: WavePattern
    analysis_date: str
    reason: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'confidence': self.confidence,
            'analysis_date': self.analysis_date,
            'reason': self.reason,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'risk_reward_ratio': self.risk_reward_ratio,
            'wave_pattern': self.wave_pattern.to_dict()
        }


class WaveDetector:
    """增强版波浪形态检测器 - 专业版"""
    
    def __init__(
        self,
        min_wave_length: int = 5,
        max_wave_length: int = 100,
        confidence_threshold: float = 0.5,
        peak_window: int = 3,
        min_change_pct: float = 2.0,
        atr_period: int = 14,
        atr_mult: float = 0.5,
    ):
        """
        初始化检测器
        
        Args:
            min_wave_length: 最小波浪长度
            max_wave_length: 最大波浪长度
            confidence_threshold: 置信度阈值
            peak_window: 峰值窗口 (用于兼容旧接口)
            min_change_pct: 最小变动百分比 (用于兼容旧接口)
            atr_period: ATR计算周期
            atr_mult: ATR倍数阈值
        """
        self.analyzer = ElliottWaveAnalyzer(
            min_wave_length=min_wave_length,
            max_wave_length=max_wave_length,
            confidence_threshold=confidence_threshold,
            atr_period=atr_period,
            atr_mult=atr_mult,
            min_dist=peak_window,
        )
        self.peak_window = peak_window
        self.min_change_pct = min_change_pct
        self.confidence_threshold = confidence_threshold
        self.logger = get_logger('analysis.wave.detector')
    
    def detect(self, symbol: str, df: pd.DataFrame) -> Optional[WaveSignal]:
        """
        检测波浪并生成交易信号
        
        Args:
            symbol: 股票代码
            df: 价格数据DataFrame
            
        Returns:
            波浪信号或None
        """
        if df.empty or len(df) < self.analyzer.min_wave_length:
            self.logger.warning(f"{symbol} 数据不足")
            return None
        
        try:
            pattern = self.analyzer.detect_wave_pattern(df)
            if not pattern:
                self.logger.info(f"{symbol} 未识别到明确波浪形态")
                return None
            
            trend = self.analyzer.analyze_trend(df, pattern)
            signal = self._generate_signal(symbol, df, pattern, trend)
            
            self.logger.info(
                f"{symbol} 检测到{pattern.wave_type.value}波浪, "
                f"置信度: {pattern.confidence:.2f}, 信号: {signal.signal_type}"
            )
            
            return signal
            
        except Exception as e:
            self.logger.error(f"{symbol} 波浪检测失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        pattern: WavePattern,
        trend: Dict[str, Any]
    ) -> WaveSignal:
        """生成交易信号"""
        current_price = df['close'].iloc[-1]
        analysis_date = df['date'].iloc[-1] if 'date' in df.columns else str(len(df))
        
        # 基础信号
        signal_type = self._determine_signal_type(pattern, trend, current_price)
        
        # 调整置信度
        final_confidence = pattern.confidence
        if pattern.guideline_scores:
            # 如果有指导原则评分，加权计算
            guideline_avg = np.mean(list(pattern.guideline_scores.values()))
            final_confidence = pattern.confidence * 0.7 + guideline_avg * 0.3
        
        # 生成理由
        reason = self._generate_reason(pattern, trend)
        
        # 计算风险收益比
        risk_reward = None
        if pattern.target_price and pattern.stop_loss:
            risk = abs(current_price - pattern.stop_loss)
            reward = abs(pattern.target_price - current_price)
            if risk > 0:
                risk_reward = reward / risk
        
        return WaveSignal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=min(0.95, final_confidence),
            wave_pattern=pattern,
            analysis_date=analysis_date,
            reason=reason,
            target_price=pattern.target_price,
            stop_loss=pattern.stop_loss,
            risk_reward_ratio=risk_reward
        )
    
    def _determine_signal_type(
        self,
        pattern: WavePattern,
        trend: Dict[str, Any],
        current_price: float
    ) -> str:
        """确定信号类型"""
        last_point = pattern.points[-1]
        position = trend.get('position', '')
        
        if pattern.wave_type == WaveType.IMPULSE:
            if pattern.direction == WaveDirection.UP:
                if 'wave_5_complete' in position:
                    return 'watch'  # 上升推动浪完成，观望
                elif last_point.wave_num in ['2', '4']:
                    return 'buy'  # 回调结束
                else:
                    return 'hold'
            else:
                if 'wave_5_complete' in position:
                    return 'watch'  # 下降推动浪完成，可能反弹
                elif last_point.wave_num in ['2', '4']:
                    return 'sell'  # 反弹结束
                else:
                    return 'sell'
        
        elif pattern.wave_type == WaveType.ZIGZAG:
            if pattern.direction == WaveDirection.DOWN:
                if last_point.wave_num == 'C':
                    return 'buy'  # 下降调整完成
                else:
                    return 'watch'
            else:
                if last_point.wave_num == 'C':
                    return 'sell'  # 上升调整完成
                else:
                    return 'watch'
        
        elif pattern.wave_type in [WaveType.FLAT, WaveType.CORRECTIVE]:
            if last_point.wave_num == 'C':
                return 'buy' if pattern.direction == WaveDirection.DOWN else 'sell'
            else:
                return 'watch'
        
        return 'watch'
    
    def _generate_reason(self, pattern: WavePattern, trend: Dict[str, Any]) -> str:
        """生成交易理由"""
        reasons = []
        
        # 波浪描述
        direction_desc = "上升" if pattern.direction == WaveDirection.UP else "下降"
        wave_type_desc = {
            WaveType.IMPULSE: "推动浪",
            WaveType.ZIGZAG: "ZigZag调整浪",
            WaveType.FLAT: "Flat调整浪",
            WaveType.CORRECTIVE: "调整浪",
        }.get(pattern.wave_type, pattern.wave_type.value)
        
        reasons.append(f"识别到{direction_desc}{wave_type_desc}(置信度{pattern.confidence:.0%})")
        
        # 当前位置
        last_wave = pattern.points[-1].wave_num
        if last_wave:
            reasons.append(f"当前处于浪{last_wave}阶段")
        
        # 斐波那契比例
        if pattern.fib_ratios:
            if 'w2_retracement' in pattern.fib_ratios:
                r2 = pattern.fib_ratios['w2_retracement']
                if 0.382 <= r2 <= 0.618:
                    reasons.append(f"浪2回撤{r2:.1%}符合黄金分割")
            
            if 'w3_vs_w1' in pattern.fib_ratios:
                r3 = pattern.fib_ratios['w3_vs_w1']
                if r3 >= 1.618:
                    reasons.append(f"浪3强延伸({r3:.2f}x)")
        
        # 指导原则评分
        if pattern.guideline_scores:
            passed = [k for k, v in pattern.guideline_scores.items() if v > 0]
            if passed:
                reasons.append(f"通过验证: {', '.join(passed[:3])}")
        
        return '; '.join(reasons)
    
    def scan_multiple(self, data_dict: Dict[str, pd.DataFrame]) -> List[WaveSignal]:
        """批量扫描多只股票"""
        signals = []
        
        for symbol, df in data_dict.items():
            try:
                signal = self.detect(symbol, df)
                if signal and signal.confidence >= self.confidence_threshold:
                    signals.append(signal)
            except Exception as e:
                self.logger.error(f"扫描 {symbol} 失败: {e}")
        
        signals.sort(key=lambda x: x.confidence, reverse=True)
        self.logger.info(f"扫描完成，发现 {len(signals)} 个交易信号")
        return signals
    
    def get_wave_statistics(self, df: pd.DataFrame, window: int = 5) -> Dict[str, Any]:
        """获取波浪统计信息"""
        peaks, troughs = self.analyzer.find_peaks_and_troughs(df, window, self.min_change_pct)
        
        if not peaks or not troughs:
            return {
                'peak_count': 0,
                'trough_count': 0,
                'wave_amplitude_avg': 0,
            }
        
        closes = df['close'].values
        amplitudes = []
        
        for i in range(min(len(peaks), len(troughs))):
            if i < len(peaks) and i < len(troughs):
                peak_price = closes[peaks[i]]
                trough_price = closes[troughs[i]]
                amplitude = abs(peak_price - trough_price) / trough_price * 100
                amplitudes.append(amplitude)
        
        return {
            'peak_count': len(peaks),
            'trough_count': len(troughs),
            'wave_amplitude_avg': round(np.mean(amplitudes), 4) if amplitudes else 0,
            'wave_amplitude_std': round(np.std(amplitudes), 4) if amplitudes else 0,
        }
