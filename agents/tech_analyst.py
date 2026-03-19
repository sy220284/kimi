"""
智能体框架 - 技术分析师智能体 (AI增强版)
集成AI子代理提供多指标综合解读
"""
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from analysis.technical.indicators import TechnicalIndicators

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class TechAnalystAgent(BaseAgent):
    """
    技术分析师智能体
    
    功能:
    1. 基础技术分析（MACD/RSI/KDJ/布林带等）
    2. AI推理增强（PatternInterpreterAgent）- 提供指标共振分析和综合建议
    
    使用AI增强:
        agent = TechAnalystAgent(use_ai=True, ai_model="deepseek/deepseek-chat")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        use_ai: bool = False,
        ai_model: str = "deepseek/deepseek-chat"
    ):
        """
        初始化技术分析师

        Args:
            config_path: 配置文件路径
            use_ai: 是否启用AI子代理增强
            ai_model: AI模型选择
        """
        super().__init__(
            agent_name="technical_analyst",
            analysis_type=AnalysisType.TECHNICAL,
            config_path=config_path
        )

        self.indicators = TechnicalIndicators()
        
        # AI子代理
        self.use_ai = use_ai
        self.ai_agent = None
        if use_ai:
            try:
                from agents.ai_subagents import PatternInterpreterAgent
                self.ai_agent = PatternInterpreterAgent(model=ai_model)
                self.logger.info(f"AI子代理已启用: {ai_model}")
            except Exception as e:
                self.logger.warning(f"AI子代理初始化失败: {e}")
                self.use_ai = False

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行技术分析

        Args:
            input_data: 输入数据

        Returns:
            分析结果（包含技术分析和AI推理）
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

            # 1. 计算技术指标
            df_with_indicators = self._calculate_indicators(df)

            # 2. 获取交易信号
            signals = self.indicators.get_all_signals(df_with_indicators)
            combined = self.indicators.get_combined_signal(df_with_indicators)
            latest = df_with_indicators.iloc[-1] if len(df_with_indicators) > 0 else None

            # 准备基础结果
            base_result = {
                'signals': signals,
                'combined_signal': combined,
                'latest': latest.to_dict() if latest is not None else {},
                'data_points': len(df),
                'status': 'success'
            }
            
            # 3. AI推理增强
            ai_result = None
            if self.use_ai and self.ai_agent and latest is not None:
                try:
                    from agents.ai_subagents import AIAgentInput
                    
                    # 提取指标数据
                    indicator_data = {
                        # MACD
                        'macd_dif': float(latest.get('macd_dif', 0)),
                        'macd_dea': float(latest.get('macd_dea', 0)),
                        'macd_hist': float(latest.get('macd_hist', 0)),
                        'macd_state': self._get_macd_state(latest),
                        # RSI
                        'rsi6': float(latest.get('rsi_6', 50)),
                        'rsi12': float(latest.get('rsi_12', 50)),
                        'rsi24': float(latest.get('rsi_24', 50)),
                        # KDJ (如果有)
                        'kdj_k': float(latest.get('kdj_k', 50)),
                        'kdj_d': float(latest.get('kdj_d', 50)),
                        'kdj_j': float(latest.get('kdj_j', 50)),
                        # 布林带
                        'boll_upper': float(latest.get('boll_upper', 0)),
                        'boll_mid': float(latest.get('boll_mid', 0)),
                        'boll_lower': float(latest.get('boll_lower', 0)),
                        'boll_width': float(latest.get('boll_width', 0)),
                        # 均线
                        'ma5': float(latest.get('ma_5', 0)),
                        'ma10': float(latest.get('ma_10', 0)),
                        'ma20': float(latest.get('ma_20', 0)),
                        'ma60': float(latest.get('ma_60', 0)),
                        # 成交量
                        'volume': float(latest.get('volume', 0)),
                        'volume_ma5': float(latest.get('volume_ma5', 0)),
                        'volume_ratio': float(latest.get('volume_ratio', 1)),
                    }
                    
                    ai_input = AIAgentInput(
                        raw_data=indicator_data,
                        context=f"分析标的: {symbol}, 最新价: {latest.get('close', 0)}"
                    )
                    
                    ai_output = self.ai_agent.analyze(ai_input)
                    
                    ai_result = {
                        'reasoning': ai_output.reasoning,
                        'conclusion': ai_output.conclusion,
                        'confidence': ai_output.confidence,
                        'action_suggestion': ai_output.action_suggestion,
                        'details': ai_output.details
                    }
                    
                    base_result['ai_analysis'] = ai_result
                    
                except Exception as e:
                    self.logger.warning(f"AI分析失败: {e}")
                    base_result['ai_error'] = str(e)

            # 计算最终置信度
            base_confidence = abs(combined.get('score', 0)) if isinstance(combined, dict) else 0.5
            if ai_result and ai_result.get('confidence'):
                final_confidence = (base_confidence + ai_result['confidence']) / 2
            else:
                final_confidence = min(base_confidence, 1.0)

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result=base_result,
                confidence=final_confidence,
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
    
    def _get_macd_state(self, latest: pd.Series) -> str:
        """获取MACD状态描述"""
        dif = latest.get('macd_dif', 0)
        dea = latest.get('macd_dea', 0)
        hist = latest.get('macd_hist', 0)
        
        if dif > dea and hist > 0:
            return "多头(金叉后)"
        elif dif < dea and hist < 0:
            return "空头(死叉后)"
        elif dif > dea:
            return "多头区域"
        else:
            return "空头区域"

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
