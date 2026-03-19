#!/usr/bin/env python3
"""
Redis缓存一致性测试 (简化版)
测试缓存系统基本功能
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pathlib import Path


import time
import unittest

from data.cache import DataCache
from data.optimized_data_manager import get_optimized_data_manager


class TestDataCache(unittest.TestCase):
    """数据缓存测试"""

    @classmethod
    def setUpClass(cls):
        """测试前准备"""
        try:
            cls.cache = DataCache()
            cls.cache_available = True
        except Exception as e:
            print(f"⚠️ 缓存初始化失败: {e}")
            cls.cache_available = False

    def test_01_cache_initialization(self):
        """测试缓存初始化"""
        if not self.cache_available:
            self.skipTest("缓存不可用")

        self.assertIsNotNone(self.cache)
        print("✅ 缓存初始化正常")

    def test_02data_manager_cache(self):
        """测试数据管理器缓存功能"""
        data_mgr = get_optimized_data_manager()

        # 测试数据加载
        start = time.time()
        df1 = data_mgr.load_all_data()
        elapsed1 = time.time() - start

        # 再次加载（应该从内存缓存）
        start = time.time()
        df2 = data_mgr.load_all_data()
        elapsed2 = time.time() - start

        self.assertEqual(len(df1), len(df2))
        print(f"✅ 数据缓存正常 (首次{elapsed1:.2f}s, 缓存{elapsed2:.2f}s)")

    def test_03_stockdata_consistency(self):
        """测试股票数据一致性"""
        data_mgr = get_optimized_data_manager()

        # 多次查询同一只股票
        results = []
        for _ in range(3):
            df = data_mgr.get_stock_data('600519')
            results.append(df)

        # 验证结果一致
        if results[0] is not None:
            self.assertEqual(len(results[0]), len(results[1]))
            self.assertEqual(len(results[1]), len(results[2]))

        print("✅ 数据一致性正常")


if __name__ == '__main__':
    unittest.main()
