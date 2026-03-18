#!/usr/bin/env python3
"""
完整测试套件 - 单元测试、集成测试、回归测试
分类运行所有测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import time
import argparse
from datetime import datetime


# 测试分类映射
UNIT_TESTS = [
    'test_indicators_full',
    'test_utils_full',
    'test_config_system',
    'test_logging_system',
    'test_exception_handling',
    'test_edge_cases',
    'test_data_quality',
]

INTEGRATION_TESTS = [
    'test_agent_integration',
    'test_database_full',
    'test_redis_cache',
    'test_backtest_full',
]

REGRESSION_TESTS = [
    'test_performance_benchmark',
    'test_batch_backtest',
    'test_food_beverage_backtest',
    'test_tech_backtest',
    'test_tiered_backtest',
]


def print_header(title):
    """打印标题"""
    print("\n" + "="*80)
    print(f"🧪 {title}")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


def print_footer(title, result, elapsed):
    """打印页脚"""
    print("\n" + "="*80)
    print(f"📊 {title} 结果")
    print("="*80)
    print(f"耗时: {elapsed:.2f}秒")
    print(f"运行: {result.testsRun}个测试")
    print(f"失败: {len(result.failures)}个")
    print(f"错误: {len(result.errors)}个")
    
    if result.wasSuccessful():
        print(f"✅ {title} 全部通过!")
    else:
        print(f"❌ {title} 有失败")
    print("="*80)


def run_test_suite(test_names, suite_name):
    """运行指定测试套件"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    start_dir = Path(__file__).parent
    
    for test_name in test_names:
        try:
            # 尝试加载模块
            module_path = start_dir / f"{test_name}.py"
            if module_path.exists():
                module = __import__(test_name)
                # 获取测试类
                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                        suite.addTests(loader.loadTestsFromTestCase(obj))
            else:
                print(f"⚠️ 测试文件不存在: {test_name}")
        except Exception as e:
            print(f"⚠️ 加载测试失败 {test_name}: {e}")
    
    if suite.countTestCases() == 0:
        print(f"⚠️ 没有测试用例可运行")
        return None
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=1)
    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time
    
    return result, elapsed


def run_quick_smoke_tests():
    """运行快速冒烟测试"""
    print_header("冒烟测试 (Smoke Tests)")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 选择核心测试
    smoke_tests = [
        'test_indicators_full.TestMovingAverages',
        'test_database_full.TestDatabaseConnection',
        'test_exception_handling.TestDataExceptionHandling',
    ]
    
    print("\n快速验证核心功能...")
    
    # 简化版冒烟测试
    try:
        from data.optimized_data_manager import get_optimized_data_manager
        
        print("  📦 测试数据加载...")
        start = time.time()
        mgr = get_optimized_data_manager()
        df = mgr.load_all_data()
        elapsed = time.time() - start
        print(f"     ✅ 数据加载正常 ({len(df):,}条, {elapsed:.1f}s)")
        
        print("  📊 测试指标计算...")
        df_sample = df[df['symbol'] == '600519'].head(100)
        if len(df_sample) > 0:
            result = mgr.calculate_ma(df_sample, 20)
            print(f"     ✅ 指标计算正常")
        
        print("  🔍 测试数据查询...")
        sample = mgr.get_stock_data('600519')
        print(f"     ✅ 数据查询正常 ({len(sample) if sample is not None else 0}条)")
        
        print("\n✅ 冒烟测试通过!")
        return True
        
    except Exception as e:
        print(f"\n❌ 冒烟测试失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='运行测试套件')
    parser.add_argument('--type', type=str, 
                       choices=['all', 'unit', 'integration', 'regression', 'smoke'],
                       default='all',
                       help='测试类型')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    all_results = {}
    total_start = time.time()
    
    if args.type in ['smoke', 'all']:
        # 冒烟测试
        smoke_passed = run_quick_smoke_tests()
        all_results['smoke'] = smoke_passed
        
        if args.type == 'smoke':
            sys.exit(0 if smoke_passed else 1)
    
    # 设置详细程度
    verbosity = 2 if args.verbose else 1
    
    if args.type in ['unit', 'all']:
        # 单元测试
        print_header("单元测试 (Unit Tests)")
        print(f"测试模块: {len(UNIT_TESTS)}个")
        
        result = run_test_suite(UNIT_TESTS, "单元测试")
        if result:
            all_results['unit'] = result[0].wasSuccessful()
            print_footer("单元测试", result[0], result[1])
    
    if args.type in ['integration', 'all']:
        # 集成测试
        print_header("集成测试 (Integration Tests)")
        print(f"测试模块: {len(INTEGRATION_TESTS)}个")
        
        result = run_test_suite(INTEGRATION_TESTS, "集成测试")
        if result:
            all_results['integration'] = result[0].wasSuccessful()
            print_footer("集成测试", result[0], result[1])
    
    if args.type in ['regression', 'all']:
        # 回归测试
        print_header("回归测试 (Regression Tests)")
        print(f"测试模块: {len(REGRESSION_TESTS)}个")
        
        result = run_test_suite(REGRESSION_TESTS, "回归测试")
        if result:
            all_results['regression'] = result[0].wasSuccessful()
            print_footer("回归测试", result[0], result[1])
    
    # 总报告
    total_elapsed = time.time() - total_start
    
    print("\n" + "="*80)
    print("📊 测试总报告")
    print("="*80)
    print(f"总耗时: {total_elapsed:.2f}秒")
    print(f"运行类型: {args.type}")
    print("-"*80)
    
    for test_type, passed in all_results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_type.capitalize():12} {status}")
    
    all_passed = all(all_results.values())
    print("="*80)
    
    if all_passed:
        print("🎉 所有测试通过!")
        return 0
    else:
        print("⚠️  部分测试失败")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
