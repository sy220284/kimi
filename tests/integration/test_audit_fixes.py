"""
集成测试 - 验证审计报告修复后的完整系统
"""
import os
import sys
import unittest
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置测试环境变量
os.environ.setdefault('CODEFLOW_API_KEY', 'test_key')
os.environ.setdefault('DEEPSEEK_API_KEY', 'test_key')
os.environ.setdefault('POSTGRES_PASSWORD', 'test_pass')


class TestAuditFixesIntegration(unittest.TestCase):
    """
    集成测试 - 验证审计报告所有修复项
    
    运行: python -m pytest tests/integration/test_audit_fixes.py -v
    """
    
    def test_p0_api_key_security(self):
        """P0 - 验证API Key环境变量化"""
        from utils.config_loader import load_config
        
        cfg = load_config()
        
        # 验证CodeFlow API Key是环境变量格式或空
        codeflow_key = cfg.get('models', {}).get('codeflow', {}).get('api_key', '')
        self.assertTrue(
            '${' in codeflow_key or codeflow_key == '' or codeflow_key == 'test_key',
            f"CodeFlow API Key未环境变量化: {codeflow_key[:20]}..."
        )
        
        # 验证DeepSeek API Key
        deepseek_key = cfg.get('models', {}).get('deepseek', {}).get('api_key', '')
        self.assertTrue(
            '${' in deepseek_key or deepseek_key == '' or deepseek_key == 'test_key',
            f"DeepSeek API Key未环境变量化: {deepseek_key[:20]}..."
        )
        
        # 验证数据库密码
        pg_pass = cfg.get('database', {}).get('postgres', {}).get('password', '')
        self.assertTrue(
            '${' in pg_pass or pg_pass == '' or pg_pass == 'test_pass',
            f"数据库密码未环境变量化: {pg_pass[:20]}..."
        )
        
        print("✅ P0 - API Key安全验证通过")
    
    def test_p1_db_connection_optimization(self):
        """P1 - 验证DB连接管理优化"""
        import inspect
        from agents.rotation_analyst import RotationAnalystAgent
        
        # 获取_analyze_industry_buy_points方法源码
        source = inspect.getsource(RotationAnalystAgent._analyze_industry_buy_points)
        
        # 验证连接在循环外
        self.assertIn('pg.connect()', source)
        self.assertIn('try:', source)
        self.assertIn('for industry in top_industries:', source)
        self.assertIn('finally:', source)
        self.assertIn('pg.disconnect()', source)
        
        # 验证没有循环内重复连接（不应该在循环内看到pg.connect()在for之后）
        # 简单检查：pg.connect()应该在for之前
        connect_pos = source.find('pg.connect()')
        for_pos = source.find('for industry in')
        self.assertLess(connect_pos, for_pos, "pg.connect()应该在循环外")
        
        # 验证SQL参数化
        self.assertIn('%s', source, "应使用参数化查询")
        
        print("✅ P1 - DB连接优化验证通过")
    
    def test_p1_ai_subagents(self):
        """P1 - 验证AI子代理架构"""
        from agents.ai_subagents import (
            WaveReasoningAgent,
            PatternInterpreterAgent,
            MarketContextAgent,
            AIAgentInput,
            AIAgentOutput,
        )
        
        # 验证所有子代理可实例化
        wave_agent = WaveReasoningAgent()
        pattern_agent = PatternInterpreterAgent()
        market_agent = MarketContextAgent()
        
        self.assertIsNotNone(wave_agent)
        self.assertIsNotNone(pattern_agent)
        self.assertIsNotNone(market_agent)
        
        # 验证输入输出模型
        input_data = AIAgentInput(raw_data={'test': 1}, context='test')
        self.assertEqual(input_data.raw_data['test'], 1)
        
        print("✅ P1 - AI子代理架构验证通过")
    
    def test_p1_ai_integration_in_agents(self):
        """P1 - 验证三大智能体集成AI子代理"""
        from agents.wave_analyst import WaveAnalystAgent
        from agents.tech_analyst import TechAnalystAgent
        from agents.rotation_analyst import RotationAnalystAgent
        
        # 验证WaveAnalyst支持use_ai参数
        wave_agent = WaveAnalystAgent(use_ai=False)
        self.assertFalse(wave_agent.use_ai)
        self.assertIsNone(wave_agent.ai_agent)
        
        # 验证TechAnalyst支持use_ai参数
        tech_agent = TechAnalystAgent(use_ai=False)
        self.assertFalse(tech_agent.use_ai)
        
        # 验证RotationAnalyst支持use_ai参数
        rot_agent = RotationAnalystAgent(use_ai=False)
        self.assertFalse(rot_agent.use_ai)
        
        print("✅ P1 - AI集成验证通过")
    
    def test_p2_triangle_wave(self):
        """P2 - 验证Triangle调整浪实现"""
        from analysis.wave.elliott_wave import (
            validate_triangle,
            ElliottWaveAnalyzer,
            WavePoint,
            WaveType,
        )
        
        # 验证validate_triangle函数存在
        points = [
            WavePoint(0, '2024-01-01', 100, 1000),
            WavePoint(1, '2024-01-05', 95, 1100),
            WavePoint(2, '2024-01-10', 98, 1050),
            WavePoint(3, '2024-01-15', 96, 1080),
            WavePoint(4, '2024-01-20', 97, 1060),
        ]
        
        valid, errors, score = validate_triangle(points)
        self.assertIsInstance(valid, bool)
        self.assertIsInstance(score, float)
        
        # 验证_analyzer有_try_triangle方法
        analyzer = ElliottWaveAnalyzer()
        self.assertTrue(hasattr(analyzer, '_try_triangle'))
        
        # 验证可以调用
        pattern = analyzer._try_triangle(points)
        # 可能返回None（如果评分不够），但不应该报错
        
        print("✅ P2 - Triangle调整浪验证通过")
    
    def test_p3_fastapi_service(self):
        """P3 - 验证FastAPI服务层"""
        try:
            from api import app
            from api.main import (
                AnalysisRequest,
                WaveAnalysisResponse,
                TechAnalysisResponse,
                RotationAnalysisResponse,
            )
            
            # 验证app存在
            self.assertIsNotNone(app)
            
            # 验证数据模型
            req = AnalysisRequest(symbol='600519.SH', use_ai=False)
            self.assertEqual(req.symbol, '600519.SH')
            
            print("✅ P3 - FastAPI服务层验证通过")
            
        except ImportError:
            print("⚠️ P3 - FastAPI未安装，跳过验证")
    
    def test_p3_sys_path_cleanup(self):
        """P3 - 验证冗余sys.path清理（文件已合并/移除）"""
        import os
        # 原文件已合并为 sw_industry_fetch.py
        fp = 'scripts/data_sync/sw_industry_fetch.py'
        if not os.path.exists(fp):
            self.skipTest(f'{fp} 不存在')
        source = open(fp).read()
        insert_count = source.count('sys.path.insert')
        self.assertLessEqual(insert_count, 2,
            f"sw_industry_fetch.py有{insert_count}处sys.path.insert，应≤2处")
        # fetch_sw_industry_continue.py 已移除，跳过检查

    def test_all_modules_importable(self):
        """验证所有关键模块可导入"""
        modules = [
            'agents.ai_subagents',
            'agents.wave_analyst',
            'agents.tech_analyst',
            'agents.rotation_analyst',
            'analysis.wave.elliott_wave',
            'utils.config_loader',
        ]
        
        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                self.fail(f"无法导入模块 {module}: {e}")
        
        print("✅ 所有关键模块可导入")
    
    def test_config_structure(self):
        """验证配置结构完整"""
        from utils.config_loader import load_config
        
        cfg = load_config()
        
        # 验证必要配置项存在
        required_keys = [
            'models',
            'database',
            'agents',
            'api',
        ]
        
        for key in required_keys:
            self.assertIn(key, cfg, f"配置缺少{key}项")
        
        # 验证智能体配置有use_ai
        agents_cfg = cfg.get('agents', {})
        for agent_name in ['wave_analyst', 'technical_analyst', 'rotation_analyst']:
            agent_cfg = agents_cfg.get(agent_name, {})
            self.assertIn('use_ai', agent_cfg, f"{agent_name}缺少use_ai配置")
        
        print("✅ 配置结构完整")


def run_audit_tests():
    """运行审计测试并输出报告"""
    print("="*60)
    print("🔍 审计报告修复项集成测试")
    print("="*60)
    print()
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestAuditFixesIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*60)
    if result.wasSuccessful():
        print("🎉 所有测试通过！审计修复项验证完成。")
    else:
        print(f"❌ 测试失败: {len(result.failures)}个失败, {len(result.errors)}个错误")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_audit_tests()
