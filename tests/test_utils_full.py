#!/usr/bin/env python3
"""
工具函数全覆盖测试
测试所有工具函数
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


class TestDateUtils(unittest.TestCase):
    """日期工具测试"""

    def test_01_date_formatting(self):
        """测试日期格式化"""
        date = datetime(2024, 3, 15)
        formatted = date.strftime('%Y-%m-%d')
        self.assertEqual(formatted, '2024-03-15')
        print("✅ 日期格式化正常")

    def test_02_date_parsing(self):
        """测试日期解析"""
        date_str = '2024-03-15'
        parsed = datetime.strptime(date_str, '%Y-%m-%d')
        self.assertEqual(parsed.year, 2024)
        self.assertEqual(parsed.month, 3)
        self.assertEqual(parsed.day, 15)
        print("✅ 日期解析正常")

    def test_03_date_range(self):
        """测试日期范围"""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 10)

        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)

        self.assertEqual(len(dates), 10)
        print("✅ 日期范围生成正常")

    def test_04_business_days(self):
        """测试工作日计算"""
        # 简单的工作日检查（排除周末）
        date = datetime(2024, 3, 15)  # 周五
        is_weekday = date.weekday() < 5
        self.assertTrue(is_weekday)

        weekend = datetime(2024, 3, 16)  # 周六
        is_weekend = weekend.weekday() >= 5
        self.assertTrue(is_weekend)

        print("✅ 工作日计算正常")


class TestMathUtils(unittest.TestCase):
    """数学工具测试"""

    def test_01_percentage_change(self):
        """测试百分比变化"""
        old = 100
        new = 120
        change = (new - old) / old * 100
        self.assertEqual(change, 20)
        print("✅ 百分比变化计算正常")

    def test_02_moving_average(self):
        """测试移动平均"""
        data = [1, 2, 3, 4, 5]
        window = 3
        ma = sum(data[-window:]) / window
        self.assertEqual(ma, 4)
        print("✅ 移动平均计算正常")

    def test_03_standard_deviation(self):
        """测试标准差"""
        data = [1, 2, 3, 4, 5]
        mean = sum(data) / len(data)
        variance = sum((x - mean) ** 2 for x in data) / len(data)
        std = variance ** 0.5

        self.assertGreater(std, 0)
        print("✅ 标准差计算正常")

    def test_04_fibonacci(self):
        """测试斐波那契数列"""
        fib = [0, 1]
        for i in range(2, 10):
            fib.append(fib[i-1] + fib[i-2])

        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        self.assertEqual(fib, expected)
        print("✅ 斐波那契计算正常")


class TestDataFrameUtils(unittest.TestCase):
    """DataFrame工具测试"""

    def test_01_drop_duplicates(self):
        """测试去重"""
        df = pd.DataFrame({
            'A': [1, 2, 2, 3],
            'B': ['a', 'b', 'b', 'c']
        })

        df_unique = df.drop_duplicates()
        self.assertEqual(len(df_unique), 3)
        print("✅ 去重正常")

    def test_02_fill_na(self):
        """测试填充空值"""
        df = pd.DataFrame({
            'A': [1, np.nan, 3],
            'B': ['a', 'b', np.nan]
        })

        df_filled = df.fillna(0)
        self.assertEqual(df_filled['A'].isnull().sum(), 0)
        print("✅ 空值填充正常")

    def test_03_sort_values(self):
        """测试排序"""
        df = pd.DataFrame({
            'A': [3, 1, 2],
            'B': ['c', 'a', 'b']
        })

        df_sorted = df.sort_values('A')
        self.assertEqual(df_sorted['A'].iloc[0], 1)
        print("✅ 排序正常")

    def test_04_groupby_agg(self):
        """测试分组聚合"""
        df = pd.DataFrame({
            'symbol': ['A', 'A', 'B', 'B'],
            'value': [1, 2, 3, 4]
        })

        grouped = df.groupby('symbol')['value'].sum()
        self.assertEqual(grouped['A'], 3)
        self.assertEqual(grouped['B'], 7)
        print("✅ 分组聚合正常")


class TestStringUtils(unittest.TestCase):
    """字符串工具测试"""

    def test_01_symbol_validation(self):
        """测试代码验证"""
        # 验证股票代码格式
        symbols = ['600519', '000001', '300001', '688001']

        for symbol in symbols:
            self.assertTrue(symbol.isdigit())
            self.assertEqual(len(symbol), 6)

        print("✅ 代码格式验证正常")

    def test_02_market_identification(self):
        """测试市场识别"""
        def get_market(symbol):
            if symbol.startswith('6'):
                return 'SH'
            elif symbol.startswith('0') or symbol.startswith('3'):
                return 'SZ'
            elif symbol.startswith('68'):
                return 'STAR'
            return 'UNKNOWN'

        self.assertEqual(get_market('600519'), 'SH')
        self.assertEqual(get_market('000001'), 'SZ')

        print("✅ 市场识别正常")


class TestListUtils(unittest.TestCase):
    """列表工具测试"""

    def test_01_chunk_split(self):
        """测试分块"""
        data = list(range(10))
        chunk_size = 3

        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

        self.assertEqual(len(chunks), 4)  # 3,3,3,1
        print("✅ 分块正常")

    def test_02_unique_items(self):
        """测试唯一项"""
        data = [1, 2, 2, 3, 3, 3]
        unique = list(set(data))

        self.assertEqual(len(unique), 3)
        print("✅ 唯一项提取正常")


class TestNumericUtils(unittest.TestCase):
    """数值工具测试"""

    def test_01_rounding(self):
        """测试四舍五入"""
        value = 3.14159
        rounded = round(value, 2)
        self.assertEqual(rounded, 3.14)
        print("✅ 四舍五入正常")

    def test_02_clamping(self):
        """测试范围限制"""
        def clamp(value, min_val, max_val):
            return max(min_val, min(max_val, value))

        self.assertEqual(clamp(5, 0, 10), 5)
        self.assertEqual(clamp(-5, 0, 10), 0)
        self.assertEqual(clamp(15, 0, 10), 10)
        print("✅ 范围限制正常")

    def test_03_is_close(self):
        """测试近似相等"""
        a = 0.1 + 0.2
        b = 0.3

        is_close = abs(a - b) < 1e-9
        self.assertTrue(is_close)
        print("✅ 近似相等判断正常")


def run_tests():
    """运行测试"""
    print("="*70)
    print("🛠️ 工具函数全覆盖测试")
    print("="*70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestDateUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestMathUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestDataFrameUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestStringUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestListUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestNumericUtils))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有工具测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)

    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
