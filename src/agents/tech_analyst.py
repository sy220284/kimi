"""
智能体框架 - 技术分析师智能体 (简化版，无外部依赖)
"""
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.technical.indicators import TechnicalIndicators

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class TechAnalystAgent(BaseAgent):
    """技术分析师智能体 - 简化版"""

    def __init__(self, config_path: Path | None = None):
        """
        初始化技术分析师

        Args:
            config_path: 配置文件路径
        """
        super().__init__(
            agent_name="technical_analyst",
            analysis_type=AnalysisType.TECHNICAL,
            config_path=config_path
        )

        self.indicators = TechnicalIndicators()

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行技术分析

        Args:
            input_data: 输入数据

        Returns:
            分析结果
        """
        from data.optimized_data_manager import get_optimized_data_manager

        start_time = time.time()
        symbol = input_data.symbol

        try:
            # 获取数据
            data_mgr = get_optimized_data_manager()
            df = data_mgr.get_stock_data(symbol)

            # 应用日期过滤
            if input_data.start_date and df is not None and not df.empty:
                df = df[df['date'] >= input_data.start_date].copy()
            if input_data.end_date and df is not None and not df.empty:
                df = df[df['date'] <= input_data.end_date].copy()

            if df is None or df.empty:
                return AgentOutput(
                    agent_type=self.analysis_type.value,
                    symbol=symbol,
                    analysis_date=datetime.now().strftime('%Y-%m-%d'),
                    result={'signals': [], 'error': '无数据'},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=time.time() - start_time,
                    error_message='无数据'
                )

            # 计算技术指标
            df_with_indicators = self._calculate_indicators(df)

            # 获取交易信号
            signals = self.indicators.get_all_signals(df_with_indicators)

            # 获取综合信号
            combined = self.indicators.get_combined_signal(df_with_indicators)

            # 获取最新指标值
            latest = df_with_indicators.iloc[-1] if len(df_with_indicators) > 0 else None

            # 计算置信度（基于信号强度）
            confidence = abs(combined.get('score', 0)) if isinstance(combined, dict) else 0.5

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={
                    'signals': signals,
                    'combined_signal': combined,
                    'latest': latest.to_dict() if latest is not None else {},
                    'data_points': len(df),
                    'status': 'success'
                },
                confidence=min(confidence, 1.0),
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )

        except Exception as e:
            self.logger.error(f"技术分析失败 {symbol}: {e}")
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={'signals': [], 'error': str(e)},
                confidence=0.0,
                state=AgentState.ERROR,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标

        Args:
            df: 原始数据

        Returns:
            包含指标的DataFrame
        """
        # 使用优化数据管理器计算指标
        from data.optimized_data_manager import get_optimized_data_manager

        data_mgr = get_optimized_data_manager()

        # 计算基础指标
        df = data_mgr.calculate_ma(df, 5)
        df = data_mgr.calculate_ma(df, 10)
        df = data_mgr.calculate_ma(df, 20)
        df = data_mgr.calculate_ema(df, 12)
        df = data_mgr.calculate_ema(df, 26)
        df = data_mgr.calculate_returns(df)
        df = data_mgr.calculate_rsi(df, 6)
        df = data_mgr.calculate_rsi(df, 14)
        df = data_mgr.calculate_rsi(df, 24)
        df = data_mgr.calculate_macd(df)
        df = data_mgr.calculate_bollinger(df)

        return df


# 保持向后兼容
TechAnalyst = TechAnalystAgent
