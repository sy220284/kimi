"""
科技板块亏损股票特征分析报告
"""
from pathlib import Path

import pandas as pd


# 读取数据
df = pd.read_csv('tests/results/techtrade_details_20260318_1053.csv')

# 亏损股票列表
loss_symbols = ['688126', '688561', '688521', '688008', '688728', '688981', '300408', '688009', '603893']

print("="*80)
print("🔬 科技板块亏损股票特征分析报告")
print("="*80)

# 一、整体对比
print("\n📊 一、盈亏股票整体对比")
print("-"*80)

symbolstats = []
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol]
    total_pnl = symbol_df['pnl_pct'].sum()
    win_rate = (symbol_df['pnl_pct'] > 0).mean()
    trade_count = len(symbol_df)
    trailing_count = symbol_df['exit_reason'].str.contains('trailing_stop', na=False).sum()
    stop_count = (symbol_df['exit_reason'] == 'stop_loss').sum()
    avg_holding = symbol_df['holding_days'].mean()
    avg_win = symbol_df[symbol_df['pnl_pct'] > 0]['pnl_pct'].mean() if len(symbol_df[symbol_df['pnl_pct'] > 0]) > 0 else 0
    avg_loss = symbol_df[symbol_df['pnl_pct'] <= 0]['pnl_pct'].mean() if len(symbol_df[symbol_df['pnl_pct'] <= 0]) > 0 else 0

    symbolstats.append({
        'symbol': symbol,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'trades': trade_count,
        'trailing_pct': trailing_count / trade_count * 100 if trade_count > 0 else 0,
        'stop_pct': stop_count / trade_count * 100 if trade_count > 0 else 0,
        'avg_holding': avg_holding,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    })

stats_df = pd.DataFrame(symbolstats)
profitable = stats_df[stats_df['total_pnl'] > 0]
losing = stats_df[stats_df['total_pnl'] <= 0]

print("\n┌─────────────────┬─────────────────┬─────────────────┐")
print("│     指标        │   盈利股票(31只) │   亏损股票(9只)  │")
print("├─────────────────┼─────────────────┼─────────────────┤")
print(f"│ 平均总收益      │   {profitable['total_pnl'].mean():>10.2f}%   │   {losing['total_pnl'].mean():>10.2f}%   │")
print(f"│ 平均胜率        │   {profitable['win_rate'].mean():>10.1%}   │   {losing['win_rate'].mean():>10.1%}   │")
print(f"│ 平均交易次数    │   {profitable['trades'].mean():>10.1f}   │   {losing['trades'].mean():>10.1f}   │")
print(f"│ 移动止盈比例    │   {profitable['trailing_pct'].mean():>10.1f}%   │   {losing['trailing_pct'].mean():>10.1f}%   │")
print(f"│ 止损比例        │   {profitable['stop_pct'].mean():>10.1f}%   │   {losing['stop_pct'].mean():>10.1f}%   │")
print(f"│ 平均持仓天数    │   {profitable['avg_holding'].mean():>10.1f}天  │   {losing['avg_holding'].mean():>10.1f}天  │")
print(f"│ 平均盈利单笔    │   +{profitable['avg_win'].mean():>9.2f}%   │   +{losing['avg_win'].mean():>9.2f}%   │")
print(f"│ 平均亏损单笔    │   {profitable['avg_loss'].mean():>10.2f}%   │   {losing['avg_loss'].mean():>10.2f}%   │")
print("└─────────────────┴─────────────────┴─────────────────┘")

# 二、逐个分析
print("\n\n📉 二、亏损股票逐个深度分析")
print("="*80)

