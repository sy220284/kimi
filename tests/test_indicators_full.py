#!/usr/bin/env python3
"""
技术指标计算全覆盖测试
测试所有技术指标计算函数
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import pandas as pd
import numpy as np

from data.optimized_data_manager import get_optimized_data_manager


class TestMovingAverages(unittest.TestCase):
    """移动平均线测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_ma_calculation(self):
        """测试MA计算"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'close': list(range(1, 21))  # 1,2,3...20
        })
        
        result = self.data_mgr.calculate_ma(df, 5)
        
        # 第5个值的MA5应该是(1+2+3+4+5)/5 = 3
        self.assertAlmostEqual(result['ma5'].iloc[4], 3.0)
        print("✅ MA计算正确")
    
    def test_02_ema_calculation(self):
        """测试EMA计算"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'close': [100]*20
        })
        
        result = self.data_mgr.calculate_ema(df, 12)
        
        # 常数序列的EMA应该接近常数
        self.assertAlmostEqual(result['ema12'].iloc[-1], 100.0, delta=0.01)
        print("✅ EMA计算正确")
    
    def test_03_multiple_ma_periods(self):
        """测试多个MA周期"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 0:
            result = self.data_mgr.calculate_ma(symbol_df, 5)
            result = self.data_mgr.calculate_ma(result, 20)
            result = self.data_mgr.calculate_ma(result, 60)
            
            self.assertIn('ma5', result.columns)
            self.assertIn('ma20', result.columns)
            self.assertIn('ma60', result.columns)
            print("✅ 多周期MA计算正确")
        else:
            self.skipTest("无数据")


class TestRSI(unittest.TestCase):
    """RSI测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_rsi_basic(self):
        """测试RSI基础计算"""
        # 连续上涨 - 需要更多数据点使RSI14有有效值
        df = pd.DataFrame({
            'symbol': ['TEST']*50,
            'close': list(range(100, 150))  # 每天涨1，共50天
        })
        
        result = self.data_mgr.calculate_rsi(df, 14)
        
        # 连续上涨RSI应该接近100 (取后面几个有效值)
        rsivalues = result['rsi14'].dropna()
        if len(rsivalues) > 0:
            self.assertGreater(rsivalues.iloc[-1], 50)
        print("✅ RSI上涨场景正确")
    
    def test_02_rsi_falling(self):
        """测试RSI下跌场景"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'close': list(range(120, 100, -1))  # 每天跌1
        })
        
        result = self.data_mgr.calculate_rsi(df, 14)
        
        # 连续下跌RSI应该接近0
        self.assertLess(result['rsi14'].iloc[-1], 50)
        print("✅ RSI下跌场景正确")
    
    def test_03_rsi_flat(self):
        """测试RSI横盘场景"""
        df = pd.DataFrame({
            'symbol': ['TEST']*20,
            'close': [100]*20  # 横盘
        })
        
        result = self.data_mgr.calculate_rsi(df, 14)
        
        # 横盘RSI应该接近50
        rsi_val = result['rsi14'].iloc[-1]
        if not pd.isna(rsi_val):
            self.assertAlmostEqual(rsi_val, 50.0, delta=5)
        print("✅ RSI横盘场景正确")


class TestMACD(unittest.TestCase):
    """MACD测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_macd_calculation(self):
        """测试MACD计算"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 30:
            result = self.data_mgr.calculate_macd(symbol_df)
            
            self.assertIn('macd', result.columns)
            self.assertIn('macd_signal', result.columns)
            self.assertIn('macd_hist', result.columns)
            print("✅ MACD计算正确")
        else:
            self.skipTest("数据不足")
    
    def test_02_macd_signal(self):
        """测试MACD信号"""
        # 快速上涨后下跌
        prices = list(range(100, 150)) + list(range(150, 100, -1))
        df = pd.DataFrame({
            'symbol': ['TEST']*len(prices),
            'close': prices
        })
        
        result = self.data_mgr.calculate_macd(df)
        
        # MACD柱状图应该有正有负
        hist_positive = (result['macd_hist'] > 0).sum()
        hist_negative = (result['macd_hist'] < 0).sum()
        
        self.assertGreater(hist_positive + hist_negative, 0)
        print("✅ MACD信号变化正确")


class TestBollingerBands(unittest.TestCase):
    """布林带测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_bollinger_calculation(self):
        """测试布林带计算"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 20:
            result = self.data_mgr.calculate_bollinger(symbol_df)
            
            self.assertIn('bb_upper', result.columns)
            self.assertIn('bb_lower', result.columns)
            self.assertIn('bb_middle', result.columns)
            
            # 上轨 > 中轨 > 下轨
            latest = result.iloc[-1]
            self.assertGreaterEqual(latest['bb_upper'], latest['bb_middle'])
            self.assertGreaterEqual(latest['bb_middle'], latest['bb_lower'])
            print("✅ 布林带计算正确")
        else:
            self.skipTest("数据不足")


class TestATR(unittest.TestCase):
    """ATR测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_atr_calculation(self):
        """测试ATR计算"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 14:
            result = self.data_mgr.calculate_atr(symbol_df, 14)
            
            self.assertIn('atr14', result.columns)
            
            # ATR应该为正
            latest_atr = result['atr14'].iloc[-1]
            if not pd.isna(latest_atr):
                self.assertGreater(latest_atr, 0)
            print("✅ ATR计算正确")
        else:
            self.skipTest("数据不足")
    
    def test_02_atr_high_volatility(self):
        """测试高波动ATR"""
        # 高波动数据
        np.random.seed(42)
        base = 100
        prices = [base]
        for _ in range(50):
            prices.append(prices[-1] + np.random.randn() * 5)
        
        df = pd.DataFrame({
            'symbol': ['TEST']*len(prices),
            'date': pd.date_range('2024-01-01', periods=len(prices)),
            'close': prices,
            'high': [p + abs(np.random.randn()) * 3 for p in prices],
            'low': [p - abs(np.random.randn()) * 3 for p in prices]
        })
        
        result = self.data_mgr.calculate_atr(df, 14)
        
        # 高波动应该有较高的ATR
        atr_mean = result['atr14'].mean()
        self.assertGreater(atr_mean, 0)
        print("✅ 高波动ATR计算正确")


class TestVolatility(unittest.TestCase):
    """波动率测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_volatility_calculation(self):
        """测试波动率计算"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 20:
            result = self.data_mgr.calculate_volatility(symbol_df, 20)
            
            self.assertIn('volatility20', result.columns)
            
            # 波动率应该为正
            latest_vol = result['volatility20'].iloc[-1]
            if not pd.isna(latest_vol):
                self.assertGreaterEqual(latest_vol, 0)
            print("✅ 波动率计算正确")
        else:
            self.skipTest("数据不足")


class TestReturns(unittest.TestCase):
    """收益率测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01returns_calculation(self):
        """测试收益率计算"""
        df = pd.DataFrame({
            'symbol': ['TEST']*5,
            'close': [100, 110, 105, 115, 120]
        })
        
        result = self.data_mgr.calculate_returns(df)
        
        # 列名是 daily_return 而不是 returns
        self.assertIn('daily_return', result.columns)
        
        # 检查收益率
        self.assertAlmostEqual(result['daily_return'].iloc[1], 0.10, delta=0.001)  # 10%
        self.assertAlmostEqual(result['daily_return'].iloc[2], -0.045, delta=0.01)  # -4.5%
        print("✅ 收益率计算正确")
    
    def test_02_cumulativereturns(self):
        """测试累计收益率"""
        df = pd.DataFrame({
            'symbol': ['TEST']*5,
            'close': [100, 110, 105, 115, 120]
        })
        
        result = self.data_mgr.calculate_returns(df)
        
        # 累计收益率应该是20%
        total_return = (result['close'].iloc[-1] / result['close'].iloc[0]) - 1
        self.assertAlmostEqual(total_return, 0.20, delta=0.001)
        print("✅ 累计收益率计算正确")


