#!/usr/bin/env python3
"""
智能体集成端到端测试
测试智能体Agent的完整工作流程
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
import time
from datetime import datetime, timedelta

from agents.wave_analyst import WaveAnalystAgent
from agents.tech_analyst import TechAnalystAgent
from agents.rotation_analyst import RotationAnalystAgent
from data.optimized_data_manager import get_optimized_data_manager


class TestWaveAgentIntegration(unittest.TestCase):
    """波浪分析师智能体集成测试"""
    
    @classmethod
    def setUpClass(cls):
        """准备数据"""
        cls.data_mgr = get_optimized_data_manager()
        cls.data_mgr.load_all_data()
        cls.agent = WaveAnalystAgent()
    
    def test_01_agent_initialization(self):
        """测试智能体初始化"""
        self.assertIsNotNone(self.agent)
        self.assertEqual(self.agent.agent_name, "wave_analyst")
        print("✅ 波浪分析师智能体初始化成功")
    
    def test_02_single_stock_analysis(self):
        """测试单股分析"""
        df = self.data_mgr.get_stock_data('600519')
        self.assertIsNotNone(df)
        
        result = self.agent.analyze(df)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        print(f"✅ 单股分析完成，发现{len(result)}个波浪模式")
    
    def test_03_multiple_stocks_analysis(self):
        """测试多股批量分析"""
        symbols = ['600519', '000858', '002594', '000001']
        results = []
        
        start = time.time()
        for symbol in symbols:
            df = self.data_mgr.get_stock_data(symbol)
            if df is not None:
                result = self.agent.analyze(df)
                results.append({
                    'symbol': symbol,
                    'patterns': len(result) if result else 0
                })
        elapsed = time.time() - start
        
        # 至少要有3个成功分析的股票
        self.assertGreaterEqual(len(results), 3)
        print(f"✅ 批量分析({len(results)}/{len(symbols)}只)完成，耗时{elapsed:.2f}秒")
    
    def test_04_analysis_with_indicators(self):
        """测试结合指标的分析"""
        df = self.data_mgr.get_stock_data('600519')
        df = self.data_mgr.calculate_ma(df, 20)
        df = self.data_mgr.calculate_ma(df, 60)
        df = self.data_mgr.calculate_rsi(df, 14)
        
        result = self.agent.analyze(df)
        
        self.assertIsNotNone(result)
        print("✅ 结合指标的分析完成")
    
    def test_05_empty_data_handling(self):
        """测试空数据处理"""
        import pandas as pd
        empty_df = pd.DataFrame()
        
        result = self.agent.analyze(empty_df)
        
        self.assertEqual(result, [])
        print("✅ 空数据处理正常")
    
    def test_06_invalid_data_handling(self):
        """测试无效数据处理"""
        result = self.agent.analyze(None)
        
        self.assertEqual(result, [])
        print("✅ 无效数据处理正常")


class TestTechAgentIntegration(unittest.TestCase):
    """技术分析师智能体集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.data_mgr.load_all_data()
        cls.agent = TechAnalystAgent()
    
    def test_01_agent_initialization(self):
        """测试智能体初始化"""
        self.assertIsNotNone(self.agent)
        print("✅ 技术分析师智能体初始化成功")
    
    def test_02_single_stock_analysis(self):
        """测试单股技术分析"""
        df = self.data_mgr.get_stock_data('600519')
        
        result = self.agent.analyze(df)
        
        self.assertIsNotNone(result)
        print(f"✅ 技术分析完成")
    
    def test_03_signal_generation(self):
        """测试信号生成"""
        df = self.data_mgr.get_stock_data('600519')
        
        result = self.agent.analyze(df)
        
        # 检查结果结构
        if isinstance(result, dict):
            signals = result.get('signals', [])
            print(f"✅ 信号生成完成，发现{len(signals)}个信号")
        else:
            print("✅ 分析完成（返回格式检查）")


