#!/usr/bin/env python3
"""
完整测试套件运行器
运行所有测试并生成报告
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import time
import unittest


def run_all_tests():
    """运行所有测试"""
    print("="*80)
    print("🧪 完整测试套件")
    print("="*80)

    # 发现所有测试
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')

    # 运行测试
    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    # 生成报告
    print("\n" + "="*80)
    print("📊 测试报告")
    print("="*80)
    print(f"总耗时: {elapsed:.2f}秒")
    print(f"测试运行: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过!")
    else:
        print("\n❌ 有测试失败")

    print("="*80)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
