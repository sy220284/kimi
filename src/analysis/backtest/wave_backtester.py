"""
回测框架 - Phase 5 验证层
验证波浪分析策略的历史表现
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class TradeAction(Enum):
    """交易动作"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class Trade:
    """交易记录"""
    symbol: str
    entry_date: str
    entry_price: float
    action: TradeAction
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    quantity: int = 100  # 默认100股
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = "open"  # open/closed
    entry_idx: int = 0  # 买入时的数据索引，用于计算持仓天数
    entry_wave: Optional[str] = None  # 买入时的浪号
    expected_wave: Optional[str] = None  # 预期下一浪(用于目标价计算)
    
    def close(self, date: str, price: float):
        """平仓"""
        self.exit_date = date
        self.exit_price = price
        self.pnl = (price - self.entry_price) * self.quantity
        self.pnl_pct = (price - self.entry_price) / self.entry_price * 100
        self.status = "closed"
    
    def holding_days(self, current_idx: int) -> int:
        """计算持仓天数"""
        return current_idx - self.entry_idx


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    start_date: str
    end_date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    total_return_pct: float
    avg_return_per_trade: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'period': f"{self.start_date} ~ {self.end_date}",
            'total_trades': self.total_trades,
            'win_rate': f"{self.win_rate:.1%}",
            'total_return': f"{self.total_return_pct:.2f}%",
            'avg_return_per_trade': f"{self.avg_return_per_trade:.2f}%",
            'max_drawdown': f"{self.max_drawdown_pct:.2f}%",
            'sharpe_ratio': f"{self.sharpe_ratio:.2f}",
            'profit_factor': f"{self.profit_factor:.2f}"
        }


