"""
波浪算法单元测试 — 匹配实际 API 签名
"""
import sys, unittest
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analysis.wave.elliott_wave import (
    ElliottWaveAnalyzer, WavePoint, WavePattern, WaveType, WaveDirection,
    validate_impulse_rules as validate_impulse,
    validate_zigzag, validate_flat, validate_triangle,
    calculate_atr, zigzag_atr,
)

def mkp(i, price, is_peak=False, is_trough=False):
    return WavePoint(i, f'2024-01-{i+1:02d}', float(price),
                     is_peak=is_peak, is_trough=is_trough)


class TestWavePoint(unittest.TestCase):
    def test_creation(self):
        p = WavePoint(0, '2024-01-01', 100.0, is_peak=True)
        self.assertEqual(p.index, 0); self.assertEqual(p.price, 100.0)
        self.assertTrue(p.is_peak); self.assertIsNone(p.wave_num)

    def test_wave_num_settable(self):
        p = WavePoint(0, '2024-01-01', 100.0)
        p.wave_num = '3'; self.assertEqual(p.wave_num, '3')


class TestValidateImpulse(unittest.TestCase):
    """validate_impulse_rules 返回 (valid, errors, score, fib_dict)"""

    def test_valid_impulse(self):
        pts = [mkp(0,100,is_trough=True), mkp(5,120,is_peak=True),
               mkp(8,108,is_trough=True), mkp(15,145,is_peak=True),
               mkp(20,132,is_trough=True), mkp(28,168,is_peak=True)]
        result = validate_impulse(pts)
        v, errors, score = result[0], result[1], result[2]
        self.assertTrue(v); self.assertGreater(score, 0.5)

    def test_wave4_breaks_wave1(self):
        pts = [mkp(0,100,is_trough=True), mkp(5,120,is_peak=True),
               mkp(8,105,is_trough=True), mkp(15,140,is_peak=True),
               mkp(18,115,is_trough=True), mkp(25,155,is_peak=True)]
        result = validate_impulse(pts)
        self.assertFalse(result[0])

    def test_insufficient_points(self):
        result = validate_impulse([mkp(0,100), mkp(5,110), mkp(8,105)])
        self.assertFalse(result[0])

    def test_wave3_not_longest_lower_score(self):
        # 浪5比浪3长 → 得分低
        pts = [mkp(0,100,is_trough=True), mkp(5,110,is_peak=True),
               mkp(8,105,is_trough=True), mkp(15,112,is_peak=True),
               mkp(18,108,is_trough=True), mkp(25,125,is_peak=True)]
        result = validate_impulse(pts)
        self.assertLessEqual(result[2], 0.85)


class TestValidateZigzag(unittest.TestCase):
    def test_valid_deep(self):
        pts = [mkp(0,100), mkp(5,72), mkp(10,88), mkp(15,58)]
        v, _, s = validate_zigzag(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.8)

    def test_valid_shallow(self):
        pts = [mkp(0,100), mkp(5,84), mkp(10,94), mkp(15,72)]
        v, _, _ = validate_zigzag(pts); self.assertTrue(v)

    def test_too_few_points(self):
        v, _, _ = validate_zigzag([mkp(0,100), mkp(5,80)]); self.assertFalse(v)

    def test_bearish_zigzag(self):
        pts = [mkp(0,100), mkp(5,118), mkp(10,105), mkp(15,128)]
        v, _, _ = validate_zigzag(pts); self.assertTrue(v)


class TestValidateFlat(unittest.TestCase):
    def test_expanded_flat(self):
        pts = [mkp(0,100), mkp(5,82), mkp(10,108), mkp(15,72)]
        v, _, s = validate_flat(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.70)

    def test_regular_flat(self):
        pts = [mkp(0,100), mkp(5,82), mkp(10,99), mkp(15,78)]
        v, _, _ = validate_flat(pts); self.assertTrue(v)

    def test_running_flat(self):
        pts = [mkp(0,100), mkp(5,88), mkp(10,102), mkp(15,92)]
        v, _, _ = validate_flat(pts); self.assertTrue(v)


class TestValidateTriangle(unittest.TestCase):
    def test_symmetric_convergence(self):
        pts = [mkp(0,100), mkp(5,85), mkp(10,95), mkp(15,87), mkp(20,93)]
        v, _, s = validate_triangle(pts)
        self.assertTrue(v); self.assertGreaterEqual(s, 0.9)

    def test_fibonacci_ideal(self):
        pts = [mkp(0,100), mkp(5,86), mkp(10,97), mkp(15,89), mkp(20,95)]
        v, _, s = validate_triangle(pts)
        self.assertTrue(v); self.assertGreater(s, 0.7)

    def test_not_enough(self):
        v, _, _ = validate_triangle([mkp(0,100), mkp(5,85), mkp(10,95)]); self.assertFalse(v)


