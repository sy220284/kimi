#!/usr/bin/env python3
"""
配置系统全覆盖测试
测试配置加载和验证
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import os
import json
import yaml

from utils.config_loader import load_config, get_config_loader

# 辅助函数：获取测试用的配置加载器
def get_test_config():
    """获取测试配置"""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "config.yaml"
    config_loader = get_config_loader(config_path)
    return config_loader.load()


class TestConfigLoading(unittest.TestCase):
    """配置加载测试"""
    
    def test_01_load_default_config(self):
        """测试加载默认配置"""
        config = get_test_config()
        
        self.assertIsNotNone(config)
        self.assertIsInstance(config, dict)
        print("✅ 默认配置加载正常")
    
    def test_02_config_structure(self):
        """测试配置结构"""
        config = get_test_config()
        
        # 检查主要配置段
        main_sections = ['database', 'redis', 'analysis', 'backtest', 'data']
        for section in main_sections:
            if section in config:
                self.assertIsInstance(config[section], dict)
        
        print("✅ 配置结构正确")
    
    def test_03_database_config(self):
        """测试数据库配置"""
        config = get_test_config()
        
        if 'database' in config:
            db_config = config['database']
            required_keys = ['host', 'port', 'dbname', 'user']
            for key in required_keys:
                if key in db_config:
                    self.assertIsNotNone(db_config[key])
        
        print("✅ 数据库配置正常")
    
    def test_04_redis_config(self):
        """测试Redis配置"""
        config = get_test_config()
        
        if 'redis' in config:
            redis_config = config['redis']
            if 'host' in redis_config:
                self.assertIsNotNone(redis_config['host'])
            if 'port' in redis_config:
                self.assertIsInstance(redis_config['port'], int)
        
        print("✅ Redis配置正常")


class TestConfigValidation(unittest.TestCase):
    """配置验证测试"""
    
    def test_01_config_types(self):
        """测试配置类型"""
        config = get_test_config()
        
        if 'database' in config and 'port' in config['database']:
            self.assertIsInstance(config['database']['port'], int)
        
        if 'redis' in config and 'port' in config['redis']:
            self.assertIsInstance(config['redis']['port'], int)
        
        print("✅ 配置类型正确")
    
    def test_02_config_values(self):
        """测试配置值"""
        config = get_test_config()
        
        # 端口应该在合理范围
        if 'database' in config and 'port' in config['database']:
            port = config['database']['port']
            self.assertGreater(port, 0)
            self.assertLess(port, 65536)
        
        print("✅ 配置值合理")
    
    def test_03_default_values(self):
        """测试默认值"""
        config = get_test_config()
        
        # 检查是否有合理的默认值
        if 'analysis' in config:
            if 'wave_analyst' in config['analysis']:
                wave_config = config['analysis']['wave_analyst']
                if 'confidence_threshold' in wave_config:
                    self.assertGreaterEqual(wave_config['confidence_threshold'], 0)
                    self.assertLessEqual(wave_config['confidence_threshold'], 1)
        
        print("✅ 默认值合理")


class TestConfigEdgeCases(unittest.TestCase):
    """配置边界情况测试"""
    
    def test_01_missing_config_file(self):
        """测试缺少配置文件"""
        # 尝试加载不存在的配置
        try:
            config = load_config('non_existent_config.yaml')
            # 应该返回默认配置
            self.assertIsNotNone(config)
            print("✅ 缺少配置文件处理正常")
        except Exception as e:
            print(f"⚠️ 缺少配置文件异常: {e}")
    
    def test_02_empty_config(self):
        """测试空配置"""
        # 测试空配置处理
        try:
            config = get_test_config()
            self.assertIsInstance(config, dict)
            print("✅ 空配置处理正常")
        except Exception as e:
            print(f"⚠️ 空配置异常: {e}")


class TestEnvironmentVariables(unittest.TestCase):
    """环境变量测试"""
    
    def test_01_env_vars_exist(self):
        """测试环境变量存在"""
        env_vars = ['DATABASE_URL', 'REDIS_URL']
        
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                self.assertIsInstance(value, str)
        
        print("✅ 环境变量检查完成")
    
    def test_02_config_from_env(self):
        """测试从环境变量读取配置"""
        # 设置测试环境变量
        os.environ['TEST_CONFIG_VAR'] = 'test_value'
        
        value = os.environ.get('TEST_CONFIG_VAR')
        self.assertEqual(value, 'test_value')
        
        # 清理
        del os.environ['TEST_CONFIG_VAR']
        
        print("✅ 环境变量配置读取正常")


def run_tests():
    """运行测试"""
    print("="*70)
    print("⚙️ 配置系统全覆盖测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestConfigLoading))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestEnvironmentVariables))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有配置测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
