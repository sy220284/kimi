# AI推理子代理设计方案

## 当前问题

现有智能体（WaveAnalyst/TechAnalyst/RotationAnalyst）仅调用技术分析模块，无真正的LLM推理能力：
- WaveAnalyst → 直接调用 ElliottWaveAnalyzer
- TechAnalyst → 直接调用 TechnicalIndicators  
- RotationAnalyst → 直接查询数据库计算动量

**问题**：智能体只是"调用器"，没有AI推理、解释、决策能力。

## 子代理方案架构

```
┌─────────────────────────────────────────────────────────────┐
│                    主智能体 (Coordinator)                     │
│  - WaveAnalystAgent                                        │
│  - TechAnalystAgent                                        │
│  - RotationAnalystAgent                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    AI推理子代理层                            │
├─────────────────────────────────────────────────────────────┤
│  WaveReasoningAgent    │  PatternInterpreterAgent           │
│  - 波浪形态推理        │  - 多指标综合解读                    │
│  - 浪型可能性评估      │  - 买卖信号优先级                    │
│  - 目标价区间预测      │  - 风险收益比评估                    │
├─────────────────────────────────────────────────────────────┤
│  MarketContextAgent    │  StrategyAdvisorAgent              │
│  - 市场环境分析        │  - 具体操作建议                    │
│  - 板块轮动解读        │  - 仓位管理建议                    │
│  - 情绪/资金流向       │  - 止损止盈调整                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    技术分析引擎层                            │
│  ElliottWaveAnalyzer / TechnicalIndicators / Database       │
└─────────────────────────────────────────────────────────────┘
```

## 子代理接口设计

```python
# agents/ai_subagents/base_ai_agent.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class AIAgentInput:
    raw_data: dict          # 技术分析原始输出
    context: str            # 市场上下文
    user_query: Optional[str] = None  # 用户具体问题

@dataclass  
class AIAgentOutput:
    reasoning: str          # AI推理过程
    conclusion: str         # 结论
    confidence: float       # 置信度
    action_suggestion: Optional[str] = None  # 操作建议

class BaseAIAgent(ABC):
    def __init__(self, model: str = "deepseek-reasoner", thinking: str = "high"):
        self.model = model
        self.thinking = thinking
    
    @abstractmethod
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        pass
```

## 具体子代理实现

### 1. WaveReasoningAgent - 波浪形态推理

```python
class WaveReasoningAgent(BaseAIAgent):
    """
    波浪形态AI推理子代理
    
    输入：波浪分析器原始输出（极值点、浪型、信号）
    输出：AI推理后的浪型解读、目标价区间、风险评估
    """
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        wave_data = input_data.raw_data
        
        prompt = f"""
你是一位资深的艾略特波浪理论分析师。请基于以下技术数据进行分析：

【原始波浪数据】
- 检测到的浪型: {wave_data.get('pattern_type', 'unknown')}
- 置信度: {wave_data.get('confidence', 0)}
- 推动浪序列: {wave_data.get('impulse_sequence', [])}
- 当前位置: 浪{wave_data.get('current_wave', '?')}
- 最新价格: {wave_data.get('current_price', 0)}

【历史极值点】
{wave_data.get('pivots', [])}

请提供：
1. 浪型分析：当前最可能是哪种浪型？为什么？
2. 目标价预测：如果是推动浪，5浪目标区间？如果是调整浪，C浪终点预估？
3. 关键价位：支撑/阻力位
4. 风险评估：当前位置的风险收益比
5. 操作建议：买入/观望/卖出的具体建议

以JSON格式输出：
{{
    "reasoning": "详细分析过程...",
    "conclusion": "核心结论",
    "target_range": ["低目标", "高目标"],
    "key_levels": {{"support": [], "resistance": []}},
    "risk_reward": "高风险/中风险/低风险",
    "action": "buy/hold/sell",
    "confidence": 0.85
}}
"""
        # 调用LLM API
        response = self._call_llm(prompt)
        return self._parse_response(response)
```

### 2. PatternInterpreterAgent - 多指标综合解读

```python
class PatternInterpreterAgent(BaseAIAgent):
    """
    技术指标综合解读子代理
    
    输入：多个技术指标（MACD、RSI、KDJ、布林带等）
    输出：指标共振分析、综合买卖信号
    """
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        indicators = input_data.raw_data
        
        prompt = f"""
作为技术分析专家，请综合解读以下指标信号：

【MACD】
- DIF: {indicators.get('macd_dif', 0):.4f}
- DEA: {indicators.get('macd_dea', 0):.4f}  
- 柱状图: {indicators.get('macd_hist', 0):.4f}
- 状态: {indicators.get('macd_state', 'neutral')}

【RSI】
- RSI6: {indicators.get('rsi6', 50):.2f}
- RSI12: {indicators.get('rsi12', 50):.2f}
- RSI24: {indicators.get('rsi24', 50):.2f}

【KDJ】
- K: {indicators.get('k', 50):.2f}
- D: {indicators.get('d', 50):.2f}
- J: {indicators.get('j', 50):.2f}

【布林带】
- 上轨: {indicators.get('boll_upper', 0):.2f}
- 中轨: {indicators.get('boll_mid', 0):.2f}
- 下轨: {indicators.get('boll_lower', 0):.2f}
- 带宽: {indicators.get('boll_width', 0):.4f}

分析要求：
1. 指标共振：哪些指标发出相同方向的信号？
2. 背离检测：价格与指标是否有背离？
3. 超买超卖：当前处于什么区域？
4. 综合评级：强烈买入/买入/中性/卖出/强烈卖出
5. 优先级排序：最重要的3个观察点
"""
        response = self._call_llm(prompt)
        return self._parse_response(response)
```

