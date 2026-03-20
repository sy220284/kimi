#!/usr/bin/env python3
"""
并发批量波浪信号扫描器 (OPT-4 + OPT-5)

特性:
  - ThreadPoolExecutor 并发扫描（workers 根据设备档位自动适配）
  - 两阶段快速过滤 (OPT-5)
  - 共享 UnifiedWaveAnalyzer 实例（只读，线程安全）
  - 预计算+增量缓存联动 OPT-1/OPT-7

使用:
    python scripts/analysis/batch_scanner.py --limit 500
    python scripts/analysis/batch_scanner.py --symbols 600519 000001
    KIMI_TIER=low python scripts/analysis/batch_scanner.py  # 低配模式
"""
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import pandas as pd
from analysis.technical.indicators import TechnicalIndicators
from analysis.wave.entry_optimizer import WaveEntryOptimizer
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer


def _load_stock_data(symbol, days=250):
    try:
        from data.db_manager import get_db_manager
        db = get_db_manager()
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now()-timedelta(days=days)).strftime('%Y-%m-%d')
        rows = db.pg.execute(
            'SELECT date,open,high,low,close,volume,amount FROM market_data '
            'WHERE symbol=%s AND date>=%s AND date<=%s ORDER BY date',
            (symbol, start, end), fetch=True)
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows)
        df['date'] = pd.to_datetime(df['date'])
        for c in ['open','high','low','close','volume','amount']:
            if c in df.columns: df[c] = df[c].astype(float)
        return df
    except Exception:
        return pd.DataFrame()


def _quick_filter(df, min_pivots=5):
    """OPT-5 第1阶段: ATR ZigZag极值点数量快筛, ~0.5ms"""
    if len(df) < 60: return False
    try:
        from analysis.wave.elliott_wave import calculate_atr, zigzag_atr
        h,l,c = df['high'].values, df['low'].values, df['close'].values
        atr = calculate_atr(h,l,c,period=10)
        idxs,_,_ = zigzag_atr(h,l,c,atr,atr_mult=0.5,min_dist=3)
        return len(idxs) >= min_pivots
    except Exception:
        return True


def _scan_one(symbol, analyzer, optimizer, ti, days, min_quality):
    df = _load_stock_data(symbol, days)
    if df.empty or len(df) < 60: return None
    if not _quick_filter(df): return None           # OPT-5 快筛
    try:                                                # OPT-1+7 预计算+缓存
        from data.incremental_indicator_cache import get_indicator_cache
        df = get_indicator_cache().get(symbol, df)
    except Exception:
        try: df = ti.calculate_all(df)
        except Exception: pass
    except Exception: pass
    try: signals = analyzer.detect(df, mode='all')  # OPT-5 精筛
    except Exception: return None
    if not signals: return None
    best = max(signals, key=lambda s:(s.quality_score+s.confidence)/2)
    if best.quality_score < min_quality: return None
    return {
        'symbol':        symbol,
        'date':          df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'close':         round(float(df['close'].iloc[-1]),3),
        'entry_type':    best.entry_type.value,
        'confidence':    round(best.confidence,3),
        'quality_score': round(best.quality_score,3),
        'resonance':     round(best.resonance_score,3),
        'entry_price':   round(best.entry_price,3),
        'target_price':  round(best.target_price,3),
        'stop_loss':     round(best.stop_loss,3),
        'rating':        optimizer.get_buy_rating(best.quality_score),
        'market':        best.market_condition or '',
        'signals_count': len(signals),
    }


def batch_scan(symbols, max_workers=None, days=None, min_quality=0.35, progress_cb=None):
    """
    并发批量扫描。workers/days 默认从性能适配器自动获取（按设备档位）。
    可通过 KIMI_SCAN_WORKERS / KIMI_SCAN_DAYS 环境变量覆盖。

    Args:
        symbols:     股票代码列表
        max_workers: 并发线程数（None=自动，LOW=2 MEDIUM=4 HIGH=8 EXTREME=16）
        days:        历史天数（None=自动，LOW=120 MEDIUM=200 HIGH=250）
        min_quality: 最低质量分（0.35=关注及以上）
        progress_cb: 进度回调 f(done, total, result_or_None)
    """
    from utils.performance_adaptor import get_adaptor
    cfg = get_adaptor()
    if max_workers is None: max_workers = cfg.scan_workers
    if days is None:        days        = cfg.scan_days

    analyzer  = UnifiedWaveAnalyzer()
    optimizer = WaveEntryOptimizer.from_config()
    ti        = TechnicalIndicators()
    results=[]; done=0; total=len(symbols); t0=time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_one,sym,analyzer,optimizer,ti,days,min_quality):sym
                   for sym in symbols}
        for fut in as_completed(futures):
            done += 1
            result = None
            try:
                result = fut.result()
                if result: results.append(result)
            except Exception: pass
            if progress_cb: progress_cb(done, total, result)
    elapsed = time.perf_counter()-t0
    results.sort(key=lambda r:(r['quality_score']+r['confidence'])/2, reverse=True)
    print(f"\n扫描完成: {total}只 信号{len(results)}只 耗时{elapsed:.1f}s ({elapsed/total*1000:.1f}ms/股)  [{cfg.tier.value}模式]")
    return results


def get_all_symbols(limit=500):
    try:
        from data.db_manager import get_db_manager
        db = get_db_manager()
        rows = db.pg.execute(
            'SELECT symbol FROM market_data GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT %s',
            (limit,), fetch=True)
        return [r['symbol'] for r in (rows or [])]
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser(description='并发波浪信号批量扫描')
    ap.add_argument('--symbols',nargs='+',help='指定股票代码')
    ap.add_argument('--limit',type=int,default=500,help='取DB前N只')
    ap.add_argument('--workers',type=int,default=8,help='并发线程数')
    ap.add_argument('--days',type=int,default=250,help='历史天数')
    ap.add_argument('--min-quality',type=float,default=0.35,help='最低质量分')
    ap.add_argument('--output',type=str,default=None,help='输出JSON文件')
    ap.add_argument('--top',type=int,default=20,help='展示TOP N')
    args = ap.parse_args()
    symbols = args.symbols or get_all_symbols(args.limit)
    print(f"扫描 {len(symbols)} 只  并发={args.workers}  days={args.days}")
    def progress(done,total,r):
        if done%50==0 or done==total:
            print(f"\r  [{done}/{total}] {done/total*100:.0f}%",end='',flush=True)
    results = batch_scan(symbols,max_workers=args.workers,days=args.days,
                         min_quality=args.min_quality,progress_cb=progress)
    for rating in ['强买入','买入','关注']:
        group=[r for r in results if r['rating']==rating]
        if not group: continue
        print(f"\n{rating} ({len(group)}只):")
        print("-"*70)
        for r in group[:args.top]:
            print(f"  {r['symbol']}  ¥{r['close']}  {r['entry_type']}"
                  f"  质量={r['quality_score']:.2f}  置信={r['confidence']:.2f}"
                  f"  目标¥{r['target_price']}  [{r['rating']}]")
    if args.output:
        out=Path(args.output)
        out.parent.mkdir(parents=True,exist_ok=True)
        with open(out,'w',encoding='utf-8') as f:
            json.dump({'scan_time':datetime.now().isoformat(),'total':len(symbols),
                       'signals':len(results),'results':results},
                      f,ensure_ascii=False,indent=2,default=str)
        print(f"\n结果已保存: {out}")

if __name__=='__main__': main()
