#!/usr/bin/env python3
"""
自选股艾略特波浪分析 + 买点识别 (v2 - 主引擎复用版)

v1 问题: 自己实现了简化波浪逻辑，与 analysis/wave/ 主引擎并行，优化参数锁在脚本里
v2 修复: 完全复用主引擎 UnifiedWaveAnalyzer + WaveEntryOptimizer
         脚本只负责: 加载自选股 -> 调用引擎 -> 格式化输出

优化参数版本 2026-03-20 (基于10轮回测，已移植到 entry_optimizer.py):
  年化收益 10.03% -> 14.82%, 最大回撤 10.21% -> 7.13%, 胜率 44.9% -> 47.7%
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd

from analysis.technical.indicators import TechnicalIndicators
from analysis.wave.entry_optimizer import WaveEntryOptimizer
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer
from data import get_db_manager


def load_self_select_stocks():
    cache_path = Path('.cache/mx_selfselect_list.json')
    if not cache_path.exists():
        print(f"警告: 自选股缓存不存在: {cache_path}")
        return []
    with open(cache_path) as f:
        data = json.load(f)
    if data and isinstance(data[0], dict):
        return [d.get('symbol', d.get('code', '')) for d in data]
    return data


def get_stock_data(symbol, days=200):
    db = get_db_manager()
    end_date   = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    clean = symbol.split('.')[0]
    result = db.pg.execute(
        'SELECT date,open,high,low,close,volume,amount FROM market_data '
        'WHERE symbol=%s AND date>=%s AND date<=%s ORDER BY date',
        (clean, start_date, end_date), fetch=True
    )
    if not result:
        return pd.DataFrame()
    df = pd.DataFrame(result)
    df['date'] = pd.to_datetime(df['date'])
    for col in ['open','high','low','close','volume','amount']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    try:
        df = TechnicalIndicators().calculate_all(df)
    except Exception:
        pass
    return df


def analyze_stock(symbol, analyzer, optimizer):
    df = get_stock_data(symbol)
    if df.empty or len(df) < 60:
        return None
    signals = analyzer.detect(df, mode='all')
    if not signals:
        return None
    rated = []
    for sig in signals:
        if not sig.is_valid or sig.confidence < 0.3:
            continue
        rated.append({
            'entry_type':    sig.entry_type.value,
            'confidence':    round(sig.confidence, 3),
            'quality_score': round(sig.quality_score, 3),
            'resonance':     round(sig.resonance_score, 3),
            'entry_price':   round(sig.entry_price, 3),
            'target_price':  round(sig.target_price, 3),
            'stop_loss':     round(sig.stop_loss, 3),
            'rating':        optimizer.get_buy_rating(sig.quality_score),
            'market':        sig.market_condition or '',
        })
    if not rated:
        return None
    rated.sort(key=lambda x: x['quality_score'], reverse=True)
    best = rated[0]
    return {
        'symbol': symbol,
        'date':   df['date'].iloc[-1].strftime('%Y-%m-%d'),
        'close':  round(float(df['close'].iloc[-1]), 3),
        'signals': rated, 'best_signal': best, 'rating': best['rating'],
    }


def main():
    print("=" * 65)
    print("自选股艾略特波浪买点分析 (v2 - 主引擎复用版)")
    print("=" * 65)
    symbols = load_self_select_stocks()
    if not symbols:
        print("无自选股，退出"); return

    print(f"自选股数量: {len(symbols)}")
    analyzer  = UnifiedWaveAnalyzer()
    optimizer = WaveEntryOptimizer()
    results = {'强买入': [], '买入': [], '关注': [], '观望': []}
    failed = 0

    for i, sym in enumerate(symbols, 1):
        print(f"\r  [{i}/{len(symbols)}] {sym} ...", end='', flush=True)
        try:
            res = analyze_stock(sym, analyzer, optimizer)
            if res:
                results[res['rating']].append(res)
            else:
                results['观望'].append({'symbol': sym, 'rating': '观望'})
        except Exception:
            failed += 1

    print()
    total = sum(len(v) for v in results.values())
    print(f"\n扫描完成: {len(symbols)}只, 有效{total}只, 失败{failed}只")

    for rating in ['强买入', '买入', '关注']:
        group = results[rating]
        if not group:
            continue
        print(f"\n{rating} ({len(group)}只)")
        print("-" * 40)
        for r in group:
            s = r.get('best_signal', {})
            print(f"  {r['symbol']}  ¥{r.get('close','?')}"
                  f"  {s.get('entry_type','?')}  置信={s.get('confidence',0):.2f}"
                  f"  质量={s.get('quality_score',0):.2f}"
                  f"  目标¥{s.get('target_price','?')}  止损¥{s.get('stop_loss','?')}")

    out = Path('.cache/wave_analysis_result.json')
    out.parent.mkdir(exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n结果已保存: {out}")


if __name__ == '__main__':
    main()
