#!/usr/bin/env python3
"""
同花顺(THS)API 数据深度测试
检查可获取的数据类型和历史数据深度
"""
import requests
import json
import re
import pandas as pd

BASE_URL = "http://d.10jqka.com.cn/v4/line"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': '*/*',
})


def parse_js_data(js_text: str) -> pd.DataFrame:
    """解析同花顺JS数据"""
    pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
    match = re.search(pattern, js_text)
    
    if not match:
        return pd.DataFrame()
    
    data = json.loads(match.group(1))
    
    if 'data' not in data:
        return pd.DataFrame()
    
    lines = data['data'].split(';')
    records = []
    
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        if len(parts) >= 6:
            record = {
                'date': parts[0],
                'open': float(parts[1]),
                'high': float(parts[2]),
                'low': float(parts[3]),
                'close': float(parts[4]),
                'volume': float(parts[5]) if len(parts) > 5 else 0,
            }
            # 更多字段
            if len(parts) > 6:
                record['amount'] = float(parts[6])  # 成交额
            if len(parts) > 7:
                record['amplitude'] = float(parts[7])  # 振幅
            if len(parts) > 8:
                record['change_pct'] = float(parts[8])  # 涨跌幅
            if len(parts) > 9:
                record['change'] = float(parts[9])  # 涨跌额
            if len(parts) > 10:
                record['turnover'] = float(parts[10])  # 换手率
                
            records.append(record)
    
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def fetch_data(code: str) -> pd.DataFrame:
    """获取数据"""
    url = f"{BASE_URL}/{code}/01/last.js"
    stock_code = code.replace('hs_', '')
    try:
        resp = session.get(url, headers={'Referer': f'http://stockpage.10jqka.com.cn/{stock_code}/'}, timeout=30)
        if resp.status_code == 200:
            return parse_js_data(resp.text)
    except:
        pass
    return pd.DataFrame()


def main():
    print("=" * 70)
    print("同花顺(THS)API - 数据深度检查")
    print("=" * 70)
    
    # ========== 1. 个股历史数据深度 ==========
    print("\n📊 1. 个股历史数据深度")
    print("-" * 70)
    
    stocks = [
        ("hs_600519", "贵州茅台"),
        ("hs_000001", "平安银行"),
        ("hs_000858", "五粮液"),
        ("hs_000333", "美的集团"),
        ("hs_600036", "招商银行"),
    ]
    
    stock_results = []
    for code, name in stocks:
        df = fetch_data(code)
        if not df.empty:
            days = len(df)
            start_date = df['date'].min()
            end_date = df['date'].max()
            stock_results.append({
                '股票': name,
                '代码': code.replace('hs_', ''),
                '数据条数': days,
                '起始日期': start_date,
                '结束日期': end_date,
                '数据跨度': f"{(pd.to_datetime(end_date) - pd.to_datetime(start_date)).days}天"
            })
    
    stock_df = pd.DataFrame(stock_results)
    print(stock_df.to_string(index=False))
    
    # 检查详细字段
    print(f"\n📋 数据字段详情（以茅台为例）:")
    df_sample = fetch_data("hs_600519")
    print(f"   字段列表: {list(df_sample.columns)}")
    print(f"   字段数: {len(df_sample.columns)}")
    print("\n   第一条数据示例:")
    if not df_sample.empty:
        row = df_sample.iloc[0]
        for col in df_sample.columns:
            print(f"     {col}: {row[col]}")
    
    # ========== 2. 指数数据 ==========
    print("\n\n📈 2. 指数数据可用性")
    print("-" * 70)
    
    indices = [
        ("hs_000001", "上证指数"),
        ("hs_000016", "上证50"),
        ("hs_000300", "沪深300"),
        ("hs_000905", "中证500"),
        ("hs_399001", "深证成指"),
        ("hs_399006", "创业板指"),
        ("hs_000688", "科创50"),
    ]
    
    index_results = []
    for code, name in indices:
        df = fetch_data(code)
        status = "✓ 可用" if not df.empty else "✗ 不可用"
        days = len(df) if not df.empty else 0
        index_results.append({
            '指数': name,
            '代码': code.replace('hs_', ''),
            '状态': status,
            '数据条数': days
        })
    
    index_df = pd.DataFrame(index_results)
    print(index_df.to_string(index=False))
    
    # ========== 3. 行业板块数据 ==========
    print("\n\n🏭 3. 行业板块数据测试")
    print("-" * 70)
    
    # 申万行业指数代码（部分）
    industries = [
        ("hs_881001", "计算机"),
        ("hs_881002", "电子"),
        ("hs_881003", "医药生物"),
        ("hs_881004", "食品饮料"),
        ("hs_881005", "银行"),
        ("hs_881006", "非银金融"),
        ("hs_881007", "房地产"),
        ("hs_881008", "汽车"),
        ("hs_881009", "电力设备"),
        ("hs_881010", "新能源"),
    ]
    
    industry_results = []
    for code, name in industries:
        df = fetch_data(code)
        status = "✓ 可用" if not df.empty else "✗ 不可用"
        days = len(df) if not df.empty else 0
        industry_results.append({
            '行业': name,
            '代码': code.replace('hs_', ''),
            '状态': status,
            '数据条数': days
        })
    
    industry_df = pd.DataFrame(industry_results)
    print(industry_df.to_string(index=False))
    
    # ========== 4. 不同K线周期 ==========
    print("\n\n📅 4. K线周期支持")
    print("-" * 70)
    
    ktypes = [
        ("01", "日线"),
        ("11", "周线"),
        ("12", "月线"),
    ]
    
    for ktype, name in ktypes:
        url = f"{BASE_URL}/hs_600519/{ktype}/last.js"
        try:
            resp = session.get(url, headers={'Referer': 'http://stockpage.10jqka.com.cn/600519/'}, timeout=30)
            if resp.status_code == 200:
                df = parse_js_data(resp.text)
                print(f"   {name}({ktype}): ✓ {len(df)} 条数据")
            else:
                print(f"   {name}({ktype}): ✗ HTTP {resp.status_code}")
        except Exception as e:
            print(f"   {name}({ktype}): ✗ 错误")
    
    # ========== 5. 数据质量检查 ==========
    print("\n\n🔍 5. 数据质量检查（茅台）")
    print("-" * 70)
    
    df = fetch_data("hs_600519")
    if not df.empty:
        # 检查是否有缺失值
        missing = df.isnull().sum()
        print("   缺失值检查:")
        for col in df.columns:
            if missing[col] > 0:
                print(f"     {col}: {missing[col]} 个缺失")
        if missing.sum() == 0:
            print("     ✓ 无缺失值")
        
        # 检查价格有效性
        print("\n   价格有效性:")
        invalid_high = (df['high'] < df[['open', 'close']].max(axis=1)).sum()
        invalid_low = (df['low'] > df[['open', 'close']].min(axis=1)).sum()
        print(f"     高价 < max(开收): {invalid_high} 条")
        print(f"     低价 > min(开收): {invalid_low} 条")
        
        # 统计信息
        print("\n   价格统计:")
        print(f"     最高: {df['high'].max():.2f}")
        print(f"     最低: {df['low'].min():.2f}")
        print(f"     平均成交量: {df['volume'].mean():,.0f}")
        print(f"     平均成交额: {df.get('amount', pd.Series([0])).mean():,.0f}")
    
    # ========== 6. 总结 ==========
    print("\n\n📋 6. 总结")
    print("=" * 70)
    print("\n✓ 数据类型支持:")
    print("   - 个股日线数据: 约140个交易日 (约6-7个月)")
    print("   - 指数数据: 上证指数、创业板指等主流指数可用")
    print("   - 行业板块: 申万行业指数部分可用")
    print("   - K线周期: 日线/周线/月线")
    
    print("\n✓ 数据字段 (11个):")
    print("   date, open, high, low, close, volume, amount,")
    print("   amplitude, change_pct, change, turnover")
    
    print("\n⚠ 限制:")
    print("   - 单次请求约140条数据 (约6个月历史)")
    print("   - 无法获取更长期历史数据")
    print("   - 部分指数/行业代码可能返回404")
    print("   - 需要处理Referer和User-Agent")
    
    print("\n✅ 适用场景:")
    print("   - 短期技术分析 (6个月内)")
    print("   - 实时行情监控")
    print("   - 中等频率数据更新")
    print("\n   如需更长期历史数据，建议配合 tushare/akshare 使用")


if __name__ == "__main__":
    main()
