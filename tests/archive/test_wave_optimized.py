#!/usr/bin/env python3
"""
波浪分析 - 优化版多周期 (降低阈值以适应短周期)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter
from analysis.wave.wave_detector import WaveDetector
import pandas as pd
from datetime import datetime, timedelta


def analyze_with_detector(symbol, name, df, detector, period_name):
    """使用指定检测器分析"""
    if len(df) < 10:
        return None
    
    signal = detector.detect(symbol, df)
    if not signal:
        return None
    
    return {
        'period': period_name,
        'wave_type': signal.wave_pattern.wave_type.value,
        'direction': signal.wave_pattern.direction.value,
        'confidence': signal.confidence,
        'signal': signal.signal_type,
        'latest_wave': signal.wave_pattern.points[-1].wave_num,
        'latest_date': signal.wave_pattern.points[-1].date,
        'latest_price': signal.wave_pattern.points[-1].price,
        'target': signal.target_price,
        'stop_loss': signal.stop_loss,
    }


def main():
    print("="*80)
    print("🌊 多周期波浪分析 - 优化版 (适应短周期)")
    print("="*80)
    
    adapter = ThsAdapter({'enabled': True})
    
    stocks = [
        ("600138", "中青旅"),
        ("002184", "海得控制"),
        ("600556", "天下秀"),
        ("002358", "森源电气"),
    ]
    
    # 优化参数 - 降低阈值让短周期也能识别
    detectors = {
        '超短期(2周)': WaveDetector(atr_period=5, atr_mult=0.2, confidence_threshold=0.3),
        '短期(1月)': WaveDetector(atr_period=7, atr_mult=0.25, confidence_threshold=0.35),
        '中期(3月)': WaveDetector(atr_period=10, atr_mult=0.4, confidence_threshold=0.4),
        '长期(1年)': WaveDetector(atr_period=14, atr_mult=0.6, confidence_threshold=0.5),
    }
    
    for symbol, name in stocks:
        print(f"\n{'='*80}")
        print(f"📊 {name} ({symbol})")
        print('='*80)
        
        # 获取数据
        df_full = adapter.get_full_history(symbol, start_year=2025, end_year=2026)
        if df_full.empty:
            continue
        
        df_full['date'] = pd.to_datetime(df_full['date'])
        current_price = df_full['close'].iloc[-1]
        print(f"当前价格: ¥{current_price:.2f}")
        
        # 各周期分析
        end_date = datetime.now()
        periods = {
            '超短期(2周)': df_full[df_full['date'] >= end_date - timedelta(days=14)],
            '短期(1月)': df_full[df_full['date'] >= end_date - timedelta(days=30)],
            '中期(3月)': df_full[df_full['date'] >= end_date - timedelta(days=90)],
            '长期(1年)': df_full,
        }
        
        found_any = False
        for period_name, df_period in periods.items():
            if len(df_period) < 10:
                continue
            
            df_copy = df_period.copy()
            df_copy['date'] = df_copy['date'].dt.strftime('%Y-%m-%d')
            
            result = analyze_with_detector(symbol, name, df_copy, detectors[period_name], period_name)
            if result:
                found_any = True
                direction = "📈" if result['direction'] == 'up' else "📉"
                print(f"\n【{period_name}】{direction}")
                print(f"  形态: {result['wave_type'].upper()} | 置信度: {result['confidence']:.0%}")
                print(f"  最新浪: {result['latest_wave']} @ {result['latest_date']} ¥{result['latest_price']:.2f}")
                if result['target']:
                    pnl = (result['target'] - current_price) / current_price * 100
                    print(f"  目标: ¥{result['target']:.2f} ({pnl:+.1f}%)")
        
        if not found_any:
            print("  未识别到波浪形态")
    
    print("\n" + "="*80)
    print("分析完成")


if __name__ == "__main__":
    main()
