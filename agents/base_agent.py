"""
智能体框架 - 智能体基类
定义通用接口
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from utils.config_loader import load_config
from utils.logger import get_logger


class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class AnalysisType(Enum):
    """分析类型"""
    WAVE = "wave"
    TECHNICAL = "technical"
    ROTATION = "rotation"


@dataclass
class AgentInput:
    """智能体输入数据"""
    symbol: str  # 股票代码
    start_date: str | None = None
    end_date: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    """智能体输出数据"""
    agent_type: str
    symbol: str
    analysis_date: str
    result: dict[str, Any]
    confidence: float
    state: AgentState
    execution_time: float  # 执行时间（秒）
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'agent_type': self.agent_type,
            'symbol': self.symbol,
            'analysis_date': self.analysis_date,
            'result': self.result,
            'confidence': self.confidence,
            'state': self.state.value,
            'execution_time': round(self.execution_time, 4),
            'error_message': self.error_message
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(
        self,
        agent_name: str,
        analysis_type: AnalysisType,
        config_path: Path | None = None
    ):
        """
        初始化智能体基类

        Args:
            agent_name: 智能体名称
            analysis_type: 分析类型
            config_path: 配置文件路径
        """
        self.agent_name = agent_name
        self.analysis_type = analysis_type
        self.config = load_config(config_path)
        self.logger = get_logger(f'agent.{agent_name}')
        self.state = AgentState.IDLE
        self._execution_start: datetime | None = None

    @abstractmethod
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行分析（子类必须实现）

        Args:
            input_data: 输入数据

        Returns:
            分析结果
        """
        pass

    def pre_process(self, input_data: AgentInput) -> AgentInput:
        """
        预处理输入数据

        Args:
            input_data: 原始输入

        Returns:
            处理后的输入
        """
        # 设置默认日期
        if not input_data.end_date:
            input_data.end_date = datetime.now().strftime('%Y-%m-%d')

        return input_data

    def post_process(self, output: AgentOutput) -> AgentOutput:
        """
        后处理输出结果

        Args:
            output: 原始输出

        Returns:
            处理后的输出
        """
        return output

    def run(self, input_data: AgentInput) -> AgentOutput:
        """
        运行智能体（完整流程）

        Args:
            input_data: 输入数据

        Returns:
            分析结果
        """
        import time

        start_time = time.time()
        self._execution_start = datetime.now()
        self.state = AgentState.RUNNING

        try:
            # 预处理
            input_data = self.pre_process(input_data)

            # 执行分析
            self.logger.info(f"开始分析 {input_data.symbol}")
            output = self.analyze(input_data)

            # 后处理
            output = self.post_process(output)

            # 更新状态
            self.state = AgentState.COMPLETED
            output.state = AgentState.COMPLETED

            self.logger.info(
                f"分析完成 {input_data.symbol}, 置信度: {output.confidence:.2f}"
            )

        except Exception as e:
            self.state = AgentState.ERROR
            execution_time = time.time() - start_time

            self.logger.error(f"分析失败 {input_data.symbol}: {e}")

            output = AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=input_data.symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={},
                confidence=0.0,
                state=AgentState.ERROR,
                execution_time=execution_time,
                error_message=str(e)
            )

        return output

    def run_batch(
        self,
        inputs: list[AgentInput]
    ) -> list[AgentOutput]:
        """
        批量运行

        Args:
            inputs: 输入数据列表

        Returns:
            分析结果列表
        """
        outputs = []

        for input_data in inputs:
            try:
                output = self.run(input_data)
                outputs.append(output)
            except Exception as e:
                self.logger.error(f"批量分析失败 {input_data.symbol}: {e}")
                outputs.append(AgentOutput(
                    agent_type=self.analysis_type.value,
                    symbol=input_data.symbol,
                    analysis_date=datetime.now().strftime('%Y-%m-%d'),
                    result={},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=0.0,
                    error_message=str(e)
                ))

        return outputs

    def get_state(self) -> AgentState:
        """获取当前状态"""
        return self.state

    def is_ready(self) -> bool:
        """检查智能体是否就绪"""
        return self.state in [AgentState.IDLE, AgentState.COMPLETED, AgentState.ERROR]

    def reset(self) -> None:
        """重置智能体状态"""
        self.state = AgentState.IDLE
        self._execution_start = None
        self.logger.info(f"智能体 {self.agent_name} 已重置")

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        return self.config.get(key, default)

    def validate_input(self, input_data: AgentInput) -> bool:
        """
        验证输入数据

        Args:
            input_data: 输入数据

        Returns:
            是否有效
        """
        if not input_data.symbol:
            self.logger.error("股票代码不能为空")
            return False

        return True

    def save_result(
        self,
        output: AgentOutput,
        storage_path: Path | None = None
    ) -> None:
        """
        保存分析结果

        Args:
            output: 分析结果
            storage_path: 存储路径
        """
        if storage_path is None:
            storage_path = Path(__file__).parent.parent.parent / "data" / "results"

        storage_path.mkdir(parents=True, exist_ok=True)

        filename = f"{output.agent_type}_{output.symbol}_{output.analysis_date}.json"
        filepath = storage_path / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(output.to_json())

        self.logger.info(f"结果已保存: {filepath}")
