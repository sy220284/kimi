# AI推理子代理设计方案

## 概述

AI子代理层为传统技术分析提供LLM增强的推理能力，将"信号"转化为"解读"。

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    主智能体 (Coordinator)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │WaveAnalyst  │  │TechAnalyst  │  │RotationAnalyst      │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                  │
├─────────────────────────────────────────────────────────────┤
│                    AI推理子代理层                            │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ WaveReasoning   │  │ PatternInterp   │                  │
│  │ 波浪形态推理    │  │ 指标综合解读    │                  │
│  ├─────────────────┤  ├─────────────────┤                  │
│  │ - 浪型可能性    │  │ - 指标共振      │                  │
│  │ - 目标价区间    │  │ - 背离检测      │                  │
│  │ - 风险评估      │  │ - 买卖优先级    │                  │
│  └─────────────────┘  └─────────────────┘                  │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ MarketContext   │  │ StrategyAdvisor │                  │
│  │ 市场环境分析    │  │ 策略顾问        │                  │
│  ├─────────────────┤  ├─────────────────┤                  │
│  │ - 市场风格      │  │ - 具体建议      │                  │
│  │ - 板块轮动      │  │ - 仓位管理      │                  │
│  │ - 资金流向      │  │ - 止损止盈      │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    技术分析引擎层                            │
│  ElliottWaveAnalyzer / TechnicalIndicators / Database       │
└─────────────────────────────────────────────────────────────┘
```

---

## 子代理接口

### 基类设计

```python
# agents/ai_subagents/base_ai_agent.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class AIAgentInput:
    """子代理输入"""
    raw_data: Dict[str, Any]      # 技术分析原始输出
    context: str                   # 市场上下文
    market_state: Optional[str] = None  # 市场状态
    user_query: Optional[str] = None    # 用户具体问题

@dataclass  
class AIAgentOutput:
    """子代理输出"""
    reasoning: str                # AI推理过程
    conclusion: str               # 结论
    confidence: float             # 置信度 (0-1)
    action_suggestion: Optional[str] = None  # 操作建议
    target_range: Optional[Dict] = None      # 目标区间
    risk_level: Optional[str] = None         # 风险等级

class BaseAIAgent(ABC):
    """AI子代理基类"""
    
    def __init__(self, model: str = "deepseek-reasoner", thinking: str = "high"):
        self.model = model
        self.thinking = thinking
    
    @abstractmethod
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        """执行AI分析"""
        pass
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API（带重试和缓存）"""
        # 实现略...
        pass
```

---

## 具体子代理

### 1. WaveReasoningAgent - 波浪形态推理

```python
class WaveReasoningAgent(BaseAIAgent):
    """
    波浪形态AI推理子代理
    
    输入：波浪分析器原始输出（极值点、浪型、信号）
    输出：AI推理后的浪型解读、目标价区间、风险评估
    """
    
    SYSTEM_PROMPT = """你是一位资深的艾略特波浪理论分析师，拥有20年技术分析经验。

分析原则：
1. 浪型识别要基于斐波那契比例和形态规则
2. 目标价预测要给出区间而非单点
3. 风险评估要量化（高/中/低）
4. 操作建议要明确（买入/观望/卖出）

输出格式必须是JSON，包含reasoning、conclusion、confidence字段。"""
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        wave_data = input_data.raw_data
        
        prompt = f"""
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
    "target_range": {{"low": 110, "high": 120}},
    "key_levels": {{"support": [105], "resistance": [125]}},
    "risk_level": "中风险",
    "action": "buy/hold/sell",
    "confidence": 0.85
}}
"""
        response = self._call_llm(prompt)
        return self._parse_response(response)
```

**能力**：
- ✅ 浪型可能性评估
- ✅ 目标价区间预测
- ✅ 斐波那契比例验证
- ✅ 风险收益比计算

---

### 2. PatternInterpreterAgent - 多指标综合解读

```python
class PatternInterpreterAgent(BaseAIAgent):
    """
    技术指标综合解读子代理
    
    输入：多个技术指标（MACD、RSI、KDJ、布林带等）
    输出：指标共振分析、综合买卖信号
    """
    
    SYSTEM_PROMPT = """你是一位技术分析专家，擅长多指标综合分析。

分析原则：
1. 重视指标共振（多个指标同向）
2. 警惕指标背离（价格与指标反向）
3. 超买超卖要结合趋势判断
4. 给出明确的综合评级

