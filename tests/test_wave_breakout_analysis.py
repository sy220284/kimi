#!/usr/bin/env python3
"""
波浪分析 - 突破结构后的浪型识别
多时间框架: 日线 -> 周线 -> 月线
识别延长浪、失败浪、或更高级别波浪
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter
from analysis.wave.wave_detector import WaveDetector
import pandas as pd


def resample_to_weekly(df_daily):
    """日线转周线"""
    df = df_daily.copy()
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    weekly = df.resample('W').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    weekly.reset_index(inplace=True)
    weekly['date'] = weekly['date'].dt.strftime('%Y-%m-%d')
    return weekly


def resample_to_monthly(df_daily):
    """日线转月线"""
    df = df_daily.copy()
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    monthly = df.resample('ME').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    monthly.reset_index(inplace=True)
    monthly['date'] = monthly['date'].dt.strftime('%Y-%m-%d')
    return monthly


def analyze_post_breakout(df_daily, symbol, name):
    """分析突破后的浪型"""
    print(f"\n{'='*80}")
    print(f"🔍 {name} ({symbol}) - 突破结构分析")
    print('='*80)
    
    current_price = df_daily['close'].iloc[-1]
    print(f"\n📈 当前价格: ¥{current_price:.2f}")
    
    # 生成多时间框架数据
    df_weekly = resample_to_weekly(df_daily)
    df_monthly = resample_to_monthly(df_daily)
    
    print("\n📊 数据转换:")
    print(f"  日线: {len(df_daily)} 条")
    print(f"  周线: {len(df_weekly)} 条 ({len(df_weekly)//52}年)")
    print(f"  月线: {len(df_monthly)} 条 ({len(df_monthly)//12}年)")
    
    # 不同时间框架使用不同参数
    timeframes = {
        '月线(长期结构)': (df_monthly, {'atr_period': 3, 'atr_mult': 0.5, 'threshold': 0.4}),
        '周线(中期结构)': (df_weekly, {'atr_period': 5, 'atr_mult': 0.4, 'threshold': 0.4}),
        '日线(短期结构)': (df_daily, {'atr_period': 14, 'atr_mult': 0.5, 'threshold': 0.5}),
    }
    
    all_patterns = []
    
    for tf_name, (df_tf, params) in timeframes.items():
        if len(df_tf) < 10:
            continue
        
        detector = WaveDetector(
            confidence_threshold=params['threshold'],
            atr_period=params['atr_period'],
            atr_mult=params['atr_mult']
        )
        
        signal = detector.detect(symbol, df_tf)
        
        print(f"\n{'─'*60}")
        print(f"【{tf_name}】")
        print('─'*60)
        
        if signal:
            pattern = signal.wave_pattern
            direction = "📈 上升" if pattern.direction.value == 'up' else "📉 下降"
            
            print(f"  识别到: {pattern.wave_type.value.upper()} {direction}")
            print(f"  置信度: {signal.confidence:.1%}")
            
            # 波浪点位
            points_str = []
            for p in pattern.points:
                if p.wave_num:
                    points_str.append(f"{p.wave_num}@{p.date[-5:]}¥{p.price:.2f}")
            print(f"  波浪点位: {' → '.join(points_str)}")
            
            # 最新浪位置
            latest = pattern.points[-1]
            print(f"  当前位置: 浪{latest.wave_num} @ {latest.date} ¥{latest.price:.2f}")
            
            # 目标价偏离度
            if signal.target_price:
                deviation = (current_price - signal.target_price) / signal.target_price * 100
                print(f"  目标价: ¥{signal.target_price:.2f} (现价偏离: {deviation:+.1f}%)")
                
                if abs(deviation) > 20:
                    print(f"  ⚠️ 警告: 价格已大幅偏离目标价{abs(deviation):.0f}%，原结构可能失效")
            
            all_patterns.append({
                'timeframe': tf_name,
                'wave_type': pattern.wave_type.value,
                'direction': pattern.direction.value,
                'confidence': signal.confidence,
                'latest_wave': latest.wave_num,
                'latest_price': latest.price,
                'target': signal.target_price,
                'current': current_price,
                'deviation': (current_price - signal.target_price) / signal.target_price * 100 if signal.target_price else 0
            })
        else:
            print("  ⚠️ 未识别到明确波浪形态")
    
    return all_patterns


def interpret_breakout(patterns, symbol, name):
    """解读突破后的浪型"""
    if not patterns:
        return
    
    print(f"\n{'='*80}")
    print(f"🧩 突破结构解读 - {name}({symbol})")
    print('='*80)
    
    current_price = patterns[0]['current']
    
    # 1. 检查是否所有目标都被突破
    all_broken = all(abs(p['deviation']) > 15 for p in patterns if p['target'])
    
    if all_broken:
        print("\n🔴 结构突破确认")
        print("  所有时间框架的目标价均已被突破")
        print("  这可能意味着:")
        
        # 分析可能的浪型
        directions = [p['direction'] for p in patterns]
        
        if len(set(directions)) == 1 and directions[0] == 'up':
            print("\n  【情景1: 延长浪 (Wave Extension)】")
            print("  原波浪的第3浪或第5浪发生延长")
            print("  特征: 价格远超预期目标，但趋势继续")
            print("  应对: 等待子浪完成，不宜逆势做空")
            
            print("\n  【情景2: 更高级别推动浪】")
            print("  当前处于更大周期的第3浪或第5浪")
            print("  特征: 月线/周线共振向上")
            print("  应对: 顺势持有，目标重新计算")
            
        elif len(set(directions)) == 1 and directions[0] == 'down':
            print("\n  【情景: 延长下跌浪】")
            print("  下跌第3浪或第5浪延长")
            print("  应对: 切勿抄底，等待止跌信号")
            
        else:
            print("\n  【情景3: 时间框架冲突】")
            print("  大周期向上，小周期向下，或反之")
            print("  应对: 以更大周期方向为主")
    
    # 2. 检查浪型位置
    print("\n📍 当前浪型位置分析:")
    
    for p in patterns:
        wave = p['latest_wave']
        tf = p['timeframe'].split('(')[0]
        
        if wave in ['3', 'C']:
            print(f"  {tf}: 浪{wave} - 主趋势浪，动能最强")
        elif wave in ['5']:
            print(f"  {tf}: 浪5 - 推动浪末端，警惕转折")
        elif wave in ['A']:
            print(f"  {tf}: A浪 - 调整开始")
        elif wave in ['B']:
            print(f"  {tf}: B浪 - 调整中继")
        elif wave in ['1', '2', '4']:
            print(f"  {tf}: 浪{wave} - 推动浪早期或调整")
    
    # 3. 给出操作建议
    print("\n💡 操作建议:")
    
    # 找最大周期的方向
    monthly = next((p for p in patterns if '月线' in p['timeframe']), None)
    weekly = next((p for p in patterns if '周线' in p['timeframe']), None)
    daily = next((p for p in patterns if '日线' in p['timeframe']), None)
    
    if monthly and weekly:
        if monthly['direction'] == weekly['direction']:
            trend = "上升" if monthly['direction'] == 'up' else "下降"
            print(f"  ✅ 月线与周线共振{ trend }，{trend}趋势确立")
            
            if monthly['direction'] == 'up':
                if monthly['latest_wave'] == '3':
                    print("  🚀 处于大周期第3浪，主升浪进行中，可追涨")
                elif monthly['latest_wave'] == '5':
                    print("  ⚠️ 处于大周期第5浪，注意止盈")
                else:
                    print("  📈 中长期向上，逢低买入")
            else:
                print("  📉 中长期向下，反弹减仓")
        else:
            print("  ⚠️ 月线与周线方向冲突，震荡格局")
            print("  建议观望，等待方向明确")


def main():
    print("="*80)
    print("🔍 突破结构后的浪型识别 (多时间框架)")
    print("="*80)
    print("\n分析方法:")
    print("  1. 日线 -> 周线 -> 月线 逐级分析")
    print("  2. 识别突破后的真实浪型")
    print("  3. 判断是延长浪、失败浪还是更大级别波浪")
    
    adapter = ThsAdapter({'enabled': True})
    
    # 重点分析突破严重的股票
    stocks = [
        ("002358", "森源电气", "⚠️ 目标偏离-40%~-50%"),
        ("600556", "天下秀", "⚠️ 目标偏离-20%~-30%"),
        ("002184", "海得控制", "✅ 结构健康"),
        ("600138", "中青旅", "✅ 结构健康"),
    ]
    
    for symbol, name, status in stocks:
        print(f"\n\n{'#'*80}")
        print(f"# {name} ({symbol}) - {status}")
        print('#'*80)
        
        df = adapter.get_full_history(symbol, start_year=2020, end_year=2026)
        if df.empty:
            continue
        
        patterns = analyze_post_breakout(df, symbol, name)
        interpret_breakout(patterns, symbol, name)
    
    print("\n\n" + "="*80)
    print("分析完成")


if __name__ == "__main__":
    main()
