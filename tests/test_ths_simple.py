#!/usr/bin/env python3
"""
同花顺(THS)适配器测试脚本 - 简化版
直接测试，不依赖utils模块
"""
import requests
import json
import re
import pandas as pd

# 同花顺API配置
BASE_URL = "http://d.10jqka.com.cn/v4/line"

def parse_jsdata(js_text: str, symbol: str) -> pd.DataFrame:
    """解析同花顺返回的JavaScript格式数据"""
    pattern = r'quotebridge_v4_line_[^(]+\((.*)\)'
    match = re.search(pattern, js_text)
    
    if not match:
        raise Exception("无法解析返回数据格式")
    
    json_str = match.group(1)
    data = json.loads(json_str)
    
    if 'data' not in data:
        raise Exception("返回数据不包含data字段")
    
    lines = data['data'].split(';')
    records = []
    
    for line in lines:
        if not line.strip():
            continue
        parts = line.split(',')
        if len(parts) >= 6:
            records.append({
                'date': parts[0],
                'open': float(parts[1]),
                'high': float(parts[2]),
                'low': float(parts[3]),
                'close': float(parts[4]),
                'volume': float(parts[5]) if len(parts) > 5 else 0,
            })
    
    df = pd.DataFrame(records)
    df['symbol'] = symbol
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def test_ths_api():
    """测试同花顺API"""
    print("=" * 60)
    print("同花顺(THS)API 直连测试")
    print("=" * 60)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
    })
    
    # 测试1: 连接测试（茅台）
    print("\n1. 连接测试 - 贵州茅台(600519)")
    try:
        url = f"{BASE_URL}/hs_600519/01/last.js"
        response = session.get(url, headers={'Referer': 'http://stockpage.10jqka.com.cn/600519/'}, timeout=30)
        print(f"   HTTP状态: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✓ 连接成功")
        else:
            print("   ✗ 连接失败")
            return
    except Exception as e:
        print(f"   ✗ 连接错误: {e}")
        return
    
    # 测试2: 数据解析
    print("\n2. 数据解析测试")
    try:
        df = parse_jsdata(response.text, "600519")
        print("   ✓ 解析成功")
        print(f"   数据条数: {len(df)}")
        print(f"   日期范围: {df['date'].min()} ~ {df['date'].max()}")
        print("\n   最新数据:")
        latest = df.iloc[-1]
        print(f"     日期: {latest['date']}")
        print(f"     开盘: {latest['open']}")
        print(f"     最高: {latest['high']}")
        print(f"     最低: {latest['low']}")
        print(f"     收盘: {latest['close']}")
        print(f"     成交量: {latest['volume']}")
    except Exception as e:
        print(f"   ✗ 解析失败: {e}")
        return
    
    # 测试3: 多股票测试
    print("\n3. 多股票测试")
    test_stocks = [
        ("hs_600519", "贵州茅台"),
        ("hs_000001", "平安银行"),
        ("hs_000858", "五粮液"),
    ]
    
    for code, name in test_stocks:
        try:
            url = f"{BASE_URL}/{code}/01/last.js"
            stock_code = code.replace('hs_', '')
            resp = session.get(url, headers={'Referer': f'http://stockpage.10jqka.com.cn/{stock_code}/'}, timeout=30)
            
            if resp.status_code == 200:
                df = parse_jsdata(resp.text, code)
                print(f"   ✓ {name}({code}) - {len(df)}条数据")
            else:
                print(f"   ✗ {name}({code}) - HTTP {resp.status_code}")
        except Exception as e:
            print(f"   ✗ {name}({code}) - {str(e)[:40]}")
    
    # 测试4: 日期过滤
    print("\n4. 日期过滤测试")
    try:
        df_filtered = df[(df['date'] >= '2024-01-01') & (df['date'] <= '2024-01-31')]
        print(f"   ✓ 过滤后: {len(df_filtered)} 条数据 (2024-01-01 ~ 2024-01-31)")
        if len(df_filtered) > 0:
            print("   数据预览:")
            print(df_filtered[['date', 'open', 'high', 'low', 'close', 'volume']].head(5).to_string(index=False))
    except Exception as e:
        print(f"   ✗ 过滤失败: {e}")
    
    # 测试5: 指数测试
    print("\n5. 指数数据测试")
    indices = [
        ("hs_000001", "上证指数"),
        ("hs_000300", "沪深300"),
        ("hs_399006", "创业板指"),
    ]
    
    for code, name in indices:
        try:
            url = f"{BASE_URL}/{code}/01/last.js"
            idx_code = code.replace('hs_', '')
            resp = session.get(url, headers={'Referer': f'http://stockpage.10jqka.com.cn/{idx_code}/'}, timeout=30)
            
            if resp.status_code == 200:
                df_idx = parse_jsdata(resp.text, code)
                latest = df_idx.iloc[-1]
                print(f"   ✓ {name} - 最新: {latest['close']}")
            else:
                print(f"   ✗ {name} - HTTP {resp.status_code}")
        except Exception as e:
            print(f"   ✗ {name} - {str(e)[:40]}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_ths_api()