输出格式必须是JSON。"""
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        indicators = input_data.raw_data
        
        prompt = f"""
【技术指标数据】
MACD:
- DIF: {indicators.get('macd_dif', 0):.4f}
- DEA: {indicators.get('macd_dea', 0):.4f}  
- 柱状图: {indicators.get('macd_hist', 0):.4f}
- 状态: {indicators.get('macd_state', 'neutral')}

RSI:
- RSI6: {indicators.get('rsi6', 50):.2f}
- RSI12: {indicators.get('rsi12', 50):.2f}
- RSI24: {indicators.get('rsi24', 50):.2f}

KDJ:
- K: {indicators.get('k', 50):.2f}
- D: {indicators.get('d', 50):.2f}
- J: {indicators.get('j', 50):.2f}

布林带:
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

**能力**：
- ✅ 指标共振检测
- ✅ 背离识别
- ✅ 超买超卖判断
- ✅ 综合信号评级

---

### 3. MarketContextAgent - 市场环境分析

```python
class MarketContextAgent(BaseAIAgent):
    """
    市场环境分析子代理
    
    输入：全市场行业轮动数据
    输出：市场环境解读、板块机会分析
    """
    
    SYSTEM_PROMPT = """你是一位宏观策略分析师，擅长市场风格判断和板块轮动分析。

分析原则：
1. 基于动量数据判断市场风格
2. 识别资金流向和板块热点
3. 判断轮动节奏（适合追涨还是埋伏）
4. 给出配置建议和预警信号

输出格式必须是JSON。"""
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        rotation_data = input_data.raw_data
        
        prompt = f"""
【市场环境数据】
强势行业TOP5:
{rotation_data.get('strong_industries', [])}

弱势行业TOP5:  
{rotation_data.get('weak_industries', [])}

有买点的行业:
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

**能力**：
- ✅ 市场风格判断
- ✅ 板块轮动解读
- ✅ 资金流向分析
- ✅ 配置建议

---

### 4. StrategyAdvisorAgent - 策略顾问

```python
class StrategyAdvisorAgent(BaseAIAgent):
    """
    具体策略建议子代理
    
    输入：波浪分析+技术指标+市场环境
    输出：具体操作建议、仓位管理、止损止盈
    """
    
    SYSTEM_PROMPT = """你是一位量化交易策略师，擅长制定具体的交易计划。

分析原则：
1. 给出具体的入场价位区间
2. 明确仓位比例建议
3. 设置技术和时间双重止损
4. 制定分批止盈方案
5. 强调风险管控

输出格式必须是JSON。"""
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        context = input_data.context  # 整合前面的分析结果
        
        prompt = f"""
【综合分析背景】
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

**能力**：
- ✅ 具体操作建议
- ✅ 仓位管理建议
- ✅ 止损止盈设置
- ✅ 风险管控方案

---

## 主智能体集成

### WaveAnalystAgent 集成示例

```python
# agents/wave_analyst.py

class WaveAnalystAgent(BaseAgent):
    def __init__(self, config_path=None, use_ai=True, use_cache=True):
        super().__init__(config_path)
        self.use_ai = use_ai
        self.use_cache = use_cache
        
        # 初始化AI子代理
        if use_ai:
            self.wave_reasoner = WaveReasoningAgent()
            self.strategy_advisor = StrategyAdvisorAgent()
            
        # 初始化缓存
        if use_cache:
            self.ai_cache = {}  # 简单内存缓存
    
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """分析流程"""
        # 1. 技术分析（原有逻辑）
        wave_result = self.wave_analyzer.detect(df)
        
        if not self.use_ai:
            return self._format_basic_output(wave_result)
        
        # 2. 检查缓存
        cache_key = self._make_cache_key(input_data.symbol, wave_result)
        if self.use_cache and cache_key in self.ai_cache:
            ai_reasoning = self.ai_cache[cache_key]
        else:
            # 3. AI推理层
            ai_input = AIAgentInput(
                raw_data=wave_result,
                context=f"分析标的: {input_data.symbol}",
                market_state=self._detect_market_state(df)
            )
            ai_reasoning = self.wave_reasoner.analyze(ai_input)
            
            # 缓存结果
            if self.use_cache:
                self.ai_cache[cache_key] = ai_reasoning
        
        # 4. 策略建议层
        strategy_input = AIAgentInput(
            raw_data=wave_result,
            context=ai_reasoning.reasoning
        )
        strategy = self.strategy_advisor.analyze(strategy_input)
        
        # 5. 整合输出
        return AgentOutput(
            result={
                'technical': wave_result,
                'ai_reasoning': ai_reasoning,
                'strategy': strategy
            },
            confidence=ai_reasoning.confidence,
            metadata={
                'ai_enabled': True,
                'cached': cache_key in self.ai_cache if self.use_cache else False
            }
        )
```

---

## 适配器模式

### AIAdapter - 统一接口

```python
# agents/ai_subagents/adapter.py

class AIAdapter:
    """
    AI子代理适配器
    
    统一接口，简化主智能体调用
    """
    
    def __init__(self, use_ai: bool = True, use_cache: bool = True):
        self.use_ai = use_ai
        self.use_cache = use_cache
        
        if use_ai:
            self.agents = {
                'wave': WaveReasoningAgent(),
                'pattern': PatternInterpreterAgent(),
                'market': MarketContextAgent(),
                'strategy': StrategyAdvisorAgent()
            }
            self.cache = {}
    
    def enhance_wave_analysis(self, wave_data: dict, symbol: str) -> Optional[dict]:
        """增强波浪分析"""
        if not self.use_ai:
            return None
            
        cache_key = f"wave_{symbol}_{hash(str(wave_data))}"
        if self.use_cache and cache_key in self.cache:
            return self.cache[cache_key]
        
        input_data = AIAgentInput(
            raw_data=wave_data,
            context=f"标的: {symbol}"
        )
        
        result = self.agents['wave'].analyze(input_data)
        
        if self.use_cache:
            self.cache[cache_key] = result
        
        return {
            'reasoning': result.reasoning,
            'conclusion': result.conclusion,
            'confidence': result.confidence,
            'target_range': result.target_range,
            'action': result.action_suggestion
        }
    
    def enhance_rotation_analysis(self, rotation_data: dict) -> Optional[dict]:
        """增强轮动分析"""
        if not self.use_ai:
            return None
        
        input_data = AIAgentInput(
            raw_data=rotation_data,
            context="全市场行业轮动分析"
        )
        
        result = self.agents['market'].analyze(input_data)
        
        return {
            'market_style': result.conclusion,
            'confidence': result.confidence,
            'rotation_rhythm': result.action_suggestion
        }
```

---

## 成本与性能优化

### 1. 缓存策略

```python
class AICache:
    """AI推理缓存"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache = {}
        self.ttl = ttl_hours * 3600
    
    def get(self, key: str) -> Optional[AIAgentOutput]:
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry['timestamp'] > self.ttl:
            del self.cache[key]
            return None
        
        return entry['data']
    
    def set(self, key: str, value: AIAgentOutput):
        self.cache[key] = {
            'data': value,
            'timestamp': time.time()
        }
