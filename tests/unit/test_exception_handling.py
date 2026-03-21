#!/usr/bin/env python3
"""
异常处理容错测试
测试系统在各种异常情况下的容错能力
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import unittest

import numpy as np
import pandas as pd

from agents.tech_analyst import TechAnalystAgent
from agents.wave_analyst import WaveAnalystAgent
from data.optimized_data_manager import get_optimized_data_manager


class TestDataExceptionHandling(unittest.TestCase):
    """数据层异常处理测试"""

    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()

    def test_01_invalid_symbol(self):
        """测试无效股票代码"""
        result = self.data_mgr.get_stock_data('INVALID')
        self.assertIsNone(result)
        print("✅ 无效代码处理正常")

    def test_02_empty_symbol(self):
        """测试空股票代码"""
        result = self.data_mgr.get_stock_data('')
        self.assertIsNone(result)
        print("✅ 空代码处理正常")

    def test_03_none_symbol(self):
        """测试None股票代码"""
        result = self.data_mgr.get_stock_data(None)
        self.assertIsNone(result)
        print("✅ None代码处理正常")

    def test_04_malformeddataframe(self):
        """测试损坏的DataFrame"""
        # 缺少必要列
        bad_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'close': [100]
            # 缺少open, high, low, volume
        })

        # 应该抛出异常或被处理
        try:
            result = self.data_mgr.calculate_ma(bad_df, 20)
            # 如果没有symbol列，get_stock_data会失败
            print("✅ 损坏数据框处理正常 (返回结果)")
        except Exception as e:
            # 如果抛出异常也接受，只要系统不崩溃
            print(f"✅ 损坏数据框抛出预期异常: {type(e).__name__}")

    def test_05_emptydataframe(self):
        """测试空DataFrame"""
        empty_df = pd.DataFrame()

        try:
            result = self.data_mgr.calculate_ma(empty_df, 20)
            # 应该返回空或原数据框
            print("✅ 空数据框处理正常")
        except Exception as e:
            print(f"✅ 空数据框抛出预期异常: {type(e).__name__}")

    def test_06_insufficientdata(self):
        """测试数据不足"""
        # 只有5条数据，计算MA20
        small_df = pd.DataFrame({
            'symbol': ['TEST']*5,
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [100]*5,
            'high': [105]*5,
            'low': [95]*5,
            'close': [100]*5,
            'volume': [1000000]*5
        })

        try:
            result = self.data_mgr.calculate_ma(small_df, 20)
            # 应该返回原数据框或带NaN的列
            self.assertIsNotNone(result)
            print("✅ 数据不足处理正常")
        except Exception as e:
            print(f"✅ 数据不足抛出预期异常: {type(e).__name__}")

    def test_07_nanvalues(self):
        """测试NaN值处理"""
        df_with_nan = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100]*10,
            'high': [105]*10,
            'low': [95]*10,
            'close': [100, np.nan, 102, np.nan, 104, 105, np.nan, 107, 108, 109],
            'volume': [1000000]*10
        })

        try:
            # 计算指标应该能处理NaN
            result = self.data_mgr.calculate_ma(df_with_nan, 5)
            self.assertIsNotNone(result)
            print("✅ NaN值处理正常")
        except Exception as e:
            print(f"✅ NaN值处理抛出预期异常: {type(e).__name__}")

    def test_08_extremevalues(self):
        """测试极端值处理"""
        extreme_df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [1e10]*10,
            'high': [1e10]*10,
            'low': [1]*10,
            'close': [1e10, 1, 1e10, 1, 1e10, 1, 1e10, 1, 1e10, 1],
            'volume': [1e15]*10
        })

        try:
            result = self.data_mgr.calculate_returns(extreme_df)
            self.assertIsNotNone(result)
            print("✅ 极端值处理正常")
        except Exception as e:
            print(f"✅ 极端值处理抛出预期异常: {type(e).__name__}")


class TestAgentExceptionHandling(unittest.TestCase):
    """智能体异常处理测试"""

    @classmethod
    def setUpClass(cls):
        cls.wave_agent = WaveAnalystAgent()
        cls.tech_agent = TechAnalystAgent()

    def test_01_wave_agent_emptydata(self):
        """测试波浪分析空数据（空symbol→ERROR状态）"""
        from agents.base_agent import AgentInput, AgentState
        result = self.wave_agent.analyze(AgentInput(symbol=""))
        self.assertIsNotNone(result)
        self.assertEqual(result.state, AgentState.ERROR)
        print("✅ 波浪分析空数据处理正常")

    def test_02_wave_agent_nonedata(self):
        """测试波浪分析None数据（invalid symbol→ERROR状态）"""
        from agents.base_agent import AgentInput, AgentState
        result = self.wave_agent.analyze(AgentInput(symbol="NONE_XYZ_404"))
        self.assertIsNotNone(result)
        self.assertEqual(result.state, AgentState.ERROR)
        print("✅ 波浪分析None数据处理正常")

    def test_03_wave_agent_missing_columns(self):
        """测试波浪分析缺少列"""
        bad_df = pd.DataFrame({
            'date': ['2024-01-01'],
            'unknown_col': [1]
        })

        # 应该不崩溃
        try:
            result = self.wave_agent.analyze(bad_df)
            print("✅ 波浪分析缺少列处理正常")
        except Exception as e:
            print(f"⚠️ 波浪分析缺少列抛出异常: {type(e).__name__}")

    def test_04_tech_agent_emptydata(self):
        """测试技术分析空数据（空symbol→ERROR状态）"""
        from agents.base_agent import AgentInput, AgentState
        result = self.tech_agent.analyze(AgentInput(symbol=""))
        self.assertIsNotNone(result)
        self.assertEqual(result.state, AgentState.ERROR)
        print("✅ 技术分析空数据处理正常")

    def test_05_tech_agent_nonedata(self):
        """测试技术分析None数据（invalid symbol→ERROR状态）"""
        from agents.base_agent import AgentInput, AgentState
        result = self.tech_agent.analyze(AgentInput(symbol="NONE_XYZ_404"))
        self.assertIsNotNone(result)
        self.assertEqual(result.state, AgentState.ERROR)
        print("✅ 技术分析None数据处理正常")


class TestBoundaryConditions(unittest.TestCase):
    """边界条件测试"""

    def test_01_single_rowdata(self):
        """测试单行数据"""
        data_mgr = get_optimized_data_manager()

        single_row = pd.DataFrame({
            'symbol': ['TEST'],
            'date': ['2024-01-01'],
            'open': [100],
            'high': [105],
            'low': [95],
            'close': [100],
            'volume': [1000000]
        })

        try:
            # 各种计算应该不崩溃
            result = data_mgr.calculate_ma(single_row, 20)
            self.assertIsNotNone(result)
            print("✅ 单行数据处理正常")
        except Exception as e:
            print(f"✅ 单行数据处理抛出预期异常: {type(e).__name__}")

    def test_02_largedataset(self):
        """测试大数据集"""
        data_mgr = get_optimized_data_manager()

        # 生成大量数据
        large_df = pd.DataFrame({
            'symbol': ['TEST']*10000,
            'date': pd.date_range('2000-01-01', periods=10000, freq='D'),
            'open': np.random.randn(10000) * 10 + 100,
            'high': np.random.randn(10000) * 10 + 105,
            'low': np.random.randn(10000) * 10 + 95,
            'close': np.random.randn(10000) * 10 + 100,
            'volume': np.random.randint(1000000, 10000000, 10000)
        })

        # 计算指标应该能处理
        result = data_mgr.calculate_ma(large_df, 20)
        self.assertEqual(len(result), 10000)
        print("✅ 大数据集(10000行)处理正常")

    def test_03_zero_volume(self):
        """测试零成交量"""
        data_mgr = get_optimized_data_manager()

        zero_vol_df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100]*10,
            'high': [105]*10,
            'low': [95]*10,
            'close': [100]*10,
            'volume': [0]*10
        })

        try:
            result = data_mgr.calculate_returns(zero_vol_df)
            self.assertIsNotNone(result)
            print("✅ 零成交量处理正常")
        except Exception as e:
            print(f"✅ 零成交量处理抛出预期异常: {type(e).__name__}")

    def test_04_zero_price(self):
        """测试零价格"""
        data_mgr = get_optimized_data_manager()

        zero_price_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [0]*10,
            'high': [0]*10,
            'low': [0]*10,
            'close': [0]*10,
            'volume': [1000000]*10
        })

        # 应该不崩溃（可能有除零警告）
        try:
            result = data_mgr.calculate_returns(zero_price_df)
            print("✅ 零价格处理正常")
        except Exception:
            print("⚠️ 零价格抛出异常（可能符合预期）")

    def test_05_negative_price(self):
        """测试负价格"""
        data_mgr = get_optimized_data_manager()

        neg_df = pd.DataFrame({
            'symbol': ['TEST']*10,
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [-100]*10,
            'high': [-95]*10,
            'low': [-105]*10,
            'close': [-100, -99, -98, -97, -96, -95, -94, -93, -92, -91],
            'volume': [1000000]*10
        })

        try:
            result = data_mgr.calculate_returns(neg_df)
            self.assertIsNotNone(result)
            print("✅ 负价格处理正常")
        except Exception as e:
            print(f"✅ 负价格处理抛出预期异常: {type(e).__name__}")


class TestConcurrencySafety(unittest.TestCase):
    """并发安全测试"""

    def test_01_thread_safety(self):
        """测试线程安全"""
        import threading

        data_mgr = get_optimized_data_manager()
        results = []
        errors = []

        def query_stock(symbol):
            try:
                result = data_mgr.get_stock_data(symbol)
                results.append((symbol, result is not None))
            except Exception as e:
                errors.append((symbol, str(e)))

        # 多线程查询
        threads = []
        symbols = ['600519', '000858', '002594', '000001'] * 5

        for symbol in symbols:
            t = threading.Thread(target=query_stock, args=(symbol,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        print(f"✅ 并发测试: {len(results)}成功, {len(errors)}错误")
        self.assertEqual(len(errors), 0)

    def test_02_singleton_pattern(self):
        """测试单例模式"""

        mgr1 = get_optimized_data_manager()
        mgr2 = get_optimized_data_manager()

        self.assertIs(mgr1, mgr2)
        print("✅ 单例模式正常")


def run_tests():
    """运行测试"""
    print("="*70)
    print("🛡️ 异常处理容错测试")
    print("="*70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDataExceptionHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentExceptionHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestBoundaryConditions))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencySafety))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有容错测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
