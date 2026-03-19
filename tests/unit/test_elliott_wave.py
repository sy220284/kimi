"""
波浪分析器单元测试 - 全面测试ElliottWaveAnalyzer
"""
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from analysis.wave.elliott_wave import (
    ElliottWaveAnalyzer,
    WavePoint,
    WavePattern,
    WaveType,
    WaveDirection,
    validate_impulse,
    validate_zigzag,
    validate_flat,
    validate_triangle,
)


class TestWavePoint(unittest.TestCase):
    """测试WavePoint数据类"""

    def test_wave_point_creation(self):
        """测试WavePoint创建"""
        point = WavePoint(
            index=0,
            date='2024-01-01',
            price=100.0,
            volume=1000,
            is_peak=True,
            is_trough=False,
            strength=0.8
        )
        
        self.assertEqual(point.index, 0)
        self.assertEqual(point.price, 100.0)
        self.assertTrue(point.is_peak)
        self.assertFalse(point.is_trough)
        self.assertEqual(point.wave_num, '')
    
    def test_wave_point_with_wave_num(self):
        """测试带浪号的WavePoint"""
        point = WavePoint(
            index=1,
            date='2024-01-05',
            price=110.0,
            volume=1200,
            is_peak=True
        )
        point.wave_num = '1'
        
        self.assertEqual(point.wave_num, '1')


