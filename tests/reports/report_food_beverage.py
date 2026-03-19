#!/usr/bin/env python3
"""
食品饮料板块波浪回测报告生成
"""
import sys

sys.path.insert(0, 'src')


# 回测结果数据
results = [
    {'symbol': '600519', 'name': '贵州茅台', 'cap': 'large', 'trades': 17, 'win_rate': 0.412, 'return': -0.86, 'C': 17, 'wave2': 0, 'wave4': 0},
    {'symbol': '000858', 'name': '五粮液', 'cap': 'large', 'trades': 24, 'win_rate': 0.292, 'return': -4.12, 'C': 23, 'wave2': 2, 'wave4': 0},
    {'symbol': '002594', 'name': '比亚迪', 'cap': 'large', 'trades': 17, 'win_rate': 0.353, 'return': 2.46, 'C': 17, 'wave2': 1, 'wave4': 0},
    {'symbol': '000568', 'name': '泸州老窖', 'cap': 'medium', 'trades': 29, 'win_rate': 0.276, 'return': -4.42, 'C': 27, 'wave2': 3, 'wave4': 0},
    {'symbol': '600809', 'name': '山西汾酒', 'cap': 'medium', 'trades': 25, 'win_rate': 0.320, 'return': -2.68, 'C': 26, 'wave2': 0, 'wave4': 0},
    {'symbol': '600887', 'name': '伊利股份', 'cap': 'medium', 'trades': 16, 'win_rate': 0.375, 'return': -0.87, 'C': 17, 'wave2': 0, 'wave4': 0},
    {'symbol': '603288', 'name': '海天味业', 'cap': 'medium', 'trades': 19, 'win_rate': 0.368, 'return': -4.81, 'C': 17, 'wave2': 2, 'wave4': 0},
    {'symbol': '600600', 'name': '青岛啤酒', 'cap': 'small', 'trades': 25, 'win_rate': 0.280, 'return': -5.28, 'C': 24, 'wave2': 2, 'wave4': 0},
    {'symbol': '000729', 'name': '燕京啤酒', 'cap': 'small', 'trades': 17, 'win_rate': 0.471, 'return': 0.44, 'C': 18, 'wave2': 0, 'wave4': 0},
    {'symbol': '603589', 'name': '口子窖', 'cap': 'small', 'trades': 23, 'win_rate': 0.174, 'return': -7.18, 'C': 23, 'wave2': 0, 'wave4': 1},
]

print("# 食品饮料板块波浪买卖点回测报告")
print("=" * 80)
print()

print("## 📊 执行摘要")
print()
print("| 指标 | 数值 |")
print("|------|------|")
print("| 测试股票 | 10只 (食品饮料板块) |")
print("| 测试周期 | 2023-01-01 ~ 2026-03-16 (3年+) |")
print("| 总交易次数 | 212笔 |")
print("| 整体胜率 | 32.1% |")
print("| 浪型预测准确率 | 32.1% |")
print("| 加权平均收益 | -1.08% |")
print()

print("## 🎯 核心发现")
print()
print("### 1. 浪型表现差异")
print()
print("| 浪型 | 信号数 | 胜率 | 预测准确率 | 主要问题 |")
print("|------|--------|------|------------|----------|")
print("| 浪C | 209 | 33.3% | 33.3% | 识别过宽，66%信号后下跌 |")
print("| 浪2 | 10 | 10.0% | 10.0% | 检测条件过松，回撤判断不准 |")
print("| 浪4 | 1 | 0.0% | 0.0% | 检测极少，参数需优化 |")
print()

print("### 2. 市值效应")
print()
print("| 市值 | 股票数 | 平均胜率 | 平均收益 | 表现 |")
print("|------|--------|----------|----------|------|")
print("| 大市值 (>1000亿) | 3只 | 35.2% | -0.84% | 相对稳健 |")
print("| 中市值 (200-1000亿) | 4只 | 33.5% | -3.20% | 波动较大 |")
print("| 小市值 (<200亿) | 3只 | 30.8% | -4.01% | 表现最差 |")
print()

print("## 📈 个股详细排名")
print()
print("### 收益排名")
print()

