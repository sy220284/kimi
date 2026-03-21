"""
回测框架 - Phase 5 验证层 (集成 UnifiedWaveAnalyzer)
验证波浪分析策略的历史表现
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

# 添加项目根目录到路径

from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer, UnifiedWaveSignal

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
    exit_date: str | None = None
    exit_price: float | None = None
    quantity: int = 100  # 默认100股
    stop_loss: float | None = None
    target_price: float | None = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    status: str = "open"  # open/closed
    entry_idx: int = 0  # 买入时的数据索引，用于计算持仓天数
    entry_wave: str | None = None  # 买入时的浪号
    expected_wave: str | None = None  # 预期下一浪(用于目标价计算)
    exit_reason: str | None = None  # 卖出原因: stop_loss/target_reached/target_proximity/wave_structure_broken/trailing_stop

    # 移动止盈相关字段
    target_hit: bool = False  # 是否已达到目标价
    target_hit_price: float | None = None  # 达到目标时的价格
    target_hit_idx: int | None = None  # 达到目标时的索引
    highest_price: float | None = None  # 达到目标后的最高价（用于移动止盈）
    trailing_stop_price: float | None = None  # 移动止盈价位

    def close(self, date: str, price: float, reason: str = ""):
        """平仓"""
        self.exit_date = date
        self.exit_price = price
        self.exit_reason = reason
        self.pnl = (price - self.entry_price) * self.quantity
        self.pnl_pct = (price - self.entry_price) / self.entry_price * 100
        self.status = "closed"

    def holding_days(self, current_idx: int) -> int:
        """计算持仓天数"""
        return current_idx - self.entry_idx

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，用于保存交易明细"""
        holding_days = None
        if self.exit_date and self.entry_date:
            try:
                from datetime import datetime
                exit_dt = datetime.strptime(self.exit_date, '%Y-%m-%d')
                entry_dt = datetime.strptime(self.entry_date, '%Y-%m-%d')
                holding_days = (exit_dt - entry_dt).days
            except Exception:
                holding_days = None

        return {
            'symbol': self.symbol,
            'entry_date': self.entry_date,
            'entry_price': round(self.entry_price, 3),
            'exit_date': self.exit_date,
            'exit_price': round(self.exit_price, 3) if self.exit_price else None,
            'quantity': self.quantity,
            'target_price': round(self.target_price, 3) if self.target_price else None,
            'stop_loss': round(self.stop_loss, 3) if self.stop_loss else None,
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct, 2),
            'holding_days': holding_days,
            'entry_wave': self.entry_wave,
            'exit_reason': self.exit_reason,
            'status': self.status
        }

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
    calmar_ratio: float = 0.0   # 年化收益 / 最大回撤，衡量单位回撤的回报
    sortino_ratio: float = 0.0  # 超额收益 / 下行标准差，比Sharpe更适合股票策略
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（数值字段返回原始浮点数，便于聚合/比较）"""
        return {
            'symbol': self.symbol,
            'start_date': str(self.start_date) if self.start_date else None,
            'end_date': str(self.end_date) if self.end_date else None,
            'period': f"{self.start_date} ~ {self.end_date}",
            'total_trades': self.total_trades,
            'win_rate': self.win_rate,                     # float 0-1
            'win_rate_pct': f"{self.win_rate:.1%}",        # formatted string
            'total_return_pct': self.total_return_pct,     # float
            'total_return': f"{self.total_return_pct:.2f}%",
            'avg_return_per_trade': self.avg_return_per_trade,  # float
            'max_drawdown_pct': self.max_drawdown_pct,     # float
            'max_drawdown': f"{self.max_drawdown_pct:.2f}%",
            'sharpe_ratio': self.sharpe_ratio,             # float
            'sortino_ratio': self.sortino_ratio,           # float
            'calmar_ratio': self.calmar_ratio,             # float
            # profit_factor=inf 时 JSON 序列化不合规，上限 999.99
            'profit_factor': min(self.profit_factor, 999.99) if self.profit_factor != float('inf') else 999.99,
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
        position_size: float = 0.2,  # 单笔基础仓位20%（Kelly模式下作为上限）
        max_positions: int = 3,  # 最大持仓数量
        max_total_position: float = 0.8,  # 最大总仓位80%
        stop_loss_pct: float = 0.05,  # 5%止损
        take_profit_pct: float = 0.15,  # 15%止盈(备用)
        min_confidence: float = 0.5,
        use_resonance: bool = True,
        min_holding_days: int = 3,  # 最小持仓天数
        use_trend_filter: bool = True,  # 使用趋势过滤
        trend_ma_period: int = 200,  # 趋势均线周期 (优化: 200日均线)
        use_dynamic_target: bool = True,  # 使用动态目标价(基于浪型)
        target_proximity_pct: float = 0.03,  # 接近目标价3%即考虑卖出
        wave_structure_break_pct: float = 0.03,  # 浪型破坏阈值3%
        commission_rate: float = 0.0003,  # 佣金费率0.03%
        # B3: Kelly 仓位管理
        use_kelly: bool = True,          # 是否启用Kelly公式动态仓位
        kelly_max_fraction: float = 0.25, # Kelly仓位上限（防止过度集中）
        stamp_tax_rate: float = 0.001,  # 印花税0.1%(仅卖出)
        slippage_rate: float = 0.001,  # 滑点0.1%
        # 移动止盈参数
        use_trailing_stop: bool = True,  # 达到目标后启用移动止盈
        trailing_stop_pct: float = 0.08,  # 移动止盈回撤8%卖出
        trailing_stop_activation: float = 1.0,  # 达到目标价100%时激活移动止盈
        # E3: 新增出场条件
        max_holding_days: int = 60,       # 最大持仓天数（时间止损，防止资金锁死）
        breakeven_pct: float = 0.05,      # 浮盈达到5%后，将止损上移至成本（保本止损）
    ):
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.max_positions = max_positions
        self.max_total_position = max_total_position
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
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.slippage_rate = slippage_rate

        # B3: Kelly 仓位管理
        self.use_kelly = use_kelly
        self.kelly_max_fraction = kelly_max_fraction
        self.use_trailing_stop = use_trailing_stop
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_stop_activation = trailing_stop_activation
        # E3
        self.max_holding_days = max_holding_days
        self.breakeven_pct    = breakeven_pct

        self.capital = initial_capital
        self.positions: dict[str, Trade] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[dict[str, Any]] = []

        # 记录持仓时的最新分析结果，用于动态更新目标价
        self.position_analysis: dict[str, Any] = {}

    def _kelly_fraction(self, wave_signal: Any) -> float:
        """
        Kelly 公式仓位计算

        f* = (b×p - q) / b
          b = 盈亏比（目标收益 / 止损距离）
          p = 置信度（信号强度作为胜率估计）
          q = 1 - p

        Returns:
            Kelly 仓位比例，限制在 [position_size×0.5, kelly_max_fraction] 之间
        """
        try:
            p = min(max(float(wave_signal.confidence), 0.3), 0.9)
            q = 1.0 - p

            entry = wave_signal.entry_price
            target = wave_signal.target_price
            stop   = wave_signal.stop_loss

            if entry <= 0 or target <= entry or stop >= entry:
                return self.position_size

            reward = target - entry
            risk   = entry - stop
            if risk <= 0:
                return self.position_size

            b = reward / risk            # 盈亏比
            kelly = (b * p - q) / b      # Kelly公式

            # 约束：不低于 position_size×0.5（避免过于保守），不超过 kelly_max_fraction
            fraction = max(self.position_size * 0.5, min(kelly, self.kelly_max_fraction))
            return round(fraction, 4)

        except Exception:
            return self.position_size

    def reset(self):
        """重置策略状态"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        self.position_analysis = {}

    def execute_trade(
        self,
        symbol: str,
        date: str,
        price: float,
        action: TradeAction,
        target_price: float | None = None,
        stop_loss: float | None = None,
        data_idx: int = 0,
        historical_df: pd.DataFrame | None = None,
        wave_signal: UnifiedWaveSignal | None = None,
        is_limit_up: bool = False,  # 是否涨停
        is_limit_down: bool = False,  # 是否跌停
        **kwargs
    ):
        """执行交易 - 适配 UnifiedWaveSignal + 交易成本 + 涨跌停处理"""

        if action == TradeAction.BUY:
            # 涨停无法买入
            if is_limit_up:
                return

            # 已有持仓则跳过
            if symbol in self.positions:
                return

            # 检查持仓数量限制
            if len(self.positions) >= self.max_positions:
                return

            # 检查总仓位限制
            current_position_value = sum(
                t.quantity * price for t in self.positions.values()
            )
            current_position_ratio = current_position_value / (self.capital + current_position_value)

            if current_position_ratio >= self.max_total_position:
                return

            # B3: Kelly 公式动态仓位
            # f* = (b×p - q) / b，其中 b=盈亏比，p=置信度（胜率估计），q=1-p
            # 使用 min(kelly_fraction, kelly_max_fraction) 防止过度集中
            if self.use_kelly and wave_signal is not None:
                kelly_frac = self._kelly_fraction(wave_signal)
            else:
                kelly_frac = self.position_size

            # 计算可用资金
            available_capital = self.capital * kelly_frac

            # 考虑买入成本(佣金+滑点)
            buy_cost_rate = self.commission_rate + self.slippage_rate
            effective_price = price * (1 + buy_cost_rate)

            # 计算股数(100股为单位)
            quantity = int(available_capital / effective_price / 100) * 100

            if quantity < 100:
                # 资金不足买入1手
                if available_capital >= effective_price * 100:
                    quantity = 100
                else:
                    return

            # 实际成本
            actual_cost = quantity * effective_price

            # 检查资金是否充足
            if actual_cost > self.capital:
                return

            # 动态目标价计算
            if self.use_dynamic_target and wave_signal:
                target_price = wave_signal.target_price
                # 确保目标价合理
                if target_price <= price * 1.001:
                    target_price = price * (1 + self.take_profit_pct)
                stop_loss = wave_signal.stop_loss

            if target_price is None or target_price <= price * 1.001:
                target_price = price * (1 + self.take_profit_pct)

            if stop_loss is None or stop_loss >= price:
                stop_loss = price * (1 - self.stop_loss_pct)

            # 从 UnifiedWaveSignal 获取浪号
            entry_wave = wave_signal.entry_type.value if wave_signal else None
            expected_wave = {'C': '1', '2': '3', '4': '5'}.get(entry_wave)

            trade = Trade(
                symbol=symbol,
                entry_date=date,
                entry_price=effective_price,  # 使用实际成交价(含成本)
                action=action,
                quantity=quantity,
                target_price=target_price,
                stop_loss=stop_loss,
                entry_idx=data_idx,
                entry_wave=entry_wave,
                expected_wave=expected_wave
            )

            self.positions[symbol] = trade
            self.trades.append(trade)

            # 扣除资金
            self.capital -= actual_cost

            # 记录信号用于后续检查
            if wave_signal:
                self.position_analysis[symbol] = wave_signal

        elif action == TradeAction.CLOSE:
            # 跌停无法卖出
            if is_limit_down:
                return

            if symbol not in self.positions:
                return

            trade = self.positions[symbol]

            # 考虑卖出成本(佣金+印花税+滑点)
            sell_cost_rate = self.commission_rate + self.stamp_tax_rate + self.slippage_rate
            effective_price = price * (1 - sell_cost_rate)

            # 获取卖出原因（从kwargs中获取）
            reason = kwargs.get('reason', '')
            trade.close(date, effective_price, reason)  # 使用实际成交价(扣除成本)

            # 回收资金
            self.capital += trade.quantity * effective_price

            if symbol in self.position_analysis:
                del self.position_analysis[symbol]

            del self.positions[symbol]

    def check_stop_loss_take_profit(
        self,
        symbol: str,
        date: str,
        price: float,
        data_idx: int = 0,
        wave_signal: UnifiedWaveSignal | None = None,
        is_limit_down: bool = False  # 跌停无法卖出
    ):
        """
        检查止损止盈 - 适配 UnifiedWaveSignal + 涨跌停处理 + 移动止盈
        """
        if symbol not in self.positions:
            return None

        # 跌停无法卖出
        if is_limit_down:
            return None

        trade = self.positions[symbol]

        # 检查最小持仓天数
        holding_days = trade.holding_days(data_idx)
        if holding_days < self.min_holding_days:
            return None

        # E3-a: 时间止损（防止资金长期被套死）
        if self.max_holding_days > 0 and holding_days >= self.max_holding_days:
            self.execute_trade(symbol, date, price, TradeAction.CLOSE,
                               data_idx=data_idx, is_limit_down=is_limit_down,
                               reason="time_stop")
            return "time_stop"

        # E3-b: 保本止损（浮盈达标后将止损上移至成本）
        if self.breakeven_pct > 0 and trade.entry_price and trade.stop_loss:
            profit_pct = (price - trade.entry_price) / trade.entry_price
            if profit_pct >= self.breakeven_pct:
                # 止损未升至成本以上时，上移至成本价
                if trade.stop_loss < trade.entry_price:
                    trade.stop_loss = trade.entry_price   # 保本

        # 1. 固定止损检查
        if trade.stop_loss and price <= trade.stop_loss:
            self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason="stop_loss")
            return "stop_loss"

        # 2. 移动止盈逻辑
        if self.use_trailing_stop and trade.target_price:
            target_threshold = trade.target_price * self.trailing_stop_activation

            # 首次达到目标价阈值，启动移动止盈
            if not trade.target_hit and price >= target_threshold:
                trade.target_hit = True
                trade.target_hit_price = price
                trade.target_hit_idx = data_idx
                trade.highest_price = price
                # 设置初始移动止盈价位（从最高点回撤 trailing_stop_pct）
                trade.trailing_stop_price = price * (1 - self.trailing_stop_pct)
                return None  # 继续持仓，启动移动止盈跟踪

            # 已经启动移动止盈，更新最高价和移动止盈价位
            if trade.target_hit:
                # 更新最高价
                if price > trade.highest_price:
                    trade.highest_price = price
                    # 更新移动止盈价位（从新的最高点回撤 trailing_stop_pct）
                    trade.trailing_stop_price = price * (1 - self.trailing_stop_pct)

                # 检查是否触发移动止盈
                if trade.trailing_stop_price and price <= trade.trailing_stop_price:
                    self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down,
                                     reason="trailing_stop")
                    return "trailing_stop"

        # 3. 原动态止盈逻辑（当不启用移动止盈或作为备选）
        if not self.use_trailing_stop and trade.target_price:
            distance_to_target = abs(trade.target_price - price) / price

            if distance_to_target <= self.target_proximity_pct:
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason="target_proximity")
                return f"target_proximity({trade.target_price:.2f})"

            if price >= trade.target_price:
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason="target_reached")
                return f"target_reached({trade.target_price:.2f})"

        return None

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

        # 综合波动率: 结合日收益率标准差和ATR百分比
        combined_volatility = max(annual_volatility, atr_pct)

        # 便捷函数
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
    """
    波浪回测器 - 集成 UnifiedWaveAnalyzer

    适配 UnifiedWaveAnalyzer 的信号结构:
    - UnifiedWaveSignal 替代原 analysis_result
    - 直接使用 detect() 方法获取信号
    """

    def __init__(
        self,
        analyzer: UnifiedWaveAnalyzer | None = None,
        strategy: WaveStrategy | None = None,
    ):
        """
        Args:
            analyzer: 波浪分析器实例（默认 UnifiedWaveAnalyzer）
            strategy: 交易策略实例（默认 WaveStrategy()）

        注意：第一个参数历史上曾被误用于传入 WaveStrategy，
              现已同时支持两种调用方式以保持向后兼容：
                WaveBacktester(my_strategy)   # 兼容旧写法
                WaveBacktester(strategy=my_strategy)  # 推荐写法
        """
        # 向后兼容：如果第一个参数是 WaveStrategy，自动识别
        if isinstance(analyzer, WaveStrategy):
            strategy = analyzer
            analyzer = None

        self.analyzer = analyzer if analyzer is not None else UnifiedWaveAnalyzer()
        self.strategy = strategy if strategy is not None else WaveStrategy()
        self._current_signals: list[UnifiedWaveSignal] = []
        self._signal_ages: dict[int, int] = {}
        self._signal_decay: dict[int, float] = {}

    def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        reanalyze_every: int = 5  # 每5天重新分析
    ) -> BacktestResult:
        """
        运行回测 - 使用 UnifiedWaveAnalyzer

        修复:
        1. 前视偏差: 只使用i之前的数据(不含当天)
        2. 涨跌停处理: 检测涨跌停,无法成交
        3. 趋势过滤: 在买入时过滤,不清空信号

        Args:
            symbol: 股票代码
            df: 历史数据
            reanalyze_every: 重新分析频率(交易日)

        Returns:
            BacktestResult
        """
        print(f"\n开始回测 {symbol}...")

        # 空数据检查
        if df is None or df.empty:
            print("⚠️ 数据为空，跳过回测")
            return BacktestResult(
                symbol=symbol,
                start_date="",
                end_date="",
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
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                profit_factor=0.0,
                trades=[],
                equity_curve=[]
            )

        print(f"数据范围: {df['date'].min()} ~ {df['date'].max()}, {len(df)} 条")

        # 重置策略状态 - 防止批量回测时状态污染
        self.strategy.reset()

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        # 计算涨跌停标记 - 根据板块设置不同阈值
        # 科创板(688)/创业板(300)涨停20%，主板(600/601/603/000/002)涨停10%
        symbol_prefix = symbol[:3] if len(symbol) >= 3 else symbol
        if symbol_prefix in ['688', '300', '301']:
            limit_up_threshold = 0.195    # 19.5%视为涨停(考虑误差)
            limit_down_threshold = -0.195  # -19.5%视为跌停
        else:
            limit_up_threshold = 0.095     # 9.5%视为涨停
            limit_down_threshold = -0.095  # -9.5%视为跌停

        df['pct_change'] = df['close'].pct_change()
        df['is_limit_up'] = df['pct_change'] >= limit_up_threshold
        df['is_limit_down'] = df['pct_change'] <= limit_down_threshold

        # 计算200日均线趋势
        if self.strategy.use_trend_filter:
            df['ma_trend'] = df['close'].rolling(window=self.strategy.trend_ma_period).mean()

        self._current_signals = []
        self._signal_ages = {}
        self._signal_decay = {}

        # OPT-B1: 预提取 numpy 数组，消除循环内 df.iloc[i] 开销（127x 提速）
        _closes    = df['close'].values.astype(float)
        _dates_str = df['date'].dt.strftime('%Y-%m-%d').values
        _limit_up  = df['is_limit_up'].values.astype(bool)
        _limit_dn  = df['is_limit_down'].values.astype(bool)

        for i in range(len(df)):
            date         = _dates_str[i]
            price        = _closes[i]
            is_limit_up  = bool(_limit_up[i])
            is_limit_down= bool(_limit_dn[i])

            # E6 + 动态重分析：定期重分析，并对持续的旧信号衰减置信度
            if i % reanalyze_every == 0 or len(self._current_signals) == 0:
                if i >= 30:
                    # E4: 动态回溯窗口（根据ATR波动率，高波动用更短窗口）
                    _atr_recent = float(np.std(_closes[max(0,i-20):i])) if i >= 20 else 1.0
                    _atr_pct    = _atr_recent / (_closes[i-1] + 1e-10)
                    _lookback   = 40 if _atr_pct > 0.03 else 60   # 高波动用40天，低波动用60天
                    lookback_start = max(0, i - _lookback)
                    analysis_df = df.iloc[lookback_start:i].copy()

                    try:
                        self._current_signals = self.analyzer.detect(analysis_df, mode='all')
                        self._signal_ages = {id(s): 0 for s in self._current_signals}
                        self._signal_decay = {id(s): 1.0 for s in self._current_signals}
                    except Exception as e:
                        self._current_signals = []
                        self._signal_ages = {}
            else:
                # E6: 信号置信度衰减（每个 reanalyze 周期信号未刷新则衰减）
                if hasattr(self, '_signal_ages'):
                    alive = []
                    for s in self._current_signals:
                        age = self._signal_ages.get(id(s), 0) + 1
                        self._signal_ages[id(s)] = age
                        # 每经过一个 reanalyze_every 周期衰减 8%
                        decay = max(0.0, 1.0 - age * 0.08)
                        # Bug 3 修复：不原地修改信号对象 confidence，
                        # 而是用 _signal_decay 字典记录衰减系数，
                        # _get_best_trade_signal 读取时应用衰减
                        effective_conf = s.confidence * decay
                        self._signal_decay[id(s)] = decay
                        if effective_conf >= 0.20:   # 低于 0.20 视为陈旧信号丢弃
                            alive.append(s)
                    self._current_signals = alive

            # 生成交易信号
            best_signal = self._get_best_trade_signal(price)

            # 买入信号 - 在这里进行趋势过滤
            if best_signal and best_signal.direction == 'up':
                # 趋势过滤: 价格低于200日均线2%则不买入
                can_buy = True
                if self.strategy.use_trend_filter:
                    ma_trend = df['ma_trend'].iloc[i]
                    if pd.notna(ma_trend) and price < ma_trend * 0.98:
                        can_buy = False

                if can_buy:
                    target = best_signal.target_price
                    stop = best_signal.stop_loss
                    # 传入历史数据用于计算波动率
                    historical_df = df.iloc[:i].copy()  # 修复: 不含当天
                    self.strategy.execute_trade(
                        symbol, date, price, TradeAction.BUY,
                        target, stop, data_idx=i,
                        historical_df=historical_df,
                        wave_signal=best_signal,
                        is_limit_up=is_limit_up,
                        is_limit_down=is_limit_down
                    )

            # 检查止损止盈 - 使用最佳信号进行动态目标价检查
            best_for_exit = self._get_best_trade_signal(price)
            self.strategy.check_stop_loss_take_profit(
                symbol, date, price, data_idx=i,
                wave_signal=best_for_exit,
                is_limit_down=is_limit_down
            )

            # 记录权益
            self.strategy.record_equity(date, price)

        # 计算结果
        return self._calculate_result(symbol, df)

    def _get_best_trade_signal(self, current_price: float) -> UnifiedWaveSignal | None:
        """获取最佳交易信号"""
        if not self._current_signals:
            return None

        # 过滤有效信号（应用衰减因子，不修改原始 confidence）
        decay_map = getattr(self, '_signal_decay', {})
        valid_signals = [
            s for s in self._current_signals
            if s.is_valid and (s.confidence * decay_map.get(id(s), 1.0)) >= 0.5
        ]

        if not valid_signals:
            return None

        # 按综合评分排序 (置信度 + 共振分数)
        valid_signals.sort(
            key=lambda x: (x.confidence + getattr(x, 'resonance_score', 0)) / 2,
            reverse=True
        )

        return valid_signals[0]

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
                sortino_ratio=0.0,
                calmar_ratio=0.0,
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
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                profit_factor=0.0,
                trades=trades
            )

        # 统计
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in closed_trades)

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))

        # 权益曲线和资金加权收益率
        equity_values = [e['total_equity'] for e in self.strategy.equity_curve]
        if equity_values and len(equity_values) >= 2:
            initial_equity = equity_values[0]
            final_equity = equity_values[-1]
            # 资金加权收益率 = (期末权益 - 期初资金) / 期初资金 * 100
            total_return_pct = (final_equity - self.strategy.initial_capital) / self.strategy.initial_capital * 100

            # 计算每日权益收益率用于Sharpe/Sortino
            # 注：包含空仓日（return≈0），会稀释波动率使Sharpe偏高
            # 这是组合回测的常规做法（Portfolio Sharpe）
            # 无风险利率：A股年化3% ≈ 日化0.0119%
            daily_returns = pd.Series(equity_values).pct_change().dropna()
            rf_daily = 0.03 / 252
            if len(daily_returns) > 1 and daily_returns.std() > 0:
                sharpe = ((daily_returns.mean() - rf_daily) / daily_returns.std()) * np.sqrt(252)
            else:
                sharpe = 0.0

            # Sortino：只惩罚下行波动（比Sharpe更适合股票策略）
            downside = daily_returns[daily_returns < rf_daily] - rf_daily
            downside_std = float(downside.std()) if len(downside) > 1 else 0.0
            sortino = ((daily_returns.mean() - rf_daily) / downside_std * np.sqrt(252)
                       ) if downside_std > 0 else 0.0
        else:
            total_return_pct = 0.0
            sharpe = 0.0
            sortino = 0.0

        # 最大回撤
        max_dd = 0
        max_dd_pct = 0.0
        peak = equity_values[0] if equity_values else 0

        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
            if peak > 0:
                dd_pct = (peak - equity) / peak * 100
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

        # Calmar：年化收益率 / 最大回撤（衡量单位风险的回报）
        # 使用复利年化：(1 + total_return)^(252/n_days) - 1
        if equity_values and len(equity_values) >= 2:
            n_days = len(equity_values)
            compound_annual = (1 + total_return_pct / 100) ** (252 / max(n_days, 1)) - 1
            calmar = (compound_annual / (max_dd_pct / 100)) if max_dd_pct > 0 else 0.0
        else:
            calmar = 0.0

        return BacktestResult(
            symbol=symbol,
            start_date=df['date'].min(),
            end_date=df['date'].max(),
            total_trades=len(closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(closed_trades) if closed_trades else 0,
            total_return=total_pnl,
            total_return_pct=total_return_pct,
            avg_return_per_trade=float(np.mean([t.pnl_pct for t in closed_trades])) if closed_trades else 0,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
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

        lines.append("\n【回测周期】")
        lines.append(f"  {result.start_date} ~ {result.end_date}")

        lines.append("\n【交易统计】")
        lines.append(f"  总交易次数: {result.total_trades}")
        lines.append(f"  盈利次数: {result.winning_trades}")
        lines.append(f"  亏损次数: {result.losing_trades}")
        lines.append(f"  胜率: {result.win_rate:.1%}")

        lines.append("\n【收益表现】")
        lines.append(f"  总收益率: {result.total_return_pct:.2f}%")
        lines.append(f"  平均每笔收益: {result.avg_return_per_trade:.2f}%")
        lines.append(f"  最大回撤: {result.max_drawdown_pct:.2f}%")

        lines.append("\n【风险指标】")
        lines.append(f"  Sharpe比率: {result.sharpe_ratio:.2f}")
        lines.append(f"  Sortino比率: {result.sortino_ratio:.2f}")
        lines.append(f"  Calmar比率: {result.calmar_ratio:.2f}")
        lines.append(f"  盈亏比: {result.profit_factor:.2f}")

        # 最近5笔交易
        if result.trades:
            lines.append("\n【最近交易】")
            for trade in result.trades[-5:]:
                status_icon = "✅" if trade.pnl > 0 else "❌" if trade.pnl < 0 else "⏸️"
                lines.append(f"  {status_icon} {trade.entry_date} 买入¥{trade.entry_price:.2f} -> "
                           f"{trade.exit_date or '持仓中'} "
                           f"{f'¥{trade.exit_price:.2f}' if trade.exit_price else ''} "
                           f"{f'收益{trade.pnl_pct:.1f}%' if trade.status == 'closed' else ''}")

        return '\n'.join(lines)
