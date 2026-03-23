"""
analysis/strategy/style.py — 交易风格枚举与预设参数

三种交易风格：
  SHORT_TERM  短线：1-5天，追热点/涨停板/题材，快进快出
  SWING       波段：5-20天，趋势突破+均线共振，主流风格
  MEDIUM_TERM 中线：20-60天，趋势跟踪，持续放量上涨标的

各风格的核心差异：
  持仓天数：短线1-5 / 波段5-20 / 中线20-60
  止损幅度：短线3-5% / 波段5-8% / 中线7-12%
  目标盈亏比：短线1.5x / 波段2.0x / 中线2.5x
  信号过滤：短线量价优先 / 波段均线+量能 / 中线趋势+基本面
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class TradingStyle(Enum):
    SHORT_TERM  = "short_term"   # 短线：1-5天
    SWING       = "swing"        # 波段：5-20天
    MEDIUM_TERM = "medium_term"  # 中线：20-60天


@dataclass(frozen=True)
class StyleConfig:
    """交易风格配置（不可变）"""
    style:            TradingStyle
    name_cn:          str
    # 持仓
    max_holding_days: int
    min_holding_days: int
    # 止损
    min_stop_pct:     float
    max_stop_pct:     float
    atr_stop_mult:    float
    # 目标价
    target_lookback:  int
    target_buffer:    float
    min_rr_ratio:     float
    # 止盈
    trail_activation: float   # 浮盈多少激活移动止盈
    trail_pct:        float   # 回撤多少触发
    breakeven_pct:    float   # 移至保本线
    # 入场
    min_factor_score: float
    min_confidence:   float
    max_positions:    int
    # 信号偏好
    prefer_volume_surge:  bool  # 是否偏好放量异动
    prefer_pullback:      bool  # 是否偏好回调入场
    # 描述
    description:      str


# ── 三种预设 ────────────────────────────────────────────

SHORT_TERM_CONFIG = StyleConfig(
    style            = TradingStyle.SHORT_TERM,
    name_cn          = "短线",
    max_holding_days = 5,
    min_holding_days = 1,
    min_stop_pct     = 0.03,
    max_stop_pct     = 0.05,
    atr_stop_mult    = 1.5,
    target_lookback  = 10,    # 看近10日高点，目标更近
    target_buffer    = 0.01,
    min_rr_ratio     = 1.5,
    trail_activation = 0.04,  # 浮盈4%激活（更敏感）
    trail_pct        = 0.02,  # 回撤2%出场（更紧）
    breakeven_pct    = 0.02,
    min_factor_score = 50.0,  # 降低因子门槛，更多信号
    min_confidence   = 0.42,
    max_positions    = 3,
    prefer_volume_surge = True,   # 短线偏好放量异动
    prefer_pullback     = False,
    description = "快进快出，追热点/题材/放量异动，止损严格，持仓1-5天",
)

SWING_CONFIG = StyleConfig(
    style            = TradingStyle.SWING,
    name_cn          = "波段",
    max_holding_days = 20,
    min_holding_days = 3,
    min_stop_pct     = 0.05,
    max_stop_pct     = 0.08,
    atr_stop_mult    = 2.0,
    target_lookback  = 30,
    target_buffer    = 0.02,
    min_rr_ratio     = 1.8,
    trail_activation = 0.06,
    trail_pct        = 0.03,
    breakeven_pct    = 0.04,
    min_factor_score = 55.0,
    min_confidence   = 0.45,
    max_positions    = 4,
    prefer_volume_surge = False,
    prefer_pullback     = True,   # 波段偏好回调买入
    description = "趋势突破后回调买入，持仓5-20天，均线+量能共振",
)

MEDIUM_TERM_CONFIG = StyleConfig(
    style            = TradingStyle.MEDIUM_TERM,
    name_cn          = "中线",
    max_holding_days = 60,
    min_holding_days = 5,
    min_stop_pct     = 0.06,
    max_stop_pct     = 0.12,
    atr_stop_mult    = 2.5,
    target_lookback  = 60,
    target_buffer    = 0.03,
    min_rr_ratio     = 2.5,
    trail_activation = 0.10,
    trail_pct        = 0.05,
    breakeven_pct    = 0.06,
    min_factor_score = 62.0,   # 更高因子门槛，质量优先
    min_confidence   = 0.50,
    max_positions    = 3,
    prefer_volume_surge = False,
    prefer_pullback     = True,
    description = "趋势跟踪，持仓20-60天，需要强趋势+高因子分",
)

STYLE_CONFIGS: dict[TradingStyle, StyleConfig] = {
    TradingStyle.SHORT_TERM:  SHORT_TERM_CONFIG,
    TradingStyle.SWING:       SWING_CONFIG,
    TradingStyle.MEDIUM_TERM: MEDIUM_TERM_CONFIG,
}


def get_style_config(style: TradingStyle | str) -> StyleConfig:
    """获取交易风格配置"""
    if isinstance(style, str):
        style = TradingStyle(style)
    return STYLE_CONFIGS[style]
