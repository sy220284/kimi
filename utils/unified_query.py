#!/usr/bin/env python3
"""
统一查询工具 - 同时匹配 THS(纯代码) 和 Tushare(带后缀) 两种 symbol 格式

P3A 重构: 改用 DatabaseDataManager + 连接池，不再硬编码数据库凭证，
统一通过 config.yaml / 环境变量管理连接参数。
"""
from __future__ import annotations

import pandas as pd

from data.db_manager import get_db_manager


def normalize_symbol(symbol: str) -> str:
    """标准化股票代码，移除交易所后缀（.SZ / .SH / .BJ）"""
    return symbol.split('.')[0]


def query_stock_data(
    symbol: str,
    start_date: str | None = None,
    end_date:   str | None = None,
) -> pd.DataFrame:
    """
    查询单只股票数据，自动匹配 '000001' 和 '000001.SZ' 两种格式

    Args:
        symbol:     股票代码（支持带/不带后缀）
        start_date: 开始日期 'YYYY-MM-DD'（可选）
        end_date:   结束日期 'YYYY-MM-DD'（可选）

    Returns:
        DataFrame: date/open/high/low/close/volume/amount
    """
    db = get_db_manager()
    base = normalize_symbol(symbol)

    conditions = ['symbol = %s']
    params: list = [base]

    if start_date:
        conditions.append('date >= %s')
        params.append(start_date)
    if end_date:
        conditions.append('date <= %s')
        params.append(end_date)

    sql = (
        'SELECT date, open, high, low, close, volume, amount '
        'FROM market_data WHERE ' + ' AND '.join(conditions) + ' ORDER BY date'
    )
    rows = db.pg.execute(sql, tuple(params), fetch=True)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    for col in ['open', 'high', 'low', 'close', 'amount']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    if 'volume' in df.columns:
        df['volume'] = df['volume'].astype(int)
    return df


def query_multi_stocks(
    symbols: list[str],
    start_date: str | None = None,
    end_date:   str | None = None,
) -> pd.DataFrame:
    """
    批量查询多只股票数据

    Returns:
        DataFrame: 含 symbol 列，按 (symbol, date) 排序
    """
    if not symbols:
        return pd.DataFrame()

    db = get_db_manager()
    bases = [normalize_symbol(s) for s in symbols]
    placeholders = ', '.join(['%s'] * len(bases))
    params: list = list(bases)

    conditions = [f'symbol IN ({placeholders})']
    if start_date:
        conditions.append('date >= %s')
        params.append(start_date)
    if end_date:
        conditions.append('date <= %s')
        params.append(end_date)

    sql = (
        'SELECT symbol, date, open, high, low, close, volume, amount '
        'FROM market_data WHERE ' + ' AND '.join(conditions) +
        ' ORDER BY symbol, date'
    )
    rows = db.pg.execute(sql, tuple(params), fetch=True)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    for col in ['open', 'high', 'low', 'close', 'amount']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    if 'volume' in df.columns:
        df['volume'] = df['volume'].astype(int)
    return df


def check_stock_coverage(symbol: str) -> dict:
    """
    检查某只股票在数据库中的数据覆盖情况

    Returns:
        dict: count / min_date / max_date / symbol
    """
    db = get_db_manager()
    base = normalize_symbol(symbol)
    rows = db.pg.execute(
        'SELECT COUNT(*) as cnt, MIN(date) as min_date, MAX(date) as max_date '
        'FROM market_data WHERE symbol = %s',
        (base,), fetch=True
    )
    if not rows:
        return {'symbol': base, 'count': 0, 'min_date': None, 'max_date': None}
    r = rows[0]
    return {
        'symbol':   base,
        'count':    int(r['cnt']),
        'min_date': str(r['min_date']) if r['min_date'] else None,
        'max_date': str(r['max_date']) if r['max_date'] else None,
    }
