"""
analysis/strategy/ashare_batch.py

A股新策略批量回测引擎
"""
from __future__ import annotations

import copy
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from analysis.strategy.ashare_strategy import AShareStrategy
from analysis.strategy.ashare_backtester import AShareBacktester, AShareBacktestResult


@dataclass
class AShareSingleResult:
    symbol: str
    status: str          # ok / skip / error
    error:  str = ""
    total_trades: int = 0
    winning_trades: int = 0
    win_rate: float = 0.0
    total_return_pct: float = 0.0
    avg_return_per_trade: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    # 新策略特有统计
    target_reached_pct:  float = 0.0  # 目标止盈占比
    trailing_stop_pct:   float = 0.0  # 移动止盈占比
    time_stop_pct:       float = 0.0  # 时间止损占比
    hard_stop_pct:       float = 0.0  # 固定止损占比
    momentum_pct:        float = 0.0  # 动量信号占比
    pullback_pct:        float = 0.0  # 回调信号占比
    data_rows:  int   = 0
    elapsed_sec:float = 0.0


@dataclass
class AShareBatchSummary:
    run_time:    str = ""
    strategy_desc: str = ""
    symbols_total:   int = 0
    symbols_ok:      int = 0
    symbols_skipped: int = 0
    symbols_error:   int = 0
    # 核心指标
    avg_win_rate:      float = 0.0
    avg_return_pct:    float = 0.0
    median_return_pct: float = 0.0
    avg_drawdown_pct:  float = 0.0
    avg_sharpe:        float = 0.0
    avg_calmar:        float = 0.0
    avg_profit_factor: float = 0.0
    # 盈亏分布
    profitable_symbols: int   = 0
    profitable_pct:     float = 0.0
    best_symbol:  str   = ""
    best_return:  float = 0.0
    worst_symbol: str   = ""
    worst_return: float = 0.0
    # 新策略特有
    avg_target_reached_pct: float = 0.0  # 目标止盈率（关键指标，旧策略=0%）
    avg_hard_stop_pct:      float = 0.0
    total_trades:           int   = 0
    elapsed_sec:            float = 0.0


