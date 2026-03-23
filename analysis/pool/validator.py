"""analysis/pool/validator.py — 策略验证引擎（自适应窗口版）"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np
import pandas as pd
from analysis.strategy.ashare_backtester import AShareBacktester
from analysis.strategy.ashare_strategy import AShareStrategy
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class WindowResult:
    window_id:int; symbol:str=""; train_start:str=""; train_end:str=""
    valid_start:str=""; valid_end:str=""
    in_ret:float=0.; in_sharpe:float=0.; in_win_rate:float=0.; in_trades:int=0
    out_ret:float=0.; out_sharpe:float=0.; out_win_rate:float=0.; out_trades:int=0
    @property
    def is_profitable(self) -> bool: return self.out_ret > 0 and self.out_trades > 0

@dataclass
class ValidationResult:
    strategy_id:str; strategy_name:str; n_windows:int
    wf_windows:list[WindowResult] = field(default_factory=list)
    wf_avg_out_ret:float=0.0; wf_avg_out_sharpe:float=0.0
    wf_avg_out_winrate:float=0.0; wf_consistency:float=0.0
    oos_sharpe:float=0.0; oos_ret:float=0.0; oos_win_rate:float=0.0; oos_max_dd:float=0.0
    is_sharpe:float=0.0; is_ret:float=0.0
    tstat:float=0.0; pvalue:float=1.0; bootstrap_ci_lo:float=0.0
    bootstrap_ci_hi:float=0.0; bootstrap_pos_rate:float=0.0
    sharpe_decay:float=0.0; overfit_flag:bool=False
    passed:bool=False; fail_reasons:list[str]=field(default_factory=list)

    def summary(self) -> str:
        status = "✅ 通过" if self.passed else f"❌ 未通过: {'; '.join(self.fail_reasons)}"
        return (
            f"策略 [{self.strategy_id}] {self.strategy_name}\n  {status}\n"
            f"  WF  : {self.n_windows}窗口 一致率={self.wf_consistency:.0%} "
            f"均收益={self.wf_avg_out_ret:+.2f}% Sharpe={self.wf_avg_out_sharpe:.2f}\n"
            f"  OOS : Sharpe={self.oos_sharpe:.2f} 收益={self.oos_ret:+.2f}% "
            f"胜率={self.oos_win_rate:.0%} DD={self.oos_max_dd:.2f}%\n"
            f"  统计: t={self.tstat:.2f} p={self.pvalue:.3f} "
            f"CI=[{self.bootstrap_ci_lo:.2f}%,{self.bootstrap_ci_hi:.2f}%]\n"
            f"  过拟: IS={self.is_sharpe:.2f} OOS={self.oos_sharpe:.2f} 衰减={self.sharpe_decay:.2f}"
        )


class StrategyValidator:
    """策略验证引擎 — 自适应窗口，防零交易误判"""

    def __init__(
        self,
        train_days:int=200, valid_days:int=130, step_days:int=50,
        max_symbols:int=5, min_windows:int=3,
        oos_ratio:float=0.30,
        n_bootstrap:int=2000, alpha:float=0.10,
        min_oos_sharpe:float=0.3, min_win_rate:float=0.38,
        max_sharpe_decay:float=1.0, min_consistency:float=0.50,
        min_trades:int=5,
    ):
        self.train_days=train_days; self.valid_days=valid_days; self.step_days=step_days
        self.max_symbols=max_symbols; self.min_windows=min_windows; self.oos_ratio=oos_ratio
        self.n_bootstrap=n_bootstrap; self.alpha=alpha
        self.min_oos_sharpe=min_oos_sharpe; self.min_win_rate=min_win_rate
        self.max_sharpe_decay=max_sharpe_decay; self.min_consistency=min_consistency
        self.min_trades=min_trades

    def validate(self, strategy_id:str, name:str, strategy_factory:Callable[[], AShareStrategy],
                 symbol_dfs:dict[str,pd.DataFrame], primary_symbol:str|None=None) -> ValidationResult:
        logger.info(f"开始验证: [{strategy_id}] {name}")
        if primary_symbol is None:
            primary_symbol = max(symbol_dfs, key=lambda s: len(symbol_dfs[s]))
        df = symbol_dfs[primary_symbol].sort_values("date").reset_index(drop=True)
        n  = len(df)
        need = self.train_days + self.valid_days
        if n < need:
            return self._fail(strategy_id, name, [f"数据不足({n}<{need})"])

        result = ValidationResult(strategy_id=strategy_id, strategy_name=name, n_windows=0)

        # 1. Walk-Forward（多股聚合，提升统计可靠性）
        wf_syms = sorted(symbol_dfs, key=lambda s: len(symbol_dfs[s]), reverse=True)[:self.max_symbols]
        all_windows = []
        for sym in wf_syms:
            sym_df = symbol_dfs[sym].sort_values("date").reset_index(drop=True)
            if len(sym_df) >= need:
                all_windows.extend(self._walk_forward_single(strategy_factory, sym, sym_df))

        result.wf_windows = all_windows; result.n_windows = len(all_windows)
        valid_w    = [w for w in all_windows if w.out_trades >= 2]
        profitable = [w for w in valid_w if w.is_profitable]
        result.wf_consistency = len(profitable)/len(valid_w) if valid_w else 0.0
        if valid_w:
            result.wf_avg_out_ret     = float(np.mean([w.out_ret     for w in valid_w]))
            result.wf_avg_out_sharpe  = float(np.mean([w.out_sharpe  for w in valid_w]))
            result.wf_avg_out_winrate = float(np.mean([w.out_win_rate for w in valid_w]))

        if result.n_windows < self.min_windows:
            return self._fail(strategy_id, name, [f"窗口数不足({result.n_windows}<{self.min_windows})"])

        # 2. OOS
        oos_r = self._oos_test(strategy_factory, primary_symbol, df)
        result.oos_sharpe=oos_r["oos_sharpe"]; result.oos_ret=oos_r["oos_ret"]
        result.oos_win_rate=oos_r["oos_win_rate"]; result.oos_max_dd=oos_r["oos_max_dd"]
        result.is_sharpe=oos_r["is_sharpe"]; result.is_ret=oos_r["is_ret"]
        result.sharpe_decay = result.is_sharpe - result.oos_sharpe
        result.overfit_flag = result.sharpe_decay > self.max_sharpe_decay

        # 3. 统计检验
        oos_rets = oos_r.get("oos_daily_rets", [])
        if len(oos_rets) >= 10:
            st = self._statistical_test(np.array(oos_rets))
            result.tstat=st["tstat"]; result.pvalue=st["pvalue"]
            result.bootstrap_ci_lo=st["ci_lo"]; result.bootstrap_ci_hi=st["ci_hi"]
            result.bootstrap_pos_rate=st["pos_rate"]

        self._judge(result)
        logger.info(f"验证完成 [{strategy_id}]: {'通过' if result.passed else '未通过'} "
                    f"OOS Sharpe={result.oos_sharpe:.2f} trades={oos_r.get('oos_trades',0)}")
        return result

    def _walk_forward_single(self, factory, symbol, df):
        windows, wid, i = [], 0, 0; n = len(df)
        while i + self.train_days + self.valid_days <= n:
            tr = df.iloc[i:i+self.train_days]
            va = df.iloc[i+self.train_days:i+self.train_days+self.valid_days]
            ir  = self._run_backtest(factory, symbol, tr)
            or_ = self._run_backtest(factory, symbol, va)
            windows.append(WindowResult(
                window_id=wid, symbol=symbol,
                train_start=str(tr["date"].iloc[0]), train_end=str(tr["date"].iloc[-1]),
                valid_start=str(va["date"].iloc[0]), valid_end=str(va["date"].iloc[-1]),
                in_ret=ir["ret"], in_sharpe=ir["sharpe"], in_win_rate=ir["win_rate"], in_trades=ir["trades"],
                out_ret=or_["ret"], out_sharpe=or_["sharpe"], out_win_rate=or_["win_rate"], out_trades=or_["trades"],
            ))
            i += self.step_days; wid += 1
        return windows

    def _oos_test(self, factory, symbol, df):
        sp = int(len(df)*(1-self.oos_ratio))
        is_r = self._run_backtest(factory, symbol, df.iloc[:sp])
        oo_r = self._run_backtest(factory, symbol, df.iloc[sp:])
        return {
            "is_sharpe":is_r["sharpe"], "is_ret":is_r["ret"],
            "oos_sharpe":oo_r["sharpe"], "oos_ret":oo_r["ret"],
            "oos_win_rate":oo_r["win_rate"], "oos_max_dd":oo_r["max_dd"],
            "oos_trades":oo_r["trades"], "oos_daily_rets":oo_r["daily_rets"],
        }

    def _statistical_test(self, rets:np.ndarray) -> dict:
        n=len(rets); mu=float(np.mean(rets)); se=float(np.std(rets,ddof=1))/np.sqrt(n)
        tstat = mu/(se+1e-10)
        try:
            from scipy import stats as sc
            pvalue = float(sc.t.sf(tstat, df=n-1))
        except Exception:
            pvalue = float(max(0, 0.5*(1-np.tanh(tstat/np.sqrt(2)))))
        rng = np.random.default_rng(42)
        boot = np.array([float(np.mean(rng.choice(rets,size=n,replace=True))) for _ in range(self.n_bootstrap)])
        ann = 252*100
        return {"tstat":round(tstat,4),"pvalue":round(pvalue,4),
                "ci_lo":round(float(np.percentile(boot,5))*ann,2),
                "ci_hi":round(float(np.percentile(boot,95))*ann,2),
                "pos_rate":round(float(np.mean(boot>0)),3)}

    def _run_backtest(self, factory, symbol, df) -> dict:
        try:
            bt = AShareBacktester(strategy=factory())
            r  = bt.run(symbol, df)
            daily_rets: list[float] = []
            if r.equity_curve and len(r.equity_curve) >= 2:
                eq = [e["total"] for e in r.equity_curve]
                daily_rets = list(np.diff(eq)/np.maximum(eq[:-1], 1e-8))
            sharpe = r.sharpe_ratio if r.total_trades > 0 else 0.0
            return {"ret":r.total_return_pct, "sharpe":sharpe,
                    "win_rate":r.win_rate if r.total_trades>0 else 0.0,
                    "max_dd":r.max_drawdown_pct, "trades":r.total_trades, "daily_rets":daily_rets}
        except Exception as e:
            logger.debug(f"回测失败 {symbol}: {e}")
            return {"ret":0.0,"sharpe":0.0,"win_rate":0.0,"max_dd":0.0,"trades":0,"daily_rets":[]}

    def _judge(self, result:ValidationResult) -> None:
        fails = []
        oos_trades = sum(w.out_trades for w in result.wf_windows)
        if result.oos_sharpe < self.min_oos_sharpe:
            fails.append(f"OOS_Sharpe={result.oos_sharpe:.2f}<{self.min_oos_sharpe}")
        if result.oos_win_rate < self.min_win_rate and oos_trades >= self.min_trades:
            fails.append(f"OOS胜率={result.oos_win_rate:.0%}<{self.min_win_rate:.0%}")
        if result.pvalue > self.alpha and result.pvalue < 1.0 and oos_trades >= self.min_trades:
            fails.append(f"p={result.pvalue:.3f}>{self.alpha}")
        if result.overfit_flag:
            fails.append(f"过拟合衰减={result.sharpe_decay:.2f}>{self.max_sharpe_decay}")
        valid_w = [w for w in result.wf_windows if w.out_trades >= 2]
        if len(valid_w) >= self.min_windows and result.wf_consistency < self.min_consistency:
            fails.append(f"WF一致率={result.wf_consistency:.0%}<{self.min_consistency:.0%}")
        if oos_trades < self.min_trades:
            fails.append(f"OOS交易{oos_trades}笔<{self.min_trades}")
        result.fail_reasons = fails
        result.passed = len(fails) == 0

    def _fail(self, sid, name, reasons):
        r = ValidationResult(strategy_id=sid, strategy_name=name, n_windows=0)
        r.fail_reasons=reasons; r.passed=False; return r
