"""
智能体框架 - 技术分析师智能体 (简化版，无外部依赖)
"""
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent, AgentInput, AgentOutput, AnalysisType, AgentState
from analysis.technical.indicators import TechnicalIndicators


class TechAnalystAgent(BaseAgent):
    """技术分析师智能体 - 简化版"""
    
    def __init__(self, config_path: Optional[Path] = None):
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
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        执行技术分析
        
        Args:
            df: 股票数据DataFrame
            
        Returns:
            分析结果字典
        """
        if df is None or df.empty:
            return {'signals': [], 'error': '无数据'}
        
        try:
            # 计算技术指标
            df_with_indicators = self._calculate_indicators(df)
            
            # 获取交易信号
            signals = self.indicators.get_all_signals(df_with_indicators)
            
            # 获取综合信号
            combined = self.indicators.get_combined_signal(df_with_indicators)
            
            # 获取最新指标值
            latest = df_with_indicators.iloc[-1] if len(df_with_indicators) > 0 else None
            
            return {
                'signals': signals,
                'combined_signal': combined,
                'latest': latest.to_dict() if latest is not None else {},
                'data_points': len(df),
                'status': 'success'
            }
            
        except Exception as e:
            self.logger.error(f"技术分析失败: {e}")
            return {'signals': [], 'error': str(e)}
    
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
