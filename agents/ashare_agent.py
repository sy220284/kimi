"""
agents/ashare_agent.py

A股智能分析Agent（新系统统一入口）

整合四层架构：
  Layer 1  数据层（复用现有 OptimizedDataManager）
  Layer 2  市场状态识别（AShareMarketRegime）
  Layer 3  多因子选股（AShareMultiFactor）
  Layer 4  信号生成与仓位决策（AShareStrategy）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from analysis.regime.market_regime import (
    AShareMarketRegime, MarketRegime, RegimeResult, REGIME_MAX_POSITION
)
from analysis.factors.multi_factor import AShareMultiFactor, FactorScore
from analysis.strategy.ashare_strategy import AShareStrategy, AShareSignal
from analysis.technical.indicators import TechnicalIndicators
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AShareAnalysis:
    """单次分析结果"""
    symbol:        str
    date:          str
    price:         float
    # Layer 2
    regime:        RegimeResult
    # Layer 3
    factor_score:  FactorScore
    # Layer 4
    signal:        AShareSignal | None
    # 综合建议
    action:        str           # BUY / HOLD / WATCH / AVOID
    reason:        str
    confidence:    float
    detail:        dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        sig_str = ""
        if self.signal:
            sig_str = (f" | 入场¥{self.signal.entry_price:.2f} "
                       f"止损¥{self.signal.stop_loss:.2f} "
                       f"目标¥{self.signal.target_price:.2f} "
                       f"仓位{self.signal.position_pct:.0%}")
        return (f"[{self.date}] {self.symbol} ¥{self.price:.2f} "
                f"→ {self.action} | {self.regime.label} "
                f"| 因子{self.factor_score.total_score:.0f}分[{self.factor_score.grade}]"
                f"{sig_str}")


class AShareAgent:
    """
    A股智能分析Agent

    用法::

        agent = AShareAgent()
        # 分析单只股票
        result = agent.analyze("600519", df)
        print(result.summary)

        # 批量扫描选股
        candidates = agent.scan(symbol_dfs, top_n=10)

        # 市场状态判断
        regime = agent.market_regime(market_df)
    """

    def __init__(
        self,
        strategy: AShareStrategy | None = None,
        min_factor_score: float = 55.0,
        regime_min_confidence: float = 0.50,
    ):
        self.strategy              = strategy or AShareStrategy()
        self.min_factor_score      = min_factor_score
        self.regime_min_confidence = regime_min_confidence
        self._regime_detector = AShareMarketRegime()
        self._factor_engine   = AShareMultiFactor()
        self._ti              = TechnicalIndicators()

    # ─────────────────────────────────────────────
    # 核心接口
    # ─────────────────────────────────────────────

    def analyze(
        self,
        symbol: str,
        df: pd.DataFrame,
        market_df: pd.DataFrame | None = None,
    ) -> AShareAnalysis:
        """
        对单只股票进行完整分析。

        Args:
            symbol:    股票代码
            df:        该股 OHLCV DataFrame
            market_df: 市场指数 DataFrame（可选，用于更精准的市场状态）

        Returns:
            AShareAnalysis
        """
        if len(df) < 60:
            return self._empty_analysis(symbol, df)

        # 技术指标
        try:
            df = self._ti.calculate_all(df.copy())
        except Exception:
            df = df.copy()

        df = df.sort_values("date").reset_index(drop=True)
        date  = str(df["date"].iloc[-1])
        price = float(df["close"].iloc[-1])

        # Layer 2：市场状态（优先用市场指数，fallback用个股）
        regime_df = market_df if market_df is not None and len(market_df) >= 60 else df
        regime = self._regime_detector.detect(regime_df)

        # Layer 3：多因子评分
        fscore = self._factor_engine.score(symbol, df)

        # Layer 4：信号生成
        signal = None
        if fscore.passed_filter and regime.is_tradeable:
            signal = self.strategy.generate_signal(symbol, df, fscore, regime)

        # 综合决策
        action, reason, conf = self._decide(regime, fscore, signal)

        return AShareAnalysis(
            symbol=symbol, date=date, price=price,
            regime=regime, factor_score=fscore, signal=signal,
            action=action, reason=reason, confidence=conf,
            detail={
                "regime_signals":  regime.signals,
                "factor_signals":  fscore.signals,
            },
        )

    def scan(
        self,
        symbol_dfs: dict[str, pd.DataFrame],
        market_df: pd.DataFrame | None = None,
        top_n: int = 10,
        min_grade: str = "B",
    ) -> list[AShareAnalysis]:
        """
        批量扫描选股，返回 top_n 只最优标的。
        """
        results = []
        for sym, df in symbol_dfs.items():
            try:
                r = self.analyze(sym, df, market_df)
                if r.action in ("BUY", "WATCH") and r.factor_score.grade >= min_grade:
                    results.append(r)
            except Exception as e:
                logger.debug(f"scan {sym} error: {e}")

        results.sort(key=lambda r: (
            r.signal.confidence if r.signal else 0,
            r.factor_score.total_score
        ), reverse=True)
        return results[:top_n]

    def market_regime(self, market_df: pd.DataFrame) -> RegimeResult:
        """直接返回市场状态"""
        return self._regime_detector.detect(market_df)

    def factor_scan(
        self,
        symbol_dfs: dict[str, pd.DataFrame],
        top_n: int = 20,
    ) -> list[FactorScore]:
        """仅运行多因子筛选，不生成交易信号"""
        scores = self._factor_engine.score_batch(symbol_dfs)
        return scores[:top_n]

    # ─────────────────────────────────────────────
    # 综合决策逻辑
    # ─────────────────────────────────────────────

    def _decide(
        self,
        regime: RegimeResult,
        fscore: FactorScore,
        signal: AShareSignal | None,
    ) -> tuple[str, str, float]:
        """将三层分析合成最终动作建议"""

        # 系统性风险：无论个股多好，空仓
        if regime.regime == MarketRegime.SYSTEMIC_RISK:
            return "AVOID", f"系统性风险，建议空仓（{regime.description}）", 0.9

        # 个股过滤未通过
        if not fscore.passed_filter:
            return "AVOID", f"多因子过滤: {fscore.filter_reason}", 0.8

        # 有有效交易信号
        if signal and signal.is_valid:
            reason = (
                f"因子{fscore.total_score:.0f}分[{fscore.grade}] "
                f"+ {regime.label} "
                f"+ {signal.signal_type.value} "
                f"盈亏比{signal.rr_ratio:.1f}x"
            )
            return "BUY", reason, signal.confidence

        # 因子分不错但无信号（等待时机）
        if fscore.total_score >= self.min_factor_score and regime.is_tradeable:
            reason = (
                f"因子{fscore.total_score:.0f}分[{fscore.grade}] "
                f"市场{regime.label}，等待入场时机"
            )
            return "WATCH", reason, 0.55

        # 因子分中等
        if fscore.total_score >= 45:
            return "HOLD", f"因子{fscore.total_score:.0f}分[{fscore.grade}]，持观望", 0.4

        return "AVOID", f"因子分过低({fscore.total_score:.0f})", 0.7

    def _empty_analysis(self, symbol: str, df: pd.DataFrame) -> AShareAnalysis:
        from analysis.regime.market_regime import RegimeResult, MarketRegime
        from analysis.factors.multi_factor import FactorScore
        dummy_regime = RegimeResult(
            regime=MarketRegime.STRUCTURAL, confidence=0.0,
            max_position=0.0, max_positions=0,
            description="数据不足")
        dummy_factor = FactorScore(symbol=symbol, total_score=0,
                                   passed_filter=False, filter_reason="数据不足")
        date = str(df["date"].iloc[-1]) if df is not None and len(df) > 0 else ""
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
        return AShareAnalysis(
            symbol=symbol, date=date, price=price,
            regime=dummy_regime, factor_score=dummy_factor, signal=None,
            action="AVOID", reason="数据不足", confidence=0.0)

    # ─────────────────────────────────────────────
    # 报告输出
    # ─────────────────────────────────────────────

    def report(self, analyses: list[AShareAnalysis]) -> str:
        lines = [
            "", "=" * 65,
            "  A股智能选股报告",
            "=" * 65,
        ]
        buy   = [a for a in analyses if a.action == "BUY"]
        watch = [a for a in analyses if a.action == "WATCH"]

        if buy:
            lines.append("\n【建议买入】")
            for a in buy:
                lines.append(f"  {a.summary}")
        if watch:
            lines.append("\n【观察候选】")
            for a in watch[:5]:
                lines.append(f"  {a.summary}")

        # 市场状态汇总
        if analyses:
            regimes = [a.regime.regime.value for a in analyses]
            from collections import Counter
            rc = Counter(regimes)
            lines.append(f"\n市场状态分布: {dict(rc)}")

        lines.append("=" * 65)
        return "\n".join(lines)
