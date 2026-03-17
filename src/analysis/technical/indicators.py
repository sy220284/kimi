"""
技术指标模块 - 技术指标计算
实现MACD、RSI、KDJ、Bollinger Bands、MA均线
使用pandas和numpy实现，返回DataFrame格式
"""
from typing import List, Optional, Dict, Any, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.logger import get_logger


class IndicatorError(Exception):
    """指标计算错误"""
    pass


@dataclass
class IndicatorValue:
    """指标值"""
    name: str
    value: Any
    timestamp: str
    signal: Optional[str] = None  # 'buy', 'sell', 'neutral'
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp,
            'signal': self.signal
        }


class TechnicalIndicators:
    """技术指标计算器"""
    
    def __init__(self):
        self.logger = get_logger('analysis.technical')
    
    def validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        验证DataFrame格式
        
        Args:
            df: 输入数据
            
        Raises:
            IndicatorError: 数据格式不正确
        """
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        
        for col in required_cols:
            if col not in df.columns:
                raise IndicatorError(f"缺少必需列: {col}")
        
        if df.empty:
            raise IndicatorError("数据为空")
    
    # ==================== MA 均线 ====================
    
    def ma(
        self,
        df: pd.DataFrame,
        period: int = 20,
        column: str = 'close',
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算简单移动平均线 (SMA/MA)
        
        Args:
            df: 价格数据
            period: 周期
            column: 计算列名
            inplace: 是否原地修改
            
        Returns:
            包含MA列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        col_name = f'MA{period}'
        result[col_name] = df[column].rolling(window=period).mean()
        
        return result
    
    def ema(
        self,
        df: pd.DataFrame,
        period: int = 20,
        column: str = 'close',
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算指数移动平均线 (EMA)
        
        Args:
            df: 价格数据
            period: 周期
            column: 计算列名
            inplace: 是否原地修改
            
        Returns:
            包含EMA列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        col_name = f'EMA{period}'
        result[col_name] = df[column].ewm(span=period, adjust=False).mean()
        
        return result
    
    def multi_ma(
        self,
        df: pd.DataFrame,
        periods: List[int] = [5, 10, 20, 60],
        column: str = 'close',
        ma_type: str = 'sma'
    ) -> pd.DataFrame:
        """
        计算多条均线
        
        Args:
            df: 价格数据
            periods: 周期列表
            column: 计算列名
            ma_type: 均线类型 ('sma' 或 'ema')
            
        Returns:
            包含多条均线的DataFrame
        """
        self.validate_dataframe(df)
        result = df.copy()
        
        for period in periods:
            if ma_type == 'sma':
                result = self.ma(result, period, column, inplace=True)
            else:
                result = self.ema(result, period, column, inplace=True)
        
        return result
    
    # ==================== MACD ====================
    
    def macd(
        self,
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        column: str = 'close',
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算MACD指标
        
        MACD = EMA(fast) - EMA(slow)
        Signal = EMA(MACD, signal_period)
        Histogram = MACD - Signal
        
        Args:
            df: 价格数据
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期
            column: 计算列名
            inplace: 是否原地修改
            
        Returns:
            包含MACD列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        
        # 计算EMA
        ema_fast = df[column].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow_period, adjust=False).mean()
        
        # 计算MACD线和信号线
        result['MACD'] = ema_fast - ema_slow
        result['MACD_Signal'] = result['MACD'].ewm(span=signal_period, adjust=False).mean()
        result['MACD_Histogram'] = result['MACD'] - result['MACD_Signal']
        
        return result
    
    def macd_signal(self, df: pd.DataFrame) -> str:
        """
        获取MACD交易信号
        
        Args:
            df: 包含MACD的数据
            
        Returns:
            'buy', 'sell', 或 'neutral'
        """
        if len(df) < 2:
            return 'neutral'
        
        # 获取最新两期的值
        macd_curr = df['MACD'].iloc[-1]
        macd_prev = df['MACD'].iloc[-2]
        signal_curr = df['MACD_Signal'].iloc[-1]
        signal_prev = df['MACD_Signal'].iloc[-2]
        hist_curr = df['MACD_Histogram'].iloc[-1]
        hist_prev = df['MACD_Histogram'].iloc[-2]
        
        # MACD金叉（MACD上穿信号线）
        if macd_prev <= signal_prev and macd_curr > signal_curr:
            return 'buy'
        
        # MACD死叉（MACD下穿信号线）
        if macd_prev >= signal_prev and macd_curr < signal_curr:
            return 'sell'
        
        # MACD柱状图由负转正
        if hist_prev <= 0 and hist_curr > 0:
            return 'buy'
        
        # MACD柱状图由正转负
        if hist_prev >= 0 and hist_curr < 0:
            return 'sell'
        
        return 'neutral'
    
    # ==================== RSI ====================
    
    def rsi(
        self,
        df: pd.DataFrame,
        period: int = 14,
        column: str = 'close',
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算RSI相对强弱指标
        
        RSI = 100 - (100 / (1 + RS))
        RS = 平均上涨幅度 / 平均下跌幅度
        
        Args:
            df: 价格数据
            period: 周期
            column: 计算列名
            inplace: 是否原地修改
            
        Returns:
            包含RSI列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        
        # 计算价格变化
        delta = df[column].diff()
        
        # 分离上涨和下跌
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 计算平均上涨和平均下跌（使用指数移动平均）
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        # 计算RS和RSI
        rs = avg_gain / avg_loss
        result[f'RSI{period}'] = 100 - (100 / (1 + rs))
        
        return result
    
    def rsi_signal(
        self,
        df: pd.DataFrame,
        period: int = 14,
        overbought: float = 70,
        oversold: float = 30
    ) -> str:
        """
        获取RSI交易信号
        
        Args:
            df: 包含RSI的数据
            period: RSI周期
            overbought: 超买阈值
            oversold: 超卖阈值
            
        Returns:
            'buy', 'sell', 或 'neutral'
        """
        col_name = f'RSI{period}'
        if col_name not in df.columns:
            return 'neutral'
        
        if len(df) < 2:
            return 'neutral'
        
        rsi_curr = df[col_name].iloc[-1]
        rsi_prev = df[col_name].iloc[-2]
        
        # 从超卖区回升
        if rsi_prev <= oversold and rsi_curr > oversold:
            return 'buy'
        
        # 从超买区回落
        if rsi_prev >= overbought and rsi_curr < overbought:
            return 'sell'
        
        # 持续超买
        if rsi_curr > overbought:
            return 'sell'
        
        # 持续超卖
        if rsi_curr < oversold:
            return 'buy'
        
        return 'neutral'
    
    # ==================== KDJ ====================
    
    def kdj(
        self,
        df: pd.DataFrame,
        k_period: int = 9,
        d_period: int = 3,
        j_period: int = 3,
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算KDJ随机指标
        
        RSV = (Close - Min(Low, n)) / (Max(High, n) - Min(Low, n)) * 100
        K = SMA(RSV, m1)
        D = SMA(K, m2)
        J = 3K - 2D
        
        Args:
            df: 价格数据
            k_period: K值周期
            d_period: D值周期
            j_period: J值计算参数
            inplace: 是否原地修改
            
        Returns:
            包含KDJ列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        
        # 计算RSV
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        
        rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
        rsv = rsv.fillna(50)  # 填充NaN为50
        
        # 计算K值
        result['K'] = rsv.ewm(alpha=1/d_period, adjust=False).mean()
        
        # 计算D值
        result['D'] = result['K'].ewm(alpha=1/d_period, adjust=False).mean()
        
        # 计算J值
        result['J'] = 3 * result['K'] - 2 * result['D']
        
        return result
    
    def kdj_signal(self, df: pd.DataFrame) -> str:
        """
        获取KDJ交易信号
        
        Args:
            df: 包含KDJ的数据
            
        Returns:
            'buy', 'sell', 或 'neutral'
        """
        if len(df) < 2:
            return 'neutral'
        
        k_curr = df['K'].iloc[-1]
        d_curr = df['D'].iloc[-1]
        j_curr = df['J'].iloc[-1]
        k_prev = df['K'].iloc[-2]
        d_prev = df['D'].iloc[-2]
        
        # K线上穿D线（金叉）且J值不高
        if k_prev <= d_prev and k_curr > d_curr and j_curr < 80:
            return 'buy'
        
        # K线下穿D线（死叉）且J值不低
        if k_prev >= d_prev and k_curr < d_curr and j_curr > 20:
            return 'sell'
        
        # J值小于0（超卖）
        if j_curr < 0:
            return 'buy'
        
        # J值大于100（超买）
        if j_curr > 100:
            return 'sell'
        
        return 'neutral'
    
    # ==================== Bollinger Bands ====================
    
    def bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        column: str = 'close',
        inplace: bool = False
    ) -> pd.DataFrame:
        """
        计算布林带 (Bollinger Bands)
        
        Middle Band = MA(close, n)
        Upper Band = MA + std_dev * std(close, n)
        Lower Band = MA - std_dev * std(close, n)
        
        Args:
            df: 价格数据
            period: 周期
            std_dev: 标准差倍数
            column: 计算列名
            inplace: 是否原地修改
            
        Returns:
            包含布林带列的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df if inplace else df.copy()
        
        # 中轨（MA）
        result['BB_Middle'] = df[column].rolling(window=period).mean()
        
        # 标准差
        rolling_std = df[column].rolling(window=period).std()
        
        # 上轨和下轨
        result['BB_Upper'] = result['BB_Middle'] + std_dev * rolling_std
        result['BB_Lower'] = result['BB_Middle'] - std_dev * rolling_std
        
        # 带宽 (Bandwidth)
        result['BB_Width'] = (result['BB_Upper'] - result['BB_Lower']) / result['BB_Middle']
        
        # %B 指标
        result['BB_PercentB'] = (df[column] - result['BB_Lower']) / (result['BB_Upper'] - result['BB_Lower'])
        
        return result
    
    def bb_signal(self, df: pd.DataFrame) -> str:
        """
        获取布林带交易信号
        
        Args:
            df: 包含布林带的数据
            
        Returns:
            'buy', 'sell', 或 'neutral'
        """
        if len(df) < 2:
            return 'neutral'
        
        close_curr = df['close'].iloc[-1]
        close_prev = df['close'].iloc[-2]
        upper = df['BB_Upper'].iloc[-1]
        lower = df['BB_Lower'].iloc[-1]
        upper_prev = df['BB_Upper'].iloc[-2]
        lower_prev = df['BB_Lower'].iloc[-2]
        
        # 触及下轨反弹
        if close_prev <= lower_prev and close_curr > close_prev:
            return 'buy'
        
        # 触及上轨回落
        if close_prev >= upper_prev and close_curr < close_prev:
            return 'sell'
        
        # 突破上轨
        if close_curr > upper:
            return 'sell'
        
        # 跌破下轨
        if close_curr < lower:
            return 'buy'
        
        return 'neutral'
    
    # ==================== 综合指标 ====================
    
    def calculate_all(
        self,
        df: pd.DataFrame,
        ma_periods: List[int] = [5, 10, 20, 60],
        macd_params: Optional[Dict] = None,
        rsi_period: int = 14,
        kdj_params: Optional[Dict] = None,
        bb_params: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        计算所有技术指标
        
        Args:
            df: 价格数据
            ma_periods: MA周期列表
            macd_params: MACD参数字典
            rsi_period: RSI周期
            kdj_params: KDJ参数字典
            bb_params: 布林带参数字典
            
        Returns:
            包含所有指标的DataFrame
        """
        self.validate_dataframe(df)
        
        result = df.copy()
        
        # MA
        result = self.multi_ma(result, periods=ma_periods)
        
        # MACD
        macd_config = macd_params or {}
        result = self.macd(result, **macd_config, inplace=True)
        
        # RSI
        result = self.rsi(result, period=rsi_period, inplace=True)
        
        # KDJ
        kdj_config = kdj_params or {}
        result = self.kdj(result, **kdj_config, inplace=True)
        
        # Bollinger Bands
        bb_config = bb_params or {}
        result = self.bollinger_bands(result, **bb_config, inplace=True)
        
        self.logger.info(f"计算完成所有指标，数据行数: {len(result)}")
        
        return result
    
    def get_all_signals(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        获取所有指标的交易信号
        
        Args:
            df: 包含所有指标的数据
            
        Returns:
            各指标的交易信号
        """
        signals = {}
        
        # MACD信号
        if 'MACD' in df.columns:
            signals['macd'] = self.macd_signal(df)
        
        # RSI信号
        for col in df.columns:
            if col.startswith('RSI'):
                period = int(col.replace('RSI', ''))
                signals[f'rsi{period}'] = self.rsi_signal(df, period=period)
        
        # KDJ信号
        if 'K' in df.columns and 'D' in df.columns:
            signals['kdj'] = self.kdj_signal(df)
        
        # 布林带信号
        if 'BB_Upper' in df.columns:
            signals['bollinger'] = self.bb_signal(df)
        
        return signals
    
    def get_combined_signal(
        self,
        df: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        获取综合交易信号
        
        Args:
            df: 包含所有指标的数据
            weights: 各指标权重
            
        Returns:
            综合信号分析结果
        """
        signals = self.get_all_signals(df)
        
        default_weights = {
            'macd': 0.3,
            'rsi': 0.25,
            'kdj': 0.25,
            'bollinger': 0.2
        }
        
        weights = weights or default_weights
        
        # 计算加权得分
        score = 0
        total_weight = 0
        
        for indicator, signal in signals.items():
            # 找到对应的权重
            weight = 0
            for key, w in weights.items():
                if key in indicator.lower():
                    weight = w
                    break
            
            if signal == 'buy':
                score += weight * 1
                total_weight += weight
            elif signal == 'sell':
                score += weight * (-1)
                total_weight += weight
        
        # 归一化得分
        if total_weight > 0:
            normalized_score = score / total_weight
        else:
            normalized_score = 0
        
        # 确定综合信号
        if normalized_score > 0.3:
            combined_signal = 'buy'
        elif normalized_score < -0.3:
            combined_signal = 'sell'
        else:
            combined_signal = 'neutral'
        
        return {
            'combined_signal': combined_signal,
            'score': round(normalized_score, 4),
            'individual_signals': signals,
            'timestamp': df['date'].iloc[-1] if 'date' in df.columns else None
        }
