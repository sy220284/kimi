#!/usr/bin/env python3
"""
波浪分析实战 - 多周期分析 (专业版)
中青旅、海得控制、天下秀、森源电气
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter
from analysis.wave.wave_detector import WaveDetector
import pandas as pd
from datetime import datetime, timedelta


def analyze_single_period(symbol: str, name: str, df: pd.DataFrame, detector: WaveDetector, period_name: str):
    """分析单个周期"""
    if df.empty or len(df) < 10:
        return None
    
    signal = detector.detect(symbol, df)
    if not signal:
        return None
    
    pattern = signal.wave_pattern
    return {
        'period': period_name,
        'wave_type': pattern.wave_type.value,
        'direction': pattern.direction.value,
        'confidence': pattern.confidence,
        'signal': signal.signal_type,
        'latest_wave': pattern.points[-1].wave_num if pattern.points else None,
        'latest_date': pattern.points[-1].date if pattern.points else None,
        'latest_price': pattern.points[-1].price if pattern.points else None,
        'current_price': df['close'].iloc[-1],
        'target': signal.target_price,
        'stop_loss': signal.stop_loss,
        'reason': signal.reason,
        'fib_ratios': pattern.fib_ratios,
    }


def analyze_stock_multi_timeframe(symbol: str, name: str, adapter: ThsAdapter):
    """多周期波浪分析 - 专业版"""
    print(f"\n{'='*80}")
    print(f"📊 {name} ({symbol}) - 多周期波浪分析")
    print('='*80)
    
    # 获取完整数据 (最近1年)
    end_year = datetime.now().year
    start_year = end_year - 1
    df_full = adapter.get_full_history(symbol, start_year=start_year, end_year=end_year)
    
    if df_full.empty:
        print("✗ 无数据")
        return None
    
    df_full['date'] = pd.to_datetime(df_full['date'])
    
    # 不同周期使用不同参数
    end_date = datetime.now()
    periodsconfig = {
        '短期(1月)': {
            'days': 30,
            'params': {'atr_period': 7, 'atr_mult': 0.3, 'confidence_threshold': 0.4}
        },
        '中期(3月)': {
            'days': 90,
            'params': {'atr_period': 14, 'atr_mult': 0.5, 'confidence_threshold': 0.5}
        },
        '长期(1年)': {
            'days': 365,
            'params': {'atr_period': 14, 'atr_mult': 0.7, 'confidence_threshold': 0.5}
        },
    }
    
    results = []
    
    for period_name, config in periodsconfig.items():
        # 过滤数据
        start_date = end_date - timedelta(days=config['days'])
        df_period = df_full[df_full['date'] >= start_date].copy()
        
        if len(df_period) < 15:
            continue
        
        df_period['date'] = df_period['date'].dt.strftime('%Y-%m-%d')
        
        # 创建该周期的检测器
        p = config['params']
        detector = WaveDetector(
            confidence_threshold=p['confidence_threshold'],
            atr_period=p['atr_period'],
            atr_mult=p['atr_mult']
        )
        
        result = analyze_single_period(symbol, name, df_period, detector, period_name)
        if result:
            results.append(result)
    
    if not results:
        print("未识别到波浪形态")
        return None
    
    # 打印结果
    current_price = df_full['close'].iloc[-1]
    print(f"\n📈 当前价格: ¥{current_price:.2f}")
    print(f"📅 数据范围: {df_full['date'].min().strftime('%Y-%m-%d')} ~ {df_full['date'].max().strftime('%Y-%m-%d')}")
    
    print(f"\n{'─'*80}")
    print("各周期波浪结构:")
    print('─'*80)
    
    for r in results:
        direction_icon = "📈" if r['direction'] == 'up' else "📉"
        signal_icon = {
            'buy': '✅ BUY',
            'sell': '❌ SELL',
            'watch': '👀 WATCH',
            'hold': '⏸️ HOLD',
        }.get(r['signal'], r['signal'])
        
        print(f"\n【{r['period']}】置信度: {r['confidence']:.1%}")
        print(f"  形态: {r['wave_type'].upper()} {direction_icon}")
        print(f"  信号: {signal_icon}")
        print(f"  最新浪: {r['latest_wave']} @ {r['latest_date']} ¥{r['latest_price']:.2f}")
        
        if r['target']:
            potential = (r['target'] - current_price) / current_price * 100
            print(f"  目标: ¥{r['target']:.2f} ({potential:+.1f}%) | 止损: ¥{r['stop_loss']:.2f}")
        
        # 显示斐波那契比例
        if r['fib_ratios']:
            fib_str = ', '.join([f"{k}={v:.2f}" for k, v in list(r['fib_ratios'].items())[:3]])
            print(f"  斐波那契: {fib_str}")
    
    # 多周期综合判断
    print(f"\n{'='*80}")
    print("📊 多周期综合判断")
    print('='*80)
    
    analysis = synthesize_timeframes(results, current_price)
    print(f"\n{analysis}")
    
    return results


def synthesize_timeframes(results: list, current_price: float) -> str:
    """综合多周期判断"""
    signals = [r['signal'] for r in results]
    directions = [r['direction'] for r in results]
    confidences = [r['confidence'] for r in results]
    
    buy_count = sum(1 for s in signals if 'buy' in s)
    sell_count = sum(1 for s in signals if 'sell' in s)
    up_count = sum(1 for d in directions if d == 'up')
    down_count = sum(1 for d in directions if d == 'down')
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    output = []
    output.append(f"📈 信号统计: 买入{buy_count}个 | 卖出{sell_count}个 | 平均置信度{avg_confidence:.1%}")
    output.append(f"📉 方向统计: 上升{up_count}个 | 下降{down_count}个")
    
    # 趋势一致性
    output.append("\n🎯 趋势一致性:")
    if up_count == len(results) and len(results) >= 2:
        output.append("  ✅ 全周期共振上升 - 强势看涨")
    elif down_count == len(results) and len(results) >= 2:
        output.append("  ⚠️ 全周期共振下降 - 强势看跌")
    elif up_count > down_count:
        output.append("  📈 中长期向上，短期可能有回调")
    elif down_count > up_count:
        output.append("  📉 中长期向下，短期可能有反弹")
    else:
        output.append("  ⚖️ 多空分歧，震荡格局")
    
    # 信号一致性
    output.append("\n💡 操作建议:")
    if buy_count >= 2 and sell_count == 0:
        output.append("  🔥 多周期买入共振 - 强烈建议买入")
    elif sell_count >= 2 and buy_count == 0:
        output.append("  ⚠️ 多周期卖出共振 - 强烈建议卖出")
    elif buy_count >= 1 and up_count >= 2:
        output.append("  ✅ 整体看多，可逢低买入")
    elif sell_count >= 1 and down_count >= 2:
        output.append("  ❌ 整体看空，建议减仓")
    else:
        output.append("  👀 信号混杂，建议观望")
    
    # 浪末警告
    latest_waves = [r['latest_wave'] for r in results if r['latest_wave']]
    if '5' in latest_waves or 'C' in latest_waves:
        output.append("\n⚠️ 风险提示:")
        output.append("  多周期显示处于浪末阶段(5浪/C浪)，可能面临趋势转折")
    
    return '\n'.join(output)


def main():
    """主函数"""
    print("="*80)
    print("🌊 Elliott Wave 多周期波浪分析 (专业版)")
    print("="*80)
    print("\n分析周期: 短期(1月) | 中期(3月) | 长期(1年)")
    print("核心算法: ATR自适应ZigZag + 严格规则验证")
    
    adapter = ThsAdapter({'enabled': True, 'timeout': 30})
    
    stocks = [
        ("600138", "中青旅"),
        ("002184", "海得控制"),
        ("600556", "天下秀"),
        ("002358", "森源电气"),
    ]
    
    all_results = {}
    for symbol, name in stocks:
        results = analyze_stock_multi_timeframe(symbol, name, adapter)
        if results:
            all_results[symbol] = {'name': name, 'results': results}
    
    # 最终汇总
    print("\n" + "="*80)
    print("📋 四只股票多周期汇总")
    print("="*80)
    
    for symbol, data in all_results.items():
        name = data['name']
        results = data['results']
        
        signals = [r['signal'] for r in results]
        directions = [r['direction'] for r in results]
        
        buy_count = sum(1 for s in signals if 'buy' in s)
        sell_count = sum(1 for s in signals if 'sell' in s)
        up_count = sum(1 for d in directions if d == 'up')
        
        trend = "📈" if up_count >= 2 else "📉"
        
        if buy_count >= 2:
            rating = "🔥 强烈买入"
        elif sell_count >= 2:
            rating = "⚠️ 强烈卖出"
        elif buy_count >= 1:
            rating = "✅ 买入"
        elif sell_count >= 1:
            rating = "❌ 卖出"
        else:
            rating = "👀 观望"
        
        print(f"\n{name}({symbol}): {trend} {rating}")
        for r in results:
            sig_emoji = {'buy': '✅', 'sell': '❌', 'watch': '👀'}.get(r['signal'], '•')
            print(f"  {r['period']}: {r['wave_type'].upper()}-{r['latest_wave']} {sig_emoji} {r['confidence']:.0%}")


if __name__ == "__main__":
    main()
