"""
解析产业链图谱，提取所有股票代码
"""
import re

def extract_stocks_from_markdown(file_path):
    """从markdown文件中提取股票代码"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配股票代码模式 (6位数字.SH/.SZ/.BJ 或 纯6位数字)
    pattern = r'(\d{6})\.(SH|SZ|BJ)'
    matches = re.findall(pattern, content)
    
    stocks = {}
    for code, suffix in matches:
        # 转换为统一格式
        if suffix == 'SH':
            # 上海主板(60)和科创板(688)
            if code.startswith('6'):
                stocks[code] = f'hs_{code}'
        elif suffix == 'SZ':
            # 深圳主板(00)和创业板(300)
            if code.startswith('00') or code.startswith('300') or code.startswith('301'):
                stocks[code] = f'hs_{code}'
        elif suffix == 'BJ':
            # 北交所
            stocks[code] = f'hs_{code}'
    
    return stocks

# 提取股票
file_path = '/root/openclaw/kimi/downloads/19cff2ad-a642-8860-8000-00009a36e4f0_产业链图谱.md'
stocks = extract_stocks_from_markdown(file_path)

print(f"共提取到 {len(stocks)} 只 unique 股票")

# 保存到文件
with open('all_industry_stocks.txt', 'w') as f:
    for code in sorted(stocks.keys()):
        f.write(f"{code}\n")

print("股票列表已保存到 all_industry_stocks.txt")

# 按板块分类
kcb = [c for c in stocks.keys() if c.startswith('688')]  # 科创板
cyb = [c for c in stocks.keys() if c.startswith('300') or c.startswith('301')]  # 创业板
sh = [c for c in stocks.keys() if c.startswith('60') and not c.startswith('688')]  # 上海主板
sz = [c for c in stocks.keys() if c.startswith('00')]  # 深圳主板
bj = [c for c in stocks.keys() if c.startswith('8') or c.startswith('4')]  # 北交所

print("\n板块分布:")
print(f"  科创板: {len(kcb)} 只")
print(f"  创业板: {len(cyb)} 只")
print(f"  上海主板: {len(sh)} 只")
print(f"  深圳主板: {len(sz)} 只")
print(f"  北交所: {len(bj)} 只")

# 显示前30只
print("\n前30只股票:")
for i, code in enumerate(list(stocks.keys())[:30], 1):
    print(f"  {i}. {code}")
