#!/usr/bin/env python3
"""
自选股全量历史数据同步 - 同花顺(THS)版
批量拉取自选股列表的历史数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from data import DatabaseDataManager

def get_selfselect_stocks():
    """从妙想API获取自选股列表"""
    apikey = os.environ.get('MX_APIKEY')
    resp = requests.post(
        'https://mkapi2.dfcfs.com/finskillshub/api/claw/self-select/get',
        headers={'Content-Type': 'application/json', 'apikey': apikey}
    )
    data = resp.json()
    stocks = data.get('data', {}).get('allResults', {}).get('result', {}).get('dataList', [])
    result = []
    for s in stocks:
        code = s.get('SECURITY_CODE')
        name = s.get('SECURITY_SHORT_NAME', '')
        result.append((code, name))
    return result

def main():
    print("=" * 80)
    print("📥 自选股全量历史数据同步 - 同花顺(THS)")
    print("=" * 80)
    
    # 1. 获取自选股列表
    print("\n📋 获取自选股列表...")
    stocks = get_selfselect_stocks()
    print(f"   ✅ 共 {len(stocks)} 只自选股")
    
    # 2. 初始化数据管理器
    print("\n🔌 初始化 THS 数据管理器...")
    manager = DatabaseDataManager()
    print("   ✅ 已连接")
    
    # 3. 批量同步
    print("\n📊 开始批量同步全量历史数据...")
    print("-" * 80)
    
    results = []
    total_start = datetime.now()
    
    for i, (symbol, name) in enumerate(stocks, 1):
        print(f"\n[{i:3d}/{len(stocks)}] {name} ({symbol})")
        print("-" * 60)
        
        try:
            # 同步5年历史数据
            count = manager.sync_symbol(symbol, years=5)
            
            # 验证
            df = manager.get_stock_data(symbol, '2020-01-01', '2026-12-31')
            
            result = {
                'symbol': symbol,
                'name': name,
                'synced': count,
                'in_db': len(df),
                'start': df['date'].min() if not df.empty else None,
                'end': df['date'].max() if not df.empty else None
            }
            results.append(result)
            
            print(f"   ✅ 同步完成: {count} 条")
            if not df.empty:
                print(f"   📅 数据范围: {df['date'].min()} ~ {df['date'].max()}")
                
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            results.append({'symbol': symbol, 'name': name, 'error': str(e)})
        
        # 每10只显示进度
        if i % 10 == 0:
            elapsed = (datetime.now() - total_start).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            print(f"\n   📊 进度: {i}/{len(stocks)} | 速率: {rate:.2f}只/秒")
    
    manager.close()
    
    # 4. 统计结果
    total_elapsed = (datetime.now() - total_start).total_seconds()
    total_synced = sum(r.get('synced', 0) for r in results if 'synced' in r)
    success = sum(1 for r in results if 'synced' in r)
    failed = sum(1 for r in results if 'error' in r)
    
    print("\n" + "=" * 80)
    print("📈 同步结果统计")
    print("=" * 80)
    print(f"\n总股票数: {len(stocks)}")
    print(f"✅ 成功: {success} 只")
    print(f"❌ 失败: {failed} 只")
    print(f"📥 总同步: {total_synced:,} 条记录")
    print(f"⏱️  耗时: {total_elapsed:.1f} 秒 ({total_elapsed/60:.1f} 分钟)")
    
    if failed > 0:
        print(f"\n⚠️  失败列表:")
        for r in results:
            if 'error' in r:
                print(f"   {r['symbol']} ({r['name']}): {r['error'][:50]}")
    
    print("\n" + "=" * 80)
    print("✅ 自选股全量同步完成!")
    print("=" * 80)

if __name__ == '__main__':
    main()