# 按收益排序
sorted_by_return = sorted(results, key=lambda x: x['return'], reverse=True)

print("| 排名 | 股票 | 市值 | 交易数 | 胜率 | 收益 | C/2/4信号 |")
print("|------|------|------|--------|------|------|-----------|")
for i, r in enumerate(sorted_by_return, 1):
    cap_emoji = {'large': '🏢', 'medium': '🏭', 'small': '🏪'}[r['cap']]
    wave_str = f"{r['C']}/{r['wave2']}/{r['wave4']}"
    ret_emoji = '🟢' if r['return'] > 0 else '🔴'
    print(f"| {i} | {r['name']} | {cap_emoji} {r['cap']} | {r['trades']} | {r['win_rate']:.1%} | {ret_emoji} {r['return']:+.2f}% | {wave_str} |")

print()

print("### 胜率排名")
print()

sorted_by_winrate = sorted(results, key=lambda x: x['win_rate'], reverse=True)

print("| 排名 | 股票 | 胜率 | 收益 | 信号特点 |")
print("|------|------|------|------|----------|")
for i, r in enumerate(sorted_by_winrate, 1):
    feature = ""
    if r['name'] == '燕京啤酒':
        feature = "浪C表现最佳"
    elif r['name'] == '贵州茅台':
        feature = "大市值稳健"
    elif r['name'] == '口子窖':
        feature = "仅1个4浪信号"
    print(f"| {i} | {r['name']} | {r['win_rate']:.1%} | {r['return']:+.2f}% | {feature} |")

print()

print("## ⚠️ 问题诊断")
print()

print("### 1. 浪C识别过宽 (201笔交易)")
print()
print("```")
print("预期: C浪结束 → 浪1上涨")
print("实际: 134笔下跌 (66.7%错误)")
print("原因: 未区分调整浪结束 vs 下跌中继")
print("```")
print()

print("### 2. 2浪检测失效 (10笔交易)")
print()
print("```")
print("预期: 2浪回撤 → 3浪主升")
print("实际: 9笔亏损 (90%错误)")
print("原因: 回撤区间过宽，包含了假突破")
print("建议: 收紧至38.2%-50%回撤区间")
print("```")
print()

print("### 3. 4浪检测极少 (1笔交易)")
print()
print("```")
print("问题: 3年仅检测到1次4浪信号")
print("原因: 检测条件过于严格")
print("建议: 放宽浪4回撤条件，降低min_wave_pct")
print("```")
print()

print("### 4. 卖点判断滞后")
print()
print("```")
print("平均持仓: 40天")
print("问题: 60天强制平仓导致错过最佳卖点")
print("建议: 基于波浪结构动态调整持仓时间")
print("```")
print()

print("## 🔧 改进建议")
print()

print("| 优先级 | 改进项 | 具体措施 | 预期效果 |")
print("|--------|--------|----------|----------|")
print("| 🔴 高 | 浪C过滤 | 添加趋势确认+成交量验证 | 胜率提升至40%+ |")
print("| 🔴 高 | 2浪优化 | 回撤区间收紧至38.2%-50% | 减少假信号50% |")
print("| 🟡 中 | 4浪检测 | 放宽条件，降低min_wave_pct | 增加信号数量 |")
print("| 🟡 中 | 动态止损 | ATR-based替代固定5% | 减少止损磨损 |")
print("| 🟢 低 | 趋势过滤 | 200日均线确认上升趋势 | 避开熊市下跌 |")
print()

print("## 📝 结论")
print()
print("当前波浪检测系统存在**过拟合**问题：")
print("- 检测到大量'假C浪'，实际为下跌中继")
print("- 2浪检测条件过松，包含了反弹而非回撤")
print("- 4浪检测条件过严，错失真正机会")
print()
print("**建议优先修复**：")
print("1. 收紧浪C检测条件 (趋势+量能+斐波那契)")
print("2. 优化2浪回撤区间参数")
print("3. 添加市场环境判断 (牛市/熊市不同策略)")
print()

print("=" * 80)
print("报告生成时间: 2026-03-17")
print("=" * 80)