class AShareBatchBacktester:
    """A股新策略批量回测"""

    def __init__(
        self,
        strategy: AShareStrategy | None = None,
        max_workers: int = 4,
        reanalyze_every: int = 5,
        min_data_rows: int = 130,
        progress_callback: Callable | None = None,
    ):
        self.strategy_template = strategy or AShareStrategy()
        self.max_workers       = max_workers
        self.reanalyze_every   = reanalyze_every
        self.min_data_rows     = min_data_rows
        self.progress_callback = progress_callback
        self._results: list[AShareSingleResult] = []
        self._summary: AShareBatchSummary | None = None
        self._trade_details: list[dict] = []

    def _run_one(self, symbol: str, df: pd.DataFrame) -> AShareSingleResult:
        t0 = time.time()
        try:
            strategy = copy.deepcopy(self.strategy_template)
            bt = AShareBacktester(
                strategy=strategy,
                reanalyze_every=self.reanalyze_every,
                min_data_rows=self.min_data_rows,
            )
            r: AShareBacktestResult = bt.run(symbol, df)
            elapsed = time.time() - t0

            # 计算各退出原因占比
            total_ex = r.total_trades or 1
            ex = r.exit_reason_counts
            sg = r.signal_type_counts

            return AShareSingleResult(
                symbol=symbol, status="ok",
                total_trades=r.total_trades,
                winning_trades=r.winning_trades,
                win_rate=r.win_rate,
                total_return_pct=r.total_return_pct,
                avg_return_per_trade=r.avg_return_per_trade,
                max_drawdown_pct=r.max_drawdown_pct,
                sharpe_ratio=r.sharpe_ratio,
                sortino_ratio=r.sortino_ratio,
                calmar_ratio=r.calmar_ratio,
                profit_factor=min(r.profit_factor, 999.99),
                target_reached_pct=ex.get("target_reached", 0) / total_ex * 100,
                trailing_stop_pct= ex.get("trailing_stop", 0) / total_ex * 100,
                time_stop_pct=     ex.get("time_stop", 0)     / total_ex * 100,
                hard_stop_pct=     ex.get("stop_loss", 0)     / total_ex * 100,
                momentum_pct=      sg.get("momentum_breakout", 0) / total_ex * 100,
                pullback_pct=      sg.get("pullback_entry", 0)    / total_ex * 100,
                data_rows=len(df),
                elapsed_sec=round(elapsed, 2),
            ), r

        except Exception as e:
            return AShareSingleResult(
                symbol=symbol, status="error",
                error=str(e)[:120],
                elapsed_sec=round(time.time() - t0, 2),
            ), None

    def run(
        self,
        symbols: list[str],
        data_loader: Callable | None = None,
    ) -> tuple[AShareBatchSummary, list[AShareSingleResult]]:

        if data_loader is None:
            from data.optimized_data_manager import get_optimized_data_manager
            dm = get_optimized_data_manager(); dm.load_all_data()
            def _loader(sym):
                return dm.get_stock_data(sym)
            data_loader = _loader

        t_start = time.time()
        total = len(symbols)
        done  = 0
        self._results = []
        self._trade_details = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {}
            for sym in symbols:
                df = data_loader(sym)
                if df is None or len(df) < self.min_data_rows:
                    self._results.append(AShareSingleResult(
                        symbol=sym, status="skip", error="数据不足"))
                    done += 1
                    if self.progress_callback:
                        self.progress_callback(done, total, sym)
                    continue
                fut = pool.submit(self._run_one, sym, df)
                future_map[fut] = sym

            for fut in as_completed(future_map):
                sym = future_map[fut]
                try:
                    sr, br = fut.result()
                except Exception as e:
                    sr = AShareSingleResult(symbol=sym, status="error", error=str(e))
                    br = None

                self._results.append(sr)
                if br is not None:
                    for t in br.trades:
                        if t.status == "closed":
                            self._trade_details.append(t.to_dict())
                done += 1
                if self.progress_callback:
                    self.progress_callback(done, total, sym)

        self._summary = self._aggregate(time.time() - t_start)
        return self._summary, self._results

    def _aggregate(self, elapsed: float) -> AShareBatchSummary:
        ok  = [r for r in self._results if r.status == "ok"]
        act = [r for r in ok if r.total_trades > 0]

        def sm(attr): return float(np.mean([getattr(r, attr) for r in act])) if act else 0.0

        rets = [r.total_return_pct for r in act]
        prof = [r for r in act if r.total_return_pct > 0]
        best = max(act, key=lambda r: r.total_return_pct, default=None)
        wrst = min(act, key=lambda r: r.total_return_pct, default=None)

        return AShareBatchSummary(
            run_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            symbols_total=len(self._results),
            symbols_ok=len(ok),
            symbols_skipped=sum(1 for r in self._results if r.status == "skip"),
            symbols_error=sum(1 for r in self._results if r.status == "error"),
            avg_win_rate=sm("win_rate"),
            avg_return_pct=sm("total_return_pct"),
            median_return_pct=float(np.median(rets)) if rets else 0.0,
            avg_drawdown_pct=sm("max_drawdown_pct"),
            avg_sharpe=sm("sharpe_ratio"),
            avg_calmar=sm("calmar_ratio"),
            avg_profit_factor=float(np.mean([min(r.profit_factor, 100) for r in act])) if act else 0.0,
            profitable_symbols=len(prof),
            profitable_pct=len(prof) / len(act) * 100 if act else 0.0,
            best_symbol=best.symbol if best else "",
            best_return=best.total_return_pct if best else 0.0,
            worst_symbol=wrst.symbol if wrst else "",
            worst_return=wrst.total_return_pct if wrst else 0.0,
            avg_target_reached_pct=sm("target_reached_pct"),
            avg_hard_stop_pct=sm("hard_stop_pct"),
            total_trades=sum(r.total_trades for r in act),
            elapsed_sec=round(elapsed, 1),
        )

    def report(self) -> str:
        s = self._summary
        if not s: return "尚未运行"
        lines = [
            "", "=" * 60,
            f"  📊 A股新策略批量回测  {s.run_time}",
            "=" * 60,
            f"  股票: {s.symbols_total}只  成功: {s.symbols_ok}  错误: {s.symbols_error}",
            "",
            "【整体表现】",
            f"  盈利股票: {s.profitable_symbols}/{s.symbols_ok} ({s.profitable_pct:.1f}%)",
            f"  均收益: {s.avg_return_pct:+.2f}%   中位数: {s.median_return_pct:+.2f}%",
            f"  均胜率: {s.avg_win_rate:.1%}   均回撤: {s.avg_drawdown_pct:.2f}%",
            f"  Sharpe: {s.avg_sharpe:.2f}   Calmar: {s.avg_calmar:.2f}",
            "",
            "【关键改进指标（对比旧波浪策略）】",
            f"  ✅ 目标止盈触达率: {s.avg_target_reached_pct:.1f}%  (旧策略: 0%)",
            f"  硬止损率:  {s.avg_hard_stop_pct:.1f}%",
            "",
            f"  总交易笔数: {s.total_trades}   耗时: {s.elapsed_sec:.0f}s",
            "=" * 60,
        ]
        return "\n".join(lines)

    def report_detail(self, top_n: int = 20) -> str:
        act = sorted(
            [r for r in self._results if r.status == "ok" and r.total_trades > 0],
            key=lambda r: r.total_return_pct, reverse=True,
        )
        hdr = f"\n{'代码':<10} {'交易':<5} {'胜率':<7} {'收益%':<9} {'回撤%':<8} {'Sharpe':<8} {'目标止盈%'}"
        sep = "-" * 60
        rows = [hdr, sep]
        for r in act[:top_n]:
            rows.append(
                f"{r.symbol:<10} {r.total_trades:<5} {r.win_rate:>6.1%} "
                f"{r.total_return_pct:>+8.2f}% {r.max_drawdown_pct:>7.2f}% "
                f"{r.sharpe_ratio:>7.2f}   {r.target_reached_pct:>7.1f}%"
            )
        return "\n".join(rows)

    def save_results(self, output_dir: str = "results") -> dict[str, str]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths = {}
        if self._summary:
            p = os.path.join(output_dir, f"ashare_summary_{ts}.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(asdict(self._summary), f, ensure_ascii=False, indent=2)
            paths["summary"] = p
        if self._results:
            p = os.path.join(output_dir, f"ashare_results_{ts}.csv")
            pd.DataFrame([asdict(r) for r in self._results]).to_csv(p, index=False, encoding="utf-8-sig")
            paths["results"] = p
        if self._trade_details:
            p = os.path.join(output_dir, f"ashare_trades_{ts}.csv")
            pd.DataFrame(self._trade_details).to_csv(p, index=False, encoding="utf-8-sig")
            paths["trades"] = p
        p = os.path.join(output_dir, f"ashare_report_{ts}.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.report() + "\n" + self.report_detail(50))
        paths["report"] = p
        return paths
