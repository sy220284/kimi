"""
波浪形态AI推理子代理
基于波浪分析结果进行AI推理，提供浪型解读和目标价预测
"""
from agents.ai_subagents.base_ai_agent import (
    AIAgentInput,
    AIAgentOutput,
    BaseAIAgent,
    parse_json_response,
)


class WaveReasoningAgent(BaseAIAgent):
    """
    波浪形态AI推理子代理
    
    输入：波浪分析器原始输出（极值点、浪型、信号）
    输出：AI推理后的浪型解读、目标价区间、风险评估
    
    使用示例:
        agent = WaveReasoningAgent(model="deepseek/deepseek-reasoner")
        input_data = AIAgentInput(
            raw_data={
                'pattern_type': 'impulse',
                'confidence': 0.75,
                'current_wave': 3,
                'current_price': 100.0,
                'pivots': [...]
            },
            context="分析标的: 600519.SH 贵州茅台"
        )
        result = agent.analyze(input_data)
    """
    
    def __init__(
        self,
        model: str = "deepseek/deepseek-reasoner",
        thinking: str = "high"
    ):
        super().__init__(
            agent_name="wave_reasoner",
            model=model,
            thinking=thinking
        )
    
    def build_prompt(self, input_data: AIAgentInput) -> str:
        """构建波浪分析prompt"""
        wave_data = input_data.raw_data
        
        # 格式化极值点数据
        pivots = wave_data.get('pivots', [])
        pivots_str = ""
        if pivots:
            for i, p in enumerate(pivots[-10:]):  # 只显示最近10个
                pivots_str += f"  {i+1}. {p.get('type', '?')} @ {p.get('price', 0):.2f} ({p.get('date', 'N/A')})\n"
        else:
            pivots_str = "  暂无显著极值点数据\n"
        
        # 格式化信号数据
        signals = wave_data.get('signals', [])
        signals_str = ""
        if signals:
            for s in signals[:5]:  # 只显示前5个信号
                signals_str += f"  - {s.get('entry_type', 'unknown')}: 置信度{s.get('confidence', 0):.2f}\n"
        else:
            signals_str = "  暂无有效交易信号\n"
        
        prompt = f"""你是一位资深的艾略特波浪理论分析师，拥有20年技术分析经验。

【分析背景】
{input_data.context}

【原始波浪数据】
- 检测到的主要浪型: {wave_data.get('pattern_type', 'unknown')}
- 整体置信度: {wave_data.get('confidence', 0):.2f}
- 当前所在浪: {wave_data.get('current_wave', 'unknown')}
- 最新价格: {wave_data.get('current_price', 0):.2f}
- 趋势方向: {wave_data.get('trend', 'unknown')}

【近期极值点】
{pivots_str}
【交易信号】
{signals_str}
请基于以上数据进行专业分析，以JSON格式输出：
{{
    "reasoning": "详细的浪型分析过程。包括：1)当前最可能的浪型判断及理由；2)推动浪还是调整浪的区分依据；3)关键斐波那契比例关系；4)与经典波浪理论的符合程度",
    "conclusion": "核心结论，用一句话概括当前波浪状态",
    "wave_position": "当前具体位置，如'3浪主升浪中'、'C浪调整末期'等",
    "target_range": {{
        "low": "低目标价（基于保守估计）",
        "mid": "中目标价（最可能情景）",
        "high": "高目标价（乐观情景）"
    }},
    "key_levels": {{
        "support": ["关键支撑位1", "关键支撑位2"],
        "resistance": ["关键阻力位1", "关键阻力位2"]
    }},
    "risk_reward": "风险收益比评估：高风险/中风险/低风险，以及理由",
    "time_estimate": "预计到达目标的时间周期（如'2-4周'、'1-2个月'）",
    "invalidation": "什么情况下当前浪型判断会被推翻（失效条件）",
    "confidence": 0.85,
    "action": "具体操作建议：强烈买入/买入/持有观望/减仓/卖出"
}}

注意：
1. reasoning字段必须详细，展现你的专业分析过程
2. target_range的价格必须是数字，与current_price同单位
3. confidence必须在0-1之间
4. 如果数据不足以判断，confidence应低于0.5并说明原因
"""
        return prompt
    
    def parse_response(self, response: str) -> AIAgentOutput:
        """解析LLM响应"""
        data = parse_json_response(response)
        
        if not data:
            return AIAgentOutput(
                reasoning="无法解析AI响应",
                conclusion="分析失败",
                confidence=0.0,
                action_suggestion="请使用原始技术分析结果"
            )
        
        # 提取推理过程
        reasoning = data.get('reasoning', '未提供详细分析')
        conclusion = data.get('conclusion', '未提供结论')
        confidence = float(data.get('confidence', 0.5))
        
        # 构建操作建议
        action = data.get('action', '观望')
        wave_position = data.get('wave_position', '')
        target = data.get('target_range', {})
        
        action_suggestion = f"{action}"
        if wave_position:
            action_suggestion += f" | 当前位置: {wave_position}"
        if target:
            low = target.get('low', '?')
            high = target.get('high', '?')
            action_suggestion += f" | 目标区间: {low}-{high}"
        
        # 构建详细详情
        details = {
            'wave_position': wave_position,
            'target_range': target,
            'key_levels': data.get('key_levels', {}),
            'risk_reward': data.get('risk_reward', '未知'),
            'time_estimate': data.get('time_estimate', '未知'),
            'invalidation': data.get('invalidation', '未知'),
            'raw_response': response[:1000]  # 保留原始响应前1000字符
        }
        
        return AIAgentOutput(
            reasoning=reasoning,
            conclusion=conclusion,
            confidence=confidence,
            action_suggestion=action_suggestion,
            details=details
        )