```

### 2. 异步处理

```python
async def analyze_async(self, input_data: AIAgentInput) -> AIAgentOutput:
    """异步分析，避免阻塞"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, self.analyze, input_data
    )
```

### 3. 成本预估

| 使用场景 | 单次调用 | 日调用量 | 日成本 |
|---------|---------|---------|--------|
| 单股分析 | ¥0.05 | 100次 | ¥5 |
| 批量分析 | ¥0.03 | 500次 | ¥15 |
| 行业轮动 | ¥0.08 | 10次 | ¥0.8 |

**优化后（带缓存）**：成本降低60-80%

---

## 风险提示

1. **API成本**：LLM调用有成本，需添加缓存机制
2. **延迟增加**：AI推理需要时间，异步处理或缓存必要
3. **幻觉问题**：LLM可能产生不合理推理，需置信度阈值过滤
4. **合规性**：投资建议需免责声明，AI建议仅供参考

---

## 实施状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 基础设施 | ✅ 完成 | BaseAIAgent、适配器实现 |
| WaveReasoningAgent | ✅ 完成 | 波浪形态推理 |
| PatternInterpreterAgent | 🔄 进行中 | 指标综合解读 |
| MarketContextAgent | 🔄 进行中 | 市场环境分析 |
| StrategyAdvisorAgent | ⏳ 待开始 | 策略顾问 |
| 缓存优化 | ✅ 完成 | 内存缓存实现 |
| 异步处理 | ⏳ 待开始 | asyncio支持 |

---

*最后更新：2026-03-21*
