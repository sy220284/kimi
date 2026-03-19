"""
智能体框架 - 波浪分析师智能体 (AI增强版)
集成AI子代理提供波浪形态推理能力
"""
import time
from datetime import datetime
from pathlib import Path

from analysis.wave.elliott_wave import ElliottWaveAnalyzer

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class WaveAnalystAgent(BaseAgent):
    """
    波浪分析师智能体
    
    功能:
    1. 基础波浪分析（ElliottWaveAnalyzer）
    2. AI推理增强（WaveReasoningAgent）- 提供浪型解读和目标价预测
    
    使用AI增强:
        agent = WaveAnalystAgent(use_ai=True, ai_model="deepseek/deepseek-reasoner")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        use_ai: bool = False,
        ai_model: str = "deepseek/deepseek-reasoner"
    ):
        """
        初始化波浪分析师

        Args:
            config_path: 配置文件路径
            use_ai: 是否启用AI子代理增强
            ai_model: AI模型选择 (如 "deepseek/deepseek-reasoner" 或 "codeflow/claude-sonnet-4-6")
        """
        super().__init__(
            agent_name="wave_analyst",
            analysis_type=AnalysisType.WAVE,
            config_path=config_path
        )

        # 基础分析器
        self.analyzer = ElliottWaveAnalyzer()
        
        # AI子代理
        self.use_ai = use_ai
        self.ai_agent = None
        if use_ai:
            try:
                from agents.ai_subagents import WaveReasoningAgent
                self.ai_agent = WaveReasoningAgent(model=ai_model)
                self.logger.info(f"AI子代理已启用: {ai_model}")
            except Exception as e:
                self.logger.warning(f"AI子代理初始化失败: {e}")
                self.use_ai = False

    def analyze(self, input_data: AgentInput) -> AgentOutput:
        """
        执行波浪分析

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
                    result={'patterns': [], 'error': '无数据'},
                    confidence=0.0,
                    state=AgentState.ERROR,
                    execution_time=time.time() - start_time,
                    error_message='无数据'
                )

            # 1. 执行基础波浪分析
            pattern = self.analyzer.detect_wave_pattern(df)
            patterns = [pattern] if pattern else []
            
            # 准备基础结果
            base_result = {
                'patterns': patterns,
                'data_points': len(df),
                'latest_price': float(df['close'].iloc[-1]) if not df.empty else 0
            }
            
            # 2. AI推理增强
            ai_result = None
            if self.use_ai and self.ai_agent and pattern:
                try:
                    from agents.ai_subagents import AIAgentInput
                    
                    # 构建波浪数据
                    wave_data = {
                        'pattern_type': pattern.pattern_type if hasattr(pattern, 'pattern_type') else 'unknown',
                        'confidence': pattern.confidence if hasattr(pattern, 'confidence') else 0.5,
                        'current_wave': getattr(pattern, 'current_wave', 'unknown'),
                        'current_price': base_result['latest_price'],
                        'pivots': getattr(pattern, 'pivots', []),
                        'signals': getattr(pattern, 'signals', [])
                    }
                    
                    ai_input = AIAgentInput(
                        raw_data=wave_data,
                        context=f"分析标的: {symbol}"
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
            base_confidence = pattern.confidence if pattern and hasattr(pattern, 'confidence') else 0.5
            if ai_result and ai_result.get('confidence'):
                # 综合技术置信度和AI置信度
                final_confidence = (base_confidence + ai_result['confidence']) / 2
            else:
                final_confidence = base_confidence

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

    # 创建智能体（启用AI增强）
    agent = WaveAnalystAgent(use_ai=True)

    # 获取数据
    from data.optimized_data_manager import get_optimized_data_manager
    data_mgr = get_optimized_data_manager()
    data_mgr.load_all_data()

    # 分析股票
    symbols = ['000001', '600519']
    for symbol in symbols:
        print(f"\n🔍 分析 {symbol}...")
        
        input_data = AgentInput(symbol=symbol)
        result = agent.analyze(input_data)
        
        if result.state.value == 'completed':
            patterns = result.result.get('patterns', [])
            print(f"  ✅ 发现 {len(patterns)} 个波浪模式")
            
            # 显示AI分析结果
            ai_analysis = result.result.get('ai_analysis')
            if ai_analysis:
                print(f"  🤖 AI结论: {ai_analysis.get('conclusion', 'N/A')}")
                print(f"  📊 AI置信度: {ai_analysis.get('confidence', 0):.2f}")
                print(f"  💡 建议: {ai_analysis.get('action_suggestion', 'N/A')}")
        else:
            print(f"  ❌ 分析失败: {result.error_message}")


if __name__ == '__main__':
    main()