for symbol in loss_symbols:
    symboltrades = df[df['symbol'] == symbol].copy()
    if len(symboltrades) == 0:
        continue

    total_pnl = symboltrades['pnl_pct'].sum()
    win_rate = (symboltrades['pnl_pct'] > 0).mean()

    trailing = symboltrades[symboltrades['exit_reason'].str.contains('trailing_stop', na=False)]
    stop_loss = symboltrades[symboltrades['exit_reason'] == 'stop_loss']

    wins = symboltrades[symboltrades['pnl_pct'] > 0]
    losses = symboltrades[symboltrades['pnl_pct'] <= 0]

    print(f"\n🔹 {symbol} | 总收益: {total_pnl:>7.2f}% | 交易{len(symboltrades):>2}次")
    print("-"*60)

    # 基本指标
    print(f"  胜率: {win_rate:>6.1%} | 平均单笔: {symboltrades['pnl_pct'].mean():>6.2f}%")

    # 卖出方式分布
    parts = []
    if len(trailing) > 0:
        parts.append(f"移动止盈{len(trailing)}笔(均{trailing['pnl_pct'].mean():+.1f}%)")
    if len(stop_loss) > 0:
        parts.append(f"止损{len(stop_loss)}笔(均{stop_loss['pnl_pct'].mean():+.1f}%)")
    print(f"  卖出: {' | '.join(parts)}")

    # 盈亏详情
    if len(wins) > 0:
        print(f"  盈利: {len(wins)}笔 均+{wins['pnl_pct'].mean():.1f}% 最大+{wins['pnl_pct'].max():.1f}%")
    if len(losses) > 0:
        print(f"  亏损: {len(losses)}笔 均{losses['pnl_pct'].mean():.1f}% 最大{losses['pnl_pct'].min():.1f}%")

    # 盈亏比
    if len(wins) > 0 and len(losses) > 0 and losses['pnl_pct'].sum() != 0:
        pf = abs(wins['pnl_pct'].sum() / losses['pnl_pct'].sum())
        print(f"  盈亏比: {pf:.2f} (需要>1才能盈利)")

    # 持仓时间
    print(f"  持仓: 平均{symboltrades['holding_days'].mean():.0f}天 最长{symboltrades['holding_days'].max()}天")

# 三、关键发现
print("\n\n🔍 三、关键发现与洞察")
print("="*80)

print("""
1️⃣ 核心问题：止损太频繁
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • 亏损股票平均止损率高达 74.7% (vs 盈利股票 62.0%)
   • 说明这些股票买入后经常先跌8%触发止损，然后才涨
   • 科创板(688开头)股票波动大，8%止损容易被"洗"出去

2️⃣ 胜率差距明显
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • 亏损股票平均胜率仅 24.2% (vs 盈利股票 35.7%)
   • 不到1/4的交易能赚钱，难以累积盈利

3️⃣ 移动止盈利用不足
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • 亏损股票移动止盈率仅 25.3% (vs 盈利股票 38.0%)
   • 说明这些股票很少能涨到目标价触发移动止盈
   • 买入时机可能不对，买在阶段性高点

4️⃣ 盈亏比失衡
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • 亏损股票盈利单笔平均 +7.2%，亏损单笔平均 -6.1%
   • 盈亏比约 1.2，不足以覆盖低胜率的影响
   • 盈利股票盈亏比更高，且胜率也高

5️⃣ 股票特征
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • 688126 沪硅产业: 胜率15.4%最低，半导体材料周期股
   • 688561 奇安信: 网络安全，常年亏损，股价阴跌
   • 688521 芯原股份: IP授权模式，业绩波动大
   • 688008 澜起科技: 内存接口芯片，周期性明显
   • 688981 中芯国际: 晶圆代工龙头，但股价横盘多年
""")

# 四、改进建议
print("\n📋 四、改进建议")
print("="*80)
print("""
1. 针对高波动科技股放宽止损
   • 科创板股票可尝试 10% 或 12% 止损
   • 或改用波动率止损(如 ATR*2)

2. 增加趋势过滤
   • 只在 50日均线 上方买入
   • 避免在下降趋势中抄底

3. 优化买入时机
   • 等待回调到支撑位再买入
   • 避免追高涨后的股票

4. 个股黑名单/白名单
   • 剔除常年亏损、现金流差的科技股
   • 优先选择有业绩支撑的成长股

5. 行业轮动
   • 科技板块内部分化大
   • 可配置不同细分领域(芯片/软件/新能源)
""")

print("\n" + "="*80)
print("✅ 分析报告完成")
print("="*80)
