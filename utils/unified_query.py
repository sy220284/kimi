#!/usr/bin/env python3
"""
统一查询工具 - 同时匹配两种symbol格式
解决 THS(纯代码) 和 Tushare(带后缀) 格式共存问题
"""
import psycopg2
import pandas as pd
from datetime import datetime, date

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'quant_analysis',
    'user': 'quant_user',
    'password': 'quant_password'
}

def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

def normalize_symbol(symbol: str) -> str:
    """标准化股票代码 - 移除后缀"""
    return symbol.replace('.SZ', '').replace('.SH', '').replace('.BJ', '')

def query_stock_data(symbol: str, start_date=None, end_date=None) -> pd.DataFrame:
    """
    查询单只股票数据 - 自动匹配两种格式
    
    Args:
        symbol: 股票代码 (支持 000001 或 000001.SZ 格式)
        start_date: 开始日期 '2024-01-01'
        end_date: 结束日期 '2024-12-31'
    
    Returns:
        DataFrame with columns: date, open, high, low, close, volume, amount, data_source
    """
    conn = get_db_connection()
    
    # 标准化代码
    base_code = normalize_symbol(symbol)
    
    # 构建查询 - 同时匹配两种格式
    sql = """
        SELECT 
            date,
            open, high, low, close,
            volume, amount,
            data_source,
            symbol as raw_symbol
        FROM market_data
        WHERE (
            symbol = %(code)s 
            OR symbol = %(code)s || '.SZ'
            OR symbol = %(code)s || '.SH'
            OR symbol = %(code)s || '.BJ'
        )
    """
    
    params = {'code': base_code}
    
    if start_date:
        sql += " AND date >= %(start)s"
        params['start'] = start_date
    if end_date:
        sql += " AND date <= %(end)s"
        params['end'] = end_date
    
    sql += " ORDER BY date"
    
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    
    # 添加标准化后的代码列
    df['symbol'] = base_code
    
    return df

def query_multi_stocks(symbols: list, start_date=None, end_date=None) -> pd.DataFrame:
    """
    批量查询多只股票数据
    
    Args:
        symbols: 股票代码列表 ['000001', '600000', '000001.SZ']
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        DataFrame with all stocks data
    """
    all_data = []
    for symbol in symbols:
        df = query_stock_data(symbol, start_date, end_date)
        if not df.empty:
            all_data.append(df)
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

def check_stock_coverage(symbol: str) -> dict:
    """
    检查某只股票的数据覆盖情况
    
    Returns:
        {
            'symbol': '000001',
            'total_records': 1500,
            'date_range': ('2020-01-01', '2026-03-19'),
            'data_sources': {'THS': 1000, 'tushare': 500},
            'formats': ['000001', '000001.SZ']
        }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    base_code = normalize_symbol(symbol)
    
    cursor.execute("""
        SELECT 
            symbol,
            COUNT(*) as cnt,
            MIN(date) as earliest,
            MAX(date) as latest,
            data_source
        FROM market_data
        WHERE (
            symbol = %s 
            OR symbol = %s || '.SZ'
            OR symbol = %s || '.SH'
            OR symbol = %s || '.BJ'
        )
        GROUP BY symbol, data_source
        ORDER BY symbol
    """, (base_code, base_code, base_code, base_code))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        return {'symbol': base_code, 'exists': False}
    
    total = sum(r[1] for r in results)
    sources = {}
    formats = set()
    
    for row in results:
        sym, cnt, earliest, latest, source = row
        sources[source or 'unknown'] = cnt
        formats.add(sym)
    
    return {
        'symbol': base_code,
        'exists': True,
        'total_records': total,
        'date_range': (min(r[2] for r in results), max(r[3] for r in results)),
        'data_sources': sources,
        'formats': list(formats)
    }

# ============ 测试 ============
if __name__ == '__main__':
    print("=" * 70)
    print("🧪 统一查询工具测试")
    print("=" * 70)
    
    # 测试1: 查询单只股票 (两种格式共存)
    test_symbols = ['000066', '601360', '000001.SZ']
    
    for sym in test_symbols:
        print(f"\n📊 查询: {sym}")
        print("-" * 40)
        
        # 检查覆盖情况
        info = check_stock_coverage(sym)
        if info['exists']:
            print(f"  总记录数: {info['total_records']}")
            print(f"  日期范围: {info['date_range'][0]} ~ {info['date_range'][1]}")
            print(f"  数据源: {info['data_sources']}")
            print(f"  格式: {info['formats']}")
        else:
            print("  ⚠️ 无数据")
    
    # 测试2: 获取最近30天数据
    print("\n" + "=" * 70)
    print("📈 最近30天数据查询示例")
    print("=" * 70)
    
    df = query_stock_data('000066', start_date='2026-02-20')
    if not df.empty:
        print(f"\n000066 中国长城 最近数据:")
        print(df[['date', 'close', 'volume', 'data_source']].tail(5).to_string(index=False))
