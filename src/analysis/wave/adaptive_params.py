"""
自适应参数优化器 - 根据市场波动率动态调整
Phase 2: 提高分析准确性
"""
import pandas as pd
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


class MarketCondition(Enum):
    """市场状态"""
    TRENDING = "trending"      # 趋势市
    RANGING = "ranging"        # 震荡市
    VOLATILE = "volatile"      # 高波动
    QUIET = "quiet"            # 低波动


@dataclass
class AdaptiveParameters:
    """自适应参数集"""
    atr_period: int
    atr_mult: float
    confidence_threshold: float
    min_dist: int
    peak_window: int
    min_change_pct: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'atr_period': self.atr_period,
            'atr_mult': self.atr_mult,
            'confidence_threshold': self.confidence_threshold,
            'min_dist': self.min_dist,
            'peak_window': self.peak_window,
            'min_change_pct': self.min_change_pct
        }


class VolatilityAnalyzer:
    """波动率分析器"""
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def calculate_volatility_regime(df: pd.DataFrame, lookback: int = 60) -> Dict[str, Any]:
        """
        计算波动率状态
        
        Returns:
            {
                'current_atr': float,
                'atr_percentile': float,  # 0-100
                'volatility_state': str,  # high/medium/low
                'market_condition': MarketCondition
            }
        """
        if len(df) < lookback:
            return {
                'current_atr': 0.0,
                'atr_percentile': 50.0,
                'volatility_state': 'medium',
                'market_condition': MarketCondition.TRENDING
            }
        
        # 计算ATR
        atr = VolatilityAnalyzer.calculate_atr(df, 14)
        current_atr = atr.iloc[-1]
        
        # ATR历史分布
        atr_history = atr.dropna()
        if len(atr_history) > 0:
            atr_percentile = (atr_history <= current_atr).mean() * 100
        else:
            atr_percentile = 50.0
        
        # 判断波动率状态
        if atr_percentile > 80:
            vol_state = 'high'
        elif atr_percentile < 20:
            vol_state = 'low'
        else:
            vol_state = 'medium'
        
        # 判断市场状态
        # 计算趋势强度 (ADX简化版)
        price_change = abs(df['close'].iloc[-1] - df['close'].iloc[-lookback])
        price_range = df['high'].tail(lookback).max() - df['low'].tail(lookback).min()
        
        trend_strength = price_change / price_range if price_range > 0 else 0
        
        if vol_state == 'high':
            if trend_strength > 0.6:
                market_condition = MarketCondition.TRENDING
            else:
                market_condition = MarketCondition.VOLATILE
        elif vol_state == 'low':
            if trend_strength < 0.3:
                market_condition = MarketCondition.RANGING
            else:
                market_condition = MarketCondition.QUIET
        else:
            market_condition = MarketCondition.TRENDING if trend_strength > 0.5 else MarketCondition.RANGING
        
        return {
            'current_atr': current_atr,
            'atr_percentile': atr_percentile,
            'volatility_state': vol_state,
            'market_condition': market_condition,
            'trend_strength': trend_strength
        }


