"""
批量回测引擎 — analysis/backtest/batch_backtester.py

功能:
  - 并行回测多只股票（ThreadPoolExecutor）
  - 聚合统计：胜率/收益/夏普/回撤/卡玛
  - 按信号类型/退出原因细分分析
  - 资金曲线合并（等权重组合模拟）
  - CSV + JSON 结果持久化
  - 进度回调支持
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from analysis.backtest.wave_backtester import (
    BacktestResult,
    WaveBacktester,
    WaveStrategy,
)
from analysis.technical.indicators import TechnicalIndicators
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from utils.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class SingleResult:
    """单只股票回测结果（压缩版，供聚合用）"""
    symbol: str
    status: str          # "ok" | "skip" | "error"
    error: str = ""
    # 基础指标
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    avg_return_per_trade: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    # 信号类型分布
    entry_c: int = 0     # C浪信号
    entry_2: int = 0     # 2浪信号
    entry_4: int = 0     # 4浪信号
    # 退出原因分布
    exit_stop_loss: int = 0
    exit_trailing_stop: int = 0
    exit_time_stop: int = 0
    exit_target: int = 0
    exit_other: int = 0
    # 持仓天数
    avg_holding_days: float = 0.0
    # 数据信息
    data_rows: int = 0
    elapsed_sec: float = 0.0


@dataclass
class BatchSummary:
    """批量回测汇总统计"""
    run_time: str = ""
    strategy_desc: str = ""
    symbols_total: int = 0
    symbols_ok: int = 0
    symbols_skipped: int = 0
    symbols_error: int = 0
    # 整体指标（有交易的股票）
    avg_win_rate: float = 0.0
    avg_return_pct: float = 0.0
    avg_drawdown_pct: float = 0.0
    avg_sharpe: float = 0.0
    avg_sortino: float = 0.0
    avg_calmar: float = 0.0
    avg_profit_factor: float = 0.0
    median_return_pct: float = 0.0
    # 盈亏分布
    profitable_symbols: int = 0
    profitable_pct: float = 0.0
    best_symbol: str = ""
    best_return: float = 0.0
    worst_symbol: str = ""
    worst_return: float = 0.0
    # 交易汇总
    total_trades: int = 0
    avg_trades_per_symbol: float = 0.0
    # 信号类型
    entry_c_total: int = 0
    entry_2_total: int = 0
    entry_4_total: int = 0
    # 退出原因
    exit_stop_loss_pct: float = 0.0
    exit_trailing_pct: float = 0.0
    exit_time_pct: float = 0.0
    exit_target_pct: float = 0.0
    # 性能
    total_elapsed_sec: float = 0.0
    avg_elapsed_per_symbol: float = 0.0


# ─────────────────────────────────────────────
# 批量回测引擎
# ─────────────────────────────────────────────

class BatchBacktester:
    """
    批量回测引擎

    用法::

        from analysis.backtest.batch_backtester import BatchBacktester, BatchConfig
        from analysis.backtest.wave_backtester import WaveStrategy

        strategy = WaveStrategy(
            initial_capital=100_000,
            stop_loss_pct=0.05,
            use_kelly=True,
        )
        config = BatchConfig(
            start_date="2020-01-01",
            end_date="2023-12-31",
            min_rows=200,
            max_workers=4,
            reanalyze_every=5,
        )
        bt = BatchBacktester(strategy=strategy, config=config)
        summary, results = bt.run(symbols)
        bt.save_results("results/")
    """

    def __init__(
        self,
        strategy: WaveStrategy | None = None,
        config: "BatchConfig | None" = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ):
        self.strategy_template = strategy or WaveStrategy()
        self.config = config or BatchConfig()
        self.progress_callback = progress_callback
        self._ti = TechnicalIndicators()
        self._summary: BatchSummary | None = None
        self._results: list[SingleResult] = []
        self._trade_details: list[dict] = []
        self._equity_curves: dict[str, list[dict]] = {}

    # ── 单股回测 ──────────────────────────────

    def _run_one(self, symbol: str, df: pd.DataFrame) -> SingleResult:
        t0 = time.time()
        try:
            if len(df) < self.config.min_rows:
                return SingleResult(symbol=symbol, status="skip",
                                    error=f"数据不足{len(df)}行<{self.config.min_rows}",
                                    data_rows=len(df))

            # 计算技术指标
            df = self._ti.calculate_all(df.copy())

            # 每次独立 strategy 防状态污染（WaveStrategy 非 dataclass，用 deepcopy）
            import copy
            strategy = copy.deepcopy(self.strategy_template)
            strategy.reset()

            bt = WaveBacktester(strategy=strategy)
            result: BacktestResult = bt.run(
                symbol, df,
                reanalyze_every=self.config.reanalyze_every
            )
            elapsed = time.time() - t0

            # 统计信号类型
            entry_c = entry_2 = entry_4 = 0
            exit_sl = exit_ts = exit_time = exit_tgt = exit_other = 0
            holding_days_list = []

            for t in result.trades:
                if t.status == "closed":
                    ew = (t.entry_wave or "").upper()
                    if ew == "C":   entry_c += 1
                    elif ew == "2": entry_2 += 1
                    elif ew == "4": entry_4 += 1

                    er = (t.exit_reason or "").lower()
                    if "stop_loss" in er:      exit_sl += 1
                    elif "trailing" in er:     exit_ts += 1
                    elif "time" in er:         exit_time += 1
                    elif "target" in er:       exit_tgt += 1
                    else:                      exit_other += 1

                    td = t.to_dict()
                    if td.get("holding_days"):
                        holding_days_list.append(td["holding_days"])

            avg_hd = float(np.mean(holding_days_list)) if holding_days_list else 0.0

            return SingleResult(
                symbol=symbol, status="ok",
                total_trades=result.total_trades,
                winning_trades=result.winning_trades,
                losing_trades=result.losing_trades,
                win_rate=result.win_rate,
                total_return_pct=result.total_return_pct,
                avg_return_per_trade=result.avg_return_per_trade,
                max_drawdown_pct=result.max_drawdown_pct,
                sharpe_ratio=result.sharpe_ratio,
                sortino_ratio=result.sortino_ratio,
                calmar_ratio=result.calmar_ratio,
                profit_factor=min(result.profit_factor, 999.99),
                entry_c=entry_c, entry_2=entry_2, entry_4=entry_4,
                exit_stop_loss=exit_sl, exit_trailing_stop=exit_ts,
                exit_time_stop=exit_time, exit_target=exit_tgt,
                exit_other=exit_other,
                avg_holding_days=avg_hd,
                data_rows=len(df), elapsed_sec=round(elapsed, 2),
            ), result

        except Exception as e:
            logger.error(f"回测 {symbol} 失败: {e}", exc_info=True)
            return SingleResult(symbol=symbol, status="error",
                                error=str(e)[:120],
                                elapsed_sec=round(time.time()-t0, 2)), None

    # ── 主入口 ────────────────────────────────

    def run(
        self,
        symbols: list[str],
        data_loader: Callable[[str], pd.DataFrame | None] | None = None,
    ) -> tuple[BatchSummary, list[SingleResult]]:
        """
        并行批量回测。

        Args:
            symbols:     股票代码列表
            data_loader: 自定义数据加载函数 symbol→DataFrame
                         默认使用 OptimizedDataManager

        Returns:
            (BatchSummary, list[SingleResult])
        """
        if data_loader is None:
            from data.optimized_data_manager import get_optimized_data_manager
            dm = get_optimized_data_manager()
            dm.load_all_data()

            def _default_loader(sym: str) -> pd.DataFrame | None:
                df = dm.get_stock_data(sym)
                if df is None or df.empty:
                    return None
                # 日期过滤
                df = df.copy()
                df["date"] = df["date"].astype(str)
                if self.config.start_date:
                    df = df[df["date"] >= self.config.start_date]
                if self.config.end_date:
                    df = df[df["date"] <= self.config.end_date]
                return df if len(df) >= self.config.min_rows else None

            data_loader = _default_loader

        t_start = time.time()
        total = len(symbols)
        done = 0
        self._results = []
        self._trade_details = []
        self._equity_curves = {}

        logger.info(f"批量回测开始: {total}只股票, workers={self.config.max_workers}")

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            future_to_sym = {}
            for sym in symbols:
                df = data_loader(sym)
                if df is None:
                    self._results.append(SingleResult(
                        symbol=sym, status="skip", error="无数据"))
                    done += 1
                    if self.progress_callback:
                        self.progress_callback(done, total, sym)
                    continue
                fut = pool.submit(self._run_one, sym, df)
                future_to_sym[fut] = sym

            for fut in as_completed(future_to_sym):
                sym = future_to_sym[fut]
                try:
                    single_result, bt_result = fut.result()
                except Exception as e:
                    single_result = SingleResult(symbol=sym, status="error", error=str(e))
                    bt_result = None

                self._results.append(single_result)

                if bt_result is not None:
                    # 保留交易明细
                    for t in bt_result.trades:
                        if t.status == "closed":
                            self._trade_details.append(t.to_dict())
                    # 保留权益曲线
                    if self.config.save_equity_curves:
                        self._equity_curves[sym] = bt_result.equity_curve

                done += 1
                if self.progress_callback:
                    self.progress_callback(done, total, sym)
                logger.info(
                    f"[{done}/{total}] {sym}: {single_result.status} "
                    f"trades={single_result.total_trades} "
                    f"ret={single_result.total_return_pct:.2f}%"
                )

        self._summary = self._aggregate(time.time() - t_start)
        return self._summary, self._results

    # ── 聚合计算 ──────────────────────────────

    def _aggregate(self, elapsed: float) -> BatchSummary:
        all_r = self._results
        ok = [r for r in all_r if r.status == "ok"]
        with_trades = [r for r in ok if r.total_trades > 0]

        def safe_mean(lst):
            return float(np.mean(lst)) if lst else 0.0

        # 退出原因百分比
        total_exits = sum(
            r.exit_stop_loss + r.exit_trailing_stop + r.exit_time_stop
            + r.exit_target + r.exit_other
            for r in with_trades
        )

        def exit_pct(attr):
            if total_exits == 0: return 0.0
            return sum(getattr(r, attr) for r in with_trades) / total_exits * 100

        returns = [r.total_return_pct for r in with_trades]
        profitable = [r for r in with_trades if r.total_return_pct > 0]

        best = max(with_trades, key=lambda r: r.total_return_pct, default=None)
        worst = min(with_trades, key=lambda r: r.total_return_pct, default=None)

        return BatchSummary(
            run_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            strategy_desc=self._describe_strategy(),
            symbols_total=len(all_r),
            symbols_ok=len(ok),
            symbols_skipped=sum(1 for r in all_r if r.status == "skip"),
            symbols_error=sum(1 for r in all_r if r.status == "error"),
            avg_win_rate=safe_mean([r.win_rate for r in with_trades]),
            avg_return_pct=safe_mean(returns),
            avg_drawdown_pct=safe_mean([r.max_drawdown_pct for r in with_trades]),
            avg_sharpe=safe_mean([r.sharpe_ratio for r in with_trades]),
            avg_sortino=safe_mean([r.sortino_ratio for r in with_trades]),
            avg_calmar=safe_mean([r.calmar_ratio for r in with_trades]),
            avg_profit_factor=safe_mean([min(r.profit_factor, 100) for r in with_trades]),
            median_return_pct=float(np.median(returns)) if returns else 0.0,
            profitable_symbols=len(profitable),
            profitable_pct=len(profitable) / len(with_trades) * 100 if with_trades else 0.0,
            best_symbol=best.symbol if best else "",
            best_return=best.total_return_pct if best else 0.0,
            worst_symbol=worst.symbol if worst else "",
            worst_return=worst.total_return_pct if worst else 0.0,
            total_trades=sum(r.total_trades for r in with_trades),
            avg_trades_per_symbol=safe_mean([r.total_trades for r in with_trades]),
            entry_c_total=sum(r.entry_c for r in with_trades),
            entry_2_total=sum(r.entry_2 for r in with_trades),
            entry_4_total=sum(r.entry_4 for r in with_trades),
            exit_stop_loss_pct=exit_pct("exit_stop_loss"),
            exit_trailing_pct=exit_pct("exit_trailing_stop"),
            exit_time_pct=exit_pct("exit_time_stop"),
            exit_target_pct=exit_pct("exit_target"),
            total_elapsed_sec=round(elapsed, 1),
            avg_elapsed_per_symbol=round(elapsed / max(len(ok), 1), 2),
        )

    def _describe_strategy(self) -> str:
        s = self.strategy_template
        parts = [
            f"capital={s.initial_capital:,.0f}",
            f"stop={s.stop_loss_pct:.0%}",
            f"kelly={'on' if s.use_kelly else 'off'}",
            f"trailing={'on' if s.use_trailing_stop else 'off'}",
            f"trend_filter={'on' if s.use_trend_filter else 'off'}",
            f"max_hold={s.max_holding_days}d",
        ]
        return " | ".join(parts)

    # ── 报告生成 ──────────────────────────────

    def report(self) -> str:
        """生成文本汇总报告"""
        if self._summary is None:
            return "尚未运行回测，请先调用 run()"

        s = self._summary
        lines = [
            "",
            "=" * 65,
            f"  📊 批量回测报告  {s.run_time}",
            "=" * 65,
            f"  策略: {s.strategy_desc}",
            "",
            "【股票覆盖】",
            f"  总计: {s.symbols_total}只  |  "
            f"成功: {s.symbols_ok}  跳过: {s.symbols_skipped}  错误: {s.symbols_error}",
            "",
            "【整体表现】（有交易的股票）",
            f"  盈利股票: {s.profitable_symbols}/{s.symbols_ok}  ({s.profitable_pct:.1f}%)",
            f"  平均收益: {s.avg_return_pct:+.2f}%   中位数: {s.median_return_pct:+.2f}%",
            f"  平均胜率: {s.avg_win_rate:.1%}",
            f"  平均回撤: {s.avg_drawdown_pct:.2f}%",
            "",
            "【风险指标】",
            f"  Sharpe:  {s.avg_sharpe:.2f}   Sortino: {s.avg_sortino:.2f}",
            f"  Calmar:  {s.avg_calmar:.2f}   盈亏比: {s.avg_profit_factor:.2f}",
            "",
            "【最佳/最差】",
            f"  🥇 最佳: {s.best_symbol}  {s.best_return:+.2f}%",
            f"  🥉 最差: {s.worst_symbol}  {s.worst_return:+.2f}%",
            "",
            "【交易统计】",
            f"  总交易笔数: {s.total_trades}   平均/只: {s.avg_trades_per_symbol:.1f}",
            f"  信号来源 — C浪: {s.entry_c_total}  2浪: {s.entry_2_total}  4浪: {s.entry_4_total}",
            "",
            "【退出原因分布】",
            f"  止损:     {s.exit_stop_loss_pct:.1f}%",
            f"  移动止盈: {s.exit_trailing_pct:.1f}%",
            f"  时间止损: {s.exit_time_pct:.1f}%",
            f"  目标止盈: {s.exit_target_pct:.1f}%",
            "",
            "【性能】",
            f"  总耗时: {s.total_elapsed_sec:.1f}s  "
            f"均耗时/只: {s.avg_elapsed_per_symbol:.2f}s",
            "=" * 65,
        ]
        return "\n".join(lines)

    def report_detail(self, top_n: int = 20) -> str:
        """生成详细的逐股排行"""
        if not self._results:
            return ""
        with_trades = sorted(
            [r for r in self._results if r.status == "ok" and r.total_trades > 0],
            key=lambda r: r.total_return_pct, reverse=True
        )
        header = (
            f"\n{'代码':<10} {'交易':<6} {'胜率':<7} {'收益%':<9} "
            f"{'回撤%':<9} {'Sharpe':<8} {'止损%':<8} 数据行"
        )
        sep = "-" * 65
        rows = [header, sep]
        for r in with_trades[:top_n]:
            sl_pct = r.exit_stop_loss / r.total_trades * 100 if r.total_trades else 0
            rows.append(
                f"{r.symbol:<10} {r.total_trades:<6} {r.win_rate:>6.1%} "
                f"{r.total_return_pct:>+8.2f}% {r.max_drawdown_pct:>8.2f}% "
                f"{r.sharpe_ratio:>7.2f}  {sl_pct:>6.1f}%  {r.data_rows}"
            )
        if with_trades[top_n:]:
            rows.append(f"  ... 还有 {len(with_trades)-top_n} 只")
        return "\n".join(rows)

    # ── 持久化 ────────────────────────────────

    def save_results(self, output_dir: str = "results") -> dict[str, str]:
        """
        保存回测结果到指定目录。

        Returns:
            {"summary_json": path, "results_csv": path, "trades_csv": path}
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = {}

        # 1. 汇总 JSON
        if self._summary:
            summary_path = os.path.join(output_dir, f"batch_summary_{ts}.json")
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self._summary), f, ensure_ascii=False, indent=2)
            paths["summary_json"] = summary_path

        # 2. 逐股结果 CSV
        if self._results:
            results_path = os.path.join(output_dir, f"batch_results_{ts}.csv")
            pd.DataFrame([asdict(r) for r in self._results]).to_csv(
                results_path, index=False, encoding="utf-8-sig"
            )
            paths["results_csv"] = results_path

        # 3. 交易明细 CSV
        if self._trade_details:
            trades_path = os.path.join(output_dir, f"batch_trades_{ts}.csv")
            pd.DataFrame(self._trade_details).to_csv(
                trades_path, index=False, encoding="utf-8-sig"
            )
            paths["trades_csv"] = trades_path

        # 4. 文本报告
        report_path = os.path.join(output_dir, f"batch_report_{ts}.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.report())
            f.write("\n")
            f.write(self.report_detail(top_n=50))
        paths["report_txt"] = report_path

        logger.info(f"结果已保存到 {output_dir}/")
        return paths


# ─────────────────────────────────────────────
# 配置类
# ─────────────────────────────────────────────

@dataclass
class BatchConfig:
    """批量回测配置"""
    start_date: str = ""          # 起始日期，空=不限
    end_date: str = ""            # 截止日期，空=不限
    min_rows: int = 200           # 最少数据行数
    max_workers: int = 4          # 并行线程数
    reanalyze_every: int = 5      # 重新分析频率（交易日）
    save_equity_curves: bool = False  # 是否保留权益曲线（内存占用较大）