class TestValidateImpulse(unittest.TestCase):
    """测试推动浪验证函数"""

    def test_valid_impulse(self):
        """测试有效的推动浪"""
        # 标准5浪推动：浪3最长，浪4不跌破浪1
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_trough=True),   # 0
            WavePoint(1, '2024-01-05', 110, 1200, is_peak=True),     # 1
            WavePoint(2, '2024-01-10', 105, 1100, is_trough=True),   # 2 (50%回撤)
            WavePoint(3, '2024-01-15', 125, 1300, is_peak=True),     # 3 (最长)
            WavePoint(4, '2024-01-20', 118, 1150, is_trough=True),   # 4 (高于1)
            WavePoint(5, '2024-01-25', 135, 1400, is_peak=True),     # 5
        ]
        
        valid, errors, score = validate_impulse(points)
        
        self.assertTrue(valid)
        self.assertEqual(len(errors), 0)
        self.assertGreater(score, 0.7)
    
    def test_wave3_not_longest(self):
        """测试浪3不是最长的情况"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_trough=True),
            WavePoint(1, '2024-01-05', 110, 1200, is_peak=True),     # +10
            WavePoint(2, '2024-01-10', 105, 1100, is_trough=True),
            WavePoint(3, '2024-01-15', 112, 1300, is_peak=True),     # +7 (不是最长)
            WavePoint(4, '2024-01-20', 108, 1150, is_trough=True),
            WavePoint(5, '2024-01-25', 120, 1400, is_peak=True),     # +12 (最长)
        ]
        
        valid, errors, score = validate_impulse(points)
        
        # 浪5比浪3长，这是不规范的
        self.assertLess(score, 0.8)
    
    def test_wave4_breaks_wave1(self):
        """测试浪4跌破浪1高点"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_trough=True),
            WavePoint(1, '2024-01-05', 110, 1200, is_peak=True),
            WavePoint(2, '2024-01-10', 105, 1100, is_trough=True),
            WavePoint(3, '2024-01-15', 125, 1300, is_peak=True),
            WavePoint(4, '2024-01-20', 108, 1150, is_trough=True),   # 跌破浪1高点
            WavePoint(5, '2024-01-25', 135, 1400, is_peak=True),
        ]
        
        valid, errors, score = validate_impulse(points)
        
        self.assertFalse(valid)
        self.assertIn('浪4', errors[0])
    
    def test_insufficient_points(self):
        """测试点数不足"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_trough=True),
            WavePoint(1, '2024-01-05', 110, 1200, is_peak=True),
            WavePoint(2, '2024-01-10', 105, 1100, is_trough=True),
        ]
        
        valid, errors, score = validate_impulse(points)
        
        self.assertFalse(valid)
        self.assertIn('6个点', errors[0])


class TestValidateZigzag(unittest.TestCase):
    """测试Zigzag调整浪验证"""

    def test_valid_zigzag(self):
        """测试有效的Zigzag"""
        # A-B-C结构，C浪超过A浪底部
        points = [
            WavePoint(0, '2024-01-01', 120, 1000, is_peak=True),     # 起点
            WavePoint(1, '2024-01-05', 100, 1200, is_trough=True),   # A
            WavePoint(2, '2024-01-10', 110, 1100, is_peak=True),     # B (50%回撤)
            WavePoint(3, '2024-01-15', 90, 1300, is_trough=True),    # C (超过A)
        ]
        
        valid, errors, score = validate_zigzag(points)
        
        self.assertTrue(valid)
        self.assertGreater(score, 0.6)
    
    def test_b_wave_deep_retracement(self):
        """测试B浪深度回撤"""
        points = [
            WavePoint(0, '2024-01-01', 120, 1000, is_peak=True),
            WavePoint(1, '2024-01-05', 100, 1200, is_trough=True),   # A
            WavePoint(2, '2024-01-10', 118, 1100, is_peak=True),     # B (90%回撤)
            WavePoint(3, '2024-01-15', 90, 1300, is_trough=True),    # C
        ]
        
        valid, errors, score = validate_zigzag(points)
        
        # B浪回撤过深，可能是Flat而不是Zigzag
        self.assertLess(score, 0.5)


class TestValidateFlat(unittest.TestCase):
    """测试Flat调整浪验证"""

    def test_valid_flat(self):
        """测试有效的Flat"""
        # A-B-C，B浪超过A浪起点
        points = [
            WavePoint(0, '2024-01-01', 120, 1000, is_peak=True),     # 起点
            WavePoint(1, '2024-01-05', 100, 1200, is_trough=True),   # A
            WavePoint(2, '2024-01-10', 125, 1100, is_peak=True),     # B (超过起点)
            WavePoint(3, '2024-01-15', 95, 1300, is_trough=True),    # C
        ]
        
        valid, errors, score = validate_flat(points)
        
        self.assertTrue(valid)
        self.assertGreater(score, 0.6)


class TestElliottWaveAnalyzer(unittest.TestCase):
    """测试ElliottWaveAnalyzer类"""

    def setUp(self):
        self.analyzer = ElliottWaveAnalyzer()
    
    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.analyzer.min_swing_pct, 0.03)
        self.assertEqual(self.analyzer.max_swing_pct, 0.30)
        self.assertEqual(self.analyzer.confidence_threshold, 0.6)
    
    def test_custom_initialization(self):
        """测试自定义参数初始化"""
        custom = ElliottWaveAnalyzer(
            min_swing_pct=0.05,
            max_swing_pct=0.25,
            confidence_threshold=0.7
        )
        
        self.assertEqual(custom.min_swing_pct, 0.05)
        self.assertEqual(custom.max_swing_pct, 0.25)
        self.assertEqual(custom.confidence_threshold, 0.7)
    
    def test_detect_pivots(self):
        """测试极值点检测"""
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=20, freq='D')
        prices = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
                  105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
        
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 1 for p in prices],
            'low': [p - 1 for p in prices],
            'close': prices,
            'volume': [1000] * 20
        })
        
        pivots = self.analyzer._detect_pivots(df)
        
        # 应该检测到一些极值点
        self.assertIsInstance(pivots, list)
        if len(pivots) > 0:
            self.assertIsInstance(pivots[0], WavePoint)
    
    def test_detect_wave_pattern_with_insufficient_data(self):
        """测试数据不足时的处理"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        prices = [100, 101, 102, 103, 104]
        
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p + 1 for p in prices],
            'low': [p - 1 for p in prices],
            'close': prices,
            'volume': [1000] * 5
        })
        
        pattern = self.analyzer.detect_wave_pattern(df)
        
        # 数据不足，可能返回None或unknown类型
        self.assertTrue(
            pattern is None or 
            (hasattr(pattern, 'wave_type') and pattern.wave_type == WaveType.UNKNOWN)
        )
    
    def test_try_impulse(self):
        """测试推动浪检测"""
        # 创建6个点推动浪
        points = [
            WavePoint(0, '2024-01-01', 100, 1000, is_trough=True),
            WavePoint(1, '2024-01-05', 110, 1200, is_peak=True),
            WavePoint(2, '2024-01-10', 105, 1100, is_trough=True),
            WavePoint(3, '2024-01-15', 125, 1300, is_peak=True),
            WavePoint(4, '2024-01-20', 118, 1150, is_trough=True),
            WavePoint(5, '2024-01-25', 135, 1400, is_peak=True),
        ]
        
        pattern = self.analyzer._try_impulse(points)
        
        if pattern is not None:
            self.assertEqual(pattern.wave_type, WaveType.IMPULSE)
            self.assertEqual(len(pattern.points), 6)
            self.assertIsNotNone(pattern.target_price)
            self.assertIsNotNone(pattern.stop_loss)


class TestWavePattern(unittest.TestCase):
    """测试WavePattern数据类"""

    def test_pattern_creation(self):
        """测试模式创建"""
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 110, 1200),
        ]
        
        pattern = WavePattern(
            wave_type=WaveType.IMPULSE,
            direction=WaveDirection.UP,
            points=points,
            confidence=0.85,
            start_date='2024-01-01',
            end_date='2024-01-05',
            target_price=120.0,
            stop_loss=95.0
        )
        
        self.assertEqual(pattern.wave_type, WaveType.IMPULSE)
        self.assertEqual(pattern.direction, WaveDirection.UP)
        self.assertEqual(pattern.confidence, 0.85)
        self.assertEqual(pattern.target_price, 120.0)
        self.assertEqual(pattern.stop_loss, 95.0)


if __name__ == '__main__':
    unittest.main()