class WaveStrategy:
    """
    波浪交易策略
    
    策略逻辑:
    1. 买入信号: 调整浪结束(浪2/4/C完成) + 共振看涨 + 趋势向上
    2. 卖出信号: 推动浪完成(浪5/C浪) + 共振看跌
    3. 止损: 波浪结构低点或固定百分比
    4. 止盈: 斐波那契目标价或固定百分比
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        position_size: float = 0.2,  # 单笔仓位20%
        stop_loss_pct: float = 0.05,  # 5%止损
        take_profit_pct: float = 0.15,  # 15%止盈(备用)
        min_confidence: float = 0.5,
        use_resonance: bool = True,
        min_holding_days: int = 3,  # 最小持仓天数
        use_trend_filter: bool = True,  # 使用趋势过滤
        trend_ma_period: int = 60,  # 趋势均线周期
        use_dynamic_target: bool = True,  # 使用动态目标价(基于浪型)
        target_proximity_pct: float = 0.03,  # 接近目标价3%即考虑卖出
        wave_structure_break_pct: float = 0.03  # 浪型破坏阈值3%
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_confidence = min_confidence
        self.use_resonance = use_resonance
        self.min_holding_days = min_holding_days
        self.use_trend_filter = use_trend_filter
        self.trend_ma_period = trend_ma_period
        self.use_dynamic_target = use_dynamic_target
        self.target_proximity_pct = target_proximity_pct
        self.wave_structure_break_pct = wave_structure_break_pct
        
        self.capital = initial_capital
        self.positions: Dict[str, Trade] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []
        
        # 记录持仓时的最新分析结果，用于动态更新目标价
        self.position_analysis: Dict[str, Any] = {}
    
    def generate_signal(
        self,
        analysis_result: Any,
        current_price: float
    ) -> Optional[TradeAction]:
        """
        根据分析结果生成交易信号
        
        Returns:
            TradeAction or None
        """
        if not analysis_result or not analysis_result.primary_pattern:
            return None
        
        pattern = analysis_result.primary_pattern
        
        # 检查置信度
        if pattern.confidence < self.min_confidence:
            return None
        
        # 检查共振
        if self.use_resonance and analysis_result.resonance:
            res = analysis_result.resonance
            # 波浪和指标方向一致才交易
            if not res.wave_aligned:
                return TradeAction.HOLD
            
            # 共振强度足够
            if res.overall_strength < 0.4:
                return TradeAction.HOLD
        
        # 获取最新浪号
        latest_wave = pattern.points[-1].wave_num if pattern.points else None
        
        # 买入条件: 调整浪结束或任何可能反弹的位置
        # 标准调整浪: 2/4/C (回调买入点)
        # ZigZag调整浪: A/B/C 
        # 起点或不确定: 0/None
        buy_waves = ['0', '2', '4', 'C', 'A', 'B', None]
        
        # 对于推动浪的1/3/5，如果前面有足够大的调整，也可以考虑买入
        # 这里简化处理: 只要不是明确的推动浪末端(5)，都尝试买入
        if latest_wave in ['1', '3'] and pattern.direction.value == 'up':
            # 检查是否是推动浪刚开始
            if len(pattern.points) <= 2:  # 刚检测到推动浪起点
                buy_waves.append('1')
        
        if latest_wave in buy_waves:
            if pattern.direction.value == 'up':
                return TradeAction.BUY
            else:
                return TradeAction.SELL  # 做空
        
        # 对于zigzag类型，如果已经到末端也尝试买入
        if pattern.wave_type.value in ['zigzag', 'corrective'] and len(pattern.points) >= 3:
            if pattern.direction.value == 'up':
                return TradeAction.BUY
        
        # 卖出条件: 推动浪完成
        if latest_wave in ['5']:
            return TradeAction.CLOSE
        
        return TradeAction.HOLD
    
    def execute_trade(
        self,
        symbol: str,
        date: str,
        price: float,
        action: TradeAction,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        data_idx: int = 0,  # 当前数据索引
        historical_df: Optional[pd.DataFrame] = None,  # 历史数据用于计算波动率
        current_analysis: Any = None  # 当前分析结果用于记录浪号
    ):
        """执行交易"""
        
        if action == TradeAction.BUY:
            # 开仓
            if symbol in self.positions:
                return  # 已有仓位
            
            position_value = self.capital * self.position_size
            quantity = int(position_value / price / 100) * 100  # 整手
            
            # 修复: 如果按仓位计算不足1手，但至少够买1手，就买1手
            if quantity < 100:
                if position_value >= price * 100:
                    quantity = 100  # 至少买1手
                else:
                    return  # 资金确实不足
            
            # 基于浪型和个股波动率计算目标价
            # 如果是动态目标价模式，根据买入浪号计算预期目标
            if self.use_dynamic_target:
                # 获取当前分析结果（从position_analysis中获取最新的）
                current_analysis = self.position_analysis.get(symbol)
                target_price = self._calculate_wave_based_target(
                    symbol, price, current_analysis, historical_df
                )
            
            # 如果仍然无法计算目标价，使用默认止盈
            if target_price is None or target_price <= price * 1.001:
                target_price = price * (1 + self.take_profit_pct)
            
            # 确保止损价 < 买入价
            calculated_stop = price * (1 - self.stop_loss_pct)
            if stop_loss is None or stop_loss >= price:
                stop_loss = calculated_stop
            
            # 获取买入浪号和预期下一浪
            entry_wave = None
            expected_wave = None
            if current_analysis and current_analysis.primary_pattern:
                entry_wave = current_analysis.primary_pattern.points[-1].wave_num if current_analysis.primary_pattern.points else None
                # 预期下一浪映射
                wave_progression = {
                    'C': '1', '2': '3', '4': '5',
                    'A': 'B', 'B': 'C', '1': '2', '3': '4', '5': None
                }
                expected_wave = wave_progression.get(entry_wave, None)
            
            trade = Trade(
                symbol=symbol,
                entry_date=date,
                entry_price=price,
                action=action,
                quantity=quantity,
                target_price=target_price,
                stop_loss=stop_loss,
                entry_idx=data_idx,  # 记录买入索引
                entry_wave=entry_wave,
                expected_wave=expected_wave
            )
            
            self.positions[symbol] = trade
            self.trades.append(trade)
            
        elif action == TradeAction.CLOSE:
            # 平仓
            if symbol not in self.positions:
                return
            
            trade = self.positions[symbol]
            trade.close(date, price)
            
            # 更新资金
            self.capital += trade.pnl
            
            # 清理持仓分析记录
            if symbol in self.position_analysis:
                del self.position_analysis[symbol]
            
            del self.positions[symbol]
    
    def check_stop_loss_take_profit(
        self, 
        symbol: str, 
        date: str, 
        price: float, 
        data_idx: int = 0,
        current_analysis: Any = None
    ):
        """
        检查止损止盈 - 动态浪型目标价版本
        
        卖出条件:
        1. 固定止损: 价格跌破止损价
        2. 动态止盈: 价格接近目标价(基于浪型计算)
        3. 浪型走坏: 持仓期间浪型结构被破坏
        """
        if symbol not in self.positions:
            return None
        
        trade = self.positions[symbol]
        
        # 检查最小持仓天数
        holding_days = trade.holding_days(data_idx)
        if holding_days < self.min_holding_days:
            return None  # 持仓时间不足，不检查止损止盈
        
        # 1. 固定止损检查
        if trade.stop_loss and price <= trade.stop_loss:
            self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx)
            return "stop_loss"
        
        # 动态目标价模式
        if self.use_dynamic_target and current_analysis and current_analysis.primary_pattern:
            pattern = current_analysis.primary_pattern
            
            # 更新持仓分析记录
            self.position_analysis[symbol] = current_analysis
            
            # 2. 动态止盈: 接近目标价
            if pattern.target_price:
                # 计算当前价格距离目标价的百分比
                distance_to_target = abs(pattern.target_price - price) / price
                
                # 如果接近目标价(在3%范围内)，卖出
                if distance_to_target <= self.target_proximity_pct:
                    self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx)
                    return f"target_proximity({pattern.target_price:.2f})"
                
                # 如果价格已经超过目标价，立即卖出
                if price >= pattern.target_price:
                    self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx)
                    return f"target_reached({pattern.target_price:.2f})"
            
            # 3. 浪型走坏检测
            if self._is_wave_structure_broken(symbol, pattern, price):
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx)
                return "wave_structure_broken"
        
        # 备用: 固定止盈(如果动态目标价不可用)
        elif not self.use_dynamic_target:
            if trade.target_price and price >= trade.target_price:
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx)
                return "take_profit_fixed"
        
        return None
    
    def _is_wave_structure_broken(self, symbol: str, current_pattern: Any, current_price: float) -> bool:
        """
        检测浪型结构是否走坏
        
        判断标准:
        1. 当前浪号从买入时发生变化(比如从浪C变成浪A，意味着新调整开始)
        2. 方向发生反转
        3. 价格跌破关键支撑位
        """
        if symbol not in self.position_analysis:
            return False
        
        entry_analysis = self.position_analysis[symbol]
        if not entry_analysis or not entry_analysis.primary_pattern:
            return False
        
        entry_pattern = entry_analysis.primary_pattern
        
        # 获取当前和买入时的浪号
        entry_wave = entry_pattern.points[-1].wave_num if entry_pattern.points else None
        current_wave = current_pattern.points[-1].wave_num if current_pattern.points else None
        
        # 标准1: 浪号变化且不是正常推进
        # 例如: 买入时是浪C(调整结束)，现在变成浪A(新调整开始)
        if entry_wave and current_wave:
            # 如果买入时是C浪(期待上涨)，现在变成A浪(新的下跌调整)
            if entry_wave == 'C' and current_wave == 'A':
                return True
            # 如果买入时是2/4浪(期待上涨)，现在变成1/3/5浪(可能已经是推动浪末端)
            if entry_wave in ['2', '4'] and current_wave in ['1', '3', '5']:
                # 如果已经有足够涨幅，认为是正常推进; 如果涨幅很小，可能是误判
                entry_price = self.positions[symbol].entry_price
                if (current_price - entry_price) / entry_price < 0.02:  # 涨幅<2%
                    return True
        
        # 标准2: 方向反转
        if entry_pattern.direction.value != current_pattern.direction.value:
            # 只有当方向从up变成down才认为是走坏
            if entry_pattern.direction.value == 'up' and current_pattern.direction.value == 'down':
                return True
        
        # 标准3: 置信度大幅下降
        if current_pattern.confidence < entry_pattern.confidence * 0.5:
            return True
        
        return False
    
    def _calculate_wave_based_target(
        self, 
        symbol: str, 
        entry_price: float, 
        analysis_result: Any,
        historical_df: pd.DataFrame
    ) -> Optional[float]:
        """
        基于浪型和个股历史波动率计算目标价
        
        策略:
        - C浪末买入 → 计算后续1浪涨幅 (推动浪开始,预期涨幅较小)
        - 2浪末买入 → 计算后续3浪涨幅 (主升浪,预期涨幅最大)  
        - 4浪末买入 → 计算后续5浪涨幅 (末浪,预期涨幅中等)
        - A/B浪买入 → 默认使用历史平均波动率
        
        波动率计算:
        - 基于个股60日涨跌幅标准差
        - 结合ATR(平均真实波幅)
        """
        if not analysis_result or not analysis_result.primary_pattern:
            return None
        
        pattern = analysis_result.primary_pattern
        
        # 获取买入时的浪号
        entry_wave = pattern.points[-1].wave_num if pattern.points else None
        
        # 计算个股历史波动率
        volatility = self._calculate_stock_volatility(historical_df)
        
        # 根据浪号确定预期涨幅倍数
        # 基于Elliott Wave理论:
        # 浪1: 通常是推动浪的开始,涨幅相对保守
        # 浪3: 通常是主升浪,涨幅最大(可能是1浪的1.618倍)
        # 浪5: 通常是末浪,涨幅与1浪相近或较小
        wave_multipliers = {
            'C': 1.0,   # C浪后1浪: 基础涨幅
            '2': 1.618, # 2浪后3浪: 主升浪,预期最高
            '4': 1.0,   # 4浪后5浪: 末浪,保守预期
            'A': 0.8,   # A浪后B浪: 反弹,较保守
            'B': 1.2,   # B浪后C浪: 可能延续
            None: 1.0   # 未知浪号: 默认
        }
        
        multiplier = wave_multipliers.get(entry_wave, 1.0)
        
        # 计算目标涨幅 = 波动率 × 浪型倍数 × 安全系数(0.8)
        # 安全系数避免过度乐观
        safety_factor = 0.8
        target_return = volatility * multiplier * safety_factor
        
        # 确保最小目标涨幅(至少5%)和最大限制(不超过30%)
        target_return = max(0.05, min(target_return, 0.30))
        
        target_price = entry_price * (1 + target_return)
        
        return target_price
    
    def _calculate_stock_volatility(self, df: pd.DataFrame, lookback: int = 60) -> float:
        """
        计算个股历史波动率
        
        综合使用:
        1. 日收益率标准差(年化)
        2. ATR(平均真实波幅)百分比
        """
        if len(df) < lookback:
            lookback = len(df)
        
        recent_df = df.tail(lookback).copy()
        
        # 方法1: 日收益率标准差(年化)
        recent_df['returns'] = recent_df['close'].pct_change()
        daily_std = recent_df['returns'].std()
        annual_volatility = daily_std * np.sqrt(252)  # 年化
        
        # 方法2: ATR百分比
        recent_df['high_low'] = recent_df['high'] - recent_df['low']
        recent_df['high_close'] = abs(recent_df['high'] - recent_df['close'].shift())
        recent_df['low_close'] = abs(recent_df['low'] - recent_df['close'].shift())
        recent_df['tr'] = recent_df[['high_low', 'high_close', 'low_close']].max(axis=1)
        atr = recent_df['tr'].mean()
        atr_pct = atr / recent_df['close'].mean() if recent_df['close'].mean() > 0 else 0
        
        # 综合波动率(取两者平均)
        # 将ATR百分比转换为与年化波动率类似的量级
        combined_volatility = (annual_volatility + atr_pct * np.sqrt(252)) / 2
        
        # 默认最小波动率10%
        return max(combined_volatility, 0.10)
    
    def record_equity(self, date: str, price: float):
        """记录权益曲线"""
        position_value = 0
        for trade in self.positions.values():
            position_value += trade.quantity * price
        
        total_equity = self.capital + position_value
        
        self.equity_curve.append({
            'date': date,
            'capital': self.capital,
            'position_value': position_value,
            'total_equity': total_equity,
            'return_pct': (total_equity - self.initial_capital) / self.initial_capital * 100
        })


class WaveBacktester:
    """波浪回测器"""
    
    def __init__(self, analyzer: Any):
        self.analyzer = analyzer
        self.strategy = WaveStrategy()
    
    def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        reanalyze_every: int = 5  # 每5天重新分析
    ) -> BacktestResult:
        """
        运行回测
        
        Args:
            symbol: 股票代码
            df: 历史数据
            reanalyze_every: 重新分析频率(交易日)
            
        Returns:
            BacktestResult
        """
        print(f"\n开始回测 {symbol}...")
        print(f"数据范围: {df['date'].min()} ~ {df['date'].max()}, {len(df)} 条")
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 计算趋势均线
        if self.strategy.use_trend_filter:
            df['ma_trend'] = df['close'].rolling(window=self.strategy.trend_ma_period).mean()
        
        current_analysis = None
        
        for i, row in df.iterrows():
            date = row['date'].strftime('%Y-%m-%d')
            price = row['close']
            
            # 趋势过滤：只在均线之上才考虑买入
            if self.strategy.use_trend_filter and 'ma_trend' in row:
                ma_trend = row['ma_trend']
                if pd.notna(ma_trend) and price < ma_trend:
                    # 价格在均线下方，跳过买入信号
                    current_analysis = None
            
            # 定期重新分析
            if i % reanalyze_every == 0 or current_analysis is None:
                # 使用最近60天数据进行分析
                lookback_start = max(0, i - 60)
                analysis_df = df.iloc[lookback_start:i+1].copy()
                
                if len(analysis_df) >= 20:
                    try:
                        current_analysis = self.analyzer.analyze(symbol, analysis_df)
                    except Exception:
                        current_analysis = None
            
            # 生成信号
            if current_analysis:
                signal = self.strategy.generate_signal(current_analysis, price)
                
                if signal == TradeAction.BUY:
                    target = current_analysis.primary_pattern.target_price if current_analysis.primary_pattern else None
                    stop = current_analysis.primary_pattern.stop_loss if current_analysis.primary_pattern else None
                    # 记录分析结果用于目标价计算
                    self.strategy.position_analysis[symbol] = current_analysis
                    # 传入历史数据用于计算波动率
                    historical_df = df.iloc[:i+1].copy()
                    self.strategy.execute_trade(symbol, date, price, signal, target, stop, data_idx=i, historical_df=historical_df, current_analysis=current_analysis)
                
                elif signal == TradeAction.CLOSE:
                    self.strategy.execute_trade(symbol, date, price, signal, data_idx=i)
            
            # 检查止损止盈 - 传入当前分析结果以支持动态目标价
            self.strategy.check_stop_loss_take_profit(symbol, date, price, data_idx=i, current_analysis=current_analysis)
            
            # 记录权益
            self.strategy.record_equity(date, price)
        
        # 计算结果
        return self._calculate_result(symbol, df)
    
    def _calculate_result(self, symbol: str, df: pd.DataFrame) -> BacktestResult:
        """计算回测结果"""
        trades = self.strategy.trades
        
        if not trades:
            return BacktestResult(
                symbol=symbol,
                start_date=df['date'].min(),
                end_date=df['date'].max(),
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_return=0.0,
                total_return_pct=0.0,
                avg_return_per_trade=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0
            )
        
        closed_trades = [t for t in trades if t.status == "closed"]
        
        if not closed_trades:
            return BacktestResult(
                symbol=symbol,
                start_date=df['date'].min(),
                end_date=df['date'].max(),
                total_trades=len(trades),
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_return=0.0,
                total_return_pct=0.0,
                avg_return_per_trade=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                trades=trades
            )
        
        # 统计
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        total_pnl_pct = sum(t.pnl_pct for t in closed_trades)
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        
        # 最大回撤
        equity_values = [e['total_equity'] for e in self.strategy.equity_curve]
        max_dd = 0
        peak = equity_values[0] if equity_values else 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        
        max_dd_pct = (max_dd / peak * 100) if peak > 0 else 0
        
        # Sharpe (简化版，假设无风险利率0)
        returns = [t.pnl_pct for t in closed_trades]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)  # 年化
        else:
            sharpe = 0
        
        return BacktestResult(
            symbol=symbol,
            start_date=df['date'].min(),
            end_date=df['date'].max(),
            total_trades=len(closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(closed_trades) if closed_trades else 0,
            total_return=total_pnl,
            total_return_pct=total_pnl_pct,
            avg_return_per_trade=total_pnl_pct / len(closed_trades) if closed_trades else 0,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            profit_factor=gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            trades=trades,
            equity_curve=self.strategy.equity_curve
        )
    
    def generate_report(self, result: BacktestResult) -> str:
        """生成回测报告"""
        lines = []
        
        lines.append(f"\n{'='*60}")
        lines.append(f"📊 {result.symbol} 回测报告")
        lines.append('='*60)
        
        lines.append(f"\n【回测周期】")
        lines.append(f"  {result.start_date} ~ {result.end_date}")
        
        lines.append(f"\n【交易统计】")
        lines.append(f"  总交易次数: {result.total_trades}")
        lines.append(f"  盈利次数: {result.winning_trades}")
        lines.append(f"  亏损次数: {result.losing_trades}")
        lines.append(f"  胜率: {result.win_rate:.1%}")
        
        lines.append(f"\n【收益表现】")
        lines.append(f"  总收益率: {result.total_return_pct:.2f}%")
        lines.append(f"  平均每笔收益: {result.avg_return_per_trade:.2f}%")
        lines.append(f"  最大回撤: {result.max_drawdown_pct:.2f}%")
        
        lines.append(f"\n【风险指标】")
        lines.append(f"  Sharpe比率: {result.sharpe_ratio:.2f}")
        lines.append(f"  盈亏比: {result.profit_factor:.2f}")
        
        # 最近5笔交易
        if result.trades:
            lines.append(f"\n【最近交易】")
            for trade in result.trades[-5:]:
                status_icon = "✅" if trade.pnl > 0 else "❌" if trade.pnl < 0 else "⏸️"
                lines.append(f"  {status_icon} {trade.entry_date} 买入¥{trade.entry_price:.2f} -> "
                           f"{trade.exit_date or '持仓中'} "
                           f"{f'¥{trade.exit_price:.2f}' if trade.exit_price else ''} "
                           f"{f'收益{trade.pnl_pct:.1f}%' if trade.status == 'closed' else ''}")
        
        return '\n'.join(lines)
