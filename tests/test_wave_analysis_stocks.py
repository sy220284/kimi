#!/usr/bin/env python3
"""
波浪分析实战 - 中青旅、海得控制、天下秀、森源电气
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from data import ThsAdapter
from analysis.wave import UnifiedWaveAnalyzer
import pandas as pd


def analyze_stock(symbol: str, name: str, adapter: ThsAdapter, detector: UnifiedWaveAnalyzer):
    """分析单只股票的波浪形态"""
    print(f"\n{'='*70}")
    print(f"📊 {name} ({symbol})")
    print('='*70)
    
    try:
        # 1. 获取最近3个月数据（聚焦近期走势）
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # 3个月
        start_year = start_date.year
        end_year = end_date.year
        
        print(f"\n1. 获取最近3个月数据 ({start_date.strftime('%Y-%m')} 至 {end_date.strftime('%Y-%m')})...")
        df = adapter.get_full_history(symbol, start_year=start_year, end_year=end_year)
        
        if df.empty:
            print("   ✗ 无数据")
            return None
        
        # 过滤最近6个月数据
        df['date'] = pd.to_datetime(df['date'])
        df = df[df['date'] >= start_date].copy()
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
        
        if df.empty:
            print("   ✗ 过滤后无数据")
            return None
        
        print(f"   ✓ 获取 {len(df)} 条数据")
        print(f"   数据范围: {df['date'].min()} ~ {df['date'].max()}")
        print(f"   最新价格: {df['close'].iloc[-1]:.2f}")
        
        # 2. 波浪检测
        print("\n2. 波浪形态检测...")
        signal = detector.detect(symbol, df)
        
        if not signal:
            print("   - 未识别到明确波浪形态")
            return None
        
        pattern = signal.wave_pattern
        print(f"   ✓ 检测到 {pattern.wave_type.value} 波浪")
        print(f"   方向: {'上升' if pattern.direction.value == 'up' else '下降'}")
        print(f"   置信度: {pattern.confidence:.2%}")
        print(f"   波浪数量: {len(pattern.points)}")
        
        # 3. 波浪详情
        print("\n3. 波浪详情:")
        for point in pattern.points:
            wave_type = "波峰📈" if point.ispeak else ("波谷📉" if point.is_trough else "-")
            print(f"   {point.wave_num}: {point.date} - {point.price:.2f} {wave_type}")
        
        # 4. 交易信号
        print("\n4. 交易信号:")
        print(f"   信号类型: {signal.signal_type.upper()}")
        print(f"   分析日期: {signal.analysis_date}")
        print(f"   理由: {signal.reason}")
        
        if signal.target_price:
            current_price = df['close'].iloc[-1]
            potential = (signal.target_price - current_price) / current_price * 100
            print(f"   目标价: {signal.target_price:.2f} ({potential:+.2f}%)")
        
        if signal.stop_loss:
            print(f"   止损价: {signal.stop_loss:.2f}")
        
        # 5. 统计数据
        print("\n5. 近期统计数据:")
        recent = df.tail(20)
        print(f"   20日涨幅: {(recent['close'].iloc[-1] / recent['close'].iloc[0] - 1) * 100:.2f}%")
        print(f"   20日最高: {recent['high'].max():.2f}")
        print(f"   20日最低: {recent['low'].min():.2f}")
        print(f"   20日均量: {recent['volume'].mean():,.0f}")
        
        return signal
        
    except Exception as e:
        print(f"   ✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """主函数"""
    print("="*70)
    print("🌊 Elliott Wave 波浪分析 - 实战分析")
    print("="*70)
    
    # 初始化适配器和检测器
    adapter = ThsAdapter({'enabled': True, 'timeout': 30})
    detector = UnifiedWaveAnalyzer(
        min_wave_length=3,
        max_wave_length=100,
        confidence_threshold=0.4,
        peak_window=2,
        min_change_pct=1.5
    )
    
    # 分析股票列表
    stocks = [
        ("600138", "中青旅"),
        ("002184", "海得控制"),
        ("600556", "天下秀"),
        ("002358", "森源电气"),
    ]
    
    results = []
    
    for symbol, name in stocks:
        signal = analyze_stock(symbol, name, adapter, detector)
        if signal:
            results.append({
                'name': name,
                'symbol': symbol,
                'signal': signal.signal_type,
                'confidence': signal.confidence,
                'wave_type': signal.wave_pattern.wave_type.value,
                'target': signal.target_price,
            })
    
    # 汇总
    print("\n" + "="*70)
    print("📋 分析汇总")
    print("="*70)
    
    if results:
        summary_df = pd.DataFrame(results)
        print("\n" + summary_df.to_string(index=False))
        
        # 买入信号
        buysignals = [r for r in results if r['signal'] == 'buy']
        if buysignals:
            print(f"\n✅ 买入信号 ({len(buysignals)}个):")
            for s in buysignals:
                print(f"   {s['name']}({s['symbol']}) - 置信度: {s['confidence']:.2%}")
        
        # 卖出信号
        sellsignals = [r for r in results if r['signal'] == 'sell']
        if sellsignals:
            print(f"\n❌ 卖出信号 ({len(sellsignals)}个):")
            for s in sellsignals:
                print(f"   {s['name']}({s['symbol']}) - 置信度: {s['confidence']:.2%}")
        
        # 观望信号
        watchsignals = [r for r in results if r['signal'] not in ['buy', 'sell']]
        if watchsignals:
            print(f"\n👀 观望信号 ({len(watchsignals)}个):")
            for s in watchsignals:
                print(f"   {s['name']}({s['symbol']}) - {s['signal']}")
    else:
        print("\n未发现有效波浪信号")
    
    print("\n" + "="*70)
    print("分析完成")
    print("="*70)


if __name__ == "__main__":
    main()
