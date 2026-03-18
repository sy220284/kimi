#!/usr/bin/env python3
"""
波浪分析 - 历史数据验证与重新分析
验证已获取的历史数据完整性，重新进行多周期分析
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter
from analysis.wave import UnifiedWaveAnalyzer
import pandas as pd
from datetime import timedelta


def validate_history(symbol, name, adapter):
    """验证历史数据完整性"""
    print(f"\n{'='*80}")
    print(f"📊 {name} ({symbol}) - 历史数据验证")
    print('='*80)
    
    # 获取完整历史
    df = adapter.get_full_history(symbol, start_year=2020, end_year=2026)
    
    if df.empty:
        print("❌ 无数据")
        return None
    
    df['date'] = pd.to_datetime(df['date'])
    
    # 数据统计
    print("\n📈 数据概况:")
    print(f"  总记录数: {len(df)}")
    print(f"  日期范围: {df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')}")
    print(f"  时间跨度: {(df['date'].max() - df['date'].min()).days} 天")
    
    # 按年统计
    df['year'] = df['date'].dt.year
    yearly = df.groupby('year').size()
    print("\n📅 按年分布:")
    for year, count in yearly.items():
        print(f"  {year}: {count} 条")
    
    # 检查数据质量
    print("\n🔍 数据质量检查:")
    print(f"  收盘价范围: ¥{df['close'].min():.2f} ~ ¥{df['close'].max():.2f}")
    print(f"  成交量范围: {df['volume'].min():,.0f} ~ {df['volume'].max():,.0f}")
    print(f"  缺失值: 收盘价{df['close'].isna().sum()}, 成交量{df['volume'].isna().sum()}")
    
    # 最新数据
    latest = df.iloc[-1]
    print(f"\n📌 最新数据 ({latest['date'].strftime('%Y-%m-%d')}):")
    print(f"  开盘: ¥{latest['open']:.2f}, 最高: ¥{latest['high']:.2f}")
    print(f"  最低: ¥{latest['low']:.2f}, 收盘: ¥{latest['close']:.2f}")
    print(f"  成交量: {latest['volume']:,.0f}")
    
    return df


def analyze_all_timeframes(symbol, name, df_full):
    """全周期分析 - 从日线到年线"""
    if df_full is None or df_full.empty:
        return
    
    print(f"\n{'─'*80}")
    print("🌊 波浪形态分析 (多周期)")
    print('─'*80)
    
    df_full = df_full.copy()
    df_full['date'] = pd.to_datetime(df_full['date'])
    
    end_date = df_full['date'].max()
    current_price = df_full['close'].iloc[-1]
    
    # 定义不同周期
    periods = {
        '近1月': (30, {'atr_period': 5, 'atr_mult': 0.15, 'threshold': 0.3}),
        '近3月': (90, {'atr_period': 7, 'atr_mult': 0.25, 'threshold': 0.35}),
        '近6月': (180, {'atr_period': 10, 'atr_mult': 0.35, 'threshold': 0.4}),
        '近1年': (365, {'atr_period': 14, 'atr_mult': 0.5, 'threshold': 0.45}),
        '近2年': (730, {'atr_period': 14, 'atr_mult': 0.6, 'threshold': 0.5}),
        '全部历史': (9999, {'atr_period': 20, 'atr_mult': 0.7, 'threshold': 0.5}),
    }
    
    results = []
    
    for period_name, (days, params) in periods.items():
        # 过滤数据
        if days == 9999:
            df_period = df_full.copy()
        else:
            start_date = end_date - timedelta(days=days)
            df_period = df_full[df_full['date'] >= start_date].copy()
        
        if len(df_period) < 20:
            continue
        
        df_period['date'] = df_period['date'].dt.strftime('%Y-%m-%d')
        
        # 创建检测器
        detector = UnifiedWaveAnalyzer(
            confidence_threshold=params['threshold'],
            atr_period=params['atr_period'],
            atr_mult=params['atr_mult']
        )
        
        signal = detector.detect(symbol, df_period)
        
        if signal:
            pattern = signal.wave_pattern
            direction_icon = "📈" if pattern.direction.value == 'up' else "📉"
            
            print(f"\n【{period_name}】{direction_icon} 置信度: {signal.confidence:.1%}")
            print(f"  形态: {pattern.wave_type.value.upper()}")
            print(f"  点位: {[p.wave_num for p in pattern.points if p.wave_num]}")
            
            # 最新浪信息
            latest_point = pattern.points[-1]
            print(f"  最新浪: {latest_point.wave_num} @ {latest_point.date} ¥{latest_point.price:.2f}")
            
            # 目标价
            if signal.target_price:
                pnl = (signal.target_price - current_price) / current_price * 100
                print(f"  目标: ¥{signal.target_price:.2f} ({pnl:+.1f}%)")
            
            # 斐波那契比例
            if pattern.fib_ratios:
                fib_info = ', '.join([f"{k}={v:.2f}" for k, v in list(pattern.fib_ratios.items())[:2]])
                print(f"  斐波那契: {fib_info}")
            
            # 指导原则评分
            if pattern.guideline_scores:
                passed = sum(1 for v in pattern.guideline_scores.values() if v > 0)
                total = len(pattern.guideline_scores)
                print(f"  规则验证: {passed}/{total} 项通过")
            
            results.append({
                'period': period_name,
                'wave_type': pattern.wave_type.value,
                'direction': pattern.direction.value,
                'confidence': signal.confidence,
                'latest_wave': latest_point.wave_num,
                'points_count': len(pattern.points)
            })
    
    # 汇总
    if results:
        print(f"\n{'='*80}")
        print("📋 分析汇总")
        print('='*80)
        
        up_count = sum(1 for r in results if r['direction'] == 'up')
        down_count = len(results) - up_count
        avg_conf = sum(r['confidence'] for r in results) / len(results)
        
        print(f"识别到波浪的周期: {len(results)} 个")
        print(f"方向统计: 📈 {up_count} 个上升 | 📉 {down_count} 个下降")
        print(f"平均置信度: {avg_conf:.1%}")
        
        # 趋势一致性
        if up_count == len(results):
            print("\n✅ 全周期共振上升 - 趋势强劲")
        elif down_count == len(results):
            print("\n⚠️ 全周期共振下降 - 趋势弱势")
        elif up_count > down_count:
            print("\n📈 整体偏强，短期可能有波动")
        else:
            print("\n📉 整体偏弱，关注反弹机会")
    else:
        print("\n⚠️ 未在任何周期识别到明确波浪形态")
    
    return results


def main():
    print("="*80)
    print("🔍 波浪分析 - 历史数据验证与全周期重新分析")
    print("="*80)
    
    adapter = ThsAdapter({'enabled': True, 'timeout': 30})
    
    stocks = [
        ("600138", "中青旅"),
        ("002184", "海得控制"),
        ("600556", "天下秀"),
        ("002358", "森源电气"),
    ]
    
    all_results = {}
    
    for symbol, name in stocks:
        df = validate_history(symbol, name, adapter)
        if df is not None:
            results = analyze_all_timeframes(symbol, name, df)
            all_results[symbol] = {'name': name, 'df': df, 'results': results}
    
    # 最终对比
    print("\n" + "="*80)
    print("📊 四只股票全周期对比")
    print("="*80)
    
    for symbol, data in all_results.items():
        name = data['name']
        results = data['results']
        current_price = data['df']['close'].iloc[-1]
        
        print(f"\n{name}({symbol}) - 当前: ¥{current_price:.2f}")
        
        if results:
            for r in results:
                icon = "📈" if r['direction'] == 'up' else "📉"
                print(f"  {r['period']:8s} | {icon} {r['wave_type']:10s} | 置信度 {r['confidence']:.0%} | 最新浪 {r['latest_wave']}")
        else:
            print("  未识别到波浪形态")
    
    print("\n" + "="*80)
    print("分析完成")


if __name__ == "__main__":
    main()
