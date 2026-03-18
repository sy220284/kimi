"""
智能体框架 - 波浪分析师智能体 (简化版)
"""
from typing import Optional
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from .base_agent import BaseAgent, AnalysisType
from analysis.wave.elliott_wave import ElliottWaveAnalyzer


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
        
        # 使用艾略特波浪分析器
        self.analyzer = ElliottWaveAnalyzer()
    
    def analyze(self, df: pd.DataFrame) -> list:
        """
        执行波浪分析
        
        Args:
            df: 股票数据DataFrame
            
        Returns:
            分析结果列表
        """
        if df is None or df.empty:
            return []
        
        try:
            # 使用艾略特波浪分析器 - 使用 detect_wave_pattern 方法
            pattern = self.analyzer.detect_wave_pattern(df)
            if pattern:
                return [pattern]
            return []
        except Exception as e:
            self.logger.error(f"波浪分析失败: {e}")
            return []


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
