"""
agents — A股智能分析Agent模块

主入口：AShareAgent
  analyze()    单股完整分析（市场状态 + 多因子 + 信号）
  scan()       批量扫描选股
  factor_scan() 仅多因子筛选
  market_regime() 市场状态判断
"""
from .ashare_agent import AShareAgent, AShareAnalysis
from .base_agent import BaseAgent, AgentInput, AgentOutput, AgentState, AnalysisType

__all__ = [
    "AShareAgent",
    "AShareAnalysis",
    "BaseAgent",
    "AgentInput",
    "AgentOutput",
    "AgentState",
    "AnalysisType",
]
