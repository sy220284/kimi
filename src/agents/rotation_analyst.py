"""
智能体框架 - 轮动分析师智能体
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
from data.data_collector import DataCollector


class RotationAnalystAgent(BaseAgent):
    """轮动分析师智能体"""
    
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
        
        # 获取轮动分析配置
        rotation_config = self.config.get('analysis', {}).get('rotation_analyst', {})
        
        self.lookback_period = rotation_config.get('lookback_period', 60)
        self.momentum_period = rotation_config.get('momentum_period', 20)
        
        self.data_collector = DataCollector(config_path)
    
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行轮动分析
        
        Args:
            input_data: 输入数据
            
        Returns:
            分析结果
        """
        import time
        start_time = time.time()
        
        # 设置分析日期范围
        if not input_data.end_date:
            end_date = datetime.now()
        else:
            end_date = datetime.strptime(input_data.end_date, '%Y-%m-%d')
        
        start_date = end_date - timedelta(days=self.lookback_period + 30)
        
        try:
            # 获取行业数据
            industry_data = self._fetch_industry_data(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if not industry_data:
                raise ValueError("无法获取行业数据")
            
            # 计算行业收益和动量
            industry_returns = self._calculate_industry_returns(industry_data)
            industry_momentum = self._calculate_momentum(industry_returns)
            
            # 行业排名
            rankings = self._rank_industries(industry_returns, industry_momentum)
            
            # 识别轮动信号
            rotation_signals = self._identify_rotation_signals(industry_data, rankings)
            
            # 生成配置建议
            allocation = self._generate_allocation(rankings, rotation_signals)
            
            # 计算置信度
            confidence = self._calculate_confidence(rankings, rotation_signals)
            
            # 构建结果
            result = {
                'industry_rankings': rankings,
                'rotation_signals': rotation_signals,
                'recommended_allocation': allocation,
                'lookback_period': self.lookback_period,
                'momentum_period': self.momentum_period,
                'analysis_date': end_date.strftime('%Y-%m-%d'),
                'industries_count': len(rankings)
            }
            
            execution_time = time.time() - start_time
            
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=input_data.symbol or "MARKET",
                analysis_date=end_date.strftime('%Y-%m-%d'),
                result=result,
                confidence=confidence,
                state=AgentState.COMPLETED,
                execution_time=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"轮动分析失败: {e}")
            raise
    
    def _fetch_industry_data(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, pd.DataFrame]:
        """
        获取行业指数数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            行业代码到DataFrame的字典
        """
        try:
            # 使用akshare获取申万行业指数
            from data.akshare_adapter import AkshareAdapter
            
            ak_adapter = AkshareAdapter({})
            industry_list = ak_adapter.get_industry_list()
            
            industry_data = {}
            
            for _, row in industry_list.iterrows():
                industry_code = row.get('industry_code', '')
                industry_name = row.get('industry_name', '')
                
                if not industry_code:
                    continue
                
                try:
                    # 获取行业历史数据
                    df = ak_adapter.get_industry_index(
                        industry_code=industry_code,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if not df.empty and len(df) >= self.momentum_period:
                        df['industry_name'] = industry_name
                        industry_data[industry_code] = df
                        
                except Exception as e:
                    self.logger.debug(f"获取 {industry_code} 数据失败: {e}")
                    continue
            
            return industry_data
            
        except Exception as e:
            self.logger.error(f"获取行业数据失败: {e}")
            return {}
    
    def _calculate_industry_returns(
        self,
        industry_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, float]:
        """
        计算各行业收益率
        
        Args:
            industry_data: 行业数据字典
            
        Returns:
            行业代码到收益率的字典
        """
        returns = {}
        
        for code, df in industry_data.items():
            try:
                if len(df) < 2:
                    continue
                
                # 计算区间收益率
                start_price = df['close'].iloc[0]
                end_price = df['close'].iloc[-1]
                
                if start_price > 0:
                    total_return = (end_price - start_price) / start_price * 100
                    returns[code] = round(total_return, 4)
                    
            except Exception as e:
                self.logger.debug(f"计算 {code} 收益率失败: {e}")
                continue
        
        return returns
    
    def _calculate_momentum(
        self,
        industry_returns: Dict[str, float]
    ) -> Dict[str, float]:
        """
        计算行业动量
        
        使用近期收益率加权计算动量得分
        
        Args:
            industry_returns: 行业收益率
            
        Returns:
            行业代码到动量得分的字典
        """
        # 简化实现：直接使用收益率作为动量
        # 实际应用中可以使用更复杂的动量计算（如加权移动平均）
        momentum = {}
        
        for code, ret in industry_returns.items():
            # 动量得分 = 收益率 * 动量因子
            momentum_score = ret * 1.0  # 可以添加更多因子
            momentum[code] = round(momentum_score, 4)
        
        return momentum
    
    def _rank_industries(
        self,
        industry_returns: Dict[str, float],
        industry_momentum: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        行业排名
        
        Args:
            industry_returns: 行业收益率
            industry_momentum: 行业动量
            
        Returns:
            排名列表
        """
        rankings = []
        
        for code in industry_returns.keys():
            ret = industry_returns.get(code, 0)
            momentum = industry_momentum.get(code, 0)
            
            # 综合得分（收益率+动量）
            score = ret * 0.6 + momentum * 0.4
            
            rankings.append({
                'industry_code': code,
                'return_60d': ret,
                'momentum_score': momentum,
                'composite_score': round(score, 4),
                'rank': 0  # 稍后设置
            })
        
        # 按综合得分排序
        rankings.sort(key=lambda x: x['composite_score'], reverse=True)
        
        # 设置排名
        for i, item in enumerate(rankings):
            item['rank'] = i + 1
        
        return rankings
    
    def _identify_rotation_signals(
        self,
        industry_data: Dict[str, pd.DataFrame],
        rankings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        识别轮动信号
        
        Args:
            industry_data: 行业数据
            rankings: 行业排名
            
        Returns:
            轮动信号列表
        """
        signals = []
        
        if len(rankings) < 5:
            return signals
        
        # 强势行业（前5）
        top_industries = rankings[:5]
        
        # 弱势行业（后5）
        bottom_industries = rankings[-5:]
        
        # 生成轮动信号
        for industry in top_industries:
            # 新晋强势
            if industry['momentum_score'] > 5:
                signals.append({
                    'type': 'momentum_leader',
                    'industry_code': industry['industry_code'],
                    'signal': 'leading',
                    'strength': 'strong' if industry['return_60d'] > 10 else 'moderate',
                    'description': f"{industry['industry_code']} 动量领先"
                })
        
        for industry in bottom_industries:
            # 超跌反弹机会
            if industry['return_60d'] < -10:
                signals.append({
                    'type': 'oversold_reversal',
                    'industry_code': industry['industry_code'],
                    'signal': 'potential_reversal',
                    'strength': 'watch',
                    'description': f"{industry['industry_code']} 超跌，关注反弹机会"
                })
        
        return signals
    
    def _generate_allocation(
        self,
        rankings: List[Dict[str, Any]],
        signals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成配置建议
        
        Args:
            rankings: 行业排名
            signals: 轮动信号
            
        Returns:
            配置建议
        """
        if not rankings:
            return {}
        
        # 推荐配置
        top_3 = rankings[:3] if len(rankings) >= 3 else rankings
        
        allocation = {
            'strategy': 'momentum_rotation',
            'top_industries': [
                {
                    'code': item['industry_code'],
                    'weight': round(0.4 / len(top_3), 4),
                    'reason': f"综合得分: {item['composite_score']}"
                }
                for item in top_3
            ],
            'cash_ratio': 0.2,  # 建议保留20%现金
            'rebalance_frequency': 'monthly',
            'risk_note': '行业轮动策略存在追高风险，建议分批建仓'
        }
        
        # 总权重
        total_weight = sum(item['weight'] for item in allocation['top_industries'])
        allocation['total_equity_weight'] = round(total_weight, 4)
        
        return allocation
    
    def _calculate_confidence(
        self,
        rankings: List[Dict[str, Any]],
        signals: List[Dict[str, Any]]
    ) -> float:
        """
        计算分析置信度
        
        Args:
            rankings: 行业排名
            signals: 轮动信号
            
        Returns:
            置信度 (0-1)
        """
        if not rankings:
            return 0.0
        
        # 基于信号数量和排名的分散程度计算置信度
        signal_factor = min(len(signals) / 5, 1.0)  # 信号越多越可信（最多5个）
        
        # 排名分化程度
        if len(rankings) >= 2:
            score_spread = rankings[0]['composite_score'] - rankings[-1]['composite_score']
            spread_factor = min(score_spread / 20, 1.0)  # 分化越大越可信
        else:
            spread_factor = 0.5
        
        confidence = (signal_factor * 0.4 + spread_factor * 0.6)
        
        return round(confidence, 4)
    
    def get_industry_comparison(
        self,
        industry_codes: List[str],
        period: int = 60
    ) -> Dict[str, Any]:
        """
        获取行业对比分析
        
        Args:
            industry_codes: 行业代码列表
            period: 对比周期（天）
            
        Returns:
            对比分析结果
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period + 30)
        
        try:
            industry_data = self._fetch_industry_data(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            # 过滤指定行业
            filtered_data = {
                k: v for k, v in industry_data.items()
                if k in industry_codes
            }
            
            # 计算对比指标
            comparison = {}
            for code, df in filtered_data.items():
                if len(df) < 2:
                    continue
                
                returns = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
                volatility = df['close'].pct_change().std() * 100 if len(df) > 1 else 0
                
                comparison[code] = {
                    'return_pct': round(returns, 4),
                    'volatility_pct': round(volatility, 4),
                    'sharpe': round(returns / (volatility + 0.001), 4),
                    'industry_name': df.get('industry_name', [''])[0] if 'industry_name' in df.columns else code
                }
            
            return {
                'comparison': comparison,
                'period_days': period,
                'best_performer': max(comparison.items(), key=lambda x: x[1]['return_pct'])[0] if comparison else None,
                'lowest_volatility': min(comparison.items(), key=lambda x: x[1]['volatility_pct'])[0] if comparison else None
            }
            
        except Exception as e:
            self.logger.error(f"行业对比分析失败: {e}")
            return {}
    
    def detect_rotation_trend(
        self,
        lookback_weeks: int = 12
    ) -> Dict[str, Any]:
        """
        检测轮动趋势
        
        Args:
            lookback_weeks: 回溯周数
            
        Returns:
            轮动趋势分析
        """
        # 这里可以实现更复杂的轮动趋势检测
        # 例如：检测哪些行业正在走强/走弱
        
        return {
            'trend': 'analyzing',
            'note': '轮动趋势分析需要更多历史数据进行时间序列分析'
        }
