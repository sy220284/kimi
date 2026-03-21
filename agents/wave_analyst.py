"""
智能体框架 - 波浪分析师智能体 (AI增强版)
集成AI子代理提供波浪形态推理能力
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 导入两个分析器，保留兼容性
from analysis.wave.elliott_wave import ElliottWaveAnalyzer
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer, UnifiedWaveSignal

from .base_agent import AgentInput, AgentOutput, AgentState, AnalysisType, BaseAgent


class WaveAnalystAgent(BaseAgent):
    """
    波浪分析师智能体
    
    功能:
    1. 基础波浪分析（ElliottWaveAnalyzer / UnifiedWaveAnalyzer）
    2. AI推理增强（WaveReasoningAgent）- 提供浪型解读和目标价预测
    
    使用统一分析器（推荐）:
        agent = WaveAnalystAgent(use_unified=True)
        
    使用基础分析器（兼容旧版）:
        agent = WaveAnalystAgent(use_unified=False)
    
    使用AI增强:
        agent = WaveAnalystAgent(use_unified=True, use_ai=True, ai_model="deepseek/deepseek-reasoner")
    """

    def __init__(
        self,
        config_path: Path | None = None,
        use_ai: bool = False,
        ai_model: str = "deepseek/deepseek-reasoner",
        use_unified: bool = True  # 是否使用统一分析器
    ):
        """
        初始化波浪分析师

        Args:
            config_path:  配置文件路径
            use_ai:       是否启用 AI 子代理增强（默认 False）
                          设为 True 前需先配置 API Key：
                            DeepSeek:  export DEEPSEEK_API_KEY=<your_key>
                            CodeFlow:  export CODEFLOW_API_KEY=<your_key>
                          未配置时会自动降级回 use_ai=False，不会报错。
                          AI 分析使用 Redis 缓存（TTL 24h），相同输入不重复计费。
            ai_model:     AI 模型标识符，格式 "provider/model_id"
                          支持: "deepseek/deepseek-reasoner"（推荐，慢思考）
                                "deepseek/deepseek-chat"（快，适合批量）
                                "codeflow/claude-sonnet-4-6"（CodeFlow接入）
            use_unified:  是否使用 UnifiedWaveAnalyzer（默认 True，推荐）
                          True  → UnifiedWaveAnalyzer（含 C/2/4 浪专项检测、
                                  多指标共振分析、入场质量评分）
                          False → ElliottWaveAnalyzer（基础波浪识别，向后兼容）
        """
        super().__init__(
            agent_name="wave_analyst",
            analysis_type=AnalysisType.WAVE,
            config_path=config_path
        )

        # 分析器选择
        self.use_unified = use_unified
        if use_unified:
            self.analyzer = UnifiedWaveAnalyzer()
            self.logger.info("使用 UnifiedWaveAnalyzer (含入场优化+共振分析)")
        else:
            self.analyzer = ElliottWaveAnalyzer()
            self.logger.info("使用 ElliottWaveAnalyzer (基础波浪分析)")
        
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

            # 应用日期过滤 (统一转为字符串比较，避免 datetime.date vs str 类型冲突)
            if df is not None and not df.empty:
                df['date'] = df['date'].astype(str)
                if input_data.start_date:
                    df = df[df['date'] >= str(input_data.start_date)].copy()
                if input_data.end_date:
                    df = df[df['date'] <= str(input_data.end_date)].copy()

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

            # 执行分析
            if self.use_unified:
                # 新版分析流程 (UnifiedWaveAnalyzer)
                signals = self.analyzer.detect(df, mode='all')
                
                if not signals:
                    return AgentOutput(
                        agent_type=self.analysis_type.value,
                        symbol=symbol,
                        analysis_date=datetime.now().strftime('%Y-%m-%d'),
                        result={'signals': [], 'message': '未检测到波浪信号'},
                        confidence=0.0,
                        state=AgentState.COMPLETED,
                        execution_time=time.time() - start_time
                    )
                
                # 选择最佳信号
                best_signal = max(signals, key=lambda s: s.confidence)
                
                result = {
                    'signals': [self._signal_to_dict(s) for s in signals],
                    'best_signal': self._signal_to_dict(best_signal),
                    'entry_type': best_signal.entry_type.value,
                    'entry_price': best_signal.entry_price,
                    'target_price': best_signal.target_price,
                    'stop_loss': best_signal.stop_loss,
                    'confidence': best_signal.confidence,
                    'quality_score': best_signal.quality_score,
                    'resonance_score': best_signal.resonance_score,
                    'data_points': len(df),
                    'latest_price': float(df['close'].iloc[-1]) if not df.empty else 0
                }
                base_confidence = best_signal.confidence
                
            else:
                # 旧版分析流程 (ElliottWaveAnalyzer)
                pattern = self.analyzer.detect_wave_pattern(df)
                patterns = [pattern] if pattern else []
                
                result = {
                    'patterns': [p.to_dict() if hasattr(p, 'to_dict') else str(p) for p in patterns],
                    'data_points': len(df),
                    'latest_price': float(df['close'].iloc[-1]) if not df.empty else 0
                }
                base_confidence = pattern.confidence if pattern and hasattr(pattern, 'confidence') else 0.5
            
            # AI推理增强
            ai_result = None
            if self.use_ai and self.ai_agent:
                try:
                    from agents.ai_subagents import AIAgentInput
                    
                    # 构建分析数据
                    if self.use_unified and signals:
                        best = signals[0]
                        wave_data = {
                            'entry_type': best.entry_type.value,
                            'entry_price': best.entry_price,
                            'target_price': best.target_price,
                            'stop_loss': best.stop_loss,
                            'confidence': best.confidence,
                            'quality_score': best.quality_score,
                            'resonance_score': best.resonance_score,
                            'current_price': result['latest_price'],
                        }
                    elif not self.use_unified and pattern:
                        wave_data = {
                            'pattern_type': pattern.pattern_type if hasattr(pattern, 'pattern_type') else 'unknown',
                            'confidence': pattern.confidence if hasattr(pattern, 'confidence') else 0.5,
                            'current_wave': getattr(pattern, 'current_wave', 'unknown'),
                            'current_price': result['latest_price'],
                            'pivots': getattr(pattern, 'pivots', []),
                            'signals': getattr(pattern, 'signals', [])
                        }
                    else:
                        wave_data = {}
                    
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
                    
                    result['ai_analysis'] = ai_result
                    
                except Exception as e:
                    self.logger.warning(f"AI分析失败: {e}")
                    result['ai_error'] = str(e)

            # 计算最终置信度
            if ai_result and ai_result.get('confidence'):
                # 综合技术置信度和AI置信度
                final_confidence = (base_confidence + ai_result['confidence']) / 2
            else:
                final_confidence = base_confidence

            return AgentOutput(
                agent_type=self.analysis_type.value,
                symbol=symbol,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                result=result,
                confidence=final_confidence,
                state=AgentState.COMPLETED,
                execution_time=time.time() - start_time,
                error_message=None
            )

        except Exception as e:
            self.logger.error(f"波浪分析失败 {symbol}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
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

    def _signal_to_dict(self, signal: UnifiedWaveSignal) -> dict[str, Any]:
        """将 UnifiedWaveSignal 转换为字典"""
        return {
            'entry_type': signal.entry_type.value,
            'entry_price': signal.entry_price,
            'target_price': signal.target_price,
            'stop_loss': signal.stop_loss,
            'confidence': signal.confidence,
            'quality_score': signal.quality_score,
            'resonance_score': signal.resonance_score,
            'direction': signal.direction,
            'trend_aligned': signal.trend_aligned,
            'trend_direction': signal.trend_direction,
            'market_condition': signal.market_condition,
            'is_valid': signal.is_valid,
        }


def main():
    """测试函数"""
    print("🤖 波浪分析智能体测试")

    # 测试统一分析器（新版）
    print("\n=== 测试 UnifiedWaveAnalyzer ===")
    agent = WaveAnalystAgent(use_unified=True, use_ai=False)

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
            signals = result.result.get('signals', [])
            print(f"  ✅ 发现 {len(signals)} 个波浪信号")
            
            best = result.result.get('best_signal')
            if best:
                print(f"  📊 最佳信号: {best['entry_type']}")
                print(f"  💰 入场价: {best['entry_price']:.2f}")
                print(f"  🎯 目标价: {best['target_price']:.2f}")
                print(f"  🛡️ 止损价: {best['stop_loss']:.2f}")
                print(f"  📈 置信度: {best['confidence']:.2f}")
                print(f"  ⭐ 质量评分: {best['quality_score']:.2f}")
                print(f"  🔄 共振评分: {best['resonance_score']:.2f}")
        else:
            print(f"  ❌ 分析失败: {result.error_message}")
    
    # 测试旧版分析器（兼容）
    print("\n=== 测试 ElliottWaveAnalyzer (兼容模式) ===")
    agent_old = WaveAnalystAgent(use_unified=False, use_ai=False)
    
    for symbol in symbols[:1]:
        print(f"\n🔍 分析 {symbol}...")
        
        input_data = AgentInput(symbol=symbol)
        result = agent_old.analyze(input_data)
        
        if result.state.value == 'completed':
            patterns = result.result.get('patterns', [])
            print(f"  ✅ 发现 {len(patterns)} 个波浪模式")
        else:
            print(f"  ❌ 分析失败: {result.error_message}")


if __name__ == '__main__':
    main()
