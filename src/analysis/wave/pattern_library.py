"""
完整波浪形态库 - Phase 2 分析层优化
支持: 三角形、WXY联合调整、复合结构、子波浪嵌套
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class TriangleType(Enum):
    """三角形类型"""
    ASCENDING = "ascending"      # 上升三角形 (水平顶，上升底)
    DESCENDING = "descending"    # 下降三角形 (水平底，下降顶)
    SYMMETRICAL = "symmetrical"  # 对称三角形 (收敛)
    EXPANDING = "expanding"      # 扩张三角形 (发散)
    RUNNING = "running"          # 奔走三角形


class CombinationType(Enum):
    """联合调整类型"""
    DOUBLE_ZIGZAG = "double_zigzag"      # WXY 双锯齿
    TRIPLE_ZIGZAG = "triple_zigzag"      # WXYXZ 三锯齿
    DOUBLE_THREE = "double_three"        # 双重三浪 (任意调整组合)
    TRIPLE_THREE = "triple_three"        # 三重三浪


@dataclass
class SubWave:
    """子波浪结构 - 用于嵌套分析"""
    wave_num: str           # 如 "1", "2", "(1)", "((1))" 等
    level: int              # 级别: 1=初级, 2=次级, 3=微级
    start_price: float
    end_price: float
    start_date: str
    end_date: str
    pattern: Optional[Any] = None  # 嵌套的子结构
    
    @property
    def length(self) -> float:
        return abs(self.end_price - self.start_price)
    
    @property
    def is_up(self) -> bool:
        return self.end_price > self.start_price


@dataclass
class WaveStructure:
    """完整波浪结构 - 包含多级嵌套"""
    level: int                          # 级别: 1=大周期, 2=中周期, 3=小周期
    wave_type: str                      # impulse / zigzag / flat / triangle / combo
    direction: str                      # up / down
    waves: List[SubWave]                # 子浪列表
    confidence: float
    fib_targets: Dict[str, float]       # 斐波那契目标位
    warnings: List[str] = field(default_factory=list)  # 警告信息
    
    def get_wave(self, num: str) -> Optional[SubWave]:
        """获取指定浪号的子浪"""
        for w in self.waves:
            if w.wave_num == num:
                return w
        return None
    
    def has_nested_structure(self, wave_num: str) -> bool:
        """检查指定浪号是否有嵌套结构"""
        wave = self.get_wave(wave_num)
        return wave is not None and wave.pattern is not None


class TriangleAnalyzer:
    """三角形调整浪分析器"""
    
    @staticmethod
    def identify(points: List[Tuple[str, float, float]], tolerance: float = 0.05) -> Optional[Dict[str, Any]]:
        """
        识别三角形调整浪
        
        Args:
            points: [(label, price, timestamp), ...] A-B-C-D-E 五点
            tolerance: 趋势线拟合容差
            
        Returns:
            {
                'type': TriangleType,
                'confidence': float,
                'converging': bool,  # 是否收敛
                'breakout_direction': str,  # 突破方向预测
                'target_price': float
            }
        """
        if len(points) < 5:
            return None
        
        # 提取 A-B-C-D-E
        A, B, C, D, E = points[0], points[1], points[2], points[3], points[4]
        
        # 分析趋势线
        tops = [A[1], C[1], E[1]]      # A, C, E 顶
        bottoms = [B[1], D[1]]         # B, D 底
        
        # 判断三角形类型
        top_trend = TriangleAnalyzer._trend_direction(tops)
        bottom_trend = TriangleAnalyzer._trend_direction(bottoms)
        
        triangle_type = None
        confidence = 0.0
        
        # 上升三角形: 水平顶，上升底
        if abs(top_trend) < tolerance and bottom_trend > tolerance:
            triangle_type = TriangleType.ASCENDING
            confidence = 0.7
        # 下降三角形: 下降顶，水平底
        elif top_trend < -tolerance and abs(bottom_trend) < tolerance:
            triangle_type = TriangleType.DESCENDING
            confidence = 0.7
        # 对称三角形: 收敛
        elif top_trend < -tolerance and bottom_trend > tolerance:
            triangle_type = TriangleType.SYMMETRICAL
            confidence = 0.8
        # 扩张三角形: 发散
        elif top_trend > tolerance and bottom_trend < -tolerance:
            triangle_type = TriangleType.EXPANDING
            confidence = 0.6
        
        if triangle_type is None:
            return None
        
        # 预测突破方向 (通常与原趋势相同)
        # 这里简化处理，实际应结合更大周期判断
        breakout_dir = "up" if triangle_type in [TriangleType.ASCENDING, TriangleType.SYMMETRICAL] else "down"
        
        # 计算目标价 (E点 + 三角形最宽处)
        max_width = max(tops) - min(bottoms)
        target = E[1] + max_width if breakout_dir == "up" else E[1] - max_width
        
        return {
            'type': triangle_type,
            'confidence': confidence,
            'converging': triangle_type != TriangleType.EXPANDING,
            'breakout_direction': breakout_dir,
            'target_price': round(target, 2)
        }
    
    @staticmethod
    def _trend_direction(values: List[float]) -> float:
        """计算趋势方向 (-1到1)"""
        if len(values) < 2:
            return 0.0
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        # 标准化
        avg_val = np.mean(values)
        return slope / (avg_val + 1e-8)


class WXYAnalyzer:
    """WXY联合调整分析器 (双锯齿/三锯齿)"""
    
    @staticmethod
    def identify(points: List[Tuple[str, float, float]], 
                 min_retracement: float = 0.382,
                 max_retracement: float = 0.786) -> Optional[Dict[str, Any]]:
        """
        识别 WXY 或 WXYXZ 联合调整
        
        WXY: 两个ZigZag由X浪连接
        WXYXZ: 三个ZigZag由X浪连接
        
        Args:
            points: W-X-Y 或 W-X-Y-X-Z
            
        Returns:
            {
                'type': 'double_zigzag' or 'triple_zigzag',
                'confidence': float,
                'w_length': float,
                'y_length': float,
                'equality_score': float  # W和Y长度相等程度
            }
        """
        if len(points) < 6:  # 至少 W-X-Y (6个点)
            return None
        
        # 简化识别 - 实际应分析每个ZigZag的内部结构
        W_end = points[2]  # W浪结束点
        X_end = points[4]  # X浪结束点  
        Y_end = points[-1] # Y浪结束点
        
        # 计算W和Y的长度
        W_start = points[0]
        W_length = abs(W_end[1] - W_start[1])
        Y_length = abs(Y_end[1] - X_end[1])
        
        # W和Y应该大致相等 (指导原则)
        if W_length > 0:
            equality = min(W_length, Y_length) / max(W_length, Y_length)
        else:
            equality = 0.0
        
        # 判断是双锯齿还是三锯齿
        if len(points) >= 10:  # W-X-Y-X-Z
            combo_type = CombinationType.TRIPLE_ZIGZAG
            confidence = 0.6 + equality * 0.2
        else:
            combo_type = CombinationType.DOUBLE_ZIGZAG
            confidence = 0.7 + equality * 0.2
        
        return {
            'type': combo_type,
            'confidence': min(0.95, confidence),
            'w_length': W_length,
            'y_length': Y_length,
            'equality_score': equality
        }


class SubWaveDetector:
    """子波浪嵌套检测器 - 在大级别波浪中检测小级别结构"""
    
    def __init__(self, max_depth: int = 2):
        """
        初始化
        
        Args:
            max_depth: 最大嵌套深度 (2=检测次级浪，3=检测微级浪)
        """
        self.max_depth = max_depth
    
    def analyze_nesting(self, df: pd.DataFrame, parent_wave: SubWave, 
                        current_level: int = 1) -> Optional[WaveStructure]:
        """
        分析子波浪嵌套结构
        
        Args:
            df: 完整数据
            parent_wave: 父级波浪
            current_level: 当前层级
            
        Returns:
            WaveStructure with nested sub-waves
        """
        if current_level >= self.max_depth:
            return None
        
        # 提取父级波浪对应的数据段
        # 这里简化处理，实际应根据日期范围过滤
        # TODO: 实现完整的数据过滤
        
        # 对父级波浪内部进行小级别波浪分析
        from .elliott_wave import ElliottWaveAnalyzer
        
        _analyzer = ElliottWaveAnalyzer(
            atr_period=max(5, 14 - current_level * 4),  # 小周期用更短ATR
            atr_mult=0.3 + current_level * 0.1,         # 小周期用更小倍数
            confidence_threshold=0.4
        )
        
        # 检测内部结构
        # TODO: 实现完整的子波浪检测
        
        return None
    
    def detect_sub_impulse(self, df: pd.DataFrame, start_idx: int, end_idx: int) -> Optional[WaveStructure]:
        """在指定范围内检测子级别推动浪"""
        if end_idx - start_idx < 20:  # 数据太少
            return None
        
        sub_df = df.iloc[start_idx:end_idx].copy()
        
        from .elliott_wave import ElliottWaveAnalyzer
        analyzer = ElliottWaveAnalyzer(
            atr_period=5,
            atr_mult=0.25,
            confidence_threshold=0.35
        )
        
        pattern = analyzer.detect_wave_pattern(sub_df)
        
        if pattern and pattern.confidence > 0.35:
            # 构建WaveStructure
            waves = []
            for i, p in enumerate(pattern.points):
                if p.wave_num:
                    waves.append(SubWave(
                        wave_num=f"({p.wave_num})",  # 括号表示次级浪
                        level=2,
                        start_price=p.price,
                        end_price=p.price,
                        start_date=p.date,
                        end_date=p.date
                    ))
            
            return WaveStructure(
                level=2,
                wave_type=pattern.wave_type.value,
                direction=pattern.direction.value,
                waves=waves,
                confidence=pattern.confidence,
                fib_targets=pattern.fib_ratios or {}
            )
        
        return None


class EnhancedWaveBuilder:
    """增强型波浪构建器 - 整合所有形态识别"""
    
    def __init__(self):
        self.triangle_analyzer = TriangleAnalyzer()
        self.wxy_analyzer = WXYAnalyzer()
        self.sub_detector = SubWaveDetector()
    
    def build_complete_structure(self, df: pd.DataFrame, 
                                  primary_pattern: Any) -> WaveStructure:
        """
        构建完整的波浪结构 (含嵌套)
        
        Args:
            df: 价格数据
            primary_pattern: 主级波浪形态
            
        Returns:
            完整的WaveStructure
        """
        # 1. 构建主级结构
        main_waves = []
        for i, p in enumerate(primary_pattern.points):
            wave = SubWave(
                wave_num=p.wave_num or str(i),
                level=1,
                start_price=p.price,
                end_price=p.price,
                start_date=p.date,
                end_date=p.date
            )
            main_waves.append(wave)
        
        structure = WaveStructure(
            level=1,
            wave_type=primary_pattern.wave_type.value,
            direction=primary_pattern.direction.value,
            waves=main_waves,
            confidence=primary_pattern.confidence,
            fib_targets=primary_pattern.fib_ratios or {}
        )
        
        # 2. 检测三角形 (如果是调整浪)
        if len(main_waves) >= 5 and structure.wave_type in ['corrective', 'flat', 'zigzag']:
            points = [(w.wave_num, w.start_price, 0) for w in main_waves[:5]]
            triangle = self.triangle_analyzer.identify(points)
            
            if triangle and triangle['confidence'] > 0.6:
                structure.wave_type = 'triangle'
                structure.fib_targets['triangle_target'] = triangle['target_price']
                structure.warnings.append(f"检测到{triangle['type'].value}三角形，突破方向: {triangle['breakout_direction']}")
        
        # 3. 检测WXY (如果点足够)
        if len(main_waves) >= 6:
            points = [(w.wave_num, w.start_price, 0) for w in main_waves]
            wxy = self.wxy_analyzer.identify(points)
            
            if wxy and wxy['confidence'] > 0.6:
                structure.wave_type = wxy['type'].value
                structure.confidence = wxy['confidence']
        
        # 4. 检测子波浪嵌套 (对推动浪)
        if structure.wave_type == 'impulse' and len(main_waves) >= 5:
            for i, wave in enumerate(structure.waves):
                if wave.wave_num in ['3', '5']:  # 3浪和5浪常有延长
                    # TODO: 精确定位子波浪数据范围
                    sub_structure = self.sub_detector.detect_sub_impulse(
                        df, i * 10, (i + 1) * 10  # 简化范围
                    )
                    if sub_structure:
                        wave.pattern = sub_structure
                        structure.warnings.append(f"浪{wave.wave_num}检测到延长结构")
        
        return structure
