#!/usr/bin/env python3
"""
批量回测脚本 — scripts/backtest/run_batch.py

用法:
  python scripts/backtest/run_batch.py                    # 回测DB全部股票
  python scripts/backtest/run_batch.py --symbols 600519 000001 300750
  python scripts/backtest/run_batch.py --workers 8 --start 2020-01-01
  python scripts/backtest/run_batch.py --stop-loss 0.04 --no-kelly --no-trailing
  python scripts/backtest/run_batch.py --output results/my_run
"""
import argparse
import sys
import os
from pathlib import Path

# 确保项目根目录在路径中
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from analysis.backtest.batch_backtester import BatchBacktester, BatchConfig
from analysis.backtest.wave_backtester import WaveStrategy


def parse_args():
    p = argparse.ArgumentParser(
        description="波浪策略批量回测",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── 股票选择 ──
    p.add_argument("--symbols", nargs="+", default=None,
                   help="指定股票代码列表；默认读取数据库全部股票")

    # ── 时间范围 ──
    p.add_argument("--start", default="", help="回测起始日期 YYYY-MM-DD")
    p.add_argument("--end",   default="", help="回测截止日期 YYYY-MM-DD")

    # ── 策略参数 ──
    p.add_argument("--capital",     type=float, default=100_000, help="初始资金")
    p.add_argument("--stop-loss",   type=float, default=0.05,   help="固定止损百分比")
    p.add_argument("--max-hold",    type=int,   default=60,      help="最大持仓天数")
    p.add_argument("--max-pos",     type=int,   default=3,       help="最大持仓数量")
    p.add_argument("--no-kelly",    action="store_true",         help="禁用 Kelly 仓位")
    p.add_argument("--no-trailing", action="store_true",         help="禁用移动止盈")
    p.add_argument("--no-trend",    action="store_true",         help="禁用趋势过滤")

    # ── 运行参数 ──
    p.add_argument("--workers",     type=int, default=4,  help="并行线程数")
    p.add_argument("--min-rows",    type=int, default=200, help="最少数据行数")
    p.add_argument("--reanalyze",   type=int, default=5,   help="重新分析频率(交易日)")
    p.add_argument("--output",      default="results",     help="结果输出目录")
    p.add_argument("--no-save",     action="store_true",   help="不保存文件，仅打印报告")
    p.add_argument("--top",         type=int, default=20,  help="排行榜显示前N名")

    return p.parse_args()


def get_all_symbols_from_db() -> list[str]:
    from utils.db_connector import PostgresConnector
    pg = PostgresConnector(host="localhost", port=5432,
                           database=os.environ.get("PG_DATABASE", "quant_analysis"),
                           username=os.environ.get("PG_USERNAME", "quant_user"),
                           password=os.environ.get("PG_PASSWORD", "quant_password"))
    pg.connect()
    rows = pg.execute(
        "SELECT DISTINCT symbol FROM market_data ORDER BY symbol",
        fetch=True
    )
    pg.disconnect()
    return [r["symbol"] for r in rows]


def main():
    args = parse_args()

    # ── 构建策略 ──
    strategy = WaveStrategy(
        initial_capital=args.capital,
        stop_loss_pct=args.stop_loss,
        max_positions=args.max_pos,
        max_holding_days=args.max_hold,
        use_kelly=not args.no_kelly,
        use_trailing_stop=not args.no_trailing,
        use_trend_filter=not args.no_trend,
    )

    # ── 构建配置 ──
    config = BatchConfig(
        start_date=args.start,
        end_date=args.end,
        min_rows=args.min_rows,
        max_workers=args.workers,
        reanalyze_every=args.reanalyze,
    )

    # ── 确定股票列表 ──
    if args.symbols:
        symbols = args.symbols
        print(f"指定 {len(symbols)} 只股票: {symbols}")
    else:
        print("从数据库读取全部股票...")
        symbols = get_all_symbols_from_db()
        print(f"共 {len(symbols)} 只股票")

    if not symbols:
        print("❌ 没有找到股票数据，请先同步数据")
        sys.exit(1)

    # ── 进度回调 ──
    def on_progress(done: int, total: int, symbol: str):
        bar_len = 30
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {done}/{total} {symbol:<10}", end="", flush=True)
        if done == total:
            print()

    # ── 运行回测 ──
    bt = BatchBacktester(
        strategy=strategy,
        config=config,
        progress_callback=on_progress,
    )

    print(f"\n策略: {bt._describe_strategy()}")
    print(f"并行: {args.workers} 线程 | 重分析: 每{args.reanalyze}天\n")

    summary, results = bt.run(symbols)

    # ── 输出报告 ──
    print(bt.report())
    print(bt.report_detail(top_n=args.top))

    # ── 保存结果 ──
    if not args.no_save:
        paths = bt.save_results(args.output)
        print(f"\n💾 已保存:")
        for k, v in paths.items():
            print(f"   {k}: {v}")

    # ── 返回码 ──
    ok_count = sum(1 for r in results if r.status == "ok" and r.total_trades > 0)
    sys.exit(0 if ok_count > 0 else 1)


if __name__ == "__main__":
    main()
