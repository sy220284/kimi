#!/usr/bin/env python3
"""补充同步食品饮料板块剩余股票"""
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pathlib import Path
from data import DatabaseDataManager

print("🍺 补充同步食品饮料板块...")

manager = DatabaseDataManager()

# 需要补充的股票
more_stocks = [
    ('600887', '伊利股份', 1996),
    ('603288', '海天味业', 2014),
    ('000729', '燕京啤酒', 1997),
    ('600597', '光明乳业', 2002),
    ('603027', '千禾味业', 2016),
    ('600872', '中炬高新', 1995),
    ('002507', '涪陵榨菜', 2010),
    ('002557', '洽洽食品', 2011),
    ('603517', '绝味食品', 2017),
    ('600298', '安琪酵母', 2000),
    ('603345', '安井食品', 2017),
    ('300146', '汤臣倍健', 2010),
    ('605499', '东鹏饮料', 2021),
    ('300999', '金龙鱼', 2020),
]

for symbol, name, ipo in more_stocks:
    try:
        print(f"{symbol} {name} ...", end=" ", flush=True)
        count = manager.sync_symbol(symbol, years=2026-ipo+1)
        print(f"✓ {count}条")
    except Exception as e:
        print(f"✗ {str(e)[:40]}")

print("\n同步完成!")
manager.close()
