"""
AI推理子代理基类模块
提供统一的LLM调用接口和输出解析
"""
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class AIAgentInput:
    """AI子代理输入"""
    raw_data: dict          # 技术分析原始输出
    context: str            # 市场上下文
    user_query: Optional[str] = None  # 用户具体问题


@dataclass
class AIAgentOutput:
    """AI子代理输出"""
    reasoning: str          # AI推理过程
    conclusion: str         # 结论
    confidence: float       # 置信度 (0-1)
    action_suggestion: Optional[str] = None  # 操作建议
    details: Optional[dict] = None  # 额外详情


class BaseAIAgent(ABC):
    """
    AI推理子代理基类
    
    支持多模型后端:
    - codeflow: Claude系列 (Haiku/Sonnet/Opus)
    - deepseek: DeepSeek系列 (Chat/Reasoner)
    """
    
    def __init__(
        self,
        agent_name: str,
        model: str = "deepseek/deepseek-reasoner",
        thinking: str = "high",
        timeout: int = 120
    ):
        self.agent_name = agent_name
        self.model = model
        self.thinking = thinking
        self.timeout = timeout
        
        # 解析模型提供商
        if "/" in model:
            self.provider, self.model_id = model.split("/", 1)
        else:
            self.provider = "deepseek"
            self.model_id = model
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从环境变量加载API配置"""
        if self.provider == "codeflow":
            self.base_url = os.environ.get("CODEFLOW_BASE_URL", "https://codeflow.asia")
            self.api_key = os.environ.get("CODEFLOW_API_KEY", "")
        elif self.provider == "deepseek":
            self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        else:
            raise ValueError(f"不支持的模型提供商: {self.provider}")
    
    @abstractmethod
    def build_prompt(self, input_data: AIAgentInput) -> str:
        """
        构建Prompt
        
        Args:
            input_data: 输入数据
            
        Returns:
            完整的prompt字符串
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: str) -> AIAgentOutput:
        """
        解析LLM响应
        
        Args:
            response: LLM原始输出
            
        Returns:
            结构化的AIAgentOutput
        """
        pass
    
    def analyze(self, input_data: AIAgentInput) -> AIAgentOutput:
        """
        执行AI分析
        
        Args:
            input_data: 输入数据
            
        Returns:
            AI分析结果
        """
        prompt = self.build_prompt(input_data)
        
        try:
            response = self._call_llm(prompt)
            return self.parse_response(response)
        except Exception as e:
            # 返回降级输出
            return AIAgentOutput(
                reasoning=f"AI分析失败: {e}",
                conclusion="无法提供AI分析结论",
                confidence=0.0,
                action_suggestion=None
            )
    
    def _call_llm(self, prompt: str) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 提示词
            
        Returns:
            LLM响应文本
        """
        if not self.api_key:
            raise ValueError(f"API Key未设置: {self.provider}")
        
        if self.provider == "codeflow":
            return self._call_codeflow(prompt)
        elif self.provider == "deepseek":
            return self._call_deepseek(prompt)
        else:
            raise ValueError(f"不支持的提供商: {self.provider}")
    
    def _call_codeflow(self, prompt: str) -> str:
        """调用CodeFlow API (Claude系列)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096 if "haiku" in self.model_id else 8192,
            "temperature": 0.3  # 低温度确保输出稳定
        }
        
        # 根据thinking级别调整
        if self.thinking == "high":
            payload["temperature"] = 0.7  # 更多创造性
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _call_deepseek(self, prompt: str) -> str:
        """调用DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.3
        }
        
        # Reasoner模型使用特殊参数
        if "reasoner" in self.model_id:
            payload["temperature"] = 0.6  # 推理模型需要更多探索
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]


class AIAgentRegistry:
    """
    AI子代理注册表
    管理所有AI子代理实例
    """
    
    _agents: dict[str, BaseAIAgent] = {}
    
    @classmethod
    def register(cls, name: str, agent: BaseAIAgent):
        """注册子代理"""
        cls._agents[name] = agent
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseAIAgent]:
        """获取子代理"""
        return cls._agents.get(name)
    
    @classmethod
    def list_agents(cls) -> list[str]:
        """列出所有已注册子代理"""
        return list(cls._agents.keys())


def parse_json_response(response: str) -> dict:
    """
    从LLM响应中提取JSON
    
    处理以下格式:
    1. 纯JSON: {"key": "value"}
    2. Markdown代码块: ```json\n{...}\n```
    3. 文本+JSON混合
    
    Args:
        response: LLM原始响应
        
    Returns:
        解析后的字典
    """
    import re
    
    # 尝试直接解析
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        pass
    
    # 提取Markdown代码块
    code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(code_block_pattern, response, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    # 尝试提取花括号内容
    brace_pattern = r'\{.*\}'
    match = re.search(brace_pattern, response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # 返回空字典
    return {}
