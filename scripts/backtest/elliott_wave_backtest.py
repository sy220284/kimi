#!/usr/bin/env python3
"""
艾略特波浪策略回测框架 (v2 - 主引擎版)

重构说明：
  v1 (792行)：自实现完整波浪识别引擎，与 analysis/wave/ 主引擎并行维护
  v2 (当前)：直接调用 analysis/ 主引擎，消除重复实现，参数通过
             config/wave_params.json 统一管理

功能：
  1. 从数据库获取历史数据
  2. 调用 UnifiedWaveAnalyzer + WaveEntryOptimizer 识别买点信号
  3. 调用 WaveBacktester 事件驱动回测（Kelly仓位/移动止盈/前瞻保护）
  4. 输出绩效指标并可保存到 wave_params.json

使用方式：
    python scripts/backtest/elliott_wave_backtest.py                     # 全库回测
    python scripts/backtest/elliott_wave_backtest.py --symbols 600519 000001
    python scripts/backtest/elliott_wave_backtest.py --save-params       # 保存最优参数
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from analysis.backtest.wave_backtester import WaveBacktester, WaveStrategy
from analysis.wave.entry_optimizer import WaveEntryOptimizer
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data.db_manager import get_db_manager
from utils.param_manager import get_wave_params, update_params_from_backtest


# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_START = '2020-01-01'
DEFAULT_END   = '2025-12-31'
DEFAULT_LIMIT = 50          # 最多回测股票数


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_symbols(limit: int = DEFAULT_LIMIT) -> list[str]:
    """从数据库获取数据量最多的 N 只股票"""
    db = get_db_manager()
    rows = db.pg.execute(
        """SELECT symbol, COUNT(*) AS cnt FROM market_data
           GROUP BY symbol ORDER BY cnt DESC LIMIT %s""",
        (limit,), fetch=True
    )
    return [r['symbol'] for r in (rows or [])]


def load_stock_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    """加载单只股票日线数据"""
    db = get_db_manager()
    rows = db.pg.execute(
        """SELECT date, open, high, low, close, volume, amount
           FROM market_data WHERE symbol=%s AND date>=%s AND date<=%s
           ORDER BY date""",
        (symbol, start, end), fetch=True
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    for col in ['open','high','low','close','volume','amount']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


# ─── Core backtest ────────────────────────────────────────────────────────────

def run_backtest(
    symbols: list[str],
    start: str = DEFAULT_START,
    end:   str = DEFAULT_END,
    initial_capital: float = 100_000,
    use_kelly: bool = True,
) -> dict:
    """
    对给定股票列表执行波浪策略回测

    Returns:
        {
            results: [BacktestResult per symbol],
            summary: {annual_return, max_drawdown, win_rate, sharpe, ...}
        }
    """
    # 共享实例（避免重复加载配置）
    analyzer  = UnifiedWaveAnalyzer()
    optimizer = WaveEntryOptimizer.from_config()
    backtester = WaveBacktester(
        strategy=WaveStrategy(
            initial_capital=initial_capital,
            use_kelly=use_kelly,
        )
    )

    results = []
    failed  = 0

    for i, sym in enumerate(symbols, 1):
        print(f"\r  [{i}/{len(symbols)}] {sym}...", end='', flush=True)
        df = load_stock_data(sym, start, end)
        if df.empty or len(df) < 120:
            continue
        try:
            result = backtester.run(df, sym)
            if result.total_trades > 0:
                results.append(result)
        except Exception as e:
            failed += 1

    print()  # newline

    if not results:
        return {'results': [], 'summary': {}}

    import numpy as np
    import dataclasses
    rets  = [r.total_return_pct for r in results]
    wins  = [r.win_rate          for r in results]
    sharpes = [r.sharpe_ratio    for r in results if r.sharpe_ratio > -9]
    mdd   = [r.max_drawdown_pct  for r in results]
    trades = sum(r.total_trades   for r in results)

    # 汇总（全期资金加权）
    total_capital = initial_capital * len(results)
    weighted_return = float(np.mean(rets)) if rets else 0.0

    # 粗略年化（假设回测区间约5年）
    years = max((datetime.fromisoformat(end) - datetime.fromisoformat(start)).days / 365.25, 1)
    annual = (1 + weighted_return / 100) ** (1 / years) - 1

    summary = {
        'stocks_backtested': len(results),
        'total_trades':      trades,
        'avg_return_pct':    round(weighted_return, 2),
        'annual_return':     round(annual * 100, 2),
        'avg_win_rate':      round(float(np.mean(wins)) * 100, 1),
        'avg_sharpe':        round(float(np.mean(sharpes)), 2) if sharpes else 0,
        'avg_max_drawdown':  round(float(np.mean(mdd)), 2),
        'failed_symbols':    failed,
    }

    print(f"\n  ── 回测汇总 ──")
    print(f"  股票数:   {summary['stocks_backtested']}  交易笔数: {summary['total_trades']}")
    print(f"  均值收益: {summary['avg_return_pct']}%   年化: {summary['annual_return']}%")
    print(f"  平均胜率: {summary['avg_win_rate']}%")
    print(f"  平均Sharpe: {summary['avg_sharpe']}   平均MaxDD: {summary['avg_max_drawdown']}%")

    return {'results': results, 'summary': summary}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='波浪策略回测 (v2, 主引擎)')
    ap.add_argument('--symbols', nargs='+', help='指定股票代码（默认取前50只）')
    ap.add_argument('--start',  default=DEFAULT_START, help=f'开始日期 (default: {DEFAULT_START})')
    ap.add_argument('--end',    default=DEFAULT_END,   help=f'结束日期 (default: {DEFAULT_END})')
    ap.add_argument('--limit',  type=int, default=DEFAULT_LIMIT, help='最多回测股票数')
    ap.add_argument('--capital',type=float, default=100_000, help='初始资金')
    ap.add_argument('--save-params', action='store_true', help='将结果保存到 wave_params.json')
    args = ap.parse_args()

    print("=" * 60)
    print("艾略特波浪策略回测 v2 (主引擎复用版)")
    print("=" * 60)

    symbols = args.symbols or get_symbols(args.limit)
    print(f"回测股票: {len(symbols)}只  期间: {args.start} ~ {args.end}")

    output = run_backtest(
        symbols=symbols, start=args.start, end=args.end,
        initial_capital=args.capital
    )

    if args.save_params and output['summary']:
        s = output['summary']
        update_params_from_backtest({
            'round': 'auto',
            'annual_return': s['annual_return'],
            'max_drawdown':  s['avg_max_drawdown'],
            'win_rate':      s['avg_win_rate'],
            'sharpe_ratio':  s['avg_sharpe'],
            'stocks_count':  s['stocks_backtested'],
            'backtest_period': f"{args.start[:4]}-{args.end[:4]}",
        })
        print(f"\n参数已保存到 config/wave_params.json")

    # 输出 TOP 10
    if output['results']:
        top10 = sorted(output['results'], key=lambda r: r.total_return_pct, reverse=True)[:10]
        print("\n── TOP 10 ──")
        for r in top10:
            print(f"  {r.symbol:8} 收益={r.total_return_pct:7.2f}%  "
                  f"胜率={r.win_rate:.1%}  Sharpe={r.sharpe_ratio:.2f}  "
                  f"DD={r.max_drawdown_pct:.1f}%  交易={r.total_trades}笔")


if __name__ == '__main__':
    main()
