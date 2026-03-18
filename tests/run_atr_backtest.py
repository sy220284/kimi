"""
自适应ATR参数回测测试
ATR(14) * 2 作为止损，移动止盈同样基于ATR
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datetime import datetime

import numpy as np
import pandas as pd

# 导入回测相关模块
from analysis.backtest.wave_backtester import (
    BacktestResult,
    Trade,
    TradeAction,
    WaveBacktester,
    WaveStrategy,
)
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data.db_manager import get_db_manager


def calculate_atr(df, period=14):
    """计算ATR指标"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(period).mean()
    return atr

class ATRWaveStrategy(WaveStrategy):
    """支持ATR动态止损的策略"""
    
    def __init__(self, atr_multiplier=2.0, trailing_atr_multiplier=2.0, **kwargs):
        # 移除stop_loss_pct，改用ATR
        super().__init__(**kwargs)
        self.use_atr_stop = True
        self.atr_multiplier = atr_multiplier
        self.trailing_atr_multiplier = trailing_atr_multiplier
        self.stop_loss_pct = None  # 不使用固定百分比
        
    def calculate_stop_loss(self, entry_price, df, idx):
        """基于ATR计算止损价"""
        if idx < 14:  # ATR需要14天数据
            return entry_price * 0.92  # 默认8%止损
        
        atr = calculate_atr(df, 14).iloc[idx]
        stop_distance = atr * self.atr_multiplier
        stop_price = entry_price - stop_distance
        
        return max(stop_price, entry_price * 0.85)  # 最大允许15%止损
    
    def calculate_trailing_stop(self, highest_price, df, idx):
        """基于ATR计算移动止盈价"""
        if idx < 14:
            return highest_price * 0.92
        
        atr = calculate_atr(df, 14).iloc[idx]
        trailing_distance = atr * self.trailing_atr_multiplier
        return highest_price - trailing_distance

