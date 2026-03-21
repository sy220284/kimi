#!/usr/bin/env python3
"""
scripts/backtest/run_ashare.py

A股新策略批量回测脚本

用法:
  python scripts/backtest/run_ashare.py
  python scripts/backtest/run_ashare.py --symbols 600519 000001 --workers 8
  python scripts/backtest/run_ashare.py --capital 200000 --stop 0.06
  python scripts/backtest/run_ashare.py --compare      # 与旧波浪策略对比
"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analysis.strategy.ashare_strategy import AShareStrategy
from analysis.strategy.ashare_batch import AShareBatchBacktester


def parse_args():
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--symbols", nargs="+", default=None)
    p.add_argument("--capital", type=float, default=100_000)
    p.add_argument("--stop",    type=float, default=0.06, help="最大止损%")
    p.add_argument("--workers", type=int,   default=4)
    p.add_argument("--output",  default="results")
    p.add_argument("--compare", action="store_true", help="同时运行旧策略对比")
    p.add_argument("--no-save", action="store_true")
    p.add_argument("--top",     type=int, default=20)
    return p.parse_args()


def get_symbols():
    from utils.db_connector import PostgresConnector
    import os
    pg = PostgresConnector(
        host="localhost", port=5432,
        database=os.environ.get("PG_DATABASE", "quant_analysis"),
        username=os.environ.get("PG_USERNAME", "quant_user"),
        password=os.environ.get("PG_PASSWORD", "quant_password"),
    )
    pg.connect()
    rows = pg.execute("SELECT DISTINCT symbol FROM market_data ORDER BY symbol", fetch=True)
    pg.disconnect()
    return [r["symbol"] for r in rows]


def main():
    args = parse_args()
    symbols = args.symbols or get_symbols()
    print(f"回测股票: {len(symbols)} 只")

    strategy = AShareStrategy(
        initial_capital=args.capital,
        max_stop_pct=args.stop,
    )

    def on_progress(done, total, sym):
        bar = "█" * int(30 * done / total) + "░" * (30 - int(30 * done / total))
        print(f"\r  [{bar}] {done}/{total} {sym:<10}", end="", flush=True)
        if done == total: print()

    bt = AShareBatchBacktester(
        strategy=strategy, max_workers=args.workers,
        progress_callback=on_progress,
    )

    print(f"\n🚀 A股新策略回测开始...")
    t0 = time.time()
    summary, results = bt.run(symbols)
    print(f"\n耗时: {time.time()-t0:.0f}s")
    print(bt.report())
    print(bt.report_detail(top_n=args.top))

    if args.compare:
        print("\n" + "=" * 60)
        print("  对比：旧波浪策略")
        print("=" * 60)
        from analysis.backtest.batch_backtester import BatchBacktester, BatchConfig
        from analysis.backtest.wave_backtester import WaveStrategy
        old_bt = BatchBacktester(
            strategy=WaveStrategy(initial_capital=args.capital),
            config=BatchConfig(min_rows=100, max_workers=args.workers),
            progress_callback=on_progress,
        )
        old_sum, _ = old_bt.run(symbols)
        print(f"\n{'指标':<22} {'旧波浪':>10} {'新A股':>10} {'Δ':>8}")
        print("-" * 52)
        metrics = [
            ("均收益%",       old_sum.avg_return_pct,   summary.avg_return_pct),
            ("均胜率",        old_sum.avg_win_rate*100, summary.avg_win_rate*100),
            ("均Sharpe",      old_sum.avg_sharpe,        summary.avg_sharpe),
            ("均回撤%",       old_sum.avg_drawdown_pct,  summary.avg_drawdown_pct),
            ("目标止盈%",     old_sum.exit_target_pct,   summary.avg_target_reached_pct),
            ("止损率%",       old_sum.exit_stop_loss_pct,summary.avg_hard_stop_pct),
        ]
        for name, old_v, new_v in metrics:
            delta = new_v - old_v
            sign = "+" if delta >= 0 else ""
            print(f"  {name:<20} {old_v:>9.2f}  {new_v:>9.2f}  {sign}{delta:>6.2f}")

    if not args.no_save:
        paths = bt.save_results(args.output)
        print(f"\n💾 结果已保存:")
        for k, v in paths.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
