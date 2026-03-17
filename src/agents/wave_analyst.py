"""
智能体框架 - 波浪分析师智能体
"""
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent, AgentInput, AgentOutput, AnalysisType, AgentState
from analysis.wave.elliott_wave import ElliottWaveAnalyzer, WavePattern, WaveType
from analysis.wave.wave_detector import WaveDetector, WaveSignal
from data.data_collector import DataCollector


class WaveAnalystAgent(BaseAgent):
    """波浪分析师智能体"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化波浪分析师
        
        Args:
            config_path: 配置文件路径
        """
        super().__init__(
            agent_name="wave_analyst",
            analysis_type=AnalysisType.WAVE,
            config_path=config_path
        )
        
        # 获取波浪分析配置
        wave_config = self.config.get('analysis', {}).get('wave_analyst', {})
        
        self.detector = WaveDetector(
            min_wave_length=wave_config.get('min_wave_length', 5),
            max_wave_length=wave_config.get('max_wave_length', 100),
            confidence_threshold=wave_config.get('confidence_threshold', 0.7),
            peak_window=5
        )
        
        self.data_collector = DataCollector(config_path)
    
    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行波浪分析
        
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
        
        # 执行波浪检测
        signal = self.detector.detect(symbol, df)
        
        if not signal:
            # 未识别到波浪形态
            execution_time = time.time() - start_time
            
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={
                    'message': '未识别到明确的波浪形态',
                    'data_points': len(df),
                    'date_range': f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}"
                },
                confidence=0.0,
                state=AgentState.COMPLETED,
                execution_time=execution_time
            )
        
        # 获取波浪统计信息
        stats = self.detector.get_wave_statistics(df)
        
        # 验证波浪形态
        validation = self.detector.validate_pattern(signal.wave_pattern, df)
        
        # 获取趋势分析
        trend = self.detector.analyzer.analyze_trend(df, signal.wave_pattern)
        
        # 构建分析结果
        result = {
            'signal': signal.to_dict(),
            'wave_statistics': stats,
            'wave_validation': validation,
            'trend_analysis': trend,
            'data_points': len(df),
            'date_range': f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}"
        }
        
        execution_time = time.time() - start_time
        
        return AgentOutput(
            agent_type=self.analysis_type.value,
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            result=result,
            confidence=signal.confidence,
            state=AgentState.COMPLETED,
            execution_time=execution_time
        )
    
    def analyze_multi_waves(
        self,
        symbols: list,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, AgentOutput]:
        """
        分析多只股票
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            股票代码到分析结果的字典
        """
        results = {}
        
        for symbol in symbols:
            try:
                input_data = AgentInput(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                
                output = self.run(input_data)
                results[symbol] = output
                
            except Exception as e:
                self.logger.error(f"分析 {symbol} 失败: {e}")
                results[symbol] = AgentOutput(
                    agent_type=self.analysis_type.value,
                    symbol=symbol,
                    analysis_date=datetime.now().strftime('%Y-%m-%d'),
                    result={'error': str(e)},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=0.0,
                    error_message=str(e)
                )
        
        return results
    
    def get_wave_signals(
        self,
        symbols: list,
        min_confidence: float = 0.7
    ) -> list:
        """
        获取波浪交易信号
        
        Args:
            symbols: 股票代码列表
            min_confidence: 最小置信度
            
        Returns:
            交易信号列表
        """
        signals = []
        
        for symbol in symbols:
            try:
                input_data = AgentInput(symbol=symbol)
                output = self.run(input_data)
                
                if output.confidence >= min_confidence:
                    signal_info = {
                        'symbol': symbol,
                        'signal': output.result.get('signal', {}).get('signal_type', 'unknown'),
                        'confidence': output.confidence,
                        'wave_type': output.result.get('signal', {}).get('wave_pattern', {}).get('wave_type', 'unknown')
                    }
                    signals.append(signal_info)
                    
            except Exception as e:
                self.logger.error(f"获取 {symbol} 信号失败: {e}")
        
        # 按置信度排序
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        return signals
    
    def pre_process(self, input_data: AgentInput) -> AgentInput:
        """
        预处理输入
        
        Args:
            input_data: 输入数据
            
        Returns:
            处理后的输入
        """
        input_data = super().pre_process(input_data)
        
        # 设置默认参数
        if 'window' not in input_data.parameters:
            input_data.parameters['window'] = 5
        
        return input_data