class ATRWaveBacktester(WaveBacktester):
    """支持ATR的改进版回测器"""
    
    def run(self, symbol: str, df: pd.DataFrame, reanalyze_every: int = 5) -> 'BacktestResult':
        """运行回测（支持ATR动态止损）"""
        
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)
        
        # 计算ATR
        df['atr'] = calculate_atr(df, 14)
        
        # 计算趋势均线
        df['ma200'] = df['close'].rolling(self.strategy.trend_ma_period).mean()
        
        self.strategy.capital = self.strategy.initial_capital
        self.strategy.positions = {}
        self.strategy.trades = []
        self.strategy.equity_curve = []
        
        # 定期分析波浪结构
        analysis_cache = {}
        last_analysis_idx = -reanalyze_every - 1
        
        for i in range(100, len(df)):  # 从第100根K线开始，确保有足够数据
            current_date = df.iloc[i]['date'].strftime('%Y-%m-%d')
            current_price = df.iloc[i]['close']
            current_high = df.iloc[i]['high']
            current_low = df.iloc[i]['low']
            
            # 趋势过滤
            trend_ma = df.iloc[i]['ma200'] if self.strategy.use_trend_filter else 0
            trend_up = current_price > trend_ma if not pd.isna(trend_ma) else True
            
            # 定期分析波浪结构
            if i - last_analysis_idx >= reanalyze_every:
                histdata = df.iloc[:i+1].copy()
                try:
                    analysis = self.analyzer.analyze(histdata)
                    analysis_cache[i] = analysis
                    last_analysis_idx = i
                except Exception:
                    analysis = analysis_cache.get(last_analysis_idx)
            else:
                analysis = analysis_cache.get(last_analysis_idx)
            
            # 检查持仓
            for _pos_symbol, trade in list(self.strategy.positions.items()):
                holding_days = i - trade.entry_idx
                
                if holding_days < self.strategy.min_holding_days:
                    continue
                
                # 动态计算止损/止盈
                if isinstance(self.strategy, ATRWaveStrategy) and self.strategy.use_atr_stop:
                    # AR动态止损
                    stop_loss = self.strategy.calculate_stop_loss(trade.entry_price, df, i)
                    
                    # 移动止盈逻辑
                    if self.strategy.use_trailing_stop and trade.target_hit:
                        if trade.highest_price is None:
                            trade.highest_price = current_high
                        else:
                            trade.highest_price = max(trade.highest_price, current_high)
                        
                        trailing_stop = self.strategy.calculate_trailing_stop(
                            trade.highest_price, df, i
                        )
                        
                        if current_low <= trailing_stop:
                            self._closetrade(trade, current_date, trailing_stop, 'trailing_stop(ATR)')
                            continue
                    
                    # 固定ATR止损
                    if current_low <= stop_loss:
                        self._closetrade(trade, current_date, stop_loss, 'stop_loss(ATR)')
                        continue
                
                else:
                    # 原百分比止损逻辑
                    if trade.stop_loss and current_low <= trade.stop_loss:
                        self._closetrade(trade, current_date, trade.stop_loss, 'stop_loss')
                        continue
                    
                    # 移动止盈
                    if self.strategy.use_trailing_stop and trade.target_hit:
                        if trade.highest_price is None:
                            trade.highest_price = current_high
                        else:
                            trade.highest_price = max(trade.highest_price, current_high)
                        
                        trailing_price = trade.highest_price * (1 - self.strategy.trailing_stop_pct)
                        
                        if current_low <= trailing_price:
                            self._closetrade(trade, current_date, trailing_price, f'trailing_stop({self.strategy.trailing_stop_pct*100:.0f}%)')
                            continue
                
                # 检查是否达到目标价（激活移动止盈）
                if trade.target_price and not trade.target_hit:
                    activation_price = trade.target_price * self.strategy.trailing_stop_activation
                    if current_high >= activation_price:
                        trade.target_hit = True
                        trade.target_hit_price = current_high
                        trade.target_hit_idx = i
                        trade.highest_price = current_high
                
                # 目标价附近卖出
                if trade.target_price:
                    proximity = abs(current_price - trade.target_price) / trade.target_price
                    if proximity <= self.strategy.target_proximity_pct:
                        self._closetrade(trade, current_date, current_price, 'target_proximity')
                        continue
            
            # 检查买入信号
            position_count = len(self.strategy.positions)
            
            if analysis and trend_up and position_count < self.strategy.max_positions:
                # 检查是否有买入信号
                signal = analysis.get('signal')
                if signal and signal.signal_type in ['BUY', 'STRONG_BUY']:
                    entry_type = getattr(signal, 'entry_type', None)
                    entry_wave = entry_type.value if entry_type else 'unknown'
                    
                    # 检查是否已有持仓
                    if symbol not in self.strategy.positions:
                        position_value = self.strategy.capital * self.strategy.position_size
                        quantity = int(position_value / current_price / 100) * 100
                        
                        if quantity >= 100:
                            # 计算止损
                            if isinstance(self.strategy, ATRWaveStrategy) and self.strategy.use_atr_stop:
                                stop_loss = self.strategy.calculate_stop_loss(current_price, df, i)
                            else:
                                stop_loss = current_price * (1 - self.strategy.stop_loss_pct)
                            
                            # 计算目标价
                            target_price = self._calculate_target_price(analysis, current_price)
                            
                            trade = Trade(
                                symbol=symbol,
                                entry_date=current_date,
                                entry_price=current_price,
                                action=TradeAction.BUY,
                                quantity=quantity,
                                stop_loss=stop_loss,
                                target_price=target_price,
                                entry_idx=i,
                                entry_wave=entry_wave
                            )
                            
                            self.strategy.positions[symbol] = trade
                            self.strategy.trades.append(trade)
                            
                            cost = quantity * current_price * (1 + self.strategy.commission_rate + self.strategy.slippage_rate)
                            self.strategy.capital -= cost
            
            # 记录权益
            total_value = self.strategy.capital
            for pos in self.strategy.positions.values():
                total_value += pos.quantity * current_price
            
            self.strategy.equity_curve.append({
                'date': current_date,
                'value': total_value,
                'price': current_price
            })
        
        # 平仓所有持仓
        if self.strategy.positions:
            final_price = df.iloc[-1]['close']
            final_date = df.iloc[-1]['date'].strftime('%Y-%m-%d')
            for trade in list(self.strategy.positions.values()):
                self._closetrade(trade, final_date, final_price, 'end_of_period')
        
        return self._create_result(symbol, df)
    
    def _closetrade(self, trade, date, price, reason):
        """平仓交易"""
        trade.close(date, price, reason)
        self.strategy.capital += trade.quantity * price * (1 - self.strategy.commission_rate -
                                                            self.strategy.stamp_tax_rate - self.strategy.slippage_rate)
        if trade.symbol in self.strategy.positions:
            del self.strategy.positions[trade.symbol]
    
    def _calculate_target_price(self, analysis, current_price):
        """计算目标价"""
        signal = analysis.get('signal')
        if signal and hasattr(signal, 'target_price') and signal.target_price:
            return signal.target_price
        return current_price * 1.15
    
    def _create_result(self, symbol, df):
        """创建回测结果"""
        
        closedtrades = [t for t in self.strategy.trades if t.status == 'closed']
        if not closedtrades:
            return BacktestResult(
                symbol=symbol,
                start_date=df.iloc[0]['date'].strftime('%Y-%m-%d'),
                end_date=df.iloc[-1]['date'].strftime('%Y-%m-%d'),
                total_trades=0,
                winningtrades=0,
                losingtrades=0,
                win_rate=0.0,
                total_return=0,
                total_return_pct=0,
                avg_return_pertrade=0,
                max_drawdown=0,
                max_drawdown_pct=0,
                sharpe_ratio=0,
                profit_factor=0,
                trades=[],
                equity_curve=self.strategy.equity_curve
            )
        
        winningtrades = sum(1 for t in closedtrades if t.pnl_pct > 0)
        losingtrades = len(closedtrades) - winningtrades
        win_rate = winningtrades / len(closedtrades) if closedtrades else 0
        
        total_pnl = sum(t.pnl for t in closedtrades)
        initial_value = self.strategy.initial_capital
        final_value = self.strategy.capital
        
        returns = [t.pnl_pct for t in closedtrades]
        avg_return = np.mean(returns) if returns else 0
        
        # 计算最大回撤
        equityvalues = [e['value'] for e in self.strategy.equity_curve]
        max_dd = 0
        peak = equityvalues[0]
        for value in equityvalues:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        # 计算Sharpe
        equityreturns = pd.Series(equityvalues).pct_change().dropna()
        sharpe = (equityreturns.mean() / equityreturns.std() * np.sqrt(252)) if equityreturns.std() > 0 else 0
        
        # 计算Profit Factor
        gross_profit = sum(t.pnl for t in closedtrades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in closedtrades if t.pnl <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return BacktestResult(
            symbol=symbol,
            start_date=df.iloc[0]['date'].strftime('%Y-%m-%d'),
            end_date=df.iloc[-1]['date'].strftime('%Y-%m-%d'),
            total_trades=len(closedtrades),
            winningtrades=winningtrades,
            losingtrades=losingtrades,
            win_rate=win_rate,
            total_return=final_value - initial_value,
            total_return_pct=(final_value - initial_value) / initial_value * 100,
            avg_return_pertrade=avg_return,
            max_drawdown=max_dd * initial_value,
            max_drawdown_pct=max_dd * 100,
            sharpe_ratio=sharpe,
            profit_factor=profit_factor,
            trades=self.strategy.trades,
            equity_curve=self.strategy.equity_curve
        )

def run_atr_backtest():
    """跑ATR自适应参数回测"""
    print(f"\n{'='*70}")
    print("🔬 ATR自适应参数回测：ATR(14) * 2")
    print(f"{'='*70}")
    print(f"开始时间: {datetime.now()}")
    
    tech_symbols = [
        '000063', '002230', '300750', '600584', '603501',
        '688981', '688012', '688008', '000938', '600570',
        '002371', '300014', '300124', '300433', '300408',
        '603019', '603893', '688111', '688126', '688599',
        '300496', '300661', '300782', '600460', '600703',
        '300474', '300223', '300373', '300666', '300724',
        '688002', '688009', '688188', '688256', '688390',
        '688396', '688521', '688561', '688728', '300604',
    ]
    
    db_manager = get_db_manager()
    analyzer = UnifiedWaveAnalyzer()
    
    results = []
    alltrade_details = []
    
    for i, symbol in enumerate(tech_symbols, 1):
        try:
            df = db_manager.get_stock_data(symbol, start_date='2017-01-01', end_date='2024-12-31')
            if df is None or len(df) < 200:
                continue
            
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            df['date'] = pd.to_datetime(df['date'])
            
            # ATR自适应策略
            strategy = ATRWaveStrategy(
                initial_capital=100000,
                position_size=0.2,
                max_positions=3,
                max_total_position=0.8,
                commission_rate=0.0003,
                stamp_tax_rate=0.001,
                slippage_rate=0.001,
                min_holding_days=3,
                use_trend_filter=True,
                trend_ma_period=200,
                use_trailing_stop=True,
                trailing_stop_activation=1.0,
                atr_multiplier=2.0,  # ATR * 2 作为止损
                trailing_atr_multiplier=2.0,
            )
            
            backtester = ATRWaveBacktester(analyzer)
            backtester.strategy = strategy
            result = backtester.run(symbol, df, reanalyze_every=5)
            
            trade_details = [t.to_dict() for t in result.trades if t.status == 'closed']
            
            results.append({
                'symbol': symbol,
                'tier': '科创' if symbol.startswith('688') else '主板',
                'trades': result.total_trades,
                'win_rate': result.win_rate,
                'return': result.total_return_pct,
                'avg_return': result.avg_return_pertrade,
                'max_dd': result.max_drawdown_pct,
                'sharpe': result.sharpe_ratio,
            })
            alltrade_details.extend(trade_details)
            
            print(f"[{i}/{len(tech_symbols)}] {symbol}: 收益{result.total_return_pct:+.2f}% 交易{result.total_trades}次")
            
        except Exception as e:
            print(f"[{i}/{len(tech_symbols)}] {symbol}: 错误 - {e}")
    
    # 汇总
    if results:
        df_results = pd.DataFrame(results)
        
        print(f"\n{'='*70}")
        print("📊 ATR自适应参数统计结果")
        print(f"{'='*70}")
        
        high_df = df_results[df_results['tier'] == '科创']
        medium_df = df_results[df_results['tier'] == '主板']
        
        print(f"\n科创板 ({len(high_df)}只):")
        print(f"  平均收益: {high_df['return'].mean():+.2f}%")
        print(f"  平均胜率: {high_df['win_rate'].mean():.1%}")
        
        print(f"\n主板/创业板 ({len(medium_df)}只):")
        print(f"  平均收益: {medium_df['return'].mean():+.2f}%")
        print(f"  平均胜率: {medium_df['win_rate'].mean():.1%}")
        
        print(f"\n总体 ({len(df_results)}只):")
        print(f"  平均收益: {df_results['return'].mean():+.2f}%")
        print(f"  平均胜率: {df_results['win_rate'].mean():.1%}")
        print(f"  盈利比例: {(df_results['return'] > 0).sum()}/{len(df_results)} ({(df_results['return'] > 0).mean():.1%})")
        
        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        df_results.to_csv(f"tests/results/tech_atr_{timestamp}.csv", index=False)
        if alltrade_details:
            pd.DataFrame(alltrade_details).to_csv(f"tests/results/tech_atrtrades_{timestamp}.csv", index=False)
        
        return df_results
    
    return None

if __name__ == '__main__':
    run_atr_backtest()
