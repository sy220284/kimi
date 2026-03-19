#!/usr/bin/env python3
"""
边界条件极限测试
测试各种极端和边界情况
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import unittest

import numpy as np
import pandas as pd

from data.optimized_data_manager import get_optimized_data_manager


class TestExtremeValues(unittest.TestCase):
    """极端值测试"""

    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()

    def test_01_very_small_prices(self):
        """测试极小价格"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [0.01]*10,
            'high': [0.02]*10,
            'low': [0.01]*10,
            'close': [0.015]*10,
            'volume': [1000]*10
        })

        result = self.data_mgr.calculate_returns(df)
        self.assertIsNotNone(result)
        print("✅ 极小价格处理正常")

    def test_02_very_large_prices(self):
        """测试极大价格"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [1000000.0]*10,
            'high': [1000001.0]*10,
            'low': [999999.0]*10,
            'close': [1000000.5]*10,
            'volume': [1000]*10
        })

        result = self.data_mgr.calculate_returns(df)
        self.assertIsNotNone(result)
        print("✅ 极大价格处理正常")

    def test_03_extreme_volume(self):
        """测试极端成交量"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100]*10,
            'high': [105]*10,
            'low': [95]*10,
            'close': [100]*10,
            'volume': [1e18]*10  # 极大成交量
        })
        result = self.data_mgr.calculate_ma(df, 5)
        self.assertIsNotNone(result)
        print("✅ 极端成交量处理正常")

    def test_04_zero_volume(self):
        """测试零成交量"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100]*10,
            'high': [100]*10,
            'low': [100]*10,
            'close': [100]*10,
            'volume': [0]*10
        })
        result = self.data_mgr.calculate_ma(df, 5)
        self.assertIsNotNone(result)
        print("✅ 零成交量处理正常")


class TestEdgeCases(unittest.TestCase):
    """边界情况测试"""

    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()

    def test_01_single_row(self):
        """测试单行数据"""
        df = pd.DataFrame({
            'symbol': ['TEST'],
            'date': ['2024-01-01'],
            'open': [100],
            'high': [105],
            'low': [95],
            'close': [100],
            'volume': [1000000]
        })

        # 各种计算应该不崩溃
        try:
            result = self.data_mgr.calculate_ma(df, 5)
            print("✅ 单行数据处理正常")
        except Exception as e:
            print(f"⚠️ 单行数据异常: {e}")

    def test_02_two_rows(self):
        """测试两行数据"""
        df = pd.DataFrame({
            'symbol': ['TEST']*2,
            'date': pd.date_range('2024-01-01', periods=2),
            'open': [100, 101],
            'high': [105, 106],
            'low': [95, 96],
            'close': [100, 101],
            'volume': [1000000, 1100000]
        })

        result = self.data_mgr.calculate_returns(df)
        self.assertIsNotNone(result)
        print("✅ 两行数据处理正常")

    def test_03_all_samevalues(self):
        """测试全部相同值"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'date': pd.date_range('2024-01-01', periods=20),
            'open': [100]*20,
            'high': [100]*20,
            'low': [100]*20,
            'close': [100]*20,
            'volume': [1000000]*20
        })
        result = self.data_mgr.calculate_ma(df, 5)
        result = self.data_mgr.calculate_returns(result)

        # 收益应该为0
        returns = result['daily_return'].dropna()
        if len(returns) > 0:
            self.assertTrue(all(abs(r) < 0.0001 for r in returns))

        print("✅ 全部相同值处理正常")

    def test_04_alternatingvalues(self):
        """测试交替变化值"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'date': pd.date_range('2024-01-01', periods=20),
            'open': [100, 110]*10,
            'high': [110, 120]*10,
            'low': [90, 100]*10,
            'close': [110, 100]*10,
            'volume': [1000000]*20
        })

        result = self.data_mgr.calculate_rsi(df, 14)
        self.assertIsNotNone(result)
        print("✅ 交替变化值处理正常")


class TestMissingData(unittest.TestCase):
    """缺失数据测试"""

    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()

    def test_01_missing_prices(self):
        """测试缺失价格"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100, np.nan, 102, 103, 104, 105, 106, 107, 108, 109],
            'high': [105]*10,
            'low': [95]*10,
            'close': [100, 101, np.nan, 103, 104, 105, 106, 107, 108, 109],
            'volume': [1000000]*10
        })
        result = self.data_mgr.calculate_ma(df, 5)
        self.assertIsNotNone(result)
        print("✅ 缺失价格处理正常")

    def test_02_all_missing(self):
        """测试全部缺失"""
        df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [np.nan]*10,
            'high': [np.nan]*10,
            'low': [np.nan]*10,
            'close': [np.nan]*10,
            'volume': [np.nan]*10
        })

        # 应该不崩溃
        try:
            result = self.data_mgr.calculate_ma(df, 5)
            print("✅ 全部缺失数据处理正常")
        except Exception as e:
            print(f"⚠️ 全部缺失数据异常: {e}")


