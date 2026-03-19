"""
AI推理子代理模块

提供基于LLM的智能分析能力，包括：
- WaveReasoningAgent: 波浪形态推理
- PatternInterpreterAgent: 技术指标综合解读
- MarketContextAgent: 市场环境分析

使用示例:
    from agents.ai_subagents import WaveReasoningAgent, AIAgentInput
    
    agent = WaveReasoningAgent(model="deepseek/deepseek-reasoner")
    result = agent.analyze(AIAgentInput(
        raw_data=wave_analysis_result,
        context="600519.SH 贵州茅台"
    ))
"""

from .base_ai_agent import AIAgentInput, AIAgentOutput, BaseAIAgent, AIAgentRegistry
from .wave_reasoning_agent import (
    WaveReasoningAgent,
    PatternInterpreterAgent,
    MarketContextAgent,
)

__all__ = [
    'AIAgentInput',
    'AIAgentOutput',
    'BaseAIAgent',
    'AIAgentRegistry',
    'WaveReasoningAgent',
    'PatternInterpreterAgent',
    'MarketContextAgent',
]