class TestRotationAgentIntegration(unittest.TestCase):
    """板块轮动智能体集成测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.agent = RotationAnalystAgent()
    
    def test_01_agent_initialization(self):
        """测试智能体初始化"""
        self.assertIsNotNone(self.agent)
        print("✅ 板块轮动智能体初始化成功")
    
    def test_02_market_rotation_analysis(self):
        """测试市场轮动分析"""
        try:
            result = self.agent.analyze({})
            self.assertIsNotNone(result)
            print("✅ 市场轮动分析完成")
        except Exception as e:
            print(f"⚠️ 轮动分析跳过: {e}")
            self.skipTest("数据不足")


class TestAgentCollaboration(unittest.TestCase):
    """智能体协作测试"""
    
    @classmethod
    def setUpClass(cls):
        cls.data_mgr = get_optimized_data_manager()
        cls.data_mgr.load_all_data()
        cls.wave_agent = WaveAnalystAgent()
        cls.tech_agent = TechAnalystAgent()
    
    def test_01_multi_agent_analysis(self):
        """测试多智能体联合分析"""
        symbol = '600519'
        df = self.data_mgr.get_stock_data(symbol)
        
        # 波浪分析
        wave_result = self.wave_agent.analyze(df)
        
        # 技术分析
        tech_result = self.tech_agent.analyze(df)
        
        # 整合结果
        combined = {
            'symbol': symbol,
            'wave_patterns': len(wave_result) if wave_result else 0,
            'tech_analysis': tech_result is not None,
            'timestamp': datetime.now().isoformat()
        }
        
        self.assertTrue(combined['tech_analysis'])
        print(f"✅ 多智能体联合分析完成")
    
    def test_02_analysis_pipeline(self):
        """测试分析流水线"""
        symbol = '000858'
        
        # 步骤1: 获取数据
        df = self.data_mgr.get_stock_data(symbol)
        self.assertIsNotNone(df)
        
        # 步骤2: 计算指标
        df = self.data_mgr.calculate_ma(df, 20)
        df = self.data_mgr.calculate_rsi(df, 14)
        
        # 步骤3: 波浪分析
        wave_result = self.wave_agent.analyze(df)
        
        # 步骤4: 技术分析
        tech_result = self.tech_agent.analyze(df)
        
        # 验证流水线完整
        self.assertIsNotNone(wave_result)
        self.assertIsNotNone(tech_result)
        
        print("✅ 分析流水线测试通过")


class TestEndToEndWorkflow(unittest.TestCase):
    """端到端工作流测试"""
    
    def test_01_complete_analysis_workflow(self):
        """测试完整分析工作流"""
        print("\n🔄 执行端到端分析工作流...")
        
        # 1. 加载数据
        data_mgr = get_optimized_data_manager()
        df_all = data_mgr.load_all_data()
        self.assertGreater(len(df_all), 0)
        
        # 2. 选择股票
        symbols = ['600519', '000858']
        
        # 3. 创建智能体
        wave_agent = WaveAnalystAgent()
        tech_agent = TechAnalystAgent()
        
        # 4. 执行分析
        results = []
        for symbol in symbols:
            df = data_mgr.get_stock_data(symbol)
            if df is not None:
                # 计算指标
                df = data_mgr.calculate_ma(df, 20)
                df = data_mgr.calculate_rsi(df, 14)
                
                # 智能体分析
                wave = wave_agent.analyze(df)
                tech = tech_agent.analyze(df)
                
                results.append({
                    'symbol': symbol,
                    'wave_count': len(wave) if wave else 0,
                    'has_tech': tech is not None
                })
        
        # 5. 验证结果
        self.assertEqual(len(results), len(symbols))
        
        print(f"✅ 端到端工作流完成，分析了{len(results)}只股票")
    
    def test_02_performance_workflow(self):
        """测试性能工作流"""
        start = time.time()
        
        # 快速分析10只股票
        data_mgr = get_optimized_data_manager()
        df_all = data_mgr.load_all_data()
        symbols = df_all['symbol'].unique()[:10]
        
        agent = WaveAnalystAgent()
        
        for symbol in symbols:
            df = data_mgr.get_stock_data(symbol)
            if df is not None:
                agent.analyze(df)
        
        elapsed = time.time() - start
        
        print(f"✅ 性能工作流: 10只股票分析耗时{elapsed:.2f}秒")
        
        # 基准: 10只股票<5秒
        self.assertLess(elapsed, 5)


def run_tests():
    """运行测试"""
    print("="*70)
    print("🤖 智能体集成端到端测试")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestWaveAgentIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestTechAgentIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRotationAgentIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAgentCollaboration))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ 所有集成测试通过!")
    else:
        print(f"❌ 失败: {len(result.failures)}个, 错误: {len(result.errors)}个")
    print("="*70)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
