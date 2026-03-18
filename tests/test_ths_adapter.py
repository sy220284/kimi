#!/usr/bin/env python3
"""
同花顺(THS)适配器测试脚本
"""
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data.ths_adapter import ThsAdapter


def test_ths_adapter():
    """测试同花顺适配器"""
    print("=" * 60)
    print("同花顺(THS)适配器测试")
    print("=" * 60)

    # 初始化适配器
    config = {
        'enabled': True,
        'timeout': 30
    }

    adapter = ThsAdapter(config)
    print("\n1. 初始化适配器")
    print(f"   数据源类型: {adapter.source_type.value}")
    print(f"   启用状态: {adapter.enabled}")

    # 测试连接
    print("\n2. 测试连接")
    connected = adapter.connect()
    print(f"   连接结果: {'✓ 成功' if connected else '✗ 失败'}")

    if not connected:
        print("   连接失败，终止测试")
        return

    # 测试获取日K线数据
    print("\n3. 测试获取日K线数据")
    test_symbols = [
        ("600519", "贵州茅台"),
        ("000001", "平安银行"),
        ("000300", "沪深300")
    ]

    for symbol, name in test_symbols:
        try:
            print(f"\n   测试 {name}({symbol})...")
            df = adapter.get_daily_kline(
                symbol=symbol,
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            if df.empty:
                print(f"   ✗ {name} - 无数据返回")
            else:
                print(f"   ✓ {name} - 获取 {len(df)} 条数据")
                print(f"     日期范围: {df['date'].min()} ~ {df['date'].max()}")
                print(f"     最新价格: {df['close'].iloc[-1]}")

                # 显示前几行
                if symbol == "600519":
                    print("\n     数据预览:")
                    print(df[['date', 'open', 'high', 'low', 'close', 'volume']].head(5).to_string(index=False))

        except Exception as e:
            print(f"   ✗ {name} - 错误: {e}")

    # 测试获取实时行情
    print("\n4. 测试获取实时行情")
    try:
        quote = adapter.get_realtime_quote("600519")
        print("   ✓ 茅台实时行情:")
        print(f"     日期: {quote.get('date')}")
        print(f"     收盘: {quote.get('close')}")
        print(f"     涨跌: {quote.get('change_pct')}%")
        print(f"     成交: {quote.get('volume')}")
    except Exception as e:
        print(f"   ✗ 获取实时行情失败: {e}")

    # 测试获取指数列表
    print("\n5. 测试获取指数列表")
    try:
        indices = adapter.get_index_list()
        print(f"   ✓ 获取 {len(indices)} 个常用指数")
        print(f"     {indices[['code', 'name']].to_string(index=False)}")
    except Exception as e:
        print(f"   ✗ 获取指数列表失败: {e}")

    # 测试不同K线周期
    print("\n6. 测试不同K线周期")
    periods = ['day', 'week', 'month']
    for period in periods:
        try:
            df = adapter.get_klinedata(
                symbol="600519",
                period=period,
                count=5
            )
            print(f"   ✓ {period}: 获取 {len(df)} 条数据")
        except Exception as e:
            print(f"   ✗ {period}: 错误 - {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_ths_adapter()
