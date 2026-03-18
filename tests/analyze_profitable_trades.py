"""
分析盈利交易卖出后的股价走势
判断是卖飞了还是卖对了
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from datetime import timedelta
from data import get_db_manager

def get_stockdata_afterexit(symbol, exit_date, days=60):
    """获取卖出后的股价数据"""
    try:
        db_manager = get_db_manager()
        
        # 转换日期格式
        exit_dt = pd.to_datetime(exit_date)
        end_dt = exit_dt + timedelta(days=days)
        
        # 查询后续数据
        query = """
        SELECT date, close, high, low
        FROM marketdata
        WHERE symbol = %s AND date > %s AND date <= %s
        ORDER BY date
        """
        
        result = db_manager.pg.execute(query, params=(symbol, exit_date, end_dt.strftime('%Y-%m-%d')), fetch=True)
        
        if result and len(result) > 0:
            return pd.DataFrame(result)
        return None
    except Exception as e:
        print(f"  获取数据失败 {symbol}: {e}")
        return None

def analyze_profitabletrades():
    """分析盈利交易卖出后的走势"""
    
    # 读取交易明细
    trades_file = Path(__file__).parent / 'results' / 'trade_details_20260318_0949.csv'
    df = pd.read_csv(trades_file)
    
    # 筛选盈利交易
    profitable = df[df['pnl_pct'] > 0].copy()
    
    print(f"\n{'='*70}")
    print("📈 盈利交易卖出后走势分析")
    print(f"{'='*70}")
    print(f"\n盈利交易总数: {len(profitable)} 笔")
    print(f"盈利交易占比: {len(profitable)/len(df)*100:.1f}%")
    
    # 按卖出原因分组统计
    print(f"\n{'='*70}")
    print("📊 按卖出原因分组")
    print(f"{'='*70}")
    
    for reason in profitable['exit_reason'].unique():
        group = profitable[profitable['exit_reason'] == reason]
        avg_return = group['pnl_pct'].mean()
        print(f"  {reason}: {len(group)}笔, 平均收益 {avg_return:.2f}%")
    
    # 分析每笔盈利交易卖出后的走势
    print(f"\n{'='*70}")
    print("🔍 分析卖出后走势 (这需要一些时间...)")
    print(f"{'='*70}")
    
    results = []
    
    for idx, row in profitable.iterrows():
        symbol = row['symbol']
        exit_date = row['exit_date']
        exit_price = row['exit_price']
        pnl_pct = row['pnl_pct']
        exit_reason = row['exit_reason']
        entry_wave = row['entry_wave']
        
        # 获取后续数据 - 确保symbol是字符串
        df_after = get_stockdata_afterexit(str(symbol), exit_date, days=60)
        
        if df_after is not None and len(df_after) > 0:
            # 计算不同时间点的涨跌幅
            price_1d = float(df_after.iloc[0]['close']) if len(df_after) >= 1 else None
            price_5d = float(df_after.iloc[min(4, len(df_after)-1)]['close']) if len(df_after) >= 1 else None
            price_10d = float(df_after.iloc[min(9, len(df_after)-1)]['close']) if len(df_after) >= 1 else None
            price_20d = float(df_after.iloc[min(19, len(df_after)-1)]['close']) if len(df_after) >= 1 else None
            
            # 60天内的最高/最低
            high_60d = float(df_after['high'].max()) if len(df_after) > 0 else None
            low_60d = float(df_after['low'].min()) if len(df_after) > 0 else None
            
            change_1d = (price_1d - exit_price) / exit_price * 100 if price_1d else None
            change_5d = (price_5d - exit_price) / exit_price * 100 if price_5d else None
            change_10d = (price_10d - exit_price) / exit_price * 100 if price_10d else None
            change_20d = (price_20d - exit_price) / exit_price * 100 if price_20d else None
            
            max_up_60d = (high_60d - exit_price) / exit_price * 100 if high_60d else None
            max_down_60d = (low_60d - exit_price) / exit_price * 100 if low_60d else None
            
            # 分类判断
            # 如果20天内继续上涨超过10%：卖飞
            # 如果20天内下跌超过10%：卖对
            # 其他：震荡
            if change_20d is not None:
                if change_20d > 10:
                    classification = "sell_too_early"  # 卖飞了
                elif change_20d < -10:
                    classification = "sell_right"  # 卖对了
                else:
                    classification = "consolidation"  # 震荡
            else:
                classification = "unknown"
            
            results.append({
                'symbol': symbol,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'pnl_pct': pnl_pct,
                'exit_reason': exit_reason,
                'entry_wave': entry_wave,
                'change_1d': change_1d,
                'change_5d': change_5d,
                'change_10d': change_10d,
                'change_20d': change_20d,
                'max_up_60d': max_up_60d,
                'max_down_60d': max_down_60d,
                'classification': classification,
                'data_days': len(df_after)
            })
        
        if (idx + 1) % 50 == 0:
            print(f"  已处理 {idx + 1}/{len(profitable)} 笔...")
    
    # 转换为DataFrame
    df_results = pd.DataFrame(results)
    
    print(f"\n{'='*70}")
    print("📊 分析结果汇总")
    print(f"{'='*70}")
    
    # 总体分类统计
    print("\n卖出决策判断 (基于20天走势):")
    for cls in ['sell_too_early', 'sell_right', 'consolidation']:
        count = (df_results['classification'] == cls).sum()
        pct = count / len(df_results) * 100
        avg_profit = df_results[df_results['classification'] == cls]['pnl_pct'].mean()
        print(f"  {cls}: {count}笔 ({pct:.1f}%), 卖出时平均收益 {avg_profit:.2f}%")
    
    # 按卖出原因分析
    print("\n按卖出原因分析:")
    for reason in df_results['exit_reason'].unique():
        group = df_results[df_results['exit_reason'] == reason]
        early_pct = (group['classification'] == 'sell_too_early').sum() / len(group) * 100
        right_pct = (group['classification'] == 'sell_right').sum() / len(group) * 100
        avg_20d = group['change_20d'].mean()
        print(f"\n  {reason}:")
        print(f"    样本数: {len(group)}笔")
        print(f"    卖飞比例: {early_pct:.1f}%")
        print(f"    卖对比例: {right_pct:.1f}%")
        print(f"    20天后平均涨跌: {avg_20d:+.2f}%")
    
    # 按买入浪型分析
    print("\n按买入浪型分析:")
    for wave in df_results['entry_wave'].unique():
        if pd.isna(wave):
            continue
        group = df_results[df_results['entry_wave'] == wave]
        if len(group) > 5:
            early_pct = (group['classification'] == 'sell_too_early').sum() / len(group) * 100
            avg_20d = group['change_20d'].mean()
            avg_max_up = group['max_up_60d'].mean()
            print(f"\n  浪{wave}:")
            print(f"    样本数: {len(group)}笔")
            print(f"    卖飞比例: {early_pct:.1f}%")
            print(f"    20天后平均: {avg_20d:+.2f}%")
            print(f"    60天最高平均: {avg_max_up:+.2f}%")
    
    # 极端案例
    print(f"\n{'='*70}")
    print("🔥 典型案例")
    print(f"{'='*70}")
    
    # 卖飞最严重的
    sell_early = df_results[df_results['classification'] == 'sell_too_early'].nlargest(5, 'change_20d')
    print("\n🏃 卖飞最严重 (卖出后继续大涨):")
    for _, row in sell_early.iterrows():
        print(f"  {row['symbol']} @ {row['exit_date'][:10]}")
        print(f"    卖出收益: {row['pnl_pct']:+.2f}%, 卖出原因: {row['exit_reason']}")
        print(f"    20天后涨: {row['change_20d']:+.2f}%, 60天最高: {row['max_up_60d']:+.2f}%")
    
    # 卖对最明显的
    sell_right = df_results[df_results['classification'] == 'sell_right'].nsmallest(5, 'change_20d')
    print("\n✅ 卖对最明显 (卖出后大跌):")
    for _, row in sell_right.iterrows():
        print(f"  {row['symbol']} @ {row['exit_date'][:10]}")
        print(f"    卖出收益: {row['pnl_pct']:+.2f}%, 卖出原因: {row['exit_reason']}")
        print(f"    20天后跌: {row['change_20d']:+.2f}%, 60天最低: {row['max_down_60d']:+.2f}%")
    
    # 保存结果
    output_file = Path(__file__).parent / 'results' / 'profitabletrades_analysis.csv'
    df_results.to_csv(output_file, index=False)
    print(f"\n💾 详细结果已保存: {output_file}")
    
    return df_results

if __name__ == '__main__':
    analyze_profitabletrades()
