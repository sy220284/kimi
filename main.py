#!/usr/bin/env python3
"""
智能体量化分析系统 - 主入口 (演示版)
使用优化数据管理器运行分析
"""
import sys
from pathlib import Path

import argparse
import time
from datetime import datetime

from data.optimized_data_manager import get_optimized_data_manager


def print_banner():
    """打印系统横幅"""
    print("="*80)
    print("🤖 智能体量化分析系统")
    print("="*80)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()


def run_data_analysis(symbols):
    """运行数据分析"""
    print("📊 运行数据分析...")
    print("-"*60)

    data_mgr = get_optimized_data_manager()

    for symbol in symbols:
        print(f"\n🔍 分析 {symbol}...")
        try:
            df = data_mgr.get_stock_data(symbol)

            if df is None or df.empty:
                print("  ⚠️ 无数据")
                continue

            # 基础统计
            print(f"  ✅ 数据条数: {len(df)}")
            print(f"  📅 时间范围: {df['date'].min()} ~ {df['date'].max()}")
            print(f"  📈 价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
            print(f"  📊 平均成交量: {df['volume'].mean():.0f}")

        except Exception as e:
            print(f"  ❌ 分析失败: {e}")


def run_indicator_analysis(symbols):
    """运行指标分析"""
    print("\n📈 运行技术指标分析...")
    print("-"*60)

    data_mgr = get_optimized_data_manager()

    for symbol in symbols:
        print(f"\n🔍 分析 {symbol}...")
        try:
            df = data_mgr.get_stock_data(symbol)

            if df is None or df.empty:
                print("  ⚠️ 无数据")
                continue

            # 计算指标
            print("  📊 计算技术指标...")
            df = data_mgr.calculate_ma(df, 20)
            df = data_mgr.calculate_ma(df, 60)
            df = data_mgr.calculate_returns(df)
            df = data_mgr.calculate_rsi(df, 14)

            latest = df.iloc[-1]
            print("  ✅ 最新数据:")
            print(f"     日期: {latest['date']}")
            print(f"     收盘价: {latest['close']:.2f}")
            print(f"     MA20: {latest.get('ma20', 'N/A')}")
            print(f"     MA60: {latest.get('ma60', 'N/A')}")
            print(f"     RSI14: {latest.get('rsi14', 'N/A')}")

        except Exception as e:
            print(f"  ❌ 分析失败: {e}")


def run_batch_analysis():
    """运行批量分析"""
    print("\n🔄 运行批量统计分析...")
    print("-"*60)

    data_mgr = get_optimized_data_manager()
    df_all = data_mgr.load_all_data()

    # 统计
    symbols = df_all['symbol'].unique()
    print(f"  📊 股票总数: {len(symbols)}")
    print(f"  📈 总记录数: {len(df_all):,}")
    print(f"  📅 时间跨度: {df_all['date'].min()} ~ {df_all['date'].max()}")

    # 按板块统计
    print("\n  📊 板块分布:")
    sectors = {
        '科创板': df_all[df_all['symbol'].str.startswith('688', na=False)]['symbol'].nunique(),
        '创业板': df_all[df_all['symbol'].str.startswith('300', na=False)]['symbol'].nunique(),
        '上海主板': df_all[df_all['symbol'].str.startswith('60', na=False)]['symbol'].nunique(),
        '深圳主板': df_all[df_all['symbol'].str.startswith('00', na=False)]['symbol'].nunique(),
    }
    for sector, count in sectors.items():
        if count > 0:
            print(f"     {sector}: {count}只")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='智能体量化分析系统')
    parser.add_argument('--mode', type=str, default='demo',
                       choices=['demo', 'data', 'tech', 'batch', 'full'],
                       help='运行模式')
    parser.add_argument('--symbols', type=str, nargs='+',
                       default=['000001', '600519', '000858', '002594'],
                       help='股票代码列表')

    args = parser.parse_args()

    # 打印横幅
    print_banner()

    # 预加载数据
    print("📦 预加载数据到内存...")
    start_time = time.time()
    data_mgr = get_optimized_data_manager()
    data_mgr.load_all_data()
    load_time = time.time() - start_time
    print(f"⏱️  数据加载耗时: {load_time:.2f}s\n")

    # 根据模式运行
    if args.mode in ['demo', 'data', 'full']:
        run_data_analysis(args.symbols)

    if args.mode in ['demo', 'tech', 'full']:
        run_indicator_analysis(args.symbols)

    if args.mode in ['demo', 'batch', 'full']:
        run_batch_analysis()

    # 总结
    total_time = time.time() - start_time
    print("\n" + "="*80)
    print("📊 运行总结")
    print("="*80)
    print(f"总耗时: {total_time:.2f}s")
    print(f"分析股票: {len(args.symbols)} 只")
    print(f"运行模式: {args.mode}")
    print("="*80)
    print("\n✅ 智能体系统运行完成!")


if __name__ == '__main__':
    main()
