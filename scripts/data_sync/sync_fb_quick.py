#!/usr/bin/env python3
"""食品饮料板块 - 简化版同步"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import DatabaseDataManager

print("🍺 同步食品饮料板块...")

manager = DatabaseDataManager()

# 核心白酒+食品饮料股 (20只)
stocks = [
    ('600519', '贵州茅台', 2001),
    ('000858', '五粮液', 1998),
    ('000568', '泸州老窖', 1994),
    ('600809', '山西汾酒', 1994),
    ('002304', '洋河股份', 2009),
    ('603369', '今世缘', 2014),
    ('600779', '水井坊', 1996),
    ('000596', '古井贡酒', 1996),
    ('600702', '舍得酒业', 1996),
    ('600600', '青岛啤酒', 1993),
    ('000729', '燕京啤酒', 1997),
    ('600887', '伊利股份', 1996),
    ('600597', '光明乳业', 2002),
    ('603288', '海天味业', 2014),
    ('603027', '千禾味业', 2016),
    ('600872', '中炬高新', 1995),
    ('002507', '涪陵榨菜', 2010),
    ('002557', '洽洽食品', 2011),
    ('603517', '绝味食品', 2017),
    ('600298', '安琪酵母', 2000),
]

total = 0
for symbol, name, ipo in stocks:
    try:
        print(f"{symbol} {name} ...", end=" ")
        count = manager.sync_symbol(symbol, years=2026-ipo+1)
        total += count
        print(f"{count}条")
    except Exception as e:
        print(f"失败: {e}")

print(f"\n✅ 完成! 共 {total} 条")
manager.close()
