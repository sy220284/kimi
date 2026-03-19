#!/usr/bin/env python3
"""
同花顺(THS)适配器 - 完整功能测试
测试完整历史数据获取
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter


def test_full_history():
    """测试完整历史数据获取"""
    print("=" * 70)
    print("同花顺(THS)适配器 - 完整历史数据测试")
    print("=" * 70)

    config = {
        'enabled': True,
        'timeout': 30,
    }

    adapter = ThsAdapter(config)

    # 测试股票
    test_stocks = [
        ("600519", "贵州茅台"),
        ("000001", "平安银行"),
    ]

    for symbol, name in test_stocks:
        print(f"\n📊 {name}({symbol})")
        print("-" * 70)

        # 1. 测试最近数据
        print("\n1. 获取最近140天数据:")
        try:
            recent_df = adapter.get_daily_kline(symbol, "2024-01-01", "2026-03-16")
            print(f"   ✓ 获取 {len(recent_df)} 条")
            if not recent_df.empty:
                print(f"   范围: {recent_df['date'].min()} ~ {recent_df['date'].max()}")
        except Exception as e:
            print(f"   ✗ 失败: {e}")

        # 2. 测试完整历史数据
        print("\n2. 获取完整历史数据:")
        try:
            # 只获取最近5年的数据以加快测试
            from datetime import datetime
            end_year = datetime.now().year
            start_year = end_year - 4  # 最近5年

            full_df = adapter.get_full_history(symbol, start_year=start_year, end_year=end_year)

            if not full_df.empty:
                print(f"   ✓ 获取 {len(full_df)} 条数据")
                print(f"   完整范围: {full_df['date'].min()} ~ {full_df['date'].max()}")
                print("\n   数据预览 (前3条):")
                cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                print(full_df[cols].head(3).to_string(index=False))
                print("\n   数据预览 (后3条):")
                print(full_df[cols].tail(3).to_string(index=False))
            else:
                print("   ✗ 未获取到数据")
        except Exception as e:
            print(f"   ✗ 失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    test_full_history()
