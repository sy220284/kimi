
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data import get_db_manager

db = get_db_manager()

print('📊 检查 2026-03-18 数据覆盖情况...\n')

# 1. 查询昨日有数据的股票
result = db.pg.execute("""
    SELECT symbol, close, volume
    FROM market_data
    WHERE date = '2026-03-18'
    ORDER BY symbol
""", fetch=True)

print(f'✅ 昨日有数据的股票: {len(result)} 只')
if result:
    print('\n前10只:')
    for r in result[:10]:
        print(f'  {r["symbol"]}: 收盘{r["close"]}, 成交量{r["volume"]}')

# 2. 查询数据库中所有股票
all_stocks = db.pg.execute('SELECT DISTINCT symbol FROM market_data', fetch=True)
all_symbols = {r['symbol'] for r in all_stocks}
yesterday_symbols = {r['symbol'] for r in result}

missing = all_symbols - yesterday_symbols
print(f'\n❌ 昨日无数据的股票: {len(missing)} 只')
if missing:
    print(f'缺失列表: {sorted(missing)[:20]}...')

# 3. 统计信息
print('\n📈 覆盖统计:')
print(f'  数据库总股票: {len(all_symbols)} 只')
print(f'  昨日有数据: {len(yesterday_symbols)} 只 ({len(yesterday_symbols)/len(all_symbols)*100:.1f}%)')
print(f'  昨日缺失: {len(missing)} 只 ({len(missing)/len(all_symbols)*100:.1f}%)')
