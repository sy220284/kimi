"""
增强版波浪分析器 - Phase 2 完整整合
整合: 完整形态库 + 子波浪嵌套 + 多指标共振 + 自适应参数
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .elliott_wave import ElliottWaveAnalyzer, WavePattern, WaveType, WaveDirection
from .wave_detector import WaveDetector, WaveSignal
from .pattern_library import (
    EnhancedWaveBuilder, WaveStructure, SubWave,
    TriangleAnalyzer, WXYAnalyzer
)
from .resonance import ResonanceAnalyzer, SignalDirection
from .adaptive_params import AdaptiveParameterOptimizer, get_adaptive_params


@dataclass
class EnhancedAnalysisResult:
    """增强版分析结果"""
    symbol: str
    primary_pattern: WavePattern
    complete_structure: WaveStructure
    resonance: Any  # ResonanceResult
    adaptive_params: Dict[str, Any]
    market_condition: str
    sub_wave_analysis: Optional[WaveStructure] = None
    triangle_detected: bool = False
    wxy_detected: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'wave_type': self.primary_pattern.wave_type.value,
            'direction': self.primary_pattern.direction.value,
            'confidence': self.primary_pattern.confidence,
            'resonance_score': self.resonance.overall_strength if self.resonance else 0,
            'market_condition': self.market_condition,
            'recommendation': self.resonance.recommendation if self.resonance else "",
            'adaptive_params': self.adaptive_params
        }


class EnhancedWaveAnalyzer:
    """
    增强版波浪分析器 - Phase 2 完整功能
    
    Features:
    1. 自适应参数优化 (可手动覆盖)
    2. 完整波浪形态识别 (三角形/WXY)
    3. 子波浪嵌套分析
    4. 多指标共振验证
    """
    
    def __init__(
        self,
        use_adaptive: bool = True,
        use_resonance: bool = True,
        # 手动参数覆盖 (用于回测优化)
        atr_mult: Optional[float] = None,
        confidence_threshold: Optional[float] = None,
        min_change_pct: Optional[float] = None,
        peak_window: Optional[int] = None,
        min_dist: Optional[int] = None
    ):
        self.use_adaptive = use_adaptive
        self.use_resonance = use_resonance
        self.wave_builder = EnhancedWaveBuilder()
        self.resonance_analyzer = ResonanceAnalyzer()
        self.param_optimizer = AdaptiveParameterOptimizer()
        
        # 手动参数覆盖
        self._override_params = {}
        if atr_mult is not None:
            self._override_params['atr_mult'] = atr_mult
        if confidence_threshold is not None:
            self._override_params['confidence_threshold'] = confidence_threshold
        if min_change_pct is not None:
            self._override_params['min_change_pct'] = min_change_pct
        if peak_window is not None:
            self._override_params['peak_window'] = peak_window
        if min_dist is not None:
            self._override_params['min_dist'] = min_dist
    
    def analyze(self, symbol: str, df: pd.DataFrame, timeframe: str = "day") -> EnhancedAnalysisResult:
        """
        完整分析流程
        
        Args:
            symbol: 股票代码
            df: 价格数据
            timeframe: 时间框架
            
        Returns:
            EnhancedAnalysisResult
        """
        # 1. 自适应参数优化 (或使用手动覆盖)
        if self.use_adaptive and not self._override_params:
            adaptive_params = self.param_optimizer.optimize(df, timeframe)
            params = adaptive_params.to_dict()
            market_condition = self.param_optimizer.optimize(df, timeframe)
            # 获取市场状态说明
            vol_analysis = self.param_optimizer.ADJUSTMENTS
        else:
            # 基础默认参数 + 手动覆盖
            params = {
                'atr_period': 14,
                'atr_mult': 0.5,
                'confidence_threshold': 0.5,
                'min_dist': 3,
                'min_change_pct': 2.0,
                'peak_window': 3
            }
            # 应用手动覆盖
            params.update(self._override_params)
            market_condition = "manual"
        
        # 2. 基础波浪检测
        detector = WaveDetector(
            confidence_threshold=params['confidence_threshold'],
            atr_period=params['atr_period'],
            atr_mult=params['atr_mult'],
            peak_window=params.get('peak_window', 3)
        )
        
        signal = detector.detect(symbol, df)
        
        if not signal:
            # 使用不同参数重试
            return self._handle_no_signal(symbol, df, timeframe)
        
        # 3. 构建完整波浪结构
        complete_structure = self.wave_builder.build_complete_structure(
            df, signal.wave_pattern
        )
        
        # 4. 检测特殊形态
        triangle_detected = complete_structure.wave_type == 'triangle'
        wxy_detected = 'zigzag' in complete_structure.wave_type and len(complete_structure.waves) >= 6
        
        # 5. 多指标共振分析
        resonance = None
        if self.use_resonance:
            resonance = self.resonance_analyzer.analyze(df, signal)
        
        # 6. 确定市场状态
        from .adaptive_params import VolatilityAnalyzer
        vol_analysis = VolatilityAnalyzer.calculate_volatility_regime(df)
        market_condition_str = vol_analysis['market_condition'].value
        
        return EnhancedAnalysisResult(
            symbol=symbol,
            primary_pattern=signal.wave_pattern,
            complete_structure=complete_structure,
            resonance=resonance,
            adaptive_params=params,
            market_condition=market_condition_str,
            triangle_detected=triangle_detected,
            wxy_detected=wxy_detected
        )
    
    def _handle_no_signal(self, symbol: str, df: pd.DataFrame, timeframe: str) -> EnhancedAnalysisResult:
        """处理未识别到波浪的情况"""
        # 尝试更宽松的参数
        detector = WaveDetector(
            confidence_threshold=0.3,
            atr_period=10,
            atr_mult=0.3
        )
        
        signal = detector.detect(symbol, df)
        
        if not signal:
            # 创建空结果
            from .elliott_wave import WavePattern, WaveType, WaveDirection, WavePoint
            empty_pattern = WavePattern(
                wave_type=WaveType.UNKNOWN,
                direction=WaveDirection.UNKNOWN,
                points=[],
                confidence=0.0,
                start_date="",
                end_date=""
            )
            
            return EnhancedAnalysisResult(
                symbol=symbol,
                primary_pattern=empty_pattern,
                complete_structure=WaveStructure(
                    level=1,
                    wave_type="unknown",
                    direction="unknown",
                    waves=[],
                    confidence=0.0,
                    fib_targets={},
                    warnings=["未识别到明确波浪形态"]
                ),
                resonance=None,
                adaptive_params={},
                market_condition="unknown"
            )
        
        return self.analyze(symbol, df, timeframe)
    
    def analyze_multi_timeframe(
        self,
        symbol: str,
        df_daily: pd.DataFrame,
        df_weekly: Optional[pd.DataFrame] = None,
        df_monthly: Optional[pd.DataFrame] = None
    ) -> Dict[str, EnhancedAnalysisResult]:
        """
        多时间框架分析
        
        Args:
            symbol: 股票代码
            df_daily: 日线数据
            df_weekly: 周线数据 (可选)
            df_monthly: 月线数据 (可选)
            
        Returns:
            {'daily': result, 'weekly': result, 'monthly': result}
        """
        results = {}
        
        # 日线
        results['daily'] = self.analyze(symbol, df_daily, 'day')
        
        # 周线
        if df_weekly is not None and not df_weekly.empty:
            results['weekly'] = self.analyze(symbol, df_weekly, 'week')
        
        # 月线
        if df_monthly is not None and not df_monthly.empty:
            results['monthly'] = self.analyze(symbol, df_monthly, 'month')
        
        return results
    
    def generate_report(self, result: EnhancedAnalysisResult) -> str:
        """生成分析报告"""
        lines = []
        
        lines.append(f"\n{'='*60}")
        lines.append(f"📊 {result.symbol} - 增强版波浪分析报告")
        lines.append('='*60)
        
        # 基础波浪信息
        pattern = result.primary_pattern
        lines.append(f"\n【波浪形态】")
        lines.append(f"  类型: {pattern.wave_type.value.upper()}")
        lines.append(f"  方向: {'📈 上升' if pattern.direction.value == 'up' else '📉 下降'}")
        lines.append(f"  置信度: {pattern.confidence:.1%}")
        
        # 特殊形态检测
        lines.append(f"\n【特殊形态检测】")
        if result.triangle_detected:
            lines.append(f"  🔺 检测到三角形调整")
        if result.wxy_detected:
            lines.append(f"  📎 检测到WXY联合调整")
        if not result.triangle_detected and not result.wxy_detected:
            lines.append(f"  无特殊复合形态")
        
        # 共振分析
        if result.resonance:
            lines.append(f"\n【多指标共振】")
            lines.append(f"  综合方向: {result.resonance.overall_direction.value}")
            lines.append(f"  共振强度: {result.resonance.overall_strength:.1%}")
            lines.append(f"  各指标信号:")
            for sig in result.resonance.signals:
                icon = "📈" if sig.direction == SignalDirection.BULLISH else "📉" if sig.direction == SignalDirection.BEARISH else "➖"
                lines.append(f"    {icon} {sig.name}: {sig.description} (强度{sig.strength:.1%})")
            
            if result.resonance.conflicts:
                lines.append(f"  ⚠️ 信号冲突:")
                for c in result.resonance.conflicts:
                    lines.append(f"    - {c}")
            
            lines.append(f"\n💡 建议: {result.resonance.recommendation}")
        
        # 自适应参数
        lines.append(f"\n【自适应参数】")
        lines.append(f"  市场状态: {result.market_condition}")
        for k, v in result.adaptive_params.items():
            lines.append(f"  {k}: {v}")
        
        return '\n'.join(lines)


# 便捷函数
def analyze_stock(symbol: str, df: pd.DataFrame, timeframe: str = "day") -> EnhancedAnalysisResult:
    """快速分析单只股票"""
    analyzer = EnhancedWaveAnalyzer()
    return analyzer.analyze(symbol, df, timeframe)

def analyze_stock_full(symbol: str, df_daily: pd.DataFrame) -> Dict[str, Any]:
    """
    完整分析（自动转换周线月线）
    
    Returns:
        包含日线/周线/月线的完整分析结果
    """
    analyzer = EnhancedWaveAnalyzer()
    
    # 转换时间框架
    def to_weekly(df):
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        weekly = df.resample('W').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna().reset_index()
        weekly['date'] = weekly['date'].dt.strftime('%Y-%m-%d')
        return weekly
    
    def to_monthly(df):
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        monthly = df.resample('ME').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna().reset_index()
        monthly['date'] = monthly['date'].dt.strftime('%Y-%m-%d')
        return monthly
    
    df_weekly = to_weekly(df_daily) if len(df_daily) > 50 else None
    df_monthly = to_monthly(df_daily) if len(df_daily) > 200 else None
    
    return analyzer.analyze_multi_timeframe(
        symbol, df_daily, df_weekly, df_monthly
    )
