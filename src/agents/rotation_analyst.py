"""
智能体框架 - 轮动分析师智能体 (简化版，无外部依赖)
分析行业轮动和板块轮动机会
"""
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class RotationAnalystAgent(BaseAgent):
    """轮动分析师智能体 - 简化版"""

    def __init__(self, config_path: Path | None = None):
        """
        初始化轮动分析师

        Args:
            config_path: 配置文件路径
        """
        super().__init__(
            agent_name="rotation_analyst",
            analysis_type=AnalysisType.ROTATION,
            config_path=config_path
        )

        self.lookback_period = 60
        self.momentum_period = 20

    def analyze(self, input_data: AgentInput | None = None) -> AgentOutput:
        """
        执行轮动分析

        Args:
            input_data: 可选的输入数据（轮动分析不需要特定symbol）

        Returns:
            分析结果
        """
        start_time = time.time()

        try:
            from data.optimized_data_manager import get_optimized_data_manager

            data_mgr = get_optimized_data_manager()
            df_all = data_mgr.load_all_data()

            if df_all.empty:
                return AgentOutput(
                    agent_type=self.analysis_type.value,
                    symbol='MARKET',
                    analysis_date=datetime.now().strftime('%Y-%m-%d'),
                    result={'status': 'no_data', 'sectors': {}},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=time.time() - start_time,
                    error_message='无数据'
                )

            # 按板块分类统计
            sectors = {
                '科创板': df_all[df_all['symbol'].str.startswith('688', na=False)]['symbol'].nunique(),
                '创业板': df_all[df_all['symbol'].str.startswith('300', na=False)]['symbol'].nunique(),
                '上海主板': df_all[df_all['symbol'].str.startswith('60', na=False)]['symbol'].nunique(),
                '深圳主板': df_all[df_all['symbol'].str.startswith('00', na=False)]['symbol'].nunique(),
            }

            # 计算各板块近期表现
            sector_performance = {}
            for sector_name, symbols in [
                ('科创板', df_all[df_all['symbol'].str.startswith('688', na=False)]['symbol'].unique()),
                ('创业板', df_all[df_all['symbol'].str.startswith('300', na=False)]['symbol'].unique()),
            ]:
                if len(symbols) > 0:
                    # 取前5只计算平均表现
                    sample_symbols = symbols[:5]
                    returns = []
                    for symbol in sample_symbols:
                        df = data_mgr.get_stock_data(symbol)
                        if df is not None and len(df) > 20:
                            df = data_mgr.calculate_returns(df)
                            recent_return = df['daily_return'].tail(20).mean() * 100
                            if not pd.isna(recent_return):
                                returns.append(recent_return)

                    if returns:
                        sector_performance[sector_name] = np.mean(returns)

            # 计算置信度（基于数据完整性）
            confidence = min(len(sector_performance) / 4, 1.0)

            strong_sectors = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)[:2]
            weak_sectors = sorted(sector_performance.items(), key=lambda x: x[1])[:2]

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol='MARKET',
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={
                    'status': 'success',
                    'sectors': sectors,
                    'sector_performance': sector_performance,
                    'strong_sectors': strong_sectors,
                    'weak_sectors': weak_sectors,
                },
                confidence=confidence,
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )

        except Exception as e:
            self.logger.error(f"轮动分析失败: {e}")
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol='MARKET',
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={'status': 'error', 'message': str(e)},
                confidence=0.0,
                state=AgentState.ERROR,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )

    def analyze_market_rotation(self) -> AgentOutput:
        """市场轮动分析"""
        return self.analyze()


# 保持向后兼容
RotationAnalyst = RotationAnalystAgent