### 3. MarketContextAgent - 市场环境分析

```python
class MarketContextAgent(BaseAIAgent):
    """
    市场环境分析子代理
    
    输入：全市场行业轮动数据
    输出：市场环境解读、板块机会分析
    """
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        rotation_data = input_data.raw_data
        
        prompt = f"""
作为宏观策略分析师，请解读以下市场环境：

【强势行业TOP5】
{rotation_data.get('strong_industries', [])}

【弱势行业TOP5】  
{rotation_data.get('weak_industries', [])}

【有买点的行业】
{rotation_data.get('buy_point_industries', [])}

分析要求：
1. 市场风格：当前是价值/成长/周期/防御主导？
2. 资金流向：哪些板块在吸引资金？
3. 轮动节奏：现在适合追涨还是埋伏？
4. 风险预警：需要警惕的板块或信号？
5. 配置建议：行业配置比例建议
"""
        response = self._call_llm(prompt)
        return self._parse_response(response)
```

### 4. StrategyAdvisorAgent - 策略顾问

```python
class StrategyAdvisorAgent(BaseAIAgent):
    """
    具体策略建议子代理
    
    输入：波浪分析+技术指标+市场环境
    输出：具体操作建议、仓位管理、止损止盈
    """
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        context = input_data.context  # 整合前面的分析结果
        
        prompt = f"""
作为量化交易策略师，请基于以下综合分析给出具体操作建议：

【综合背景】
{context}

【当前持仓假设】
- 假设空仓，计划建仓
- 假设已持有相关标的

请提供：
1. 具体操作建议：
   - 入场价位区间
   - 建议仓位比例（如20%/30%/50%）
   - 入场条件（什么信号确认后入场）

2. 止损设置：
   - 技术止损位
   - 时间止损（持有多久无表现离场）
   - 最大亏损比例

3. 止盈策略：
   - 目标价区间
   - 分批止盈方案
   - 移动止盈触发条件

4. 风险管控：
   - 单一标的最大仓位
   - 总体风险敞口
   - 意外情况应对
"""
        response = self._call_llm(prompt)
        return self._parse_response(response)
```

## 主智能体集成方案

```python
# agents/wave_analyst.py 改造示例

class WaveAnalystAgent(BaseAgent):
    def __init__(self, config_path=None, use_ai=True):
        super().__init__(...)
        self.use_ai = use_ai
        # 初始化AI子代理
        if use_ai:
            self.wave_reasoner = WaveReasoningAgent()
            self.strategy_advisor = StrategyAdvisorAgent()
    
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        # 1. 技术分析（原有逻辑）
        wave_result = self.wave_analyzer.detect(df)
        
        if not self.use_ai:
            return self._format_basic_output(wave_result)
        
        # 2. AI推理层
        ai_input = AIAgentInput(
            raw_data=wave_result,
            context=f"分析标的: {input_data.symbol}"
        )
        ai_reasoning = self.wave_reasoner.analyze(ai_input)
        
        # 3. 策略建议层
        strategy_input = AIAgentInput(
            raw_data=wave_result,
            context=ai_reasoning.reasoning
        )
        strategy = self.strategy_advisor.analyze(strategy_input)
        
        # 4. 整合输出
        return AgentOutput(
            result={
                'technical': wave_result,
                'ai_reasoning': ai_reasoning,
                'strategy': strategy
            },
            ...
        )
```

## 实施方案

### Phase 1: 基础设施
1. 创建 `agents/ai_subagents/` 目录
2. 实现 `BaseAIAgent` 基类
3. 封装LLM调用（支持CodeFlow/DeepSeek切换）

### Phase 2: 子代理实现
1. WaveReasoningAgent - 波浪形态推理
2. PatternInterpreterAgent - 指标综合解读
3. MarketContextAgent - 市场环境分析

### Phase 3: 主智能体集成
1. WaveAnalystAgent 集成AI子代理
2. TechAnalystAgent 集成AI子代理
3. RotationAnalystAgent 集成AI子代理

### Phase 4: 测试优化
1. 对比AI增强 vs 纯技术分析的输出质量
2. 调整prompt提升推理质量
3. 添加缓存减少API调用成本

## 预期收益

1. **解释性增强**：AI可以提供"为什么是这个浪型"的详细解释
2. **决策质量提升**：多维度综合分析，减少单一指标误判
3. **用户体验改善**：自然语言输出，非技术人员也能理解
4. **灵活性提升**：通过prompt调整即可改变分析风格（保守/激进）

## 风险提示

1. **API成本**：LLM调用有成本，需添加缓存机制
2. **延迟增加**：AI推理需要时间，异步处理或缓存必要
3. **幻觉问题**：LLM可能产生不合理推理，需置信度阈值过滤
4. **合规性**：投资建议需免责声明，AI建议仅供参考
