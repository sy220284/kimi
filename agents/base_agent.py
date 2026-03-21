"""
agents/base_agent.py — 智能体基类（新系统版）

适配新系统：
  - AnalysisType 换为 REGIME/FACTOR/SIGNAL/BACKTEST
  - ActionRecommendation: BUY/WATCH/HOLD/AVOID
  - AgentInput 接收 DataFrame，不再依赖旧数据层
  - 移除旧 Wave/Technical/Rotation 引用
"""
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from utils.config_loader import load_config
from utils.logger import get_logger


class AgentState(Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    COMPLETED = "completed"
    ERROR     = "error"


class AnalysisType(Enum):
    """分析类型（对应新系统四层）"""
    REGIME   = "regime"
    FACTOR   = "factor"
    SIGNAL   = "signal"
    BACKTEST = "backtest"


class ActionRecommendation(Enum):
    """操作建议"""
    BUY   = "BUY"
    WATCH = "WATCH"
    HOLD  = "HOLD"
    AVOID = "AVOID"


@dataclass
class AgentInput:
    """Agent 输入"""
    symbol:     str
    df:         pd.DataFrame | None = None
    start_date: str | None = None
    end_date:   str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.end_date:
            self.end_date = datetime.now().strftime("%Y-%m-%d")


@dataclass
class AgentOutput:
    """Agent 输出"""
    agent_type:     str
    symbol:         str
    analysis_date:  str
    action:         str
    confidence:     float
    reason:         str
    result:         dict[str, Any]
    state:          AgentState
    execution_time: float
    error_message:  str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type":     self.agent_type,
            "symbol":         self.symbol,
            "analysis_date":  self.analysis_date,
            "action":         self.action,
            "confidence":     self.confidence,
            "reason":         self.reason,
            "result":         self.result,
            "state":          self.state.value,
            "execution_time": round(self.execution_time, 4),
            "error_message":  self.error_message,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class BaseAgent(ABC):
    """
    A股智能分析 Agent 基类

    子类只需实现 analyze(input_data) -> AgentOutput
    基类提供 run() / run_batch() / validate_input() / save_result()
    """

    def __init__(self, agent_name: str, analysis_type: AnalysisType,
                 config_path: Path | None = None):
        self.agent_name    = agent_name
        self.analysis_type = analysis_type
        self.config        = load_config(config_path)
        self.logger        = get_logger(f"agent.{agent_name}")
        self.state         = AgentState.IDLE

    @abstractmethod
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """执行分析，子类实现"""

    def run(self, input_data: AgentInput) -> AgentOutput:
        t0 = time.time()
        self.state = AgentState.RUNNING
        try:
            if not self.validate_input(input_data):
                raise ValueError(f"输入校验失败: {input_data.symbol}")
            input_data = self.pre_process(input_data)
            self.logger.info(f"开始分析 {input_data.symbol}")
            output = self.analyze(input_data)
            output = self.post_process(output)
            self.state = AgentState.COMPLETED
            output.state = AgentState.COMPLETED
            output.execution_time = time.time() - t0
            self.logger.info(f"完成 {input_data.symbol} action={output.action} conf={output.confidence:.2f}")
        except Exception as e:
            self.state = AgentState.ERROR
            self.logger.error(f"失败 {input_data.symbol}: {e}")
            output = AgentOutput(
                agent_type=self.analysis_type.value, symbol=input_data.symbol,
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                action=ActionRecommendation.AVOID.value, confidence=0.0,
                reason=str(e), result={}, state=AgentState.ERROR,
                execution_time=time.time()-t0, error_message=str(e))
        return output

    def run_batch(self, inputs: list[AgentInput]) -> list[AgentOutput]:
        return [self.run(inp) for inp in inputs]

    def pre_process(self, inp: AgentInput) -> AgentInput: return inp
    def post_process(self, out: AgentOutput) -> AgentOutput: return out

    def validate_input(self, input_data: AgentInput) -> bool:
        if not input_data.symbol:
            self.logger.error("股票代码不能为空"); return False
        return True

    def get_state(self) -> AgentState: return self.state
    def is_ready(self) -> bool: return self.state != AgentState.RUNNING
    def reset(self) -> None: self.state = AgentState.IDLE

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def save_result(self, output: AgentOutput, storage_path: Path | None = None) -> None:
        p = storage_path or Path("results")
        p.mkdir(parents=True, exist_ok=True)
        fname = f"{output.agent_type}_{output.symbol}_{output.analysis_date}.json"
        (p / fname).write_text(output.to_json(), encoding="utf-8")
        self.logger.debug(f"结果已保存: {p/fname}")
