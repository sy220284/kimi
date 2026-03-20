"""
AI推理子代理基类模块
提供统一的LLM调用接口和输出解析
支持自动重试机制处理超时和限流
P1-B: 新增 Redis 结果缓存，TTL=86400s（24h），相同分析不重复调用 LLM
"""
import hashlib
import json
import os
import time
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

    def _cache_key(self, input_data: 'AIAgentInput') -> str:
        """生成 Redis 缓存 Key（基于 agent_name + raw_data + context 的哈希）"""
        payload = json.dumps({
            "agent": self.agent_name,
            "model": self.model_id,
            "data": input_data.raw_data,
            "ctx": input_data.context,
        }, sort_keys=True, ensure_ascii=False, default=str)
        return f"ai_cache:{hashlib.md5(payload.encode()).hexdigest()}"

    def _get_redis(self):
        """获取 Redis 连接（可选依赖，失败时静默跳过缓存）"""
        try:
            from utils.config_manager import config as cfg_mgr
            redis_cfg = cfg_mgr.get('core.database.redis', {})
            import redis
            r = redis.Redis(
                host=redis_cfg.get('host', 'localhost'),
                port=redis_cfg.get('port', 6379),
                db=redis_cfg.get('db', 0),
                password=redis_cfg.get('password') or None,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            r.ping()
            return r
        except Exception:
            return None

    def analyze(self, input_data: 'AIAgentInput') -> 'AIAgentOutput':
        """
        执行AI分析（含 Redis 结果缓存，TTL=86400s）

        缓存策略：
        - Key = md5(agent_name + model + raw_data + context)
        - 命中缓存时直接返回，不调用 LLM
        - Redis 不可用时自动降级为直接调用
        - 缓存 TTL 通过 AI_CACHE_TTL 环境变量配置（默认 86400s）
        """
        cache_ttl = int(os.environ.get("AI_CACHE_TTL", "86400"))
        cache_key = self._cache_key(input_data)

        # 尝试读缓存
        redis_client = self._get_redis()
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return AIAgentOutput(
                        reasoning=data.get("reasoning", ""),
                        conclusion=data.get("conclusion", ""),
                        confidence=data.get("confidence", 0.0),
                        action_suggestion=data.get("action_suggestion"),
                        details=data.get("details"),
                    )
            except Exception:
                pass  # 缓存读取失败，继续正常调用

        # 调用 LLM
        prompt = self.build_prompt(input_data)
        try:
            response = self._call_llm(prompt)
            result = self.parse_response(response)
        except Exception as e:
            return AIAgentOutput(
                reasoning=f"AI分析失败: {e}",
                conclusion="无法提供AI分析结论",
                confidence=0.0,
                action_suggestion=None
            )

        # 写缓存
        if redis_client:
            try:
                redis_client.setex(
                    cache_key,
                    cache_ttl,
                    json.dumps({
                        "reasoning": result.reasoning,
                        "conclusion": result.conclusion,
                        "confidence": result.confidence,
                        "action_suggestion": result.action_suggestion,
                        "details": result.details,
                    }, ensure_ascii=False, default=str)
                )
            except Exception:
                pass  # 缓存写入失败不影响结果

        return result

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
        """
        调用CodeFlow API (Claude系列)
        带重试机制处理超时和限流
        """
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

        # 重试配置
        max_retries = 3
        base_delay = 2  # 基础延迟秒数

        last_exception = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                    continue
                raise last_exception

            except requests.exceptions.HTTPError as e:
                last_exception = e
                # 检查是否限流 (429)
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise last_exception

            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise last_exception

        raise last_exception if last_exception else RuntimeError("调用失败")

    def _call_deepseek(self, prompt: str) -> str:
        """
        调用DeepSeek API
        带重试机制处理超时和限流
        """
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

        # 重试配置
        max_retries = 3
        base_delay = 2  # 基础延迟秒数

        last_exception = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()

                result = response.json()
                return result["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                    continue
                raise last_exception

            except requests.exceptions.HTTPError as e:
                last_exception = e
                # 检查是否限流 (429)
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise last_exception

            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise last_exception

        raise last_exception if last_exception else RuntimeError("调用失败")


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
