#!/usr/bin/env python3
"""
回测参数同步脚本 - 将回测结果同步到配置文件

使用方法:
    # 从回测报告文件同步
    python scripts/update_backtest_params.py --report scripts/backtest/elliott_wave_backtest_report.md
    
    # 直接指定参数
    python scripts/update_backtest_params.py \
        --round 11 \
        --annual-return 15.2 \
        --max-drawdown 6.8 \
        --win-rate 48.5 \
        --sharpe-ratio 1.55 \
        --rsi-threshold 36 \
        --buy-threshold 0.42

    # 查看当前参数
    python scripts/update_backtest_params.py --show
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.param_manager import (
    get_wave_params,
    update_params_from_backtest,
    list_param_history
)


def parse_report_file(report_path: Path) -> dict:
    """
    从回测报告Markdown文件解析参数
    """
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    result = {
        'round': 0,
        'annual_return': 0.0,
        'max_drawdown': 0.0,
        'win_rate': 0.0,
        'sharpe_ratio': 0.0,
        'params': {}
    }
    
    # 提取轮次
    round_match = re.search(r'(\d+)轮(?:优化)?', content)
    if round_match:
        result['round'] = int(round_match.group(1))
    
    # 提取绩效指标
    return_match = re.search(r'年化收益[:：]\s*(\d+\.?\d*)%', content)
    if return_match:
        result['annual_return'] = float(return_match.group(1))
    
    drawdown_match = re.search(r'最大回撤[:：]\s*(\d+\.?\d*)%', content)
    if drawdown_match:
        result['max_drawdown'] = float(drawdown_match.group(1))
    
    win_rate_match = re.search(r'胜率[:：]\s*(\d+\.?\d*)%', content)
    if win_rate_match:
        result['win_rate'] = float(win_rate_match.group(1))
    
    sharpe_match = re.search(r'夏普比率[:：]\s*(\d+\.?\d*)', content)
    if sharpe_match:
        result['sharpe_ratio'] = float(sharpe_match.group(1))
    
    # 提取参数配置（YAML格式代码块）
    yaml_match = re.search(r'```ya?ml\n(.*?)```', content, re.DOTALL)
    if yaml_match:
        yaml_content = yaml_match.group(1)
        
        # 解析关键参数
        rsi_match = re.search(r'RSI超卖阈值[:：]\s*<?(\d+)', yaml_content)
        if rsi_match:
            result['params']['scoring.rsi_oversold_threshold'] = float(rsi_match.group(1))
        
        buy_threshold_match = re.search(r'买点评分阈值[:：]\s*(\d+)', yaml_content)
        if buy_threshold_match:
            result['params']['thresholds.buy'] = float(buy_threshold_match.group(1)) / 100
        
        strong_buy_match = re.search(r'强买入阈值[:：]\s*(\d+)', yaml_content)
        if strong_buy_match:
            result['params']['thresholds.strong_buy'] = float(strong_buy_match.group(1)) / 100
        
        rsi_weight_match = re.search(r'RSI超卖权重[:：]\s*(\d+)', yaml_content)
        if rsi_weight_match:
            result['params']['scoring.rsi_weight'] = float(rsi_weight_match.group(1)) / 100
        
        macd_weight_match = re.search(r'MACD底背离权重[:：]\s*(\d+)', yaml_content)
        if macd_weight_match:
            result['params']['scoring.macd_divergence_weight'] = float(macd_weight_match.group(1)) / 100
    
    return result


def main():
    parser = argparse.ArgumentParser(description='回测参数同步工具')
    parser.add_argument('--report', type=Path, help='回测报告Markdown文件路径')
    parser.add_argument('--round', type=int, help='回测轮次')
    parser.add_argument('--annual-return', type=float, help='年化收益率(%)')
    parser.add_argument('--max-drawdown', type=float, help='最大回撤(%)')
    parser.add_argument('--win-rate', type=float, help='胜率(%)')
    parser.add_argument('--sharpe-ratio', type=float, help='夏普比率')
    parser.add_argument('--rsi-threshold', type=float, help='RSI超卖阈值')
    parser.add_argument('--buy-threshold', type=float, help='买入阈值(0-1)')
    parser.add_argument('--strong-buy-threshold', type=float, help='强买入阈值(0-1)')
    parser.add_argument('--show', action='store_true', help='显示当前参数')
    parser.add_argument('--history', action='store_true', help='显示参数历史')
    parser.add_argument('--description', type=str, help='更新描述')
    
    args = parser.parse_args()
    
    # 显示当前参数
    if args.show:
        params = get_wave_params()
        print("=" * 60)
        print("📋 当前回测参数")
        print("=" * 60)
        print(json.dumps(params, indent=2, ensure_ascii=False))
        return
    
    # 显示历史
    if args.history:
        print("=" * 60)
        print("📜 参数历史版本")
        print("=" * 60)
        history = list_param_history()
        for h in history[:10]:
            perf = h.get('performance', {})
            print(f"\n⏰ {h['timestamp']}")
            print(f"   版本: v{h['version']}")
            print(f"   收益: {perf.get('annual_return', 0):.2f}%")
            print(f"   回撤: {perf.get('max_drawdown', 0):.2f}%")
            print(f"   胜率: {perf.get('win_rate', 0):.1f}%")
        return
    
    # 从报告文件解析
    if args.report:
        if not args.report.exists():
            print(f"❌ 报告文件不存在: {args.report}")
            sys.exit(1)
        
        result = parse_report_file(args.report)
        print(f"📄 从报告解析到参数:")
        print(f"   轮次: {result['round']}")
        print(f"   年化收益: {result['annual_return']:.2f}%")
        print(f"   最大回撤: {result['max_drawdown']:.2f}%")
        print(f"   胜率: {result['win_rate']:.1f}%")
        print(f"   更新参数: {list(result['params'].keys())}")
    else:
        # 从命令行参数构建
        result = {
            'round': args.round or 0,
            'annual_return': args.annual_return or 0.0,
            'max_drawdown': args.max_drawdown or 0.0,
            'win_rate': args.win_rate or 0.0,
            'sharpe_ratio': args.sharpe_ratio or 0.0,
            'params': {}
        }
        
        if args.rsi_threshold:
            result['params']['scoring.rsi_oversold_threshold'] = args.rsi_threshold
        if args.buy_threshold:
            result['params']['thresholds.buy'] = args.buy_threshold
        if args.strong_buy_threshold:
            result['params']['thresholds.strong_buy'] = args.strong_buy_threshold
    
    if not result['params']:
        print("⚠️ 没有可更新的参数")
        parser.print_help()
        sys.exit(1)
    
    # 确认更新
    print("\n" + "=" * 60)
    print("⚠️ 即将更新参数")
    print("=" * 60)
    for k, v in result['params'].items():
        print(f"   {k}: {v}")
    
    confirm = input("\n确认更新? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ 已取消")
        sys.exit(0)
    
    # 执行更新
    update_params_from_backtest(
        round_num=result['round'],
        annual_return=result['annual_return'],
        max_drawdown=result['max_drawdown'],
        win_rate=result['win_rate'],
        sharpe_ratio=result['sharpe_ratio'],
        param_updates=result['params'],
        description=args.description or f"基于第{result['round']}轮回测优化"
    )
    
    print("\n✅ 参数已更新到 config/wave_params.json")
    print("   下次启动 entry_optimizer 时将自动加载新参数")


if __name__ == '__main__':
    main()
