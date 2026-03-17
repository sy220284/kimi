"""
智能体框架 - 技术分析师智能体
"""
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent, AgentInput, AgentOutput, AnalysisType, AgentState
from analysis.technical.indicators import TechnicalIndicators
from data.data_collector import DataCollector


class TechAnalystAgent(BaseAgent):
    """技术分析师智能体"""
    
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
        self.data_collector = DataCollector(config_path)
        
        # 获取技术指标配置
        tech_config = self.config.get('analysis', {}).get('technical_analyst', {})
        self.indicator_config = tech_config.get('indicators', [])
    
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行技术分析
        
        Args:
            input_data: 输入数据
            
        Returns:
            分析结果
        """
        import time
        start_time = time.time()
        
        symbol = input_data.symbol
        
        # 获取数据
        try:
            df = self.data_collector.get_daily_kline(
                symbol=symbol,
                start_date=input_data.start_date,
                end_date=input_data.end_date
            )
            
            if df.empty:
                raise ValueError(f"无法获取 {symbol} 的数据")
            
        except Exception as e:
            self.logger.error(f"数据获取失败: {e}")
            raise
        
        # 计算技术指标
        df_with_indicators = self._calculate_indicators(df)
        
        # 获取最新指标值
        latest_values = self._get_latest_indicator_values(df_with_indicators)
        
        # 获取交易信号
        signals = self.indicators.get_all_signals(df_with_indicators)
        
        # 获取综合信号
        combined = self.indicators.get_combined_signal(df_with_indicators)
        
        # 计算置信度
        confidence = self._calculate_confidence(signals, combined)
        
        # 构建分析结果
        result = {
            'latest_indicators': latest_values,
            'signals': signals,
            'combined_signal': combined,
            'data_points': len(df),
            'date_range': f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}"
        }
        
        # 添加信号描述
        result['signal_description'] = self._generate_signal_description(combined, latest_values)
        
        execution_time = time.time() - start_time
        
        return AgentOutput(
            agent_type=self.analysis_type.value,
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            result=result,
            confidence=confidence,
            state=AgentState.COMPLETED,
            execution_time=execution_time
        )
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        Args:
            df: 原始数据
            
        Returns:
            包含指标的DataFrame
        """
        # 解析配置中的指标参数
        macd_params = {}
        rsi_period = 14
        kdj_params = {}
        bb_params = {}
        
        for indicator_config in self.indicator_config:
            name = indicator_config.get('name', '').upper()
            
            if name == 'MACD':
                macd_params = {
                    'fast_period': indicator_config.get('fast_period', 12),
                    'slow_period': indicator_config.get('slow_period', 26),
                    'signal_period': indicator_config.get('signal_period', 9)
                }
            elif name == 'RSI':
                rsi_period = indicator_config.get('period', 14)
            elif name == 'KDJ':
                kdj_params = {
                    'k_period': indicator_config.get('k_period', 9),
                    'd_period': indicator_config.get('d_period', 3),
                    'j_period': indicator_config.get('j_period', 3)
                }
            elif name == 'BOLLINGER_BANDS':
                bb_params = {
                    'period': indicator_config.get('period', 20),
                    'std_dev': indicator_config.get('std_dev', 2.0)
                }
        
        # 计算所有指标
        return self.indicators.calculate_all(
            df,
            macd_params=macd_params if macd_params else None,
            rsi_period=rsi_period,
            kdj_params=kdj_params if kdj_params else None,
            bb_params=bb_params if bb_params else None
        )
    
    def _get_latest_indicator_values(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        获取最新指标值
        
        Args:
            df: 包含指标的数据
            
        Returns:
            最新指标值
        """
        if df.empty:
            return {}
        
        latest = df.iloc[-1]
        values = {}
        
        # MA
        for col in df.columns:
            if col.startswith('MA') or col.startswith('EMA'):
                values[col] = round(latest[col], 4) if pd.notna(latest[col]) else None
        
        # MACD
        for col in ['MACD', 'MACD_Signal', 'MACD_Histogram']:
            if col in df.columns:
                values[col] = round(latest[col], 4) if pd.notna(latest[col]) else None
        
        # RSI
        for col in df.columns:
            if col.startswith('RSI'):
                values[col] = round(latest[col], 2) if pd.notna(latest[col]) else None
        
        # KDJ
        for col in ['K', 'D', 'J']:
            if col in df.columns:
                values[col] = round(latest[col], 2) if pd.notna(latest[col]) else None
        
        # Bollinger Bands
        for col in ['BB_Upper', 'BB_Middle', 'BB_Lower', 'BB_Width', 'BB_PercentB']:
            if col in df.columns:
                values[col] = round(latest[col], 4) if pd.notna(latest[col]) else None
        
        # 价格信息
        values['close'] = round(latest['close'], 4)
        values['volume'] = int(latest['volume']) if pd.notna(latest['volume']) else None
        
        return values
    
    def _calculate_confidence(
        self,
        signals: Dict[str, str],
        combined: Dict[str, Any]
    ) -> float:
        """
        计算分析置信度
        
        Args:
            signals: 各指标信号
            combined: 综合信号
            
        Returns:
            置信度 (0-1)
        """
        score = combined.get('score', 0)
        
        # 信号一致性检查
        buy_count = sum(1 for s in signals.values() if s == 'buy')
        sell_count = sum(1 for s in signals.values() if s == 'sell')
        neutral_count = sum(1 for s in signals.values() if s == 'neutral')
        
        total = len(signals)
        if total == 0:
            return 0.5
        
        # 信号一致性越高，置信度越高
        max_agreement = max(buy_count, sell_count, neutral_count)
        consistency = max_agreement / total
        
        # 综合得分（信号一致性和信号强度）
        confidence = (consistency * 0.5 + abs(score) * 0.5)
        
        return round(min(confidence, 1.0), 4)
    
    def _generate_signal_description(
        self,
        combined: Dict[str, Any],
        latest_values: Dict[str, Any]
    ) -> str:
        """
        生成信号描述
        
        Args:
            combined: 综合信号
            latest_values: 最新指标值
            
        Returns:
            信号描述文本
        """
        signal = combined.get('combined_signal', 'neutral')
        score = combined.get('score', 0)
        
        descriptions = []
        
        if signal == 'buy':
            descriptions.append(f"买入信号 (强度: {score:.2f})")
        elif signal == 'sell':
            descriptions.append(f"卖出信号 (强度: {abs(score):.2f})")
        else:
            descriptions.append("观望信号")
        
        # 添加关键指标信息
        if 'RSI14' in latest_values:
            rsi = latest_values['RSI14']
            if rsi:
                if rsi > 70:
                    descriptions.append(f"RSI超买 ({rsi:.1f})")
                elif rsi < 30:
                    descriptions.append(f"RSI超卖 ({rsi:.1f})")
        
        if 'J' in latest_values:
            j = latest_values['J']
            if j:
                if j > 100:
                    descriptions.append(f"KDJ超买 (J={j:.1f})")
                elif j < 0:
                    descriptions.append(f"KDJ超卖 (J={j:.1f})")
        
        if 'BB_PercentB' in latest_values:
            percent_b = latest_values['BB_PercentB']
            if percent_b is not None:
                if percent_b > 1:
                    descriptions.append("价格突破布林带上轨")
                elif percent_b < 0:
                    descriptions.append("价格跌破布林带下轨")
        
        return " | ".join(descriptions)
    
    def screen_stocks(
        self,
        symbols: List[str],
        signal_filter: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        股票筛选
        
        Args:
            symbols: 股票代码列表
            signal_filter: 信号过滤 ('buy', 'sell', None表示全部)
            min_confidence: 最小置信度
            
        Returns:
            筛选结果列表
        """
        results = []
        
        for symbol in symbols:
            try:
                input_data = AgentInput(symbol=symbol)
                output = self.run(input_data)
                
                combined_signal = output.result.get('combined_signal', {}).get('combined_signal', 'neutral')
                
                # 信号过滤
                if signal_filter and combined_signal != signal_filter:
                    continue
                
                # 置信度过滤
                if output.confidence < min_confidence:
                    continue
                
                results.append({
                    'symbol': symbol,
                    'signal': combined_signal,
                    'confidence': output.confidence,
                    'indicators': output.result.get('latest_indicators', {}),
                    'description': output.result.get('signal_description', '')
                })
                
            except Exception as e:
                self.logger.error(f"筛选 {symbol} 失败: {e}")
        
        # 按置信度排序
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        return results
