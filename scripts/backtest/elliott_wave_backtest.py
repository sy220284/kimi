#!/usr/bin/env python3
"""
艾略特波浪理论回测框架 - 10轮优化版本

功能：
1. 从数据库获取历史数据（2020-2025）
2. 实现艾略特波浪买卖策略
3. 执行回测计算绩效指标
4. 10轮参数优化循环
"""

import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/智能体系统')
from data import get_db_manager


@dataclass
class BacktestConfig:
    """回测配置"""
    # 时间范围
    start_date: str = '2020-01-01'
    end_date: str = '2025-01-01'
    
    # 交易成本
    commission_rate: float = 0.0015  # 双边0.15%
    
    # 仓位管理
    position_size: float = 0.2  # 固定仓位20%
    use_kelly: bool = False
    
    # 止损设置
    stop_loss_pct: float = -0.08  # 固定-8%止损
    use_trailing_stop: bool = False
    
    # C浪买点参数
    rsi_oversold: float = 35
    retracement_c_min: float = 0.30
    retracement_c_max: float = 1.0
    retracement_24_min: float = 0.30
    retracement_24_max: float = 0.70
    
    # 权重参数
    macd_divergence_weight: int = 20
    rsi_oversold_weight: int = 10
    hammer_weight: int = 10
    volume_shrink_weight: int = 10
    near_low_weight: int = 10
    macd_golden_cross_weight: int = 15
    
    # 卖点参数
    rsi_overbought: float = 70
    profit_target_135: float = 0.15  # 1/3/5浪盈利目标
    profit_target_24: float = 0.08  # 2/4浪盈利目标
    
    # 评分阈值
    buy_score_threshold: int = 35
    strong_buy_threshold: int = 50
    
    # 持仓限制
    max_holding_days: int = 60
    max_positions: int = 10


@dataclass
class Trade:
    """交易记录"""
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    position_size: float = 0
    pnl: float = 0
    pnl_pct: float = 0
    exit_reason: str = ''
    holding_days: int = 0
    signals: List[str] = field(default_factory=list)


@dataclass
class BacktestResult:
    """回测结果"""
    config: BacktestConfig
    trades: List[Trade] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    # 绩效指标
    total_return: float = 0
    annual_return: float = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    max_drawdown: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


class TechnicalIndicators:
    """技术指标计算"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods=[5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
        """计算MACD"""
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=signal).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """计算RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def calculate_bollinger(df: pd.DataFrame, period=20, std=2) -> pd.DataFrame:
        """计算布林带"""
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + std * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - std * df['bb_std']
        return df
    
    @staticmethod
    def detect_macd_divergence(df: pd.DataFrame, lookback=20) -> Tuple[bool, str]:
        """检测MACD底背离"""
        if len(df) < lookback + 5:
            return False, ''
        
        recent = df.tail(lookback)
        
        # 找近期低点
        price_low_idx = recent['low'].idxmin()
        price_low = recent.loc[price_low_idx, 'low']
        
        # 找MACD低点
        macd_low_idx = recent['macd'].idxmin()
        macd_low = recent.loc[macd_low_idx, 'macd']
        
        # 检测底背离：价格创新低但MACD未创新低
        current_price = df['close'].iloc[-1]
        current_macd = df['macd'].iloc[-1]
        
        # 简化的底背离检测
        price_making_lower_lows = recent['low'].iloc[-5:].min() < recent['low'].iloc[:-5].min()
        macd_not_making_lower_lows = recent['macd'].iloc[-5:].min() >= recent['macd'].iloc[:-5].min() * 0.9
        
        if price_making_lower_lows and macd_not_making_lower_lows and current_macd < 0:
            return True, 'MACD底背离'
        
        return False, ''
    
    @staticmethod
    def detect_hammer(df: pd.DataFrame) -> Tuple[bool, str]:
        """检测锤子线形态"""
        if len(df) < 2:
            return False, ''
        
        latest = df.iloc[-1]
        open_p = latest['open']
        close = latest['close']
        high = latest['high']
        low = latest['low']
        
        body = abs(close - open_p)
        upper_shadow = high - max(open_p, close)
        lower_shadow = min(open_p, close) - low
        
        # 锤子线条件：下影线长，实体小，上影线短
        if lower_shadow > body * 2 and upper_shadow < body and body > 0:
            return True, '锤子线'
        
        return False, ''
    
    @staticmethod
    def detect_volume_shrink(df: pd.DataFrame, ratio=0.7) -> Tuple[bool, str]:
        """检测缩量"""
        if len(df) < 20:
            return False, ''
        
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].tail(20).mean()
        
        if current_vol < avg_vol * ratio:
            return True, '缩量止跌'
        
        return False, ''


