"""
AI子代理适配器 - 统一输入输出转换

解决 AgentInput/Output 与 AIAgentInput/Output 之间的不一致问题
"""
from typing import Any

from agents.base_agent import AgentInput, AgentOutput, AgentState
from .base_ai_agent import AIAgentInput, AIAgentOutput


def to_ai_input(
    agent_input: AgentInput,
    raw_data: dict[str, Any] | None = None,
    additional_context: dict[str, Any] | None = None
) -> AIAgentInput:
    """
    将 AgentInput 转换为 AIAgentInput
    
    Args:
        agent_input: 主智能体输入
        raw_data: 分析原始数据（如波浪信号、技术指标等）
        additional_context: 额外上下文信息
        
    Returns:
        AIAgentInput 实例
        
    示例:
        ai_input = to_ai_input(
            agent_input,
            raw_data={'entry_type': 'C', 'confidence': 0.75},
            additional_context={'market_condition': 'bullish'}
        )
    """
    # 构建上下文
    context = {
        'symbol': agent_input.symbol,
        'start_date': agent_input.start_date,
        'end_date': agent_input.end_date,
        'parameters': agent_input.parameters,
    }
    
    if additional_context:
        context.update(additional_context)
    
    return AIAgentInput(
        raw_data=raw_data or {},
        context=str(context)
    )


def to_agent_output(
    ai_output: AIAgentOutput,
    agent_type: str,
    symbol: str,
    execution_time: float,
    analysis_date: str | None = None
) -> AgentOutput:
    """
    将 AIAgentOutput 转换为 AgentOutput
    
    Args:
        ai_output: AI子代理输出
        agent_type: 智能体类型 (如 'wave', 'technical', 'rotation')
        symbol: 股票代码
        execution_time: 执行时间（秒）
        analysis_date: 分析日期，默认为今天
        
    Returns:
        AgentOutput 实例
        
    示例:
        result = to_agent_output(
            ai_output,
            agent_type='wave',
            symbol='000001',
            execution_time=2.5
        )
    """
    from datetime import datetime
    
    if analysis_date is None:
        analysis_date = datetime.now().strftime('%Y-%m-%d')
    
    # 确定状态
    state = AgentState.COMPLETED if ai_output.success else AgentState.ERROR
    
    # 构建结果字典
    result = {
        'ai_reasoning': ai_output.reasoning,
        'ai_conclusion': ai_output.conclusion,
        'ai_confidence': ai_output.confidence,
        'ai_action_suggestion': ai_output.action_suggestion,
        'ai_details': ai_output.details,
    }
    
    return AgentOutput(
        agent_type=agent_type,
        symbol=symbol,
        analysis_date=analysis_date,
        result=result,
        confidence=ai_output.confidence,
        state=state,
        execution_time=execution_time,
        error_message=ai_output.error_message
    )


def merge_with_ai_result(
    base_result: dict[str, Any],
    ai_output: AIAgentOutput,
    include_raw: bool = False
) -> dict[str, Any]:
    """
    将 AI 分析结果合并到基础结果中
    
    Args:
        base_result: 基础分析结果（技术/波浪分析结果）
        ai_output: AI子代理输出
        include_raw: 是否包含原始AI输出
        
    Returns:
        合并后的结果字典
        
    示例:
        result = {
            'entry_price': 100.0,
            'confidence': 0.75,
        }
        merged = merge_with_ai_result(result, ai_output)
        # merged 现在包含 AI 分析结论
    """
    merged = base_result.copy()
    
    merged['ai_analysis'] = {
        'reasoning': ai_output.reasoning,
        'conclusion': ai_output.conclusion,
        'confidence': ai_output.confidence,
        'action_suggestion': ai_output.action_suggestion,
    }
    
    if include_raw:
        merged['ai_raw'] = {
            'details': ai_output.details,
            'success': ai_output.success,
            'error_message': ai_output.error_message,
        }
    
    return merged


def extract_confidence(ai_output: AIAgentOutput) -> float:
    """
    从 AI 输出中提取置信度
    
    如果 AI 输出中没有置信度，返回 0.5（中性）
    """
    if hasattr(ai_output, 'confidence') and ai_output.confidence is not None:
        return float(ai_output.confidence)
    return 0.5


def combine_confidences(base_confidence: float, ai_confidence: float, weight: float = 0.5) -> float:
    """
    结合技术置信度和 AI 置信度
    
    Args:
        base_confidence: 技术分析置信度 (0-1)
        ai_confidence: AI分析置信度 (0-1)
        weight: AI 置信度权重 (0-1)，默认 0.5
        
    Returns:
        综合置信度
        
    示例:
        final = combine_confidences(0.75, 0.80, weight=0.4)
        # final = 0.75 * 0.6 + 0.80 * 0.4 = 0.77
    """
    return base_confidence * (1 - weight) + ai_confidence * weight


# 便捷函数，用于智能体内部快速转换
def quick_ai_analyze(
    ai_agent,
    agent_input: AgentInput,
    raw_data: dict[str, Any],
    context: dict[str, Any] | None = None
) -> tuple[dict[str, Any], float]:
    """
    快速执行 AI 分析并返回结果
    
    Args:
        ai_agent: AI子代理实例
        agent_input: 主智能体输入
        raw_data: 分析原始数据
        context: 额外上下文
        
    Returns:
        (ai_result_dict, confidence) 元组
        
    示例:
        ai_result, ai_conf = quick_ai_analyze(
            self.ai_agent,
            input_data,
            wave_data
        )
    """
    import time
    
    try:
        ai_input = to_ai_input(agent_input, raw_data, context)
        
        start = time.time()
        ai_output = ai_agent.analyze(ai_input)
        elapsed = time.time() - start
        
        result = {
            'reasoning': ai_output.reasoning,
            'conclusion': ai_output.conclusion,
            'confidence': ai_output.confidence,
            'action_suggestion': ai_output.action_suggestion,
            'details': ai_output.details,
            'execution_time': elapsed,
        }
        
        return result, ai_output.confidence
        
    except Exception as e:
        return {
            'error': str(e),
            'reasoning': 'AI分析失败',
            'conclusion': '无法提供AI增强分析',
            'confidence': 0.0,
        }, 0.0


if __name__ == '__main__':
    # 测试适配器
    print("=== AI适配器测试 ===\n")
    
    # 模拟 AgentInput
    agent_input = AgentInput(
        symbol='000001',
        start_date='2024-01-01',
        end_date='2024-12-31',
        parameters={'lookback': 60}
    )
    
    # 测试 to_ai_input
    ai_input = to_ai_input(
        agent_input,
        raw_data={'entry_type': 'C', 'confidence': 0.75},
        additional_context={'market': 'bullish'}
    )
    print("1. to_ai_input 结果:")
    print(f"   raw_data: {ai_input.raw_data}")
    print(f"   context: {ai_input.context}")
    
    # 测试 combine_confidences
    print("\n2. combine_confidences 结果:")
    print(f"   技术置信度 0.75 + AI置信度 0.80 (权重0.4) = {combine_confidences(0.75, 0.80, 0.4):.2f}")
    
    print("\n✅ 适配器测试完成")
