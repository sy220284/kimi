"""
智能体框架 - 轮动分析师智能体 (简化版，无外部依赖)
分析行业轮动和板块轮动机会
"""
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent, AgentInput, AgentOutput, AnalysisType, AgentState


class RotationAnalystAgent(BaseAgent):
    """轮动分析师智能体 - 简化版"""
    
    def __init__(self, config_path: Optional[Path] = None):
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
    
    def analyze(self, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行轮动分析
        
        Args:
            data: 可选的分析数据
            
        Returns:
            分析结果字典
        """
        try:
            from data.optimized_data_manager import get_optimized_data_manager
            
            data_mgr = get_optimized_data_manager()
            df_all = data_mgr.load_all_data()
            
            if df_all.empty:
                return {'status': 'no_data', 'sectors': {}}
            
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
                            recent_return = df['returns'].tail(20).mean() * 100
                            if not pd.isna(recent_return):
                                returns.append(recent_return)
                    
                    if returns:
                        sector_performance[sector_name] = np.mean(returns)
            
            return {
                'status': 'success',
                'sectors': sectors,
                'sector_performance': sector_performance,
                'strong_sectors': sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)[:2],
                'weak_sectors': sorted(sector_performance.items(), key=lambda x: x[1])[:2],
            }
            
        except Exception as e:
            self.logger.error(f"轮动分析失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def analyze_market_rotation(self) -> Dict[str, Any]:
        """市场轮动分析"""
        return self.analyze()


# 保持向后兼容
RotationAnalyst = RotationAnalystAgent
