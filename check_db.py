import sys

sys.path.insert(0, 'src')
from data import get_db_manager

db = get_db_manager()

# 1. 总数据量
result = db.pg.execute('SELECT COUNT(*) as total FROM market_data', fetch=True)
print(f'📊 总数据量: {result[0]["total"]:,} 条')

# 2. 股票数量
result = db.pg.execute('SELECT COUNT(DISTINCT symbol) as stocks FROM market_data', fetch=True)
print(f'📈 股票数量: {result[0]["stocks"]} 只')

# 3. 数据时间范围
result = db.pg.execute('SELECT MIN(date) as min_date, MAX(date) as max_date FROM market_data', fetch=True)
print(f'📅 数据范围: {result[0]["min_date"]} ~ {result[0]["max_date"]}')

# 4. 最近3天数据量
result = db.pg.execute("""
    SELECT date, COUNT(*) as count
    FROM market_data
    WHERE date >= CURRENT_DATE - INTERVAL '3 days'
    GROUP BY date
    ORDER BY date DESC
""", fetch=True)
print('\n📅 最近3天数据:')
for row in result:
    print(f'  {row["date"]}: {row["count"]:,} 条')

# 5. 板块分布
result = db.pg.execute("""
    SELECT sector, COUNT(DISTINCT symbol) as count
    FROM stock_info
    WHERE sector IS NOT NULL
    GROUP BY sector
    ORDER BY count DESC
    LIMIT 5
""", fetch=True)
print('\n🏢 前5大板块:')
for row in result:
    print(f'  {row["sector"]}: {row["count"]} 只')
