"""
智能体框架 - 波浪分析师智能体 (简化版)
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.wave.elliott_wave import ElliottWaveAnalyzer

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class WaveAnalystAgent(BaseAgent):
    """波浪分析师智能体"""

    def __init__(self, config_path: Path | None = None):
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

        # 使用艾略特波浪分析器
        self.analyzer = ElliottWaveAnalyzer()

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行波浪分析

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
                    result={'patterns': [], 'error': '无数据'},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=time.time() - start_time,
                    error_message='无数据'
                )

            # 执行波浪分析
            pattern = self.analyzer.detect_wave_pattern(df)
            patterns = [pattern] if pattern else []

            # 计算置信度
            confidence = pattern.confidence if pattern and hasattr(pattern, 'confidence') else 0.5

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={'patterns': patterns, 'data_points': len(df)},
                confidence=confidence,
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )

        except Exception as e:
            self.logger.error(f"波浪分析失败 {symbol}: {e}")
            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result={'patterns': [], 'error': str(e)},
                confidence=0.0,
                state=AgentState.ERROR,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )


def main():
    """测试函数"""
    print("🤖 波浪分析智能体测试")

    # 创建智能体
    agent = WaveAnalystAgent()

    # 获取数据
    from data.optimized_data_manager import get_optimized_data_manager
    data_mgr = get_optimized_data_manager()
    data_mgr.load_all_data()

    # 分析股票
    symbols = ['000001', '600519']
    for symbol in symbols:
        print(f"\n🔍 分析 {symbol}...")
        df = data_mgr.get_stock_data(symbol)

        if df is not None and not df.empty:
            result = agent.analyze(df)
            print(f"  ✅ 发现 {len(result)} 个波浪模式")
        else:
            print("  ⚠️ 无数据")


if __name__ == '__main__':
    main()