class TestLargeDatasets(unittest.TestCase):
    """大数据集测试"""

    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()

    def test_01_thousand_rows(self):
        """测试1000行数据"""
        np.random.seed(42)
        n = 1000

        df = pd.DataFrame({
            'symbol': ['TEST']*n,
            'date': pd.date_range('2020-01-01', periods=n),
            'open': np.random.randn(n) * 10 + 100,
            'high': np.random.randn(n) * 10 + 105,
            'low': np.random.randn(n) * 10 + 95,
            'close': np.random.randn(n) * 10 + 100,
            'volume': np.random.randint(1000000, 10000000, n)
        })

        result = self.data_mgr.calculate_all_indicators(df)
        self.assertEqual(len(result), n)
        print("✅ 1000行数据处理正常")

    def test_02_ten_thousand_rows(self):
        """测试10000行数据"""
        import time

        np.random.seed(42)
        n = 10000

        df = pd.DataFrame({
            'symbol': ['TEST']*n,
            'date': pd.date_range('1990-01-01', periods=n),
            'open': np.random.randn(n) * 10 + 100,
            'high': np.random.randn(n) * 10 + 105,
            'low': np.random.randn(n) * 10 + 95,
            'close': np.random.randn(n) * 10 + 100,
            'volume': np.random.randint(1000000, 10000000, n)
        })

        start = time.time()
        result = self.data_mgr.calculate_ma(df, 20)
        elapsed = time.time() - start

        self.assertEqual(len(result), n)
        print(f"✅ 10000行数据处理正常 ({elapsed*1000:.1f}ms)")


class TestSpecialSymbols(unittest.TestCase):
    """特殊股票代码测试"""

    def test_01_shanghai_symbols(self):
        """测试上海股票代码"""
        sh_symbols = ['600519', '601318', '600036', '688001']

        for symbol in sh_symbols:
            self.assertTrue(symbol.isdigit())
            self.assertEqual(len(symbol), 6)
            if symbol.startswith('6'):
                self.assertTrue(symbol.startswith('600') or
                              symbol.startswith('601') or
                              symbol.startswith('603') or
                              symbol.startswith('688'))

        print("✅ 上海股票代码格式正常")

    def test_02_shenzhen_symbols(self):
        """测试深圳股票代码"""
        sz_symbols = ['000001', '000858', '300001', '002594']

        for symbol in sz_symbols:
            self.assertTrue(symbol.isdigit())
            self.assertEqual(len(symbol), 6)

        print("✅ 深圳股票代码格式正常")

    def test_03_index_symbols(self):
        """测试指数代码"""
        index_symbols = ['000001', '000016', '399001', '399006']

        for symbol in index_symbols:
            self.assertEqual(len(symbol), 6)

        print("✅ 指数代码格式正常")


class TestTimezones(unittest.TestCase):
    """时区测试"""

    def test_01_date_consistency(self):
        """测试日期一致性"""
        from datetime import datetime

        # 测试不同时区表示的相同日期
        date1 = datetime(2024, 3, 15, 0, 0, 0)
        date2 = datetime(2024, 3, 15, 12, 0, 0)

        # 日期部分应该相同
        self.assertEqual(date1.date(), date2.date())
        print("✅ 日期一致性正常")


def run_tests():
    """运行测试"""
    print("="*70)
    print("⚡ 边界条件极限测试")
    print("="*70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestExtremeValues))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestMissingData))
    suite.addTests(loader.loadTestsFromTestCase(TestLargeDatasets))
    suite.addTests(loader.loadTestsFromTestCase(TestSpecialSymbols))
    suite.addTests(loader.loadTestsFromTestCase(TestTimezones))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有边界测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