class PatternInterpreterAgent(BaseAIAgent):
    """
    技术指标综合解读子代理
    
    输入：多个技术指标（MACD、RSI、KDJ、布林带等）
    输出：指标共振分析、综合买卖信号
    """
    
    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        thinking: str = "medium"
    ):
        super().__init__(
            agent_name="pattern_interpreter",
            model=model,
            thinking=thinking
        )
    
    def build_prompt(self, input_data: AIAgentInput) -> str:
        """构建指标解读prompt"""
        ind = input_data.raw_data
        
        # 格式化指标数据
        prompt = f"""你是一位技术分析专家，擅长多指标共振分析。

【分析背景】
{input_data.context}

【MACD指标】
- DIF: {ind.get('macd_dif', 0):.4f}
- DEA: {ind.get('macd_dea', 0):.4f}
- 柱状图(MACD): {ind.get('macd_hist', 0):.4f}
- 状态: {ind.get('macd_state', 'neutral')}
- 金叉/死叉: {ind.get('macd_cross', '无')}

【RSI指标】
- RSI6: {ind.get('rsi6', 50):.2f} (超买>80, 超卖<20)
- RSI12: {ind.get('rsi12', 50):.2f}
- RSI24: {ind.get('rsi24', 50):.2f}

【KDJ指标】
- K值: {ind.get('kdj_k', 50):.2f}
- D值: {ind.get('kdj_d', 50):.2f}
- J值: {ind.get('kdj_j', 50):.2f}
- 状态: {ind.get('kdj_state', 'neutral')}

【布林带】
- 上轨(UPPER): {ind.get('boll_upper', 0):.2f}
- 中轨(MID): {ind.get('boll_mid', 0):.2f}
- 下轨(LOWER): {ind.get('boll_lower', 0):.2f}
- 带宽: {ind.get('boll_width', 0):.4f}
- 当前价格位置: {ind.get('boll_position', 'unknown')}

【均线系统】
- MA5: {ind.get('ma5', 0):.2f}
- MA10: {ind.get('ma10', 0):.2f}
- MA20: {ind.get('ma20', 0):.2f}
- MA60: {ind.get('ma60', 0):.2f}

【成交量指标】
- 当前成交量: {ind.get('volume', 0)}
- 成交量MA5: {ind.get('volume_ma5', 0)}
- 量比: {ind.get('volume_ratio', 1):.2f}

请进行综合分析，以JSON格式输出：
{{
    "reasoning": "详细分析过程：1)各指标的独立解读；2)指标间的一致/矛盾关系；3)与价格的背离情况",
    "conclusion": "综合结论",
    "signal_alignment": "信号一致性：强烈看多/看多/中性/看空/强烈看空",
    "divergence": {{
        "detected": true/false,
        "type": "顶背离/底背离/无",
        "description": "背离描述"
    }},
    "overbought_oversold": "超买超卖状态：严重超买/轻度超买/中性/轻度超卖/严重超卖",
    "volatility_state": "波动率状态：高波动/正常波动/低波动（布林带宽度判断）",
    "top_signals": [
        "最重要的观察点1",
        "最重要的观察点2",
        "最重要的观察点3"
    ],
    "confidence": 0.75,
    "action": "综合建议：强烈买入/买入/持有观望/卖出/强烈卖出",
    "timeframe": "建议操作周期：短线(1-5天)/中线(1-4周)/长线(1-6个月)"
}}
"""
        return prompt
    
    def parse_response(self, response: str) -> AIAgentOutput:
        """解析LLM响应"""
        data = parse_json_response(response)
        
        if not data:
            return AIAgentOutput(
                reasoning="无法解析AI响应",
                conclusion="指标分析失败",
                confidence=0.0
            )
        
        reasoning = data.get('reasoning', '')
        conclusion = data.get('conclusion', '')
        confidence = float(data.get('confidence', 0.5))
        
        # 构建操作建议
        action = data.get('action', '观望')
        alignment = data.get('signal_alignment', '')
        timeframe = data.get('timeframe', '')
        
        action_suggestion = f"{action}"
        if alignment:
            action_suggestion += f" | 信号一致性: {alignment}"
        if timeframe:
            action_suggestion += f" | 周期: {timeframe}"
        
        details = {
            'signal_alignment': alignment,
            'divergence': data.get('divergence', {}),
            'overbought_oversold': data.get('overbought_oversold', '未知'),
            'volatility_state': data.get('volatility_state', '未知'),
            'top_signals': data.get('top_signals', []),
            'raw_response': response[:1000]
        }
        
        return AIAgentOutput(
            reasoning=reasoning,
            conclusion=conclusion,
            confidence=confidence,
            action_suggestion=action_suggestion,
            details=details
        )