class ElliottWaveStrategy:
    """艾略特波浪策略"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.indicators = TechnicalIndicators()
    
    def identify_wave_stage(self, df: pd.DataFrame) -> Dict:
        """识别当前波浪阶段"""
        if len(df) < 60:
            return {'stage': 'unknown', 'confidence': 0}
        
        # 找近期高低点
        recent_high = df['high'].tail(60).max()
        recent_low = df['low'].tail(60).min()
        current_price = df['close'].iloc[-1]
        
        # 计算回调幅度
        if recent_high > recent_low:
            retracement = (recent_high - current_price) / (recent_high - recent_low)
        else:
            retracement = 0
        
        # 计算RSI
        rsi = df['rsi'].iloc[-1]
        
        # 判断波浪阶段
        stage_info = {
            'current_price': current_price,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'retracement_pct': retracement * 100,
            'rsi': rsi
        }
        
        # C浪末端判断：大幅回调+RSI超卖
        if retracement > 0.8 and rsi < self.config.rsi_oversold:
            stage_info['stage'] = 'c_wave_end'
            stage_info['wave_name'] = 'C浪末端'
            stage_info['confidence'] = min(100, int((retracement * 100 + (self.config.rsi_oversold - rsi)) / 2))
        # 2浪/4浪回调判断：中度回调
        elif 0.3 <= retracement <= 0.7 and rsi < 45:
            stage_info['stage'] = 'wave_2_or_4'
            stage_info['wave_name'] = '2浪/4浪回调'
            stage_info['confidence'] = int(retracement * 100)
        # 1浪/3浪/5浪上涨
        elif retracement < 0.3 and rsi > 50:
            stage_info['stage'] = 'wave_135'
            stage_info['wave_name'] = '1/3/5浪上涨'
            stage_info['confidence'] = int((1 - retracement) * 100)
        else:
            stage_info['stage'] = 'unclear'
            stage_info['wave_name'] = '趋势不明'
            stage_info['confidence'] = 20
        
        return stage_info
    
    def calculate_buy_score(self, df: pd.DataFrame, wave_info: Dict) -> Dict:
        """计算买点评分"""
        score = 0
        signals = []
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        config = self.config
        
        # 1. MACD底背离检测
        is_divergence, div_signal = self.indicators.detect_macd_divergence(df)
        if is_divergence:
            score += config.macd_divergence_weight
            signals.append(f'{div_signal} +{config.macd_divergence_weight}')
        
        # 2. RSI超卖检测
        if latest['rsi'] < config.rsi_oversold:
            score += config.rsi_oversold_weight
            signals.append(f'RSI超卖 +{config.rsi_oversold_weight}')
        elif latest['rsi'] < config.rsi_oversold + 5:
            score += config.rsi_oversold_weight // 2
            signals.append(f'RSI脱离超卖 +{config.rsi_oversold_weight // 2}')
        
        # 3. 锤子线形态
        is_hammer, hammer_signal = self.indicators.detect_hammer(df)
        if is_hammer:
            score += config.hammer_weight
            signals.append(f'{hammer_signal} +{config.hammer_weight}')
        
        # 4. 缩量止跌
        is_shrink, shrink_signal = self.indicators.detect_volume_shrink(df)
        if is_shrink:
            score += config.volume_shrink_weight
            signals.append(f'{shrink_signal} +{config.volume_shrink_weight}')
        
        # 5. 接近前低
        if wave_info['retracement_pct'] > 90:
            score += config.near_low_weight
            signals.append(f'接近前低 +{config.near_low_weight}')
        elif wave_info['retracement_pct'] > 80:
            score += config.near_low_weight // 2
            signals.append(f'回调较深 +{config.near_low_weight // 2}')
        
        # 6. MACD金叉
        if latest['macd'] > latest['macd_signal'] and prev['macd'] <= prev['macd_signal']:
            score += config.macd_golden_cross_weight
            signals.append(f'MACD金叉 +{config.macd_golden_cross_weight}')
        
        # 7. 站上5日线
        if latest['close'] > latest['ma5']:
            score += 5
            signals.append('站上5日线 +5')
        
        # 评级
        if score >= config.strong_buy_threshold:
            rating = '强买入'
        elif score >= config.buy_score_threshold:
            rating = '买入'
        elif score >= 20:
            rating = '关注'
        else:
            rating = '观望'
        
        return {
            'score': score,
            'signals': signals,
            'rating': rating,
            'price': latest['close'],
            'rsi': latest['rsi'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal']
        }
    
    def check_sell_signal(self, df: pd.DataFrame, entry_price: float, 
                         holding_days: int, wave_info: Dict) -> Tuple[bool, str]:
        """检查卖出信号"""
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        current_price = latest['close']
        pnl_pct = (current_price - entry_price) / entry_price
        
        config = self.config
        
        # 1. 止损检查
        if pnl_pct <= config.stop_loss_pct:
            return True, '止损离场'
        
        # 2. 跌破前低止损
        if current_price < wave_info['recent_low'] * 1.02:
            return True, '跌破前低'
        
        # 3. 盈利目标（按波浪类型）
        if wave_info['stage'] in ['c_wave_end']:
            if pnl_pct >= config.profit_target_135:
                return True, f'达到盈利目标{config.profit_target_135*100:.0f}%'
        elif wave_info['stage'] in ['wave_2_or_4']:
            if pnl_pct >= config.profit_target_24:
                return True, f'达到盈利目标{config.profit_target_24*100:.0f}%'
        
        # 4. RSI超买
        if latest['rsi'] > config.rsi_overbought:
            return True, 'RSI超买'
        
        # 5. MACD死叉
        if latest['macd'] < latest['macd_signal'] and prev['macd'] >= prev['macd_signal']:
            return True, 'MACD死叉'
        
        # 6. 跌破10日线
        if current_price < latest['ma10']:
            return True, '跌破10日线'
        
        # 7. 持仓时间限制
        if holding_days >= config.max_holding_days:
            return True, '持仓时间到期'
        
        return False, ''


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.strategy = ElliottWaveStrategy(config)
        self.db = get_db_manager()
    
    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从数据库获取股票数据"""
        result = self.db.pg.execute('''
            SELECT date, open, high, low, close, volume, amount
            FROM market_data
            WHERE symbol = %s AND date >= %s AND date <= %s
            ORDER BY date
        ''', (symbol, start_date, end_date), fetch=True)
        
        if not result:
            return pd.DataFrame()
        
        # 处理返回的字典列表
        if isinstance(result[0], dict):
            df = pd.DataFrame(result)
        else:
            df = pd.DataFrame(result, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # 将Decimal类型转换为float
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        return df
    
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备数据，计算技术指标"""
        df = self.strategy.indicators.calculate_ma(df)
        df = self.strategy.indicators.calculate_macd(df)
        df = self.strategy.indicators.calculate_rsi(df)
        return df
    
    def run_backtest(self, symbols: List[str]) -> BacktestResult:
        """执行回测"""
        result = BacktestResult(config=self.config)
        
        for i, symbol in enumerate(symbols, 1):
            try:
                if i % 10 == 0:
                    print(f"  进度: {i}/{len(symbols)} ({i/len(symbols)*100:.0f}%)")
                df = self.get_stock_data(symbol, self.config.start_date, self.config.end_date)
                if len(df) < 60:
                    continue
                
                df = self.prepare_data(df)
                self._backtest_single_stock(symbol, df, result)
            except Exception as e:
                print(f"回测 {symbol} 失败: {e}")
                continue
        
        # 计算绩效指标
        self._calculate_performance(result)
        return result
    
    def _backtest_single_stock(self, symbol: str, df: pd.DataFrame, result: BacktestResult):
        """单股票回测"""
        position = None
        
        for i in range(60, len(df)):
            current_df = df.iloc[:i+1]
            current_date = current_df['date'].iloc[-1]
            current_price = current_df['close'].iloc[-1]
            
            wave_info = self.strategy.identify_wave_stage(current_df)
            
            # 检查是否有持仓
            if position is not None:
                holding_days = (current_date - position.entry_date).days
                should_sell, sell_reason = self.strategy.check_sell_signal(
                    current_df, position.entry_price, holding_days, wave_info
                )
                
                if should_sell:
                    position.exit_date = current_date
                    position.exit_price = current_price
                    position.pnl = (current_price - position.entry_price) * position.position_size
                    position.pnl_pct = (current_price - position.entry_price) / position.entry_price
                    position.exit_reason = sell_reason
                    position.holding_days = holding_days
                    result.trades.append(position)
                    position = None
            else:
                # 检查买入条件
                buy_signal = self.strategy.calculate_buy_score(current_df, wave_info)
                
                if buy_signal['score'] >= self.config.buy_score_threshold:
                    position = Trade(
                        symbol=symbol,
                        entry_date=current_date,
                        entry_price=current_price,
                        position_size=self.config.position_size,
                        signals=buy_signal['signals']
                    )
        
        # 处理未平仓的持仓
        if position is not None:
            position.exit_date = df['date'].iloc[-1]
            position.exit_price = df['close'].iloc[-1]
            position.pnl = (position.exit_price - position.entry_price) * position.position_size
            position.pnl_pct = (position.exit_price - position.entry_price) / position.entry_price
            position.exit_reason = '回测结束'
            position.holding_days = (position.exit_date - position.entry_date).days
            result.trades.append(position)
    
    def _calculate_performance(self, result: BacktestResult):
        """计算绩效指标"""
        trades = result.trades
        if not trades:
            return
        
        result.total_trades = len(trades)
        result.winning_trades = sum(1 for t in trades if t.pnl_pct > 0)
        result.losing_trades = sum(1 for t in trades if t.pnl_pct <= 0)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0
        
        # 盈亏统计
        wins = [t.pnl_pct for t in trades if t.pnl_pct > 0]
        losses = [t.pnl_pct for t in trades if t.pnl_pct <= 0]
        
        result.avg_win = np.mean(wins) if wins else 0
        result.avg_loss = np.mean(losses) if losses else 0
        
        # 盈亏比
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        result.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # 累计收益（考虑交易成本）
        cumulative_returns = []
        cumulative = 1.0
        for trade in trades:
            trade_return = trade.pnl_pct * trade.position_size * (1 - self.config.commission_rate * 2)
            cumulative *= (1 + trade_return)
            cumulative_returns.append(cumulative - 1)
        
        result.total_return = cumulative - 1
        
        # 年化收益
        years = 5  # 2020-2025
        result.annual_return = (1 + result.total_return) ** (1/years) - 1
        
        # 最大回撤
        if cumulative_returns:
            peak = cumulative_returns[0]
            max_dd = 0
            for ret in cumulative_returns:
                if ret > peak:
                    peak = ret
                dd = (peak - ret) / (1 + peak)
                max_dd = max(max_dd, dd)
            result.max_drawdown = max_dd
        
        # 夏普比率（简化计算）
        returns = [t.pnl_pct for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                result.sharpe_ratio = avg_return / std_return * np.sqrt(252)
        
        # Calmar比率
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annual_return / result.max_drawdown


def get_available_symbols() -> List[str]:
    """获取可用股票列表"""
    db = get_db_manager()
    result = db.pg.execute('''
        SELECT DISTINCT symbol FROM market_data 
        WHERE date >= '2020-01-01'
        ORDER BY symbol
    ''', fetch=True)
    # 处理返回的字典列表
    if result and isinstance(result, list):
        if isinstance(result[0], dict):
            return [r['symbol'] for r in result]
        else:
            return [r[0] for r in result]
    return []


def run_optimization_round(round_num: int, config: BacktestConfig, symbols: List[str]) -> BacktestResult:
    """执行单轮优化"""
    print(f"\n{'='*80}")
    print(f"第 {round_num} 轮回测优化")
    print(f"{'='*80}")
    
    print(f"\n参数配置:")
    print(f"  RSI超卖阈值: <{config.rsi_oversold}")
    print(f"  C浪回调幅度: {config.retracement_c_min*100:.0f}%-{config.retracement_c_max*100:.0f}%")
    print(f"  2/4浪回调幅度: {config.retracement_24_min*100:.0f}%-{config.retracement_24_max*100:.0f}%")
    print(f"  买点评分阈值: {config.buy_score_threshold}")
    print(f"  止损比例: {config.stop_loss_pct*100:.0f}%")
    print(f"  MACD底背离权重: {config.macd_divergence_weight}")
    print(f"  RSI超卖权重: {config.rsi_oversold_weight}")
    print(f"  锤子线权重: {config.hammer_weight}")
    
    # 执行回测
    engine = BacktestEngine(config)
    result = engine.run_backtest(symbols[:20])  # 使用前20只股票加速测试
    
    # 打印结果
    print(f"\n回测结果:")
    print(f"  总交易次数: {result.total_trades}")
    print(f"  胜率: {result.win_rate*100:.2f}%")
    print(f"  总收益率: {result.total_return*100:.2f}%")
    print(f"  年化收益率: {result.annual_return*100:.2f}%")
    print(f"  最大回撤: {result.max_drawdown*100:.2f}%")
    print(f"  盈亏比: {result.profit_factor:.2f}")
    print(f"  夏普比率: {result.sharpe_ratio:.2f}")
    print(f"  Calmar比率: {result.calmar_ratio:.2f}")
    
    return result


def analyze_and_improve(round_num: int, result: BacktestResult) -> BacktestConfig:
    """分析结果并改进参数"""
    config = result.config
    
    print(f"\n第 {round_num} 轮分析:")
    print("-" * 60)
    
    issues = []
    improvements = []
    
    # 问题1: 胜率过低
    if result.win_rate < 0.45:
        issues.append(f"胜率过低 ({result.win_rate*100:.1f}%)，需要提高入场标准")
        config.buy_score_threshold += 5
        improvements.append(f"买点评分阈值提高到 {config.buy_score_threshold}")
    elif result.win_rate > 0.65:
        issues.append(f"胜率过高 ({result.win_rate*100:.1f}%)，可能存在过拟合")
        config.buy_score_threshold -= 3
        improvements.append(f"买点评分阈值降低到 {config.buy_score_threshold}")
    
    # 问题2: 最大回撤过大
    if result.max_drawdown > 0.20:
        issues.append(f"最大回撤过大 ({result.max_drawdown*100:.1f}%)")
        config.stop_loss_pct = max(-0.15, config.stop_loss_pct - 0.02)
        improvements.append(f"止损收紧到 {config.stop_loss_pct*100:.0f}%")
    
    # 问题3: 交易次数过少
    if result.total_trades < 20:
        issues.append(f"交易次数过少 ({result.total_trades})，信号太严格")
        config.buy_score_threshold -= 5
        config.rsi_oversold += 3
        improvements.append(f"降低评分阈值到 {config.buy_score_threshold}，放宽RSI到 {config.rsi_oversold}")
    
    # 问题4: 盈亏比过低
    if result.profit_factor < 1.2:
        issues.append(f"盈亏比过低 ({result.profit_factor:.2f})")
        config.profit_target_135 += 0.03
        config.profit_target_24 += 0.02
        improvements.append(f"提高盈利目标")
    
    # 问题5: 夏普比率过低
    if result.sharpe_ratio < 0.5:
        issues.append(f"夏普比率过低 ({result.sharpe_ratio:.2f})")
        # 增加MACD底背离权重
        config.macd_divergence_weight += 5
        improvements.append(f"增加MACD底背离权重到 {config.macd_divergence_weight}")
    
    if not issues:
        print("  ✓ 整体表现良好，微调参数")
        # 微调优化
        if result.win_rate < 0.50:
            config.rsi_oversold_weight += 2
        if result.max_drawdown > 0.15:
            config.hammer_weight += 2
    else:
        for issue in issues:
            print(f"  ✗ {issue}")
    
    for imp in improvements:
        print(f"  → {imp}")
    
    return config


def main():
    """主函数：执行10轮优化"""
    print("="*80)
    print("艾略特波浪理论回测优化 - 10轮循环")
    print("="*80)
    
    # 获取可用股票
    print("\n获取股票列表...")
    symbols = get_available_symbols()
    print(f"可用股票数量: {len(symbols)}")
    
    # 初始配置
    config = BacktestConfig()
    
    # 存储每轮结果
    all_results = []
    
    # 执行10轮优化
    for round_num in range(1, 11):
        result = run_optimization_round(round_num, config, symbols)
        all_results.append({
            'round': round_num,
            'config': config,
            'result': result
        })
        
        # 分析并改进（最后一轮不改进）
        if round_num < 10:
            config = analyze_and_improve(round_num, result)
    
    # 输出最终报告
    print("\n" + "="*80)
    print("10轮优化总结报告")
    print("="*80)
    
    print("\n各轮绩效对比:")
    print("-" * 100)
    print(f"{'轮次':<6}{'胜率':<10}{'总收益':<12}{'年化收益':<12}{'最大回撤':<12}{'盈亏比':<10}{'夏普':<10}{'交易数':<8}")
    print("-" * 100)
    
    for data in all_results:
        r = data['result']
        print(f"{data['round']:<6}{r.win_rate*100:>6.1f}%  {r.total_return*100:>8.2f}%  "
              f"{r.annual_return*100:>8.2f}%  {r.max_drawdown*100:>8.2f}%  "
              f"{r.profit_factor:>8.2f}  {r.sharpe_ratio:>8.2f}  {r.total_trades:>6}")
    
    # 找出最优配置
    best_result = max(all_results, key=lambda x: x['result'].sharpe_ratio if x['result'].sharpe_ratio else 0)
    print("\n" + "="*80)
    print(f"最优配置（第 {best_result['round']} 轮）")
    print("="*80)
    
    best_config = best_result['config']
    print(f"\n最终推荐参数:")
    print(f"  RSI超卖阈值: <{best_config.rsi_oversold}")
    print(f"  C浪回调幅度: {best_config.retracement_c_min*100:.0f}%-{best_config.retracement_c_max*100:.0f}%")
    print(f"  买点评分阈值: {best_config.buy_score_threshold}")
    print(f"  强买入阈值: {best_config.strong_buy_threshold}")
    print(f"  止损比例: {best_config.stop_loss_pct*100:.0f}%")
    print(f"  MACD底背离权重: {best_config.macd_divergence_weight}")
    print(f"  RSI超卖权重: {best_config.rsi_oversold_weight}")
    print(f"  锤子线权重: {best_config.hammer_weight}")
    print(f"  缩量止跌权重: {best_config.volume_shrink_weight}")
    print(f"  接近前低权重: {best_config.near_low_weight}")
    print(f"  MACD金叉权重: {best_config.macd_golden_cross_weight}")
    
    # 保存结果
    output = {
        'optimization_history': [
            {
                'round': d['round'],
                'win_rate': d['result'].win_rate,
                'total_return': d['result'].total_return,
                'annual_return': d['result'].annual_return,
                'max_drawdown': d['result'].max_drawdown,
                'profit_factor': d['result'].profit_factor,
                'sharpe_ratio': d['result'].sharpe_ratio,
                'total_trades': d['result'].total_trades
            } for d in all_results
        ],
        'best_config': {
            'round': best_result['round'],
            'rsi_oversold': best_config.rsi_oversold,
            'retracement_c_min': best_config.retracement_c_min,
            'retracement_c_max': best_config.retracement_c_max,
            'buy_score_threshold': best_config.buy_score_threshold,
            'strong_buy_threshold': best_config.strong_buy_threshold,
            'stop_loss_pct': best_config.stop_loss_pct,
            'macd_divergence_weight': best_config.macd_divergence_weight,
            'rsi_oversold_weight': best_config.rsi_oversold_weight,
            'hammer_weight': best_config.hammer_weight,
            'volume_shrink_weight': best_config.volume_shrink_weight,
            'near_low_weight': best_config.near_low_weight,
            'macd_golden_cross_weight': best_config.macd_golden_cross_weight
        }
    }
    
    with open('/tmp/elliott_wave_backtest_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n结果已保存到: /tmp/elliott_wave_backtest_results.json")


if __name__ == '__main__':
    main()
