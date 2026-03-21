#!/usr/bin/env python3
"""
main.py — A股量化分析系统 主入口

用法：
  python main.py --mode scan    --symbols 600519 000858 000001
  python main.py --mode analyze --symbol  600519
  python main.py --mode backtest --symbol 600519
  python main.py --mode regime  --symbol  000001
"""
import argparse
import sys
from datetime import datetime

from data.optimized_data_manager import get_optimized_data_manager
from agents.ashare_agent import AShareAgent
from analysis.strategy.ashare_backtester import AShareBacktester
from analysis.strategy.ashare_batch import AShareBatchBacktester
from analysis.strategy.ashare_strategy import AShareStrategy
from analysis.regime.market_regime import AShareMarketRegime


def print_banner():
    print("=" * 70)
    print("  📊 A股量化分析系统 v2.0")
    print(f"  启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def mode_analyze(symbol: str, dm):
    """单股完整分析"""
    df = dm.get_stock_data(symbol)
    if df is None:
        print(f"❌ 无数据: {symbol}")
        return
    agent = AShareAgent()
    r = agent.analyze(symbol, df)
    print(f"\n{'='*55}")
    print(r.summary)
    print(f"  市场状态: {r.regime.label}  置信度={r.regime.confidence:.2f}")
    print(f"  多因子:  {r.factor_score.total_score:.1f}分[{r.factor_score.grade}]  ", end="")
    print(f"动量={r.factor_score.momentum_score:.0f} 趋势={r.factor_score.trend_score:.0f}")
    if r.signal and r.signal.is_valid:
        s = r.signal
        print(f"  信号: {s.signal_type.value}  盈亏比={s.rr_ratio:.1f}x  仓位={s.position_pct:.0%}")
        print(f"    入场¥{s.entry_price:.2f} → 目标¥{s.target_price:.2f}  止损¥{s.stop_loss:.2f}")
    print(f"{'='*55}")


def mode_scan(symbols: list[str], dm):
    """批量扫描选股"""
    agent = AShareAgent()
    sdfs = {s: df for s in symbols if (df := dm.get_stock_data(s)) is not None}
    results = agent.scan(sdfs, top_n=10)
    print(agent.report(results))


def mode_regime(symbol: str, dm):
    """市场状态"""
    df = dm.get_stock_data(symbol)
    if df is None:
        print(f"❌ 无数据: {symbol}"); return
    r = AShareMarketRegime().detect(df)
    print(f"\n{symbol} 市场状态: {r.label}")
    print(f"  置信度: {r.confidence:.2f}  最大仓位: {r.max_position:.0%}")
    print(f"  描述: {r.description}")
    print(f"  得分: 趋势={r.trend_score:.2f} 量能={r.volume_score:.2f} "
          f"动量={r.momentum_score:.2f} 风险={r.risk_score:.2f}")


def mode_backtest(symbol: str, dm):
    """单股回测"""
    df = dm.get_stock_data(symbol)
    if df is None:
        print(f"❌ 无数据: {symbol}"); return
    bt = AShareBacktester()
    r = bt.run(symbol, df)
    d = r.to_dict()
    print(f"\n{symbol} 回测结果:")
    print(f"  交易次数: {r.total_trades}   胜率: {r.win_rate:.1%}")
    print(f"  总收益: {r.total_return_pct:+.2f}%   最大回撤: {r.max_drawdown_pct:.2f}%")
    print(f"  Sharpe: {r.sharpe_ratio:.2f}   Calmar: {r.calmar_ratio:.2f}")
    ex = r.exit_reason_counts; total = r.total_trades or 1
    print(f"  目标止盈: {ex.get('target_reached',0)/total:.0%}  "
          f"止损: {ex.get('stop_loss',0)/total:.0%}  "
          f"时间止损: {ex.get('time_stop',0)/total:.0%}")


def mode_batch(symbols: list[str], dm):
    """批量回测"""
    def prog(d, t, s): print(f"\r  [{d}/{t}] {s:<10}", end="", flush=True)
    bt = AShareBatchBacktester(max_workers=4, progress_callback=prog)
    summary, results = bt.run(symbols, data_loader=dm.get_stock_data)
    print()
    print(bt.report())
    print(bt.report_detail(top_n=20))


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="A股量化分析系统")
    parser.add_argument("--mode", choices=["analyze","scan","regime","backtest","batch"],
                        default="scan")
    parser.add_argument("--symbol", help="单只股票代码")
    parser.add_argument("--symbols", nargs="+", help="多只股票代码")
    args = parser.parse_args()

    dm = get_optimized_data_manager()
    dm.load_all_data()
    all_symbols = [s for s in (args.symbols or []) if s]
    if not all_symbols and args.symbol:
        all_symbols = [args.symbol]
    if not all_symbols:
        # 默认取数据库所有股票
        from utils.db_connector import PostgresConnector
        import os
        try:
            pg = PostgresConnector(host="localhost", port=5432,
                database=os.environ.get("PG_DATABASE","quant_analysis"),
                username=os.environ.get("PG_USERNAME","quant_user"),
                password=os.environ.get("PG_PASSWORD","quant_password"))
            pg.connect()
            all_symbols = [r["symbol"] for r in pg.execute(
                "SELECT DISTINCT symbol FROM market_data ORDER BY symbol", fetch=True)]
            pg.disconnect()
        except Exception:
            print("❌ 无法连接数据库，请指定 --symbol 或 --symbols"); sys.exit(1)

    if args.mode == "analyze":
        mode_analyze(all_symbols[0], dm)
    elif args.mode == "scan":
        mode_scan(all_symbols, dm)
    elif args.mode == "regime":
        mode_regime(all_symbols[0], dm)
    elif args.mode == "backtest":
        mode_backtest(all_symbols[0], dm)
    elif args.mode == "batch":
        mode_batch(all_symbols, dm)


if __name__ == "__main__":
    main()