class MarketContextAgent(BaseAIAgent):
    """
    市场环境分析子代理
    
    输入：全市场行业轮动数据
    输出：市场环境解读、板块机会分析
    """
    
    def __init__(
        self,
        model: str = "deepseek/deepseek-reasoner",
        thinking: str = "high"
    ):
        super().__init__(
            agent_name="market_context",
            model=model,
            thinking=thinking
        )
    
    def build_prompt(self, input_data: AIAgentInput) -> str:
        """构建市场环境分析prompt"""
        data = input_data.raw_data
        
        # 格式化行业数据
        strong = data.get('strong_industries', [])
        weak = data.get('weak_industries', [])
        buy_points = data.get('buy_point_industries', [])
        
        strong_str = ""
        for i, ind in enumerate(strong[:5], 1):
            strong_str += f"  {i}. {ind.get('name', 'N/A')}: +{ind.get('momentum_20d', 0):.2f}%\n"
        
        weak_str = ""
        for i, ind in enumerate(weak[:5], 1):
            weak_str += f"  {i}. {ind.get('name', 'N/A')}: {ind.get('momentum_20d', 0):.2f}%\n"
        
        buy_str = ""
        if buy_points:
            for ind in buy_points[:5]:
                sig = ind.get('buy_signal', {})
                buy_str += f"  - {ind.get('name', 'N/A')}: {sig.get('type', '?')}浪买点，置信度{sig.get('confidence', 0):.2f}\n"
        else:
            buy_str = "  当前无明确行业买点信号\n"
        
        prompt = f"""你是一位宏观策略分析师，擅长从行业轮动中识别市场风格和资金流向。

【市场概览】
{input_data.context}

【强势行业TOP5】（20日动量）
{strong_str}
【弱势行业TOP5】（20日动量）
{weak_str}
【有买点的行业】
{buy_str}

请进行深入分析，以JSON格式输出：
{{
    "reasoning": "详细分析：1)当前市场风格判断（价值/成长/周期/防御）；2)资金流向分析；3)经济周期位置推测；4)强势行业的持续性评估",
    "conclusion": "市场环境核心结论",
    "market_style": "市场风格：价值/成长/周期/防御/均衡，以及占比评估",
    "sector_rotation": "轮动节奏：追涨型/埋伏型/混沌期",
    "money_flow": "资金流向：流入板块 vs 流出板块",
    "leading_sectors": ["领涨板块1", "领涨板块2"],
    "laggard_sectors": ["弱势板块1", "弱势板块2"],
    "opportunities": [
        {{
            "sector": "机会板块",
            "rationale": "理由",
            "risk_level": "高/中/低"
        }}
    ],
    "risks": ["风险点1", "风险点2"],
    "allocation_advice": {{
        "growth": "成长板块建议仓位(如30%)",
        "value": "价值板块建议仓位",
        "cyclical": "周期板块建议仓位",
        "defensive": "防御板块建议仓位"
    }},
    "confidence": 0.80,
    "action": "策略建议：积极进攻/均衡配置/防御为主/空仓观望"
}}
"""
        return prompt
    
    def parse_response(self, response: str) -> AIAgentOutput:
        """解析LLM响应"""
        data = parse_json_response(response)
        
        if not data:
            return AIAgentOutput(
                reasoning="无法解析AI响应",
                conclusion="市场环境分析失败",
                confidence=0.0
            )
        
        reasoning = data.get('reasoning', '')
        conclusion = data.get('conclusion', '')
        confidence = float(data.get('confidence', 0.5))
        
        # 构建操作建议
        action = data.get('action', '观望')
        style = data.get('market_style', '')
        rotation = data.get('sector_rotation', '')
        
        action_suggestion = f"{action}"
        if style:
            action_suggestion += f" | 风格: {style}"
        if rotation:
            action_suggestion += f" | 轮动: {rotation}"
        
        details = {
            'market_style': style,
            'sector_rotation': rotation,
            'money_flow': data.get('money_flow', ''),
            'leading_sectors': data.get('leading_sectors', []),
            'laggard_sectors': data.get('laggard_sectors', []),
            'opportunities': data.get('opportunities', []),
            'risks': data.get('risks', []),
            'allocation_advice': data.get('allocation_advice', {}),
            'raw_response': response[:1000]
        }
        
        return AIAgentOutput(
            reasoning=reasoning,
            conclusion=conclusion,
            confidence=confidence,
            action_suggestion=action_suggestion,
            details=details
        )
