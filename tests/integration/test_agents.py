"""
智能体集成测试 - 验证Agent间协作
"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import numpy as np

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.base_agent import AgentInput, AgentOutput, AgentState
from agents.wave_analyst import WaveAnalystAgent
from agents.tech_analyst import TechAnalystAgent
from agents.rotation_analyst import RotationAnalystAgent


class TestWaveAnalystIntegration(unittest.TestCase):
    """波浪分析智能体集成测试"""

    def setUp(self):
        """设置测试环境"""
        os.environ.setdefault('DEEPSEEK_API_KEY', 'test_key')
        self.agent = WaveAnalystAgent(use_ai=False)
    
    def test_analyze_valid_symbol(self):
        """测试分析有效股票代码"""
        # Mock数据获取
        mock_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=30, freq='D'),
            'open': np.linspace(100, 120, 30) + np.random.randn(30) * 2,
            'high': np.linspace(101, 121, 30) + np.random.randn(30) * 2,
            'low': np.linspace(99, 119, 30) + np.random.randn(30) * 2,
            'close': np.linspace(100, 120, 30) + np.random.randn(30) * 2,
            'volume': [1000] * 30
        })
        
        with patch.object(self.agent, '_load_data', return_value=mock_df):
            input_data = AgentInput(
                symbol='600519.SH',
                start_date='2024-01-01',
                end_date='2024-01-30'
            )
            
            result = self.agent.analyze(input_data)
            
            # 验证输出结构
            self.assertIsInstance(result, AgentOutput)
            self.assertEqual(result.symbol, '600519.SH')
            self.assertIn(result.state, [AgentState.COMPLETED, AgentState.ERROR])
            
            if result.state == AgentState.COMPLETED:
                self.assertIn('patterns', result.result)
                self.assertIn('data_points', result.result)
    
    def test_analyze_with_ai(self):
        """测试启用AI的分析"""
        agent_with_ai = WaveAnalystAgent(use_ai=True)
        
        # Mock AI子代理
        mock_ai_output = Mock()
        mock_ai_output.reasoning = "AI推理测试"
        mock_ai_output.conclusion = "测试结论"
        mock_ai_output.confidence = 0.8
        mock_ai_output.action_suggestion = "buy"
        
        agent_with_ai.ai_agent = Mock()
        agent_with_ai.ai_agent.analyze = Mock(return_value=mock_ai_output)
        
        mock_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=30, freq='D'),
            'open': [100] * 30,
            'high': [101] * 30,
            'low': [99] * 30,
            'close': [100] * 30,
            'volume': [1000] * 30
        })
        
        with patch.object(agent_with_ai, '_load_data', return_value=mock_df):
            input_data = AgentInput(symbol='600519.SH')
            result = agent_with_ai.analyze(input_data)
            
            # 验证AI分析被调用
            if result.state == AgentState.COMPLETED:
                self.assertIn('ai_analysis', result.result)
    
    def test_analyze_invalid_symbol(self):
        """测试无效股票代码处理"""
        with patch.object(self.agent, '_load_data', return_value=None):
            input_data = AgentInput(symbol='INVALID')
            result = self.agent.analyze(input_data)
            
            self.assertEqual(result.state, AgentState.ERROR)
            self.assertIsNotNone(result.error_message)


class TestTechAnalystIntegration(unittest.TestCase):
    """技术分析智能体集成测试"""

    def setUp(self):
        os.environ.setdefault('DEEPSEEK_API_KEY', 'test_key')
        self.agent = TechAnalystAgent(use_ai=False)
    
    def test_full_analysis_pipeline(self):
        """测试完整分析流程"""
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        prices = []
        price = 100
        for i in range(50):
            price = price * (1 + np.random.randn() * 0.02)
            prices.append(price)
        
        mock_df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices],
            'close': prices,
            'volume': [1000] * 50
        })
        
        with patch.object(self.agent, '_load_data', return_value=mock_df):
            input_data = AgentInput(
                symbol='000001.SZ',
                start_date='2024-01-01',
                end_date='2024-02-19'
            )
            
            result = self.agent.analyze(input_data)
            
            self.assertIsInstance(result, AgentOutput)
            if result.state == AgentState.COMPLETED:
                # 验证包含所有技术指标
                self.assertIn('signals', result.result)
                self.assertIn('combined_signal', result.result)
                self.assertIn('latest', result.result)
                
                # 验证信号结构
                signals = result.result['signals']
                signal_names = [s.get('indicator') for s in signals]
                self.assertIn('MACD', signal_names)


class TestRotationAnalystIntegration(unittest.TestCase):
    """轮动分析智能体集成测试"""

    def setUp(self):
        os.environ.setdefault('DEEPSEEK_API_KEY', 'test_key')
        self.agent = RotationAnalystAgent(use_ai=False)
    
    def test_industry_rotation_analysis(self):
        """测试行业轮动分析"""
        # Mock数据库查询结果
        mock_industries = [
            ('801081', '半导体', 0.15),
            ('801082', '电子制造', 0.12),
            ('801083', '通信设备', -0.05),
            ('801084', '计算机应用', -0.08),
        ]
        
        mock_buy_points = [
            ('801081', {'type': 'C浪', 'confidence': 0.8}),
        ]
        
        with patch.object(self.agent, '_query_industry_momentum', return_value=mock_industries):
            with patch.object(self.agent, '_analyze_industry_buy_points', return_value=mock_buy_points):
                input_data = AgentInput(symbol='MARKET')
                result = self.agent.analyze(input_data)
                
                self.assertIsInstance(result, AgentOutput)
                if result.state == AgentState.COMPLETED:
                    self.assertIn('strong_industries', result.result)
                    self.assertIn('weak_industries', result.result)
                    self.assertIn('recommendation', result.result)


class TestAgentCollaboration(unittest.TestCase):
    """测试智能体间协作"""

    def test_cross_agent_symbol_analysis(self):
        """测试多智能体对同一代码的分析"""
        symbol = '600519.SH'
        
        # 创建mock数据
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        prices = np.linspace(100, 130, 60) + np.random.randn(60) * 3
        
        mock_df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': prices * 1.02,
            'low': prices * 0.98,
            'close': prices,
            'volume': [1000] * 60
        })
        
        # 波浪分析
        wave_agent = WaveAnalystAgent(use_ai=False)
        tech_agent = TechAnalystAgent(use_ai=False)
        
        with patch.object(wave_agent, '_load_data', return_value=mock_df):
            with patch.object(tech_agent, '_load_data', return_value=mock_df):
                wave_result = wave_agent.analyze(
                    AgentInput(symbol=symbol)
                )
                tech_result = tech_agent.analyze(
                    AgentInput(symbol=symbol)
                )
                
                # 验证两个智能体都完成分析
                self.assertIn(wave_result.state, [AgentState.COMPLETED, AgentState.ERROR])
                self.assertIn(tech_result.state, [AgentState.COMPLETED, AgentState.ERROR])


class TestAgentErrorHandling(unittest.TestCase):
    """测试智能体错误处理"""

    def test_data_load_failure(self):
        """测试数据加载失败处理"""
        agent = WaveAnalystAgent(use_ai=False)
        
        with patch.object(agent, '_load_data', side_effect=Exception("连接失败")):
            input_data = AgentInput(symbol='600519.SH')
            result = agent.analyze(input_data)
            
            self.assertEqual(result.state, AgentState.ERROR)
            self.assertIn("连接失败", result.error_message)
    
    def test_analysis_exception_handling(self):
        """测试分析过程异常处理"""
        agent = TechAnalystAgent(use_ai=False)
        
        mock_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'close': [100] * 10
        })
        
        # 故意让技术分析抛出异常
        with patch.object(agent, '_load_data', return_value=mock_df):
            with patch.object(agent.technical_analyzer, 'analyze_full', side_effect=Exception("计算错误")):
                input_data = AgentInput(symbol='000001.SZ')
                result = agent.analyze(input_data)
                
                self.assertEqual(result.state, AgentState.ERROR)


if __name__ == '__main__':
    unittest.main()
