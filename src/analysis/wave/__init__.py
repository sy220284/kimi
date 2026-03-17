"""
波浪分析模块初始化文件 - Phase 1 & 2 完整功能 + 统一分析器

核心功能:
- 基础波浪识别 (1-2-3-4-5, A-B-C)
- ATR自适应极值点检测
- 严格规则引擎验证
- 完整形态库 (三角形, WXY联合调整)
- 子波浪嵌套分析
- 多指标共振验证 (MACD/RSI/Volume)
- 自适应参数优化
- 统一波浪分析器 (新增)
"""

# ========== 统一波浪分析器 (新增 - 推荐使用) ==========
from .unified_analyzer import (
    UnifiedWaveAnalyzer,
    UnifiedWaveSignal,
    WaveEntryType,
    detect_waves,
    detect_wave_by_type
)

# ========== Phase 1: 基础波浪分析 ==========
from .elliott_wave import (
    ElliottWaveAnalyzer,
    WavePattern, WavePoint,
    WaveType, WaveDirection,
    WaveValidation,
    calculate_atr, zigzag_atr,
    validate_impulse_rules
)

# ========== 2/4浪检测器 (保留向后兼容) ==========
from .wave4_detector import (
    Wave4Detector,
    Wave4Signal,
    detect_wave4
)

from .wave2_detector import (
    Wave2Detector,
    Wave2Signal,
    detect_wave2
)

# ========== 增强版检测器 ==========
from .enhanced_detector import (
    enhanced_pivot_detection,
    label_wave_numbers,
    validate_wave_structure,
    PivotPoint
)

# ========== Phase 2: 增强功能 ==========
from .pattern_library import (
    WaveStructure, SubWave,
    TriangleAnalyzer, TriangleType,
    WXYAnalyzer, CombinationType,
    EnhancedWaveBuilder,
    SubWaveDetector
)

from .resonance import (
    ResonanceAnalyzer,
    ResonanceResult,
    IndicatorSignal,
    SignalDirection,
    MACDAnalyzer,
    RSIAnalyzer,
    VolumeAnalyzer
)

from .adaptive_params import (
    AdaptiveParameterOptimizer,
    AdaptiveParameters,
    VolatilityAnalyzer,
    MarketCondition,
    get_adaptive_params
)

__all__ = [
    # 统一分析器 (推荐使用)
    'UnifiedWaveAnalyzer',
    'UnifiedWaveSignal',
    'WaveEntryType',
    'detect_waves',
    'detect_wave_by_type',
    
    # Phase 1 - 基础
    'ElliottWaveAnalyzer',
    'WavePattern', 'WavePoint',
    'WaveType', 'WaveDirection',
    'WaveValidation',
    'calculate_atr', 'zigzag_atr',
    'validate_impulse_rules',
    
    # 2/4浪检测器 (向后兼容)
    'Wave4Detector',
    'Wave4Signal',
    'detect_wave4',
    'Wave2Detector',
    'Wave2Signal',
    'detect_wave2',
    
    # 增强版检测器
    'enhanced_pivot_detection',
    'label_wave_numbers',
    'validate_wave_structure',
    'PivotPoint',
    
    # Phase 2 - 形态库
    'WaveStructure', 'SubWave',
    'TriangleAnalyzer', 'TriangleType',
    'WXYAnalyzer', 'CombinationType',
    'EnhancedWaveBuilder',
    'SubWaveDetector',
    
    # Phase 2 - 共振分析
    'ResonanceAnalyzer',
    'ResonanceResult',
    'IndicatorSignal',
    'SignalDirection',
    'MACDAnalyzer',
    'RSIAnalyzer',
    'VolumeAnalyzer',
    
    # Phase 2 - 自适应参数
    'AdaptiveParameterOptimizer',
    'AdaptiveParameters',
    'VolatilityAnalyzer',
    'MarketCondition',
    'get_adaptive_params',
]
