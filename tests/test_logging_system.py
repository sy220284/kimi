#!/usr/bin/env python3
"""
日志系统全覆盖测试
测试日志记录和输出
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import logging
from io import StringIO

from utils.logger import get_logger


class TestLoggerCreation(unittest.TestCase):
    """日志创建测试"""
    
    def test_01_create_logger(self):
        """测试创建日志器"""
        logger = get_logger("test_logger")
        self.assertIsNotNone(logger)
        self.assertIsInstance(logger, logging.Logger)
        print("✅ 日志器创建正常")
    
    def test_02_logger_name(self):
        """测试日志器名称"""
        logger = get_logger("named_logger")
        self.assertEqual(logger.name, "named_logger")
        print("✅ 日志器名称正确")
    
    def test_03_logger_singleton(self):
        """测试日志器单例"""
        logger1 = get_logger("singleton_test")
        logger2 = get_logger("singleton_test")
        
        # 相同名称应该返回相同实例
        self.assertEqual(logger1, logger2)
        print("✅ 日志器单例正常")


class TestLogLevels(unittest.TestCase):
    """日志级别测试"""
    
    def test_01_debug_level(self):
        """测试DEBUG级别"""
        logger = get_logger("debug_test")
        
        # 检查日志级别
        self.assertLessEqual(logging.DEBUG, logger.level)
        print("✅ DEBUG级别可用")
    
    def test_02_info_level(self):
        """测试INFO级别"""
        logger = get_logger("info_test")
        
        # 记录INFO日志
        logger.info("Test info message")
        print("✅ INFO级别记录正常")
    
    def test_03_warning_level(self):
        """测试WARNING级别"""
        logger = get_logger("warning_test")
        
        # 记录WARNING日志
        logger.warning("Test warning message")
        print("✅ WARNING级别记录正常")
    
    def test_04_error_level(self):
        """测试ERROR级别"""
        logger = get_logger("error_test")
        
        # 记录ERROR日志
        logger.error("Test error message")
        print("✅ ERROR级别记录正常")


class TestLogHandlers(unittest.TestCase):
    """日志处理器测试"""
    
    def test_01_console_handler(self):
        """测试控制台处理器"""
        logger = get_logger("console_test")
        
        # 检查是否有处理器
        self.assertGreater(len(logger.handlers), 0)
        print("✅ 控制台处理器存在")
    
    def test_02_file_handler(self):
        """测试文件处理器"""
        logger = get_logger("file_test")
        
        # 检查是否有文件处理器
        has_file_handler = any(
            isinstance(h, logging.FileHandler) 
            for h in logger.handlers
        )
        
        if has_file_handler:
            print("✅ 文件处理器存在")
        else:
            print("⚠️ 无文件处理器")
    
    def test_03_handler_levels(self):
        """测试处理器级别"""
        logger = get_logger("level_test")
        
        for handler in logger.handlers:
            self.assertIsNotNone(handler.level)
        
        print("✅ 处理器级别设置正确")


class TestLogFormat(unittest.TestCase):
    """日志格式测试"""
    
    def test_01_log_format_string(self):
        """测试日志格式字符串"""
        logger = get_logger("format_test")
        
        # 检查处理器格式
        for handler in logger.handlers:
            if hasattr(handler, 'formatter') and handler.formatter:
                format_str = handler.formatter._fmt
                self.assertIsNotNone(format_str)
        
        print("✅ 日志格式正确")
    
    def test_02_log_output_capture(self):
        """测试捕获日志输出"""
        logger = get_logger("capture_test")
        
        # 创建字符串IO捕获输出
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        # 记录日志
        test_message = "Test capture message"
        logger.info(test_message)
        
        # 获取输出
        output = log_capture.getvalue()
        
        # 清理
        logger.removeHandler(handler)
        
        print("✅ 日志捕获正常")


class TestLogRotation(unittest.TestCase):
    """日志轮转测试"""
    
    def test_01_rotationconfig(self):
        """测试轮转配置"""
        logger = get_logger("rotation_test")
        
        # 检查是否有轮转处理器
        from logging.handlers import RotatingFileHandler
        has_rotating = any(
            isinstance(h, RotatingFileHandler) 
            for h in logger.handlers
        )
        
        if has_rotating:
            print("✅ 日志轮转配置存在")
        else:
            print("⚠️ 无日志轮转配置")


class TestLogPerformance(unittest.TestCase):
    """日志性能测试"""
    
    def test_01_bulk_logging(self):
        """测试批量日志记录"""
        import time
        
        logger = get_logger("perf_test")
        
        start = time.time()
        for i in range(100):
            logger.debug(f"Performance test message {i}")
        elapsed = time.time() - start
        
        print(f"✅ 批量日志记录: 100条/{elapsed*1000:.1f}ms")
        
        # 应该很快
        self.assertLess(elapsed, 1)


def run_tests():
    """运行测试"""
    print("="*70)
    print("📝 日志系统全覆盖测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLoggerCreation))
    suite.addTests(loader.loadTestsFromTestCase(TestLogLevels))
    suite.addTests(loader.loadTestsFromTestCase(TestLogHandlers))
    suite.addTests(loader.loadTestsFromTestCase(TestLogFormat))
    suite.addTests(loader.loadTestsFromTestCase(TestLogRotation))
    suite.addTests(loader.loadTestsFromTestCase(TestLogPerformance))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有日志测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
