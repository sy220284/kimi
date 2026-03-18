#!/usr/bin/env python3
"""
自适应回测增强器 - 基于回测结果动态优化波浪分析
结合参数优化器和回测框架，实现数据驱动的策略改进
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Any

from ..backtest.wave_backtester import WaveBacktester
from ..wave import EnhancedWaveAnalyzer
from .param_optimizer import ParameterSet


class AdaptiveBacktester:
    """
    自适应回测器
    
    核心功能:
    1. 定期重新优化参数
    2. 根据回测表现动态调整策略
    3. 记录参数演变历史
    4. 识别最佳交易时段
    """
    
    def __init__(
        self,
        initial_params: Optional[ParameterSet] = None,
        optimization_interval: int = 60,  # 每60天重新优化
        lookback_window: int = 120  # 使用最近120天数据优化
    ):
        self.current_params = initial_params or ParameterSet()
        self.optimization_interval = optimization_interval
        self.lookback_window = lookback_window
        
        self.param_history: List[Dict[str, Any]] = []
        self.performance_history: List[Dict[str, Any]] = []
        
    def run_adaptive_backtest(
        self,
        symbol: str,
        df: pd.DataFrame,
        enable_optimization: bool = True
    ) -> Dict[str, Any]:
        """
        运行自适应回测
        
        特点:
        - 定期重新优化参数
        - 记录参数变化对收益的影响
        - 识别最佳参数配置
        """
        print(f"\n{'='*70}")
        print(f"🔄 自适应回测: {symbol}")
        print(f"{'='*70}")
        
        df = df.copy().sort_values('date')
        
        all_trades = []
        _equity_curve = []
        current_capital = 100000
        
        # 滑动窗口回测
        window_size = self.optimization_interval
        step_size = 20  # 每20天推进一次
        
        for start_idx in range(self.lookback_window, len(df) - window_size, step_size):
            end_idx = start_idx + window_size
            
            window_df = df.iloc[start_idx:end_idx].copy()
            current_date = window_df['date'].iloc[-1]
            
            print(f"\n📅 窗口 {current_date}: 数据[{start_idx}:{end_idx}]")
            
            # 可选：重新优化参数
            if enable_optimization and len(self.param_history) > 0:
                self._adaptive_optimize(window_df, current_capital)
            
            # 使用当前参数运行回测
            result = self._run_window_backtest(
                symbol, window_df, self.current_params
            )
            
            # 记录结果
            current_capital *= (1 + result['return_pct'] / 100)
            
            self.performance_history.append({
                'date': current_date,
                'capital': current_capital,
                'return_pct': result['return_pct'],
                'win_rate': result['win_rate'],
                'param_id': self.current_params.get_id()
            })
            
            all_trades.extend(result['trades'])
            
            print(f"   本窗口收益: {result['return_pct']:.2f}% | 累计: {current_capital/1000-100:.1f}%")
        
        # 生成报告
        return self._generate_adaptive_report(symbol, all_trades)
    
    def _adaptive_optimize(self, df: pd.DataFrame, current_capital: float):
        """根据最近表现自适应调整参数"""
        # 简化的自适应逻辑：根据胜率调整置信度门槛
        recent_performance = self.performance_history[-3:] if len(self.performance_history) >= 3 else []
        
        if not recent_performance:
            return
        
        avg_win_rate = np.mean([p['win_rate'] for p in recent_performance])
        
        # 胜率过低，提高门槛
        if avg_win_rate < 0.4:
            self.current_params.confidence_threshold = min(0.8, self.current_params.confidence_threshold + 0.05)
            print(f"   ⚠️ 胜率{avg_win_rate:.1%}过低，提高置信度门槛至{self.current_params.confidence_threshold:.2f}")
        
        # 胜率良好，可以尝试降低门槛捕捉更多机会
        elif avg_win_rate > 0.6:
            self.current_params.confidence_threshold = max(0.3, self.current_params.confidence_threshold - 0.02)
            print(f"   ✅ 胜率{avg_win_rate:.1%}良好，降低置信度门槛至{self.current_params.confidence_threshold:.2f}")
    
    def _run_window_backtest(
        self,
        symbol: str,
        df: pd.DataFrame,
        params: ParameterSet
    ) -> Dict[str, Any]:
        """在单个窗口运行回测"""
        try:
            analyzer = EnhancedWaveAnalyzer(
                atr_mult=params.atr_mult,
                min_change_pct=params.min_change_pct,
                peak_window=params.peak_window
            )
            
            backtester = WaveBacktester(analyzer)
            backtester.strategy.min_confidence = params.confidence_threshold
            backtester.strategy.stop_loss_pct = params.stop_loss_pct
            backtester.strategy.take_profit_pct = params.take_profit_pct
            
            result = backtester.run(symbol, df, reanalyze_every=5)
            
            return {
                'return_pct': result.total_return_pct,
                'win_rate': result.win_rate,
                'trades': result.trades,
                'max_drawdown': result.max_drawdown_pct
            }
            
        except Exception as e:
            print(f"   回测失败: {e}")
            return {
                'return_pct': 0,
                'win_rate': 0,
                'trades': [],
                'max_drawdown': 0
            }
    
    def _generate_adaptive_report(self, symbol: str, all_trades: List[Any]) -> Dict[str, Any]:
        """生成自适应回测报告"""
        closed_trades = [t for t in all_trades if t.status == 'closed']
        
        if not closed_trades:
            return {'error': '没有完成交易'}
        
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        
        _total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(winning_trades) / len(closed_trades)
        
        # 计算收益曲线
        returns = [p['return_pct'] for p in self.performance_history]
        cumulative_return = np.prod([1 + r/100 for r in returns]) - 1
        
        # 找出最佳参数配置
        param_performance = {}
        for perf in self.performance_history:
            pid = perf['param_id']
            if pid not in param_performance:
                param_performance[pid] = []
            param_performance[pid].append(perf['return_pct'])
        
        best_param = max(param_performance.items(), 
                        key=lambda x: np.mean(x[1]))
        
        report = {
            'symbol': symbol,
            'total_trades': len(closed_trades),
            'win_rate': win_rate,
            'cumulative_return_pct': cumulative_return * 100,
            'avg_window_return_pct': np.mean(returns),
            'best_param_id': best_param[0],
            'best_param_avg_return': np.mean(best_param[1]),
            'param_changes': len(self.param_history),
            'performance_history': self.performance_history
        }
        
        print(f"\n{'='*70}")
        print(f"📊 自适应回测报告: {symbol}")
        print(f"{'='*70}")
        print(f"总交易次数: {report['total_trades']}")
        print(f"胜率: {report['win_rate']:.1%}")
        print(f"累计收益: {report['cumulative_return_pct']:.2f}%")
        print(f"平均每窗口收益: {report['avg_window_return_pct']:.2f}%")
        print(f"最佳参数ID: {report['best_param_id']}")
        print(f"参数调整次数: {report['param_changes']}")
        
        return report


class BacktestAnalyzer:
    """
    回测结果分析器
    
    深度分析回测结果，提取改进信号
    """
    
    @staticmethod
    def analyze_trade_patterns(trades: List[Any]) -> Dict[str, Any]:
        """分析交易模式"""
        if not trades:
            return {}
        
        closed_trades = [t for t in trades if t.status == 'closed']
        
        # 按入场时间分组分析
        trades_by_hour = {}
        for t in closed_trades:
            hour = pd.to_datetime(t.entry_date).hour
            if hour not in trades_by_hour:
                trades_by_hour[hour] = []
            trades_by_hour[hour].append(t)
        
        # 找出最佳/最差入场时段
        hour_performance = {}
        for hour, trades in trades_by_hour.items():
            wins = sum(1 for t in trades if t.pnl > 0)
            avg_pnl = np.mean([t.pnl_pct for t in trades])
            hour_performance[hour] = {
                'win_rate': wins / len(trades),
                'avg_return': avg_pnl,
                'count': len(trades)
            }
        
        # 按持有时间分析
        holding_periods = []
        for t in closed_trades:
            if t.exit_date:
                days = (pd.to_datetime(t.exit_date) - pd.to_datetime(t.entry_date)).days
                holding_periods.append({
                    'days': days,
                    'pnl_pct': t.pnl_pct
                })
        
        return {
            'hour_performance': hour_performance,
            'holding_analysis': holding_periods,
            'best_hour': max(hour_performance.items(), key=lambda x: x[1]['win_rate'])[0] if hour_performance else None
        }
    
    @staticmethod
    def generate_improvement_suggestions(
        backtest_result: Dict[str, Any],
        trade_analysis: Dict[str, Any]
    ) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # 分析胜率
        win_rate = backtest_result.get('win_rate', 0)
        if win_rate < 0.4:
            suggestions.append("胜率过低，建议提高confidence_threshold +0.1，减少假信号")
        elif win_rate > 0.7:
            suggestions.append("胜率良好但可能错过机会，可尝试降低门槛 +0.05")
        
        # 分析回撤
        max_dd = backtest_result.get('max_drawdown_pct', 0)
        if max_dd > 15:
            suggestions.append(f"最大回撤{max_dd:.1f}%过大，建议收紧止损至3-4%")
        
        # 分析盈亏比
        pf = backtest_result.get('profit_factor', 0)
        if pf < 1.0:
            suggestions.append("盈亏比小于1，建议延长持有时间或调整止盈策略")
        
        # 分析交易频率
        trade_count = backtest_result.get('total_trades', 0)
        if trade_count < 5:
            suggestions.append("交易次数过少，建议降低min_change_pct捕捉更多波浪")
        elif trade_count > 50:
            suggestions.append("交易过于频繁，建议提高ATR倍数过滤噪声")
        
        return suggestions
