"""
analysis/strategy — 交易策略模块

主要类：
    AShareStrategy      基础中线策略
    MultiStyleStrategy  多风格策略（短线/波段/中线 + 组合风控）
    TradingStyle        交易风格枚举
    AShareBacktester    单股回测
    AShareBatchBacktester 批量回测
    AShareSignalDetector  多风格信号检测
"""
from .ashare_strategy import AShareStrategy, AShareSignal, AShareTrade, SignalType
from .ashare_backtester import AShareBacktester, AShareBacktestResult
from .ashare_batch import AShareBatchBacktester
from .style import TradingStyle, StyleConfig, get_style_config, STYLE_CONFIGS
from .multi_style import MultiStyleStrategy, PortfolioRiskState
from .signal_detector import AShareSignalDetector, ExtendedSignalType

__all__ = [
    "AShareStrategy", "AShareSignal", "AShareTrade", "SignalType",
    "AShareBacktester", "AShareBacktestResult",
    "AShareBatchBacktester",
    "TradingStyle", "StyleConfig", "get_style_config", "STYLE_CONFIGS",
    "MultiStyleStrategy", "PortfolioRiskState",
    "AShareSignalDetector", "ExtendedSignalType",
]
