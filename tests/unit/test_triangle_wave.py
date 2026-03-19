"""
Triangle调整浪测试 - 验证三角形检测功能
"""
import unittest

import numpy as np

from analysis.wave.elliott_wave import (
    ElliottWaveAnalyzer,
    validate_triangle,
    WavePoint,
    WaveType,
)


class TestValidateTriangle(unittest.TestCase):
    """测试Triangle验证函数"""

    def test_valid_triangle(self):
        """测试有效的三角形"""
        # 创建收敛的三角形点位 (A-B-C-D-E)
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_peak=True),
            WavePoint(1, '2024-01-05', 95, 1100, is_trough=True),   # B < A
            WavePoint(2, '2024-01-10', 98, 1050, is_peak=True),     # C < A, C > B
            WavePoint(3, '2024-01-15', 96, 1080, is_trough=True),   # D > B, D < C
            WavePoint(4, '2024-01-20', 97, 1060, is_peak=True),     # E < C, E > D
        ]
        
        valid, errors, score = validate_triangle(points)
        
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
        self.assertGreater(score, 0.5)
    
    def test_not_enough_points(self):
        """测试点数不足"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 95, 1100),
            WavePoint(2, '2024-01-10', 98, 1050),
        ]
        
        valid, errors, score = validate_triangle(points)
        
        self.assertFalse(valid)
        self.assertIn('5个点', errors[0])
    
    def test_diverging_triangle(self):
        """测试发散三角形（不应识别为三角形）"""
        # 发散：子浪长度递增
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_peak=True),
            WavePoint(1, '2024-01-05', 95, 1100, is_trough=True),   # AB = 5
            WavePoint(2, '2024-01-10', 103, 1050, is_peak=True),    # BC = 8 (> AB)
            WavePoint(3, '2024-01-15', 90, 1080, is_trough=True),   # CD = 13 (> BC)
            WavePoint(4, '2024-01-20', 105, 1060, is_peak=True),    # DE = 15 (> CD)
        ]
        
        valid, errors, score = validate_triangle(points)
        
        # 发散三角形评分较低
        self.assertLess(score, 0.6)
    
    def test_e_out_of_range(self):
        """测试E浪超出范围"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_peak=True),
            WavePoint(1, '2024-01-05', 95, 1100, is_trough=True),
            WavePoint(2, '2024-01-10', 98, 1050, is_peak=True),
            WavePoint(3, '2024-01-15', 96, 1080, is_trough=True),
            WavePoint(4, '2024-01-20', 110, 1060, is_peak=True),  # E超出AD范围
        ]
        
        valid, errors, score = validate_triangle(points)
        
        self.assertFalse(valid)
        self.assertIn('E浪超出', errors[0])
    
    def test_perfect_convergence(self):
        """测试完美收敛三角形"""
        # 理想斐波那契比例收缩
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_peak=True),
            WavePoint(1, '2024-01-05', 90, 1100, is_trough=True),   # AB = 10
            WavePoint(2, '2024-01-10', 94, 1050, is_peak=True),     # BC = 4 (0.4)
            WavePoint(3, '2024-01-15', 92, 1080, is_trough=True),   # CD = 2 (0.5)
            WavePoint(4, '2024-01-20', 93, 1060, is_peak=True),     # DE = 1 (0.5)
        ]
        
        valid, errors, score = validate_triangle(points)
        
        self.assertTrue(valid)
        self.assertGreater(score, 0.7)


class TestTriangleDetection(unittest.TestCase):
    """测试三角形检测集成"""

    def setUp(self):
        self.analyzer = ElliottWaveAnalyzer()
    
    def test_try_triangle_with_valid_data(self):
        """测试用有效数据识别三角形"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 95, 1100),
            WavePoint(2, '2024-01-10', 98, 1050),
            WavePoint(3, '2024-01-15', 96, 1080),
            WavePoint(4, '2024-01-20', 97, 1060),
        ]
        
        pattern = self.analyzer._try_triangle(points)
        
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern.wave_type, WaveType.TRIANGLE)
        self.assertEqual(len(pattern.points), 5)
        self.assertIn('A', [p.wave_num for p in pattern.points])
        self.assertIn('E', [p.wave_num for p in pattern.points])
    
    def test_try_triangle_with_invalid_data(self):
        """测试用无效数据识别三角形"""
        # 发散的数据
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 90, 1100),
            WavePoint(2, '2024-01-10', 105, 1050),  # 超过A
            WavePoint(3, '2024-01-15', 85, 1080),   # 低于B
            WavePoint(4, '2024-01-20', 110, 1060),  # 超过C
        ]
        
        pattern = self.analyzer._try_triangle(points)
        
        # 发散三角形评分很低，可能返回None
        if pattern is not None:
            self.assertLess(pattern.confidence, 0.5)
    
    def test_triangle_target_calculation(self):
        """测试三角形目标价计算"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 95, 1100),   # 下降调整
            WavePoint(2, '2024-01-10', 98, 1050),
            WavePoint(3, '2024-01-15', 96, 1080),
            WavePoint(4, '2024-01-20', 97, 1060),
        ]
        
        pattern = self.analyzer._try_triangle(points)
        
        self.assertIsNotNone(pattern)
        self.assertIsNotNone(pattern.target_price)
        self.assertIsNotNone(pattern.stop_loss)
        
        # 下降三角形，目标应低于E
        self.assertLess(pattern.target_price, 97)
        # 止损应在B上方
        self.assertGreater(pattern.stop_loss, 95)


class TestTriangleIntegration(unittest.TestCase):
    """三角形集成测试"""

    def setUp(self):
        self.analyzer = ElliottWaveAnalyzer()
    
    def test_detect_with_triangle_pattern(self):
        """测试在完整数据流中检测三角形"""
        import pandas as pd
        
        # 创建模拟的三角形价格数据
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        
        # 模拟收敛三角形价格走势
        prices = []
        base = 100
        for i in range(30):
            if i < 5:
                p = base + i  # 上升到A
            elif i < 10:
                p = base + 5 - (i-5) * 0.8  # 下降到B (80%回撤)
            elif i < 15:
                p = base + 1 + (i-10) * 0.6  # 上升到C (小于A)
            elif i < 20:
                p = base + 4 - (i-15) * 0.4  # 下降到D (高于B)
            elif i < 25:
                p = base + 2 + (i-20) * 0.3  # 上升到E (小于C)
            else:
                p = base + 3.5 + (i-25) * 0.5  # 突破
            prices.append(p)
        
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 0.5 for p in prices],
            'low': [p - 0.5 for p in prices],
            'close': prices,
            'volume': [1000] * 30
        })
        
        # 检测波浪模式
        pattern = self.analyzer.detect_wave_pattern(df)
        
        # 验证检测到某种模式
        self.assertIsNotNone(pattern)
        # 可能是三角形或其他调整浪
        self.assertIn(pattern.wave_type.value, 
                     ['triangle', 'flat', 'zigzag', 'impulse', 'unknown'])


if __name__ == '__main__':
    unittest.main()