class TestElliottWaveAnalyzer(unittest.TestCase):
    def setUp(self):
        self.ea = ElliottWaveAnalyzer()

    def test_initialization_defaults(self):
        self.assertGreater(self.ea.confidence_threshold, 0)
        self.assertGreater(self.ea.atr_mult, 0)

    def test_custom_init(self):
        ea2 = ElliottWaveAnalyzer(confidence_threshold=0.7, atr_mult=0.6)
        self.assertEqual(ea2.confidence_threshold, 0.7)
        self.assertEqual(ea2.atr_mult, 0.6)

    def test_detect_pivots(self):
        np.random.seed(0)
        n=50; p=100+np.cumsum(np.random.randn(n)*2)
        df = pd.DataFrame({'date':pd.date_range('2024-01-01',periods=n).strftime('%Y-%m-%d'),
            'open':p,'high':p+1,'low':p-1,'close':p,'volume':np.ones(n)*1e6})
        pivots = self.ea._detect_pivots(df)
        self.assertIsInstance(pivots, list)

    def test_detect_wave_pattern_short_data(self):
        df = pd.DataFrame({'date':['2024-01-0%d'%i for i in range(1,6)],
            'open':[100]*5,'high':[101]*5,'low':[99]*5,'close':[100]*5,'volume':[1e6]*5})
        result = self.ea.detect_wave_pattern(df)
        self.assertTrue(result is None or hasattr(result, 'wave_type'))

    def test_try_impulse(self):
        pts = [mkp(0,100,is_trough=True), mkp(5,120,is_peak=True),
               mkp(8,108,is_trough=True), mkp(15,145,is_peak=True),
               mkp(20,132,is_trough=True), mkp(28,168,is_peak=True)]
        pat = self.ea._try_impulse(pts)
        if pat:
            self.assertEqual(pat.wave_type, WaveType.IMPULSE)
            self.assertIsNotNone(pat.target_price)

    def test_try_diagonal(self):
        pts = [mkp(0,100), mkp(5,116), mkp(10,107), mkp(15,119), mkp(20,111)]
        pat = self.ea._try_diagonal(pts)
        if pat:
            self.assertIn(pat.wave_type, [WaveType.ENDING_DIAGONAL, WaveType.LEADING_DIAGONAL])


class TestWavePattern(unittest.TestCase):
    def test_pattern_creation(self):
        pts = [WavePoint(0,'2024-01-01',100.0), WavePoint(1,'2024-01-05',110.0)]
        p = WavePattern(wave_type=WaveType.IMPULSE, direction=WaveDirection.UP,
                        points=pts, confidence=0.85, start_date='2024-01-01',
                        end_date='2024-01-05', target_price=120.0, stop_loss=95.0)
        self.assertEqual(p.wave_type, WaveType.IMPULSE)
        self.assertEqual(p.confidence, 0.85)
        self.assertEqual(p.target_price, 120.0)


class TestZigZagUtils(unittest.TestCase):
    def setUp(self):
        np.random.seed(42); n=200
        t=np.arange(n); p=100*np.exp(0.0003*t+0.012*np.cumsum(np.random.randn(n)))
        self.h=p*(1+0.005); self.l=p*(1-0.005); self.c=p

    def test_calculate_atr(self):
        atr = calculate_atr(self.h, self.l, self.c, 14)
        self.assertEqual(len(atr), len(self.c))
        self.assertGreater(float(atr[-1]), 0)

    def test_zigzag_returns_pivots(self):
        atr = calculate_atr(self.h, self.l, self.c, 10)
        idxs, prices, types = zigzag_atr(self.h, self.l, self.c, atr, 0.4, 3)
        self.assertGreater(len(idxs), 5)
        self.assertEqual(len(idxs), len(prices))
        self.assertEqual(len(idxs), len(types))

    def test_zigzag_fewer_pivots_with_larger_mult(self):
        atr = calculate_atr(self.h, self.l, self.c, 10)
        n_small = len(zigzag_atr(self.h,self.l,self.c,atr,0.3,3)[0])
        n_large = len(zigzag_atr(self.h,self.l,self.c,atr,1.0,3)[0])
        self.assertGreaterEqual(n_small, n_large)


if __name__ == '__main__':
    unittest.main(verbosity=2)
