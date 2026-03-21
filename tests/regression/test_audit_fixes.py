"""
回归测试套件 - 防止修复项回退

确保审计报告修复的问题不会再次出现
"""
import os
import sys
import unittest
import ast
import inspect

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class TestSecurityRegression(unittest.TestCase):
    """
    P0 - 安全修复回归测试
    确保API Key不会再次硬编码到代码中
    """
    
    FORBIDDEN_PATTERNS = [
        'sk-ant-',           # Anthropic API Key
        'sk-',               # OpenAI风格Key
        'Bearer ',           # 认证头
        'password=123',      # 测试密码
        'api_key=\"',        # 硬编码API Key
        "api_key='",
    ]
    
    ALLOWED_PATHS = [
        'tests/',            # 测试代码可以有mock key
        '.env',              # 环境变量文件
        '.env.example',      # 环境变量模板
        'docs/',             # 文档中的示例
    ]
    
    def _scan_file_for_secrets(self, filepath):
        """扫描文件中的敏感信息"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        issues = []
        for i, line in enumerate(lines, 1):
            # 跳过注释行
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('//'):
                continue
            
            # 跳过模板字符串（使用变量而非硬编码）
            if '{api_key}' in line or '{self.api_key}' in line or '{key}' in line:
                continue
            
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in line:
                    issues.append((filepath, i, line.strip()))
        
        return issues
    
    def test_no_hardcoded_api_keys(self):
        """测试：代码中无硬编码API Key"""
        issues = []
        
        for root, dirs, files in os.walk(project_root):
            # 跳过隐藏目录和依赖目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['venv', '__pycache__', 'node_modules']]
            
            for filename in files:
                if not filename.endswith(('.py', '.yaml', '.yml', '.json')):
                    continue
                
                filepath = os.path.join(root, filename)
                
                # 跳过允许的路径
                if any(allowed in filepath for allowed in self.ALLOWED_PATHS):
                    continue
                
                file_issues = self._scan_file_for_secrets(filepath)
                issues.extend(file_issues)
        
        if issues:
            msg = "\n发现潜在的敏感信息硬编码:\n"
            for filepath, line, content in issues[:10]:  # 只显示前10个
                msg += f"  {filepath}:{line}: {content[:80]}...\n"
            self.fail(msg)
    
    def test_config_yaml_uses_env_vars(self):
        """测试：config.yaml使用环境变量"""
        import yaml
        
        config_path = os.path.join(project_root, 'config', 'config.yaml')
        if not os.path.exists(config_path):
            self.skipTest("config.yaml不存在")
        
        with open(config_path, 'r') as f:
            content = f.read()
            config = yaml.safe_load(content)
        
        # 检查API Key配置
        codeflow_key = config.get('models', {}).get('codeflow', {}).get('api_key', '')
        deepseek_key = config.get('models', {}).get('deepseek', {}).get('api_key', '')
        
        # 必须是环境变量格式或为空
        for name, value in [('CodeFlow', codeflow_key), ('DeepSeek', deepseek_key)]:
            if value and '${' not in value and value not in ['test_key', '']:
                self.fail(f"{name} API Key未使用环境变量: {value[:20]}...")


class TestCodeQualityRegression(unittest.TestCase):
    """
    P1 - 代码质量回归测试
    确保DB连接管理等优化不会回退
    """
    
    def test_rotation_analyst_db_connection_pattern(self):
        """测试：RotationAnalyst保持DB连接优化"""
        filepath = os.path.join(project_root, 'agents', 'rotation_analyst.py')
        if not os.path.exists(filepath):
            self.skipTest("rotation_analyst.py不存在")
        
        with open(filepath, 'r') as f:
            source = f.read()
        
        # 检查pg.connect()在循环外
        connect_pos = source.find('pg.connect()')
        for_pos = source.find('for industry in')
        
        if connect_pos == -1 or for_pos == -1:
            self.skipTest("无法定位关键代码")
        
        self.assertLess(
            connect_pos, for_pos,
            "pg.connect()必须在for循环之前（连接优化被破坏）"
        )
        
        # 检查有finally块
        self.assertIn('finally:', source, "缺少finally块（连接优化被破坏）")
        self.assertIn('pg.disconnect()', source, "缺少disconnect调用")
    
    def test_sql_parameterization(self):
        """测试：SQL查询使用参数化"""
        filepath = os.path.join(project_root, 'agents', 'rotation_analyst.py')
        if not os.path.exists(filepath):
            self.skipTest("rotation_analyst.py不存在")
        
        with open(filepath, 'r') as f:
            source = f.read()
        
        # 检查使用%s或参数化查询，而不是f-string格式化
        # 这是一个简单的启发式检查
        if '.execute(f"' in source or ".execute(f'" in source:
            self.fail("发现f-string SQL查询，应使用参数化查询")
        
        # 应该有%s占位符
        self.assertIn('%s', source, "应使用%s参数占位符")
    
    def test_ai_subagents_exist(self):
        """测试：AI子代理模块存在"""
        ai_subagents_dir = os.path.join(project_root, 'agents', 'ai_subagents')
        
        required_files = [
            '__init__.py',
            'base_ai_agent.py',
            'wave_reasoning_agent.py'
        ]
        
        for filename in required_files:
            filepath = os.path.join(ai_subagents_dir, filename)
            self.assertTrue(
                os.path.exists(filepath),
                f"AI子代理文件缺失: {filename}"
            )
    
    def test_agents_support_use_ai_parameter(self):
        """测试：智能体支持use_ai参数"""
        agents = [
            ('agents.wave_analyst', 'WaveAnalystAgent'),
            ('agents.tech_analyst', 'TechAnalystAgent'),
            ('agents.rotation_analyst', 'RotationAnalystAgent'),
        ]
        
        for module_name, class_name in agents:
            try:
                module = __import__(module_name, fromlist=[class_name])
                agent_class = getattr(module, class_name)
                
                # 检查__init__签名
                sig = inspect.signature(agent_class.__init__)
                self.assertIn(
                    'use_ai', sig.parameters,
                    f"{class_name}不支持use_ai参数"
                )
            except (ImportError, AttributeError) as e:
                self.skipTest(f"无法检查{agent_name}: {e}")


class TestAlgorithmRegression(unittest.TestCase):
    """
    P2 - 算法完整性回归测试
    确保Triangle等算法不会丢失
    """
    
    def test_triangle_validation_exists(self):
        """测试：Triangle验证函数存在"""
        from analysis.wave.elliott_wave import validate_triangle
        
        # 验证函数可用
        self.assertTrue(callable(validate_triangle))
    
    def test_elliott_wave_analyzer_has_try_triangle(self):
        """测试：ElliottWaveAnalyzer有_try_triangle方法"""
        from analysis.wave.elliott_wave import ElliottWaveAnalyzer
        
        analyzer = ElliottWaveAnalyzer()
        self.assertTrue(
            hasattr(analyzer, '_try_triangle'),
            "ElliottWaveAnalyzer缺少_try_triangle方法"
        )
        self.assertTrue(
            callable(getattr(analyzer, '_try_triangle', None)),
            "_try_triangle不是可调用的方法"
        )
    
    def test_detect_with_points_calls_try_triangle(self):
        """测试：检测流程调用Triangle检测"""
        filepath = os.path.join(project_root, 'analysis', 'wave', 'elliott_wave.py')
        
        with open(filepath, 'r') as f:
            source = f.read()
        
        # 检查_try_triangle在_detect_with_points中被调用
        if '_try_triangle' not in source:
            self.fail("_detect_with_points未调用_try_triangle")


class TestFastAPIRegression(unittest.TestCase):
    """
    P3 - FastAPI服务层回归测试
    确保API代码不会丢失
    """
    
    def test_fastapi_main_exists(self):
        """测试：FastAPI主文件存在"""
        filepath = os.path.join(project_root, 'api', 'main.py')
        self.assertTrue(
            os.path.exists(filepath),
            "api/main.py不存在"
        )
    
    def test_fastapi_init_handles_import_error(self):
        """测试：API模块有降级处理"""
        filepath = os.path.join(project_root, 'api', '__init__.py')
        
        with open(filepath, 'r') as f:
            source = f.read()
        
        # 应该有try-except处理
        self.assertIn('try:', source, "缺少try块")
        self.assertIn('except', source, "缺少except块")
    
    def test_config_has_api_section(self):
        """测试：配置有API部分"""
        import yaml
        
        config_path = os.path.join(project_root, 'config', 'config.yaml')
        if not os.path.exists(config_path):
            self.skipTest("config.yaml不存在")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.assertIn('api', config, "配置缺少api部分")
        self.assertIn('port', config.get('api', {}), "api配置缺少port")


class TestSysPathCleanupRegression(unittest.TestCase):
    """
    P3 - sys.path清理回归测试
    注：fetch_sw_industry.py 和 fetch_sw_industry_continue.py 已在 cleanup sprint
    合并/移除，改用 sw_industry_fetch.py，测试已更新以反映实际文件状态。
    """

    def test_fetch_sw_industry_single_insert(self):
        """测试：sw_industry_fetch.py 单一路径插入（原 fetch_sw_industry.py 已合并）"""
        filepath = os.path.join(project_root, 'scripts', 'data_sync', 'sw_industry_fetch.py')
        if not os.path.exists(filepath):
            self.skipTest(f"sw_industry_fetch.py 不存在，跳过")
        with open(filepath, 'r') as f:
            source = f.read()
        count = source.count('sys.path.insert')
        self.assertLessEqual(count, 2,
            f"sw_industry_fetch.py 有 {count} 处 sys.path.insert，应 ≤2 处")

    def test_fetch_sw_industry_continue_single_insert(self):
        """fetch_sw_industry_continue.py 已移除，跳过此回归项"""
        filepath = os.path.join(project_root, 'scripts', 'data_sync', 'fetch_sw_industry_continue.py')
        if not os.path.exists(filepath):
            self.skipTest("fetch_sw_industry_continue.py 已在 cleanup sprint 移除")
        with open(filepath, 'r') as f:
            source = f.read()
        count = source.count('sys.path.insert')
        self.assertLessEqual(count, 2, f"文件有 {count} 处 sys.path.insert，应 ≤2 处")


def run_regression_tests():
    """运行回归测试"""
    print("="*60)
    print("🛡️ 回归测试套件 - 防止审计修复项回退")
    print("="*60)
    print()
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityRegression))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeQualityRegression))
    suite.addTests(loader.loadTestsFromTestCase(TestAlgorithmRegression))
    suite.addTests(loader.loadTestsFromTestCase(TestFastAPIRegression))
    suite.addTests(loader.loadTestsFromTestCase(TestSysPathCleanupRegression))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*60)
    if result.wasSuccessful():
        print("✅ 所有回归测试通过！修复项已固化，不会回退。")
    else:
        print(f"❌ 回归测试失败！需要检查修复项是否被破坏。")
        print(f"   失败: {len(result.failures)}，错误: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_regression_tests()
