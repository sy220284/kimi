"""
AI子代理测试 - 验证AI推理功能
"""
import unittest
from unittest.mock import Mock, patch

from agents.ai_subagents import (
    AIAgentInput,
    AIAgentOutput,
    WaveReasoningAgent,
    PatternInterpreterAgent,
    MarketContextAgent,
)


class TestWaveReasoningAgent(unittest.TestCase):
    """测试波浪形态推理子代理"""

    def setUp(self):
        self.agent = WaveReasoningAgent(model="deepseek/deepseek-reasoner")
    
    def test_build_prompt(self):
        """测试Prompt构建"""
        input_data = AIAgentInput(
            raw_data={
                'pattern_type': 'impulse',
                'confidence': 0.75,
                'current_wave': 3,
                'current_price': 100.0,
                'pivots': [
                    {'type': 'trough', 'price': 90, 'date': '2024-01-01'},
                    {'type': 'peak', 'price': 95, 'date': '2024-01-10'},
                ],
                'signals': []
            },
            context="测试标的: 600519.SH"
        )
        
        prompt = self.agent.build_prompt(input_data)
        
        # 验证Prompt包含关键信息
        self.assertIn('600519.SH', prompt)
        self.assertIn('impulse', prompt)
        self.assertIn('100.0', prompt)
        self.assertIn('target_range', prompt)  # 要求输出JSON格式
    
    def test_parse_response_valid_json(self):
        """测试解析有效的JSON响应"""
        response = """
        {
            "reasoning": "当前处于3浪主升浪，浪1长度10元，浪2回撤38.2%，符合标准推动浪结构。",
            "conclusion": "推动浪3浪进行中",
            "wave_position": "3浪主升浪",
            "target_range": {"low": 110.0, "mid": 115.0, "high": 120.0},
            "key_levels": {"support": [98, 95], "resistance": [110, 120]},
            "risk_reward": "中风险",
            "time_estimate": "2-4周",
            "invalidation": "跌破浪2低点95",
            "confidence": 0.85,
            "action": "buy"
        }
        """
        
        output = self.agent.parse_response(response)
        
        self.assertIsInstance(output, AIAgentOutput)
        self.assertIn('3浪', output.reasoning)
        self.assertEqual(output.confidence, 0.85)
        self.assertIn('buy', output.action_suggestion)
    
    def test_parse_response_invalid_json(self):
        """测试解析无效的JSON响应"""
        response = "这不是有效的JSON"
        
        output = self.agent.parse_response(response)
        
        self.assertEqual(output.confidence, 0.0)
        self.assertIn('无法解析', output.reasoning)


class TestPatternInterpreterAgent(unittest.TestCase):
    """测试技术指标综合解读子代理"""

    def setUp(self):
        self.agent = PatternInterpreterAgent(model="deepseek/deepseek-chat")
    
    def test_build_prompt(self):
        """测试Prompt构建"""
        input_data = AIAgentInput(
            raw_data={
                'macd_dif': 0.5,
                'macd_dea': 0.3,
                'macd_hist': 0.2,
                'macd_state': '多头',
                'rsi6': 65,
                'rsi12': 60,
                'rsi24': 55,
                'kdj_k': 70,
                'kdj_d': 60,
                'kdj_j': 90,
                'boll_upper': 110,
                'boll_mid': 100,
                'boll_lower': 90,
                'ma5': 101,
                'ma10': 100,
                'ma20': 98,
            },
            context="测试标的: 000001.SZ, 最新价: 102"
        )
        
        prompt = self.agent.build_prompt(input_data)
        
        self.assertIn('MACD', prompt)
        self.assertIn('RSI', prompt)
        self.assertIn('000001.SZ', prompt)
    
    def test_parse_response(self):
        """测试响应解析"""
        response = """
        {
            "reasoning": "MACD金叉，RSI中性，KDJ超买，布林带开口向上",
            "conclusion": "多头趋势，但KDJ超买需警惕",
            "signal_alignment": "看多",
            "divergence": {"detected": false, "type": "无"},
            "overbought_oversold": "轻度超买",
            "top_signals": ["MACD金叉", "突破布林中轨", "KDJ超买"],
            "confidence": 0.75,
            "action": "买入",
            "timeframe": "中线"
        }
        """
        
        output = self.agent.parse_response(response)
        
        self.assertEqual(output.confidence, 0.75)
        self.assertIn('MACD', output.reasoning)


class TestMarketContextAgent(unittest.TestCase):
    """测试市场环境分析子代理"""

    def setUp(self):
        self.agent = MarketContextAgent(model="deepseek/deepseek-reasoner")
    
    def test_build_prompt(self):
        """测试Prompt构建"""
        input_data = AIAgentInput(
            raw_data={
                'strong_industries': [
                    {'name': '半导体', 'momentum_20d': 15.5},
                    {'name': '人工智能', 'momentum_20d': 12.3},
                ],
                'weak_industries': [
                    {'name': '房地产', 'momentum_20d': -8.5},
                ],
                'buy_point_industries': [
                    {'name': '新能源', 'buy_signal': {'type': 'C浪', 'confidence': 0.8}}
                ]
            },
            context="分析日期: 2024-03-19"
        )
        
        prompt = self.agent.build_prompt(input_data)
        
        self.assertIn('半导体', prompt)
        self.assertIn('新能源', prompt)
        self.assertIn('allocation_advice', prompt)


class TestBaseAIAgent(unittest.TestCase):
    """测试AI代理基类"""

    def test_model_parsing(self):
        """测试模型名称解析"""
        from agents.ai_subagents.base_ai_agent import BaseAIAgent
        
        # 创建测试子类
        class TestAgent(BaseAIAgent):
            def build_prompt(self, input_data):
                return "test"
            def parse_response(self, response):
                return AIAgentOutput("test", "test", 0.5)
        
        # 测试DeepSeek模型
        agent = TestAgent("test_agent", "deepseek/deepseek-reasoner", "high")
        self.assertEqual(agent.provider, "deepseek")
        self.assertEqual(agent.model_id, "deepseek-reasoner")
        self.assertEqual(agent.thinking, "high")
        
        # 测试DeepSeek模型 (positional: agent_name, model, thinking)
        agent = TestAgent("test_agent2", "deepseek/deepseek-chat", "low")
        self.assertEqual(agent.provider, "deepseek")
        self.assertEqual(agent.model_id, "deepseek-chat")


class TestIntegration(unittest.TestCase):
    """集成测试 - 模拟完整调用流程"""

    @patch('agents.ai_subagents.base_ai_agent.requests.post')
    def test_full_analysis_flow(self, mock_post):
        """测试完整的分析流程"""
        # Mock LLM响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"reasoning": "测试推理", "conclusion": "测试结论", "confidence": 0.8}'
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # 设置环境变量
        import os
        os.environ['DEEPSEEK_API_KEY'] = 'test_key'
        
        agent = WaveReasoningAgent()
        
        input_data = AIAgentInput(
            raw_data={'pattern_type': 'impulse', 'confidence': 0.7, 'current_price': 100},
            context="测试"
        )
        
        # 注意：这里会实际尝试调用API（被mock）
        # 如果环境变量未设置，会返回降级输出
        output = agent.analyze(input_data)
        
        # 验证输出结构
        self.assertIsInstance(output, AIAgentOutput)
        self.assertIsNotNone(output.reasoning)


if __name__ == '__main__':
    unittest.main()