class AdaptiveParameterOptimizer:
    """
    自适应参数优化器
    
    根据市场状态自动调整波浪分析参数
    """
    
    # 基准参数
    BASE_PARAMS = {
        'atr_period': 14,
        'atr_mult': 0.5,
        'confidence_threshold': 0.5,
        'min_dist': 3,
        'peak_window': 3,
        'min_change_pct': 2.0
    }
    
    # 参数调整系数
    ADJUSTMENTS = {
        MarketCondition.TRENDING: {
            'atr_mult': 1.2,           # 趋势市用更大倍数，减少噪声
            'confidence_threshold': 0.6, # 提高置信度要求
            'min_dist': 1.0,           # 减少最小距离，捕捉更多浪
        },
        MarketCondition.RANGING: {
            'atr_mult': 0.7,           # 震荡市用更小倍数
            'confidence_threshold': 0.45,
            'min_dist': 1.5,
        },
        MarketCondition.VOLATILE: {
            'atr_mult': 1.5,           # 高波动用大倍数过滤噪声
            'confidence_threshold': 0.7, # 严格筛选
            'min_dist': 0.8,
        },
        MarketCondition.QUIET: {
            'atr_mult': 0.4,           # 低波动用小倍数
            'confidence_threshold': 0.4,
            'min_dist': 2.0,           # 增加距离，避免过度细分
        }
    }
    
    @classmethod
    def optimize(cls, df: pd.DataFrame, timeframe: str = "day") -> AdaptiveParameters:
        """
        根据数据特征优化参数
        
        Args:
            df: 价格数据
            timeframe: 时间框架 (day/week/month)
            
        Returns:
            AdaptiveParameters
        """
        # 分析波动率状态
        vol_analysis = VolatilityAnalyzer.calculate_volatility_regime(df)
        market_condition = vol_analysis['market_condition']
        
        # 获取基准参数
        params = cls.BASE_PARAMS.copy()
        
        # 应用时间框架调整
        if timeframe == "week":
            params['atr_period'] = 5
            params['min_dist'] = 2
        elif timeframe == "month":
            params['atr_period'] = 3
            params['min_dist'] = 1
            params['atr_mult'] *= 1.5
        
        # 应用市场状态调整
        adjustments = cls.ADJUSTMENTS.get(market_condition, {})
        
        for key, factor in adjustments.items():
            if key in params:
                if key in ['atr_mult', 'confidence_threshold']:
                    params[key] *= factor
                elif key in ['min_dist', 'peak_window']:
                    params[key] = int(params[key] * factor)
        
        # 确保参数在合理范围内
        params['atr_period'] = max(3, min(30, params['atr_period']))
        params['atr_mult'] = max(0.1, min(2.0, params['atr_mult']))
        params['confidence_threshold'] = max(0.3, min(0.9, params['confidence_threshold']))
        params['min_dist'] = max(1, min(10, params['min_dist']))
        
        return AdaptiveParameters(**params)
    
    @classmethod
    def get_parameters_for_scanning(cls, df: pd.DataFrame) -> Dict[str, AdaptiveParameters]:
        """
        生成多组参数用于扫描不同周期
        
        Returns:
            {
                'conservative': 保守参数,
                'aggressive': 激进参数,
                'adaptive': 自适应参数
            }
        """
        vol_analysis = VolatilityAnalyzer.calculate_volatility_regime(df)
        _ = vol_analysis['market_condition']
        
        # 自适应参数
        adaptive = cls.optimize(df)
        
        # 保守参数 (提高阈值)
        conservative = AdaptiveParameters(
            atr_period=adaptive.atr_period,
            atr_mult=adaptive.atr_mult * 1.3,
            confidence_threshold=min(0.8, adaptive.confidence_threshold + 0.15),
            min_dist=adaptive.min_dist + 1,
            peak_window=adaptive.peak_window + 1,
            min_change_pct=adaptive.min_change_pct * 1.3
        )
        
        # 激进参数 (降低阈值)
        aggressive = AdaptiveParameters(
            atr_period=max(5, adaptive.atr_period - 3),
            atr_mult=adaptive.atr_mult * 0.7,
            confidence_threshold=max(0.3, adaptive.confidence_threshold - 0.15),
            min_dist=max(1, adaptive.min_dist - 1),
            peak_window=max(2, adaptive.peak_window - 1),
            min_change_pct=adaptive.min_change_pct * 0.7
        )
        
        return {
            'conservative': conservative,
            'adaptive': adaptive,
            'aggressive': aggressive
        }
    
    @staticmethod
    def explain_parameters(params: AdaptiveParameters, market_condition: MarketCondition) -> str:
        """解释参数选择的理由"""
        explanations = {
            MarketCondition.TRENDING: "趋势市场，放大ATR倍数过滤噪声，提高置信度",
            MarketCondition.RANGING: "震荡市场，减小ATR倍数捕捉波动",
            MarketCondition.VOLATILE: "高波动市场，严格参数避免过度交易",
            MarketCondition.QUIET: "低波动市场，宽松参数捕捉小浪"
        }
        
        base = explanations.get(market_condition, "标准参数")
        
        return f"{base} | ATR周期={params.atr_period}, 倍数={params.atr_mult:.2f}, 置信度={params.confidence_threshold:.2f}"


# 便捷函数
def get_adaptive_params(df: pd.DataFrame, timeframe: str = "day") -> Dict[str, Any]:
    """获取自适应参数字典"""
    optimizer = AdaptiveParameterOptimizer()
    params = optimizer.optimize(df, timeframe)
    return params.to_dict()
