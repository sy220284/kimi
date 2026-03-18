#!/usr/bin/env python3
"""
性能基准回归测试
测试各模块性能是否达标
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import time

from data.optimized_data_manager import get_optimized_data_manager


class TestPerformanceBenchmark(unittest.TestCase):
    """性能基准测试"""
    
    @classmethod
    def setUpClass(cls):
        """准备测试数据"""
        cls.data_mgr = get_optimized_data_manager()
        cls.data_mgr.load_all_data()
        
        # 获取一些测试股票
        cls.test_symbols = ['600519', '000858', '002594', '000001']
    
    def test_01_single_stock_query_speed(self):
        """测试单股查询速度"""
        symbol = '600519'
        
        times = []
        for _ in range(100):
            start = time.time()
            df = self.data_mgr.get_stock_data(symbol)
            times.append(time.time() - start)
        
        avg_time = sum(times) / len(times) * 1000  # ms
        max_time = max(times) * 1000
        
        print(f"✅ 单股查询: 平均{avg_time:.2f}ms, 最大{max_time:.2f}ms")
        
        # 基准: 单股查询<1ms
        self.assertLess(avg_time, 1.0)
    
    def test_02_batch_stock_query_speed(self):
        """测试批量查询速度"""
        symbols = self.test_symbols * 25  # 100只股票
        
        start = time.time()
        for symbol in symbols:
            self.data_mgr.get_stock_data(symbol)
        elapsed = time.time() - start
        
        avg_time = elapsed / len(symbols) * 1000
        
        print(f"✅ 批量查询({len(symbols)}只): 总耗时{elapsed*1000:.1f}ms, 平均{avg_time:.2f}ms/只")
        
        # 基准: 100只查询<50ms
        self.assertLess(elapsed * 1000, 50)
    
    def test_03_indicator_calculation_speed(self):
        """测试指标计算速度"""
        df = self.data_mgr.get_stock_data('600519')
        self.assertIsNotNone(df)
        
        # MA计算
        start = time.time()
        for _ in range(100):
            _ = self.data_mgr.calculate_ma(df.copy(), 20)
        ma_time = (time.time() - start) / 100 * 1000
        
        # RSI计算
        start = time.time()
        for _ in range(100):
            _ = self.data_mgr.calculate_rsi(df.copy(), 14)
        rsi_time = (time.time() - start) / 100 * 1000
        
        # MACD计算
        start = time.time()
        for _ in range(50):
            _ = self.data_mgr.calculate_macd(df.copy())
        macd_time = (time.time() - start) / 50 * 1000
        
        print(f"✅ 指标计算: MA20={ma_time:.2f}ms, RSI14={rsi_time:.2f}ms, MACD={macd_time:.2f}ms")
        
        # 基准
        self.assertLess(ma_time, 5)
        self.assertLess(rsi_time, 10)
        self.assertLess(macd_time, 50)
    
    def test_04_batch_indicator_calculation(self):
        """测试批量指标计算"""
        symbols = self.test_symbols * 10  # 40只
        
        start = time.time()
        for symbol in symbols:
            df = self.data_mgr.get_stock_data(symbol)
            if df is not None:
                df = self.data_mgr.calculate_ma(df, 20)
                df = self.data_mgr.calculate_rsi(df, 14)
        elapsed = time.time() - start
        
        print(f"✅ 批量指标计算({len(symbols)}只): 总耗时{elapsed*1000:.1f}ms")
        
        # 基准: 40只股票计算指标<2秒
        self.assertLess(elapsed, 2)
    
    def test_05_full_table_load_speed(self):
        """测试全表加载速度"""
        # 创建新实例测试加载
        start = time.time()
        mgr = get_optimized_data_manager()
        df = mgr.load_all_data()
        load_time = time.time() - start
        
        rows = len(df)
        symbols = df['symbol'].nunique()
        
        print(f"✅ 全表加载: {rows:,}条记录, {symbols}只股票, {load_time:.2f}秒")
        
        # 基准: 100万条数据<15秒
        self.assertLess(load_time, 15)
        self.assertGreater(rows, 500000)
    
    def test_06_memory_usage(self):
        """测试内存使用"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # 加载前内存
            mem_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # 重新加载数据
            mgr = get_optimized_data_manager()
            _ = mgr.load_all_data()
            
            # 加载后内存
            mem_after = process.memory_info().rss / 1024 / 1024
            mem_used = mem_after - mem_before
            
            print(f"✅ 内存使用: 加载前{mem_before:.0f}MB, 加载后{mem_after:.0f}MB, 增量{mem_used:.0f}MB")
            
            # 基准: 100万条数据<1GB内存
            self.assertLess(mem_used, 1000)
        except ImportError:
            print("⚠️  跳过内存测试 (psutil未安装)")
            self.skipTest("psutil未安装")
    
    def test_07dataframe_operations(self):
        """测试DataFrame操作性能"""
        df = self.data_mgr.load_all_data()
        
        # groupby操作
        start = time.time()
        grouped = df.groupby('symbol')['close'].mean()
        groupby_time = (time.time() - start) * 1000
        
        # 筛选操作
        start = time.time()
        filtered = df[df['close'] > df['open']]
        filter_time = (time.time() - start) * 1000
        
        # 排序操作
        start = time.time()
        _sorteddf = df.sort_values(['symbol', 'date'])
        sort_time = (time.time() - start) * 1000
        
        print(f"✅ DataFrame操作: groupby={groupby_time:.1f}ms, filter={filter_time:.1f}ms, sort={sort_time:.1f}ms")
        
        # 基准
        self.assertLess(groupby_time, 1000)
        self.assertLess(filter_time, 500)
        self.assertLess(sort_time, 3000)


class TestPerformanceRegression(unittest.TestCase):
    """性能回归测试"""
    
    def test_query_regression(self):
        """测试查询性能是否退化"""
        data_mgr = get_optimized_data_manager()
        
        # 基准时间
        baseline_time = 0.05  # 50ms for 100 queries
        
        start = time.time()
        for _ in range(100):
            data_mgr.get_stock_data('600519')
        actual_time = time.time() - start
        
        # 允许20%的性能波动
        self.assertLess(actual_time, baseline_time * 1.2, 
                       f"查询性能退化: 期望<{baseline_time*1.2*1000:.0f}ms, 实际{actual_time*1000:.0f}ms")
    
    def test_calculation_regression(self):
        """测试计算性能是否退化"""
        data_mgr = get_optimized_data_manager()
        df = data_mgr.get_stock_data('600519')
        
        if df is None:
            self.skipTest("无数据")
        
        baseline_time = 0.005  # 5ms for MA calculation
        
        start = time.time()
        for _ in range(100):
            _ = data_mgr.calculate_ma(df.copy(), 20)
        actual_time = (time.time() - start) / 100
        
        self.assertLess(actual_time, baseline_time * 1.2,
                       f"计算性能退化: 期望<{baseline_time*1.2*1000:.0f}ms, 实际{actual_time*1000:.0f}ms")


def run_tests():
    """运行测试"""
    print("="*70)
    print("🚀 性能基准回归测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceBenchmark))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceRegression))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有性能测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
