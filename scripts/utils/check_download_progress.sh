#!/bin/bash
# 下载进度汇报脚本 - 从数据库查询真实进度

cd /root/.openclaw/workspace/quant_agent_system

# 从数据库查询真实进度
echo "📊 数据下载进度汇报"
echo "===================="

# 使用Python查询数据库
python3 -c "
import sys
sys.path.insert(0, 'src')
from data.db_manager import get_db_manager

try:
    db = get_db_manager()
    result = db.pg.execute('SELECT COUNT(DISTINCT symbol) as stocks, COUNT(*) as total FROM market_data', fetch=True)
    stocks = result[0]['stocks']
    total = result[0]['total']
    percent = stocks / 514 * 100
    
    print(f'当前进度: {stocks}/514 ({percent:.1f}%)')
    print(f'数据库记录: {total:,} 条')
    
    remaining = 514 - stocks
    if remaining > 0:
        # 估算剩余时间 (每只约30秒)
        mins = remaining * 30 / 60
        hours = mins / 60
        if hours >= 1:
            print(f'预计剩余: {hours:.1f}小时')
        else:
            print(f'预计剩余: {mins:.0f}分钟')
    else:
        print('✅ 下载完成!')
except Exception as e:
    print(f'查询失败: {e}')
"
