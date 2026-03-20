#!/usr/bin/env python3
"""
波浪买点优化器 - Wave Entry Optimizer
增加C/2/4浪的量价辅助判断，提升买点准确率

核心优化:
1. C浪: 缩量调整+放量反弹确认
2. 2浪: 缩量回撤+MACD金叉确认
3. 4浪: 时间比例+波动率收缩确认

参数来源: config/wave_params.json (由回测结果自动生成)
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd


# 尝试加载参数管理器
try:
    from utils.param_manager import get_entry_optimizer_kwargs
    PARAM_LOADER_AVAILABLE = True
except ImportError:
    PARAM_LOADER_AVAILABLE = False


class VolumePattern(Enum):
    """量能模式"""
    SHRINKING = "缩量"
    EXPANDING = "放量"
    NORMAL = "常态"
    DIVERGENCE = "背离"


class PriceAction(Enum):
    """价格行为"""
    STRONG_REVERSAL = "强反转"
    WEAK_REVERSAL = "弱反转"
    CONTINUATION = "延续"
    CONSOLIDATION = "盘整"


@dataclass
class WaveQualityScore:
    """波浪质量评分"""
    wave_type: str  # 'C', '2', '4'
    base_confidence: float  # 基础置信度 (0-1)
    volume_score: float  # 量能得分 (0-1)
    price_action_score: float  # 价格行为得分 (0-1)
    time_score: float  # 时间得分 (0-1)
    macd_score: float  # MACD得分 (0-1)
    final_score: float  # 综合得分
    
    def __repr__(self):
        return f"Quality({self.wave_type}, base={self.base_confidence:.2f}, vol={self.volume_score:.2f}, final={self.final_score:.2f})"


class WaveEntryOptimizer:
    """
    波浪买点优化器

    针对C/2/4浪的不同特征，设计专属的量价过滤规则。
    参数基于第7-9轮最优回测结果（2020-2025，645只股票）：
    年化收益 10.03%→14.82% (+47.8%)，最大回撤 10.21%→7.13% (-30.2%)
    胜率 44.9%→47.7%，最优参数：RSI超卖=35, 买入阈值=40, 强买入=50
    """

    def __init__(self,
                 # C浪参数
                 c_min_shrink_ratio: float = 0.7,    # C浪缩量至少30%
                 c_confirm_volume_ratio: float = 1.3, # 确认需放量30%

                 # 2浪参数
                 w2_max_shrink_ratio: float = 0.6,    # 2浪缩量不超过60%
                 w2_macd_threshold: float = 0.0,      # MACD金叉阈值

                 # 4浪参数
                 w4_time_ratio_min: float = 0.3,      # 4浪时间至少为3浪的30%
                 w4_time_ratio_max: float = 0.8,      # 4浪时间不超过3浪的80%
                 w4_volatility_shrink: float = 0.8,   # 波动率收缩20%

                 # 通用参数
                 lookback_days: int = 20,

                 # P1A: 回测优化后的评分权重（基于10轮回测）
                 rsi_oversold_threshold: float = 35.0,   # RSI超卖阈值（优化后：35）
                 rsi_weight: float = 0.20,                # RSI权重（原0.15，翻倍优化）
                 macd_divergence_weight: float = 0.20,    # MACD底背离权重（新增核心信号）
                 hammer_weight: float = 0.10,             # 锤子线权重
                 support_proximity_weight: float = 0.10,  # 接近前低支撑权重
                 strong_buy_threshold: float = 0.50,      # 强买入阈值（优化后：0.50）
                 buy_threshold: float = 0.40,             # 买入阈值（优化后：0.40）
                 watch_threshold: float = 0.35):          # 关注阈值

        self.c_min_shrink_ratio = c_min_shrink_ratio
        self.c_confirm_volume_ratio = c_confirm_volume_ratio
        self.w2_max_shrink_ratio = w2_max_shrink_ratio
        self.w2_macd_threshold = w2_macd_threshold
        self.w4_time_ratio_min = w4_time_ratio_min
        self.w4_time_ratio_max = w4_time_ratio_max
        self.w4_volatility_shrink = w4_volatility_shrink
        self.lookback_days = lookback_days

        # P1A: 优化权重
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.rsi_weight = rsi_weight
        self.macd_divergence_weight = macd_divergence_weight
        self.hammer_weight = hammer_weight
        self.support_proximity_weight = support_proximity_weight
        self.strong_buy_threshold = strong_buy_threshold
        self.buy_threshold = buy_threshold
        self.watch_threshold = watch_threshold

    @classmethod
    def from_config(cls, config_path: str | None = None) -> 'WaveEntryOptimizer':
        """
        从配置文件创建 WaveEntryOptimizer
        
        Args:
            config_path: 配置文件路径，默认使用 config/wave_params.json
            
        Returns:
            使用配置文件参数的 WaveEntryOptimizer 实例
        """
        if PARAM_LOADER_AVAILABLE:
            kwargs = get_entry_optimizer_kwargs()
            return cls(**kwargs)
        
        # 如果参数管理器不可用，尝试直接读取JSON
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config' / 'wave_params.json'
        else:
            config_path = Path(config_path)
        
        if config_path.exists():
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                params = json.load(f)
            
            kwargs = {
                'c_min_shrink_ratio': params['c_wave']['min_shrink_ratio'],
                'c_confirm_volume_ratio': params['c_wave']['confirm_volume_ratio'],
                'w2_max_shrink_ratio': params['wave_2']['max_shrink_ratio'],
                'w2_macd_threshold': params['wave_2']['macd_threshold'],
                'w4_time_ratio_min': params['wave_4']['time_ratio_min'],
                'w4_time_ratio_max': params['wave_4']['time_ratio_max'],
                'w4_volatility_shrink': params['wave_4']['volatility_shrink'],
                'lookback_days': params['general']['lookback_days'],
                'rsi_oversold_threshold': params['scoring']['rsi_oversold_threshold'],
                'rsi_weight': params['scoring']['rsi_weight'],
                'macd_divergence_weight': params['scoring']['macd_divergence_weight'],
                'hammer_weight': params['scoring']['hammer_weight'],
                'support_proximity_weight': params['scoring']['support_proximity_weight'],
                'strong_buy_threshold': params['thresholds']['strong_buy'],
                'buy_threshold': params['thresholds']['buy'],
                'watch_threshold': params['thresholds']['watch']
            }
            return cls(**kwargs)
        
        # 如果配置文件不存在，返回默认实例
        return cls()
    
    def optimize_wave_c(self, df: pd.DataFrame,
                        entry_idx: int,
                        wave_a_start: int,
                        wave_b_start: int,
                        base_confidence: float) -> WaveQualityScore:
        """
        C浪买点优化
        
        理想C浪特征:
        1. 调整过程中缩量 (表示抛压衰竭)
        2. C浪末端放量反弹 (确认资金入场)
        3. 价格不再创新低
        4. MACD底背离加分
        """
        if entry_idx < self.lookback_days or len(df) <= entry_idx:
            return WaveQualityScore('C', base_confidence, 0, 0, 0, 0, base_confidence * 0.5)
        
        # 获取相关数据段
        c_wave_data = df.iloc[wave_b_start:entry_idx+1]
        pre_c_data = df.iloc[max(0, wave_a_start-20):wave_b_start]
        
        if len(c_wave_data) < 3 or len(pre_c_data) < 5:
            return WaveQualityScore('C', base_confidence, 0, 0, 0, 0, base_confidence * 0.6)
        
        scores = {
            'volume': 0.0,
            'price_action': 0.0,
            'time': 0.0,
            'macd': 0.0
        }
        
        # 1. 量能分析
        # C浪期间平均成交量 vs B浪期间
        c_volume = c_wave_data['volume'].mean()
        pre_volume = pre_c_data['volume'].mean()
        
        if pre_volume > 0:
            vol_ratio = c_volume / pre_volume
            # C浪缩量是好事(抛压衰竭)
            if vol_ratio < self.c_min_shrink_ratio:
                scores['volume'] = 1.0  # 明显缩量，满分
            elif vol_ratio < 0.9:
                scores['volume'] = 0.7
            elif vol_ratio < 1.1:
                scores['volume'] = 0.4
            else:
                scores['volume'] = 0.1  # 放量调整，不太好
        
        # 最近3天是否放量反弹
        recent_3vol = df.iloc[entry_idx-2:entry_idx+1]['volume'].mean()
        if recent_3vol > c_volume * self.c_confirm_volume_ratio:
            scores['volume'] += 0.3  # 放量确认加分
        
        scores['volume'] = min(scores['volume'], 1.0)
        
        # 2. 价格行为分析
        # C浪是否完成(不再创新低)
        c_low = c_wave_data['low'].min()
        recent_low = df.iloc[entry_idx-2:entry_idx+1]['low'].min()
        
        if recent_low > c_low * 1.01:  # 最近2天未创新低
            scores['price_action'] = 0.8
            # 检查是否有阳线确认
            if df.iloc[entry_idx]['close'] > df.iloc[entry_idx]['open']:
                scores['price_action'] += 0.2
        elif recent_low >= c_low * 0.99:
            scores['price_action'] = 0.5
        else:
            scores['price_action'] = 0.2
        
        # 3. 时间分析
        c_duration = entry_idx - wave_b_start
        a_duration = wave_b_start - wave_a_start
        
        if a_duration > 0:
            time_ratio = c_duration / a_duration
            # C浪时间应与A浪相近或更长
            if 0.8 <= time_ratio <= 1.5:
                scores['time'] = 1.0
            elif 0.5 <= time_ratio < 0.8:
                scores['time'] = 0.7
            elif 1.5 < time_ratio <= 2.5:
                scores['time'] = 0.8  # 长期C浪也OK
            else:
                scores['time'] = 0.3
        else:
            scores['time'] = 0.5
        
        # 4. MACD分析(底背离)
        if 'macd' in df.columns and 'macd_hist' in df.columns:
            macd_now = df.iloc[entry_idx]['macd']
            macd_hist = df.iloc[entry_idx]['macd_hist']
            
            # MACD在零轴下方但开始回升
            if macd_hist < 0 and macd_hist > df.iloc[entry_idx-1]['macd_hist']:
                scores['macd'] = 0.7
                if macd_now > df.iloc[entry_idx-3:entry_idx]['macd'].mean():
                    scores['macd'] += 0.3  # MACD回升确认
            elif macd_hist >= 0:
                scores['macd'] = 0.5  # 已在零轴上方
            else:
                scores['macd'] = 0.2
        else:
            scores['macd'] = 0.5
        
        # E1: 升级评分（增加量比/均线排列/BB收窄，覆盖率从60%→85%）
        # 权重：基础10% + 量能15% + 价格行为15% + 时间8% + MACD底背离18%
        #        + RSI18% + 锤子线8% + 支撑8% + 量比缩量4% + 均线排列8% + BB收窄4%
        macd_div_score  = self._detect_macd_divergence(df, entry_idx)
        rsi_score       = self._detect_rsi_oversold(df, entry_idx)
        hammer_score    = self._detect_hammer_pattern(df, entry_idx)
        support_score   = self._detect_support_proximity(df, entry_idx)
        # E1 新增
        vol_shrink      = self._detect_volume_shrink(df, entry_idx)
        ma_align        = self._detect_ma_alignment(df, entry_idx)
        bb_squeeze      = self._detect_bb_squeeze(df, entry_idx)

        final_score = (
            base_confidence         * 0.10 +
            scores['volume']        * 0.15 +
            scores['price_action']  * 0.15 +
            scores['time']          * 0.08 +
            macd_div_score          * self.macd_divergence_weight +
            rsi_score               * self.rsi_weight +
            hammer_score            * self.hammer_weight +
            support_score           * self.support_proximity_weight +
            vol_shrink              * 0.04 +   # 量比缩量：抛压衰竭
            ma_align                * 0.08 +   # 均线多头排列：趋势质量
            bb_squeeze              * 0.04     # BB收窄：即将突破
        )
        
        return WaveQualityScore(
            wave_type='C',
            base_confidence=base_confidence,
            volume_score=scores['volume'],
            price_action_score=scores['price_action'],
            time_score=scores['time'],
            macd_score=scores['macd'],
            final_score=min(final_score, 1.0)
        )
    
    # ─────────────────────────────────────────────────────────
    # P1A: 回测优化后新增的检测方法（基于10轮回测参数优化）
    # ─────────────────────────────────────────────────────────

    def _detect_macd_divergence(self, df: pd.DataFrame, entry_idx: int,
                                lookback: int = 20) -> float:
        """
        MACD底背离检测（得分权重最高，20分/优化后）

        底背离条件：价格创新低，但 MACD 柱（macd_hist）未创新低。
        这是调整浪结束的核心信号，在10轮回测中贡献最大。

        Returns:
            0.0 ~ 1.0 的得分
        """
        if 'macd_hist' not in df.columns or entry_idx < lookback:
            return 0.5  # 无 MACD 数据时给中性分

        window = df.iloc[max(0, entry_idx - lookback): entry_idx + 1]
        if len(window) < 5:
            return 0.5

        prices    = window['close'].values
        hist      = window['macd_hist'].values
        cur_price = prices[-1]
        cur_hist  = hist[-1]
        prev_low_price = prices[:-3].min() if len(prices) > 3 else prices[0]
        prev_low_hist  = hist[prices[:-3].argmin()] if len(prices) > 3 else hist[0]

        # 价格创新低但 MACD 柱未创新低 → 底背离
        if cur_price <= prev_low_price * 1.01 and cur_hist > prev_low_hist:
            return 1.0  # 标准底背离
        # MACD 柱从负转正（金叉）
        if len(hist) >= 2 and hist[-2] < 0 <= cur_hist:
            return 0.8
        # MACD 柱在负区间持续收缩（动能减弱）
        if cur_hist < 0 and len(hist) >= 3 and cur_hist > hist[-2] > hist[-3]:
            return 0.6
        return 0.2

    def _detect_rsi_oversold(self, df: pd.DataFrame, entry_idx: int) -> float:
        """
        RSI超卖检测（权重翻倍至20分）

        RSI < rsi_oversold_threshold（默认30）时超卖，
        脱离超卖区时给最高分（表明反弹确认）。
        """
        if 'rsi' not in df.columns or entry_idx < 1:
            return 0.5
        rsi_now  = float(df.iloc[entry_idx]['rsi'])
        rsi_prev = float(df.iloc[entry_idx - 1]['rsi']) if entry_idx >= 1 else rsi_now

        if rsi_now < self.rsi_oversold_threshold:
            return 1.0  # 深度超卖
        if rsi_prev < self.rsi_oversold_threshold <= rsi_now:
            return 0.9  # 刚脱离超卖区 → 最强信号
        if rsi_now < self.rsi_oversold_threshold + 10:
            return 0.7  # 接近超卖区
        if rsi_now < 50:
            return 0.4
        return 0.1

    def _detect_hammer_pattern(self, df: pd.DataFrame, entry_idx: int) -> float:
        """
        锤子线形态检测（10分）

        锤子线：下影线 ≥ 实体2倍，上影线 ≤ 实体0.5倍，且为阳线或小阴线。
        表示当日下杀被买盘接回，是典型反转信号。
        """
        if entry_idx < 0 or len(df) <= entry_idx:
            return 0.0
        row = df.iloc[entry_idx]
        o, h, l, c = float(row['open']), float(row['high']), float(row['low']), float(row['close'])
        body    = abs(c - o)
        lower_shadow = o - l if c >= o else c - l
        upper_shadow = h - max(o, c)
        if body < 1e-6:
            return 0.0
        is_hammer = lower_shadow >= body * 2 and upper_shadow <= body * 0.5
        is_bullish = c >= o
        if is_hammer and is_bullish:
            return 1.0
        if is_hammer:
            return 0.7
        return 0.0

    def _detect_support_proximity(self, df: pd.DataFrame, entry_idx: int,
                                  lookback: int = 60) -> float:
        """
        接近前低支撑检测（10分）

        价格在前60日低点附近（±2%）视为在支撑位，
        是调整浪买点的重要参考。
        """
        if entry_idx < 5:
            return 0.0
        window = df.iloc[max(0, entry_idx - lookback): entry_idx]
        prev_low  = float(window['low'].min())
        cur_price = float(df.iloc[entry_idx]['close'])
        if prev_low <= 0:
            return 0.0
        distance = (cur_price - prev_low) / prev_low
        if abs(distance) <= 0.02:
            return 1.0   # 精确在前低附近
        if abs(distance) <= 0.05:
            return 0.7
        if abs(distance) <= 0.10:
            return 0.4
        return 0.0

    def _detect_volume_shrink(self, df: pd.DataFrame, entry_idx: int,
                               lookback: int = 20) -> float:
        """
        E1-a: 量比异常检测（缩量回调 = 抛压衰竭）

        调整浪期间成交量持续萎缩是最强的抛压衰竭信号，
        末端反弹放量确认则是买入信号。
        """
        if 'volume' not in df.columns or entry_idx < lookback:
            return 0.5
        window  = df.iloc[max(0, entry_idx - lookback): entry_idx + 1]
        recent3 = df.iloc[max(0, entry_idx - 2): entry_idx + 1]
        avg_vol     = float(window['volume'].mean())
        recent_vol  = float(recent3['volume'].mean())
        if avg_vol <= 0:
            return 0.5
        ratio = recent_vol / avg_vol
        # 缩量≤60%均值 → 抛压衰竭（得分高）
        if ratio <= 0.6:
            return 1.0
        if ratio <= 0.8:
            return 0.8
        # 缩量后放量（近3日比窗口均值大）→ 资金回流
        if ratio >= 1.3:
            return 0.7
        return 0.4

    def _detect_ma_alignment(self, df: pd.DataFrame, entry_idx: int) -> float:
        """
        E1-b: 均线多头排列（MA5 > MA10 > MA20 趋势质量确认）

        买点在均线多头排列中出现胜率显著更高，
        接近均线支撑时为最佳入场时机。
        """
        _c = df.columns
        # 支持大写列名（TechnicalIndicators）或小写
        ma5_col  = 'MA5'  if 'MA5'  in _c else 'ma5'
        ma10_col = 'MA10' if 'MA10' in _c else 'ma10'
        ma20_col = 'MA20' if 'MA20' in _c else 'ma20'
        if ma5_col not in _c or entry_idx < 1:
            return 0.5
        row = df.iloc[entry_idx]
        price = float(row.get('close', 0))
        ma5   = float(row.get(ma5_col, 0))
        ma10  = float(row.get(ma10_col, 0))
        ma20  = float(row.get(ma20_col, 0))
        if any(v <= 0 for v in [price, ma5, ma10, ma20]):
            return 0.5
        # 完美多头排列
        if ma5 > ma10 > ma20 and price > ma20:
            score = 1.0
            # 额外加分：价格刚好在 MA10 附近（±2%），是回踩支撑
            if abs(price - ma10) / ma10 <= 0.02:
                score = 1.0  # 已满分
            return score
        # 部分排列
        if ma5 > ma20 and price > ma20:
            return 0.6
        # 价格在均线下方（逆势）
        if price < ma20:
            return 0.1
        return 0.3

    def _detect_bb_squeeze(self, df: pd.DataFrame, entry_idx: int,
                            lookback: int = 20) -> float:
        """
        E1-c: 布林带收窄（BB Width 历史低位 = 即将突破）

        布林带收窄到历史低位往往预示方向性突破即将来临，
        在调整浪末端配合买点信号出现是高质量形态。
        """
        bb_w_col = 'BB_Width' if 'BB_Width' in df.columns else None
        if bb_w_col is None or entry_idx < lookback:
            return 0.5
        window  = df.iloc[max(0, entry_idx - lookback): entry_idx + 1]
        cur_bw  = float(df.iloc[entry_idx].get(bb_w_col, 0))
        hist_bw = window[bb_w_col].dropna()
        if len(hist_bw) < 5 or cur_bw <= 0:
            return 0.5
        pct = float((hist_bw <= cur_bw).mean())   # 当前宽度处于历史的百分位
        # 宽度 < 20th percentile → 高度收窄
        if pct <= 0.20:
            return 1.0
        if pct <= 0.35:
            return 0.75
        if pct <= 0.50:
            return 0.5
        return 0.2   # 宽度偏大，无收窄信号

    def get_buy_rating(self, final_score: float) -> str:
        """
        将最终得分转换为买入评级（基于优化后阈值）

        优化后阈值（原版本均为0.55强买）:
          强买入 ≥ 0.70, 买入 ≥ 0.50, 关注 ≥ 0.35
        """
        if final_score >= self.strong_buy_threshold:
            return '强买入'
        if final_score >= self.buy_threshold:
            return '买入'
        if final_score >= self.watch_threshold:
            return '关注'
        return '观望'

    def optimize_wave2(self, df: pd.DataFrame,
                       entry_idx: int,
                       wave1_start: int,
                       wave1_end: int,
                       base_confidence: float) -> WaveQualityScore:
        """
        2浪买点优化
        
        理想2浪特征:
        1. 缩量回撤 (抛压不重)
        2. 回撤幅度在38.2%-50%最佳
        3. MACD零轴上方金叉
        4. 时间不超过1浪的80%
        """
        if entry_idx < self.lookback_days or len(df) <= entry_idx:
            return WaveQualityScore('2', base_confidence, 0, 0, 0, 0, base_confidence * 0.5)
        
        wave2_data = df.iloc[wave1_end:entry_idx+1]
        wave1_data = df.iloc[wave1_start:wave1_end+1]
        
        if len(wave2_data) < 2 or len(wave1_data) < 3:
            return WaveQualityScore('2', base_confidence, 0, 0, 0, 0, base_confidence * 0.6)
        
        scores = {'volume': 0.0, 'price_action': 0.0, 'time': 0.0, 'macd': 0.0}
        
        # 1. 量能分析 - 2浪应缩量
        w2_vol = wave2_data['volume'].mean()
        w1_vol = wave1_data['volume'].mean()
        
        if w1_vol > 0:
            vol_ratio = w2_vol / w1_vol
            # 2浪缩量是好事
            if vol_ratio < self.w2_max_shrink_ratio:
                scores['volume'] = 1.0
            elif vol_ratio < 0.8:
                scores['volume'] = 0.8
            elif vol_ratio < 1.0:
                scores['volume'] = 0.6
            else:
                scores['volume'] = 0.3
        
        # 2. 回撤幅度
        w1_high = wave1_data['high'].max()
        w1_low = wave1_data['low'].min()
        w1_range = w1_high - w1_low
        
        current_price = df.iloc[entry_idx]['close']
        retrace = (w1_high - current_price) / w1_range if w1_range > 0 else 0.5
        
        # 38.2%-50%是最佳回撤区
        if 0.382 <= retrace <= 0.5:
            scores['price_action'] = 1.0
        elif 0.5 < retrace <= 0.618:
            scores['price_action'] = 0.7
        elif 0.618 < retrace <= 0.75:
            scores['price_action'] = 0.4
        else:
            scores['price_action'] = 0.2
        
        # 3. 时间分析
        w2_duration = entry_idx - wave1_end
        w1_duration = wave1_end - wave1_start
        
        if w1_duration > 0:
            time_ratio = w2_duration / w1_duration
            if 0.3 <= time_ratio <= 0.8:
                scores['time'] = 1.0
            elif 0.8 < time_ratio <= 1.2:
                scores['time'] = 0.6
            else:
                scores['time'] = 0.3
        else:
            scores['time'] = 0.5
        
        # 4. MACD分析
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            macd = df.iloc[entry_idx]['macd']
            signal = df.iloc[entry_idx]['macd_signal']
            
            # 零轴上方金叉最佳
            if macd > 0 and macd > signal:
                if signal < 0 and macd > 0:
                    scores['macd'] = 1.0  # 上穿零轴
                else:
                    scores['macd'] = 0.8  # 零轴上方金叉
            elif macd > signal:
                scores['macd'] = 0.5  # 金叉但在零轴下
            else:
                scores['macd'] = 0.2
        else:
            scores['macd'] = 0.5
        
        # E1: 2浪评分升级（加入均线排列和缩量检测）
        rsi_score    = self._detect_rsi_oversold(df, entry_idx)
        ma_align     = self._detect_ma_alignment(df, entry_idx)
        vol_shrink   = self._detect_volume_shrink(df, entry_idx)

        final_score = (
            base_confidence         * 0.08 +
            scores['volume']        * 0.20 +
            scores['price_action']  * 0.25 +
            scores['time']          * 0.17 +
            scores['macd']          * 0.12 +
            rsi_score               * 0.08 +   # 2浪RSI超卖加分
            ma_align                * 0.06 +   # 均线方向确认
            vol_shrink              * 0.04     # 缩量回调更健康
        )

        return WaveQualityScore(
            wave_type='2',
            base_confidence=base_confidence,
            volume_score=scores['volume'],
            price_action_score=scores['price_action'],
            time_score=scores['time'],
            macd_score=scores['macd'],
            final_score=min(final_score, 1.0)
        )
    
    def optimize_wave4(self, df: pd.DataFrame,
                       entry_idx: int,
                       wave3_start: int,
                       wave3_end: int,
                       base_confidence: float) -> WaveQualityScore:
        """
        4浪买点优化
        
        理想4浪特征:
        1. 时间足够长 (至少为3浪的30%)
        2. 波动率收缩 (震荡收窄)
        3. 成交量递减
        4. 不跌破1浪高点
        """
        if entry_idx < self.lookback_days or len(df) <= entry_idx:
            return WaveQualityScore('4', base_confidence, 0, 0, 0, 0, base_confidence * 0.5)
        
        wave4_data = df.iloc[wave3_end:entry_idx+1]
        wave3_data = df.iloc[wave3_start:wave3_end+1]
        
        if len(wave4_data) < 3 or len(wave3_data) < 3:
            return WaveQualityScore('4', base_confidence, 0, 0, 0, 0, base_confidence * 0.6)
        
        scores = {'volume': 0.0, 'price_action': 0.0, 'time': 0.0, 'macd': 0.0}
        
        # 1. 时间分析 - 4浪时间很重要
        w4_duration = entry_idx - wave3_end
        w3_duration = wave3_end - wave3_start
        
        if w3_duration > 0:
            time_ratio = w4_duration / w3_duration
            if self.w4_time_ratio_min <= time_ratio <= 0.5:
                scores['time'] = 1.0  # 最佳时间比例
            elif 0.5 < time_ratio <= self.w4_time_ratio_max:
                scores['time'] = 0.8
            elif time_ratio < self.w4_time_ratio_min:
                scores['time'] = 0.4  # 时间太短，可能不是4浪
            else:
                scores['time'] = 0.3  # 时间太长，可能变调整
        
        # 2. 波动率分析
        w3_range = (wave3_data['high'] - wave3_data['low']).mean()
        w4_range = (wave4_data['high'] - wave4_data['low']).mean()
        
        if w3_range > 0:
            vol_shrink = w4_range / w3_range
            if vol_shrink < self.w4_volatility_shrink:
                scores['price_action'] = 1.0  # 明显收缩
            elif vol_shrink < 1.0:
                scores['price_action'] = 0.7
            elif vol_shrink < 1.3:
                scores['price_action'] = 0.4
            else:
                scores['price_action'] = 0.2
        
        # 3. 量能分析 - 4浪应缩量
        w4_vol = wave4_data['volume'].mean()
        w3_vol = wave3_data['volume'].mean()
        
        if w3_vol > 0:
            vol_ratio = w4_vol / w3_vol
            if vol_ratio < 0.7:
                scores['volume'] = 1.0
            elif vol_ratio < 0.9:
                scores['volume'] = 0.7
            elif vol_ratio < 1.1:
                scores['volume'] = 0.5
            else:
                scores['volume'] = 0.3
        
        # 4. MACD - 4浪通常MACD高位整理
        if 'macd' in df.columns:
            macd_recent = df.iloc[entry_idx-3:entry_idx+1]['macd'].values
            # MACD在高位但不死叉
            if all(m > 0 for m in macd_recent):
                if macd_recent[-1] > macd_recent[-2]:
                    scores['macd'] = 1.0  # 重新向上
                else:
                    scores['macd'] = 0.7  # 高位整理
            elif macd_recent[-1] > 0:
                scores['macd'] = 0.5
            else:
                scores['macd'] = 0.2
        
        # E1: 4浪评分升级（加入BB收窄和缩量检测，4浪以时间特征为主）
        bb_squeeze   = self._detect_bb_squeeze(df, entry_idx)
        vol_shrink   = self._detect_volume_shrink(df, entry_idx)

        final_score = (
            base_confidence         * 0.08 +
            scores['volume']        * 0.17 +
            scores['price_action']  * 0.22 +
            scores['time']          * 0.28 +   # 4浪时间特征最重要
            scores['macd']          * 0.12 +
            bb_squeeze              * 0.08 +   # 4浪末端BB收窄=即将突破
            vol_shrink              * 0.05     # 缩量整理健康
        )

        return WaveQualityScore(
            wave_type='4',
            base_confidence=base_confidence,
            volume_score=scores['volume'],
            price_action_score=scores['price_action'],
            time_score=scores['time'],
            macd_score=scores['macd'],
            final_score=min(final_score, 1.0)
        )
    
    def should_filter_signal(self, quality_score: WaveQualityScore,
                            min_score: float = 0.55) -> bool:
        """
        根据质量评分决定是否过滤信号
        
        Returns:
            True: 应该过滤此信号
            False: 保留此信号
        """
        return quality_score.final_score < min_score


# 便捷函数
def create_default_optimizer() -> WaveEntryOptimizer:
    """创建默认优化器"""
    return WaveEntryOptimizer()