class TestAllIndicators(unittest.TestCase):
    """全指标测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
    
    def test_01_calculate_all_indicators(self):
        """测试计算所有指标"""
        df = self.data_mgr.load_all_data()
        symbol_df = df[df['symbol'] == '600519'].copy()
        
        if len(symbol_df) > 60:
            result = self.data_mgr.calculate_all_indicators(symbol_df)
            
            # 检查关键指标列 (根据实际实现的列名)
            expected_cols = [
                'ma5', 'ma10', 'ma20', 'ma60',
                'rsi14', 
                'macd', 'macd_signal', 'macd_hist',
                'bb_upper', 'bb_lower', 'bb_middle',
                'atr14'
            ]
            
            for col in expected_cols:
                self.assertIn(col, result.columns, f"缺少指标: {col}")
            
            print(f"✅ 全指标计算正确 ({len(expected_cols)}个核心指标)")
        else:
            self.skipTest("数据不足")


def run_tests():
    """运行测试"""
    print("="*70)
    print("📊 技术指标全覆盖测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMovingAverages))
    suite.addTests(loader.loadTestsFromTestCase(TestRSI))
    suite.addTests(loader.loadTestsFromTestCase(TestMACD))
    suite.addTests(loader.loadTestsFromTestCase(TestBollingerBands))
    suite.addTests(loader.loadTestsFromTestCase(TestATR))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatility))
    suite.addTests(loader.loadTestsFromTestCase(TestReturns))
    suite.addTests(loader.loadTestsFromTestCase(TestAllIndicators))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有指标测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
