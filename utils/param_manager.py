#!/usr/bin/env python3
"""
回测参数管理器 - Backtest Parameter Manager

功能：
1. 从配置文件加载优化后的回测参数
2. 将新的回测结果保存到配置文件
3. 支持参数版本管理和历史追溯
4. 自动同步到 entry_optimizer

使用方式：
    # 加载参数
    from utils.param_manager import get_wave_params
    params = get_wave_params()
    
    # 保存新的回测结果
    from utils.param_manager import save_backtest_result
    save_backtest_result({
        'round': 11,
        'annual_return': 15.2,
        'max_drawdown': 6.8,
        'win_rate': 48.5,
        'params': {...}
    })
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# 参数文件路径
PARAMS_FILE = Path(__file__).parent.parent / 'config' / 'wave_params.json'
PARAMS_HISTORY_DIR = Path(__file__).parent.parent / 'config' / 'wave_params_history'


def get_wave_params() -> dict[str, Any]:
    """
    获取当前波浪买点优化器参数
    
    Returns:
        参数字典，如果文件不存在则返回默认参数
    """
    if PARAMS_FILE.exists():
        with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 返回默认参数（与 entry_optimizer 默认值一致）
    return {
        "_meta": {
            "version": "1.0",
            "description": "默认参数",
            "last_updated": datetime.now().isoformat()
        },
        "c_wave": {
            "min_shrink_ratio": 0.7,
            "confirm_volume_ratio": 1.3
        },
        "wave_2": {
            "max_shrink_ratio": 0.6,
            "macd_threshold": 0.0
        },
        "wave_4": {
            "time_ratio_min": 0.3,
            "time_ratio_max": 0.8,
            "volatility_shrink": 0.8
        },
        "scoring": {
            "rsi_oversold_threshold": 35.0,
            "rsi_weight": 0.20,
            "macd_divergence_weight": 0.20,
            "hammer_weight": 0.10,
            "support_proximity_weight": 0.10
        },
        "thresholds": {
            "strong_buy": 0.50,
            "buy": 0.40,
            "watch": 0.35
        },
        "general": {
            "lookback_days": 20
        }
    }


def save_wave_params(params: dict[str, Any], backup: bool = True) -> None:
    """
    保存波浪买点优化器参数
    
    Args:
        params: 参数字典
        backup: 是否备份历史版本
    """
    # 更新时间戳
    if '_meta' not in params:
        params['_meta'] = {}
    params['_meta']['last_updated'] = datetime.now().isoformat()
    
    # 备份历史版本
    if backup and PARAMS_FILE.exists():
        PARAMS_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = PARAMS_HISTORY_DIR / f'wave_params_{timestamp}.json'
        with open(PARAMS_FILE, 'r', encoding='utf-8') as src:
            with open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
    
    # 保存新参数
    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params, f, indent=2, ensure_ascii=False)


def update_params_from_backtest(
    round_num: int,
    annual_return: float,
    max_drawdown: float,
    win_rate: float,
    sharpe_ratio: float,
    param_updates: dict[str, Any],
    description: str = ""
) -> dict[str, Any]:
    """
    根据回测结果更新参数
    
    Args:
        round_num: 回测轮次
        annual_return: 年化收益率
        max_drawdown: 最大回撤
        win_rate: 胜率
        sharpe_ratio: 夏普比率
        param_updates: 更新的参数字典
        description: 更新描述
        
    Returns:
        更新后的完整参数字典
    """
    # 加载当前参数
    params = get_wave_params()
    
    # 更新元数据
    params['_meta'].update({
        'version': f'1.{round_num}',
        'backtest_round': f'第{round_num}轮',
        'last_updated': datetime.now().isoformat(),
        'description': description or f'基于第{round_num}轮回测优化',
        'performance': {
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe_ratio
        }
    })
    
    # 更新参数
    for key, value in param_updates.items():
        # 支持嵌套路径，如 "scoring.rsi_weight"
        keys = key.split('.')
        target = params
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
    
    # 保存
    save_wave_params(params)
    
    return params


def get_entry_optimizer_kwargs() -> dict[str, Any]:
    """
    获取 entry_optimizer.WaveEntryOptimizer 的 kwargs
    
    Returns:
        可以直接传给 WaveEntryOptimizer.__init__ 的字典
    """
    params = get_wave_params()
    
    return {
        # C浪参数
        'c_min_shrink_ratio': params['c_wave']['min_shrink_ratio'],
        'c_confirm_volume_ratio': params['c_wave']['confirm_volume_ratio'],
        
        # 2浪参数
        'w2_max_shrink_ratio': params['wave_2']['max_shrink_ratio'],
        'w2_macd_threshold': params['wave_2']['macd_threshold'],
        
        # 4浪参数
        'w4_time_ratio_min': params['wave_4']['time_ratio_min'],
        'w4_time_ratio_max': params['wave_4']['time_ratio_max'],
        'w4_volatility_shrink': params['wave_4']['volatility_shrink'],
        
        # 通用参数
        'lookback_days': params['general']['lookback_days'],
        
        # 评分参数
        'rsi_oversold_threshold': params['scoring']['rsi_oversold_threshold'],
        'rsi_weight': params['scoring']['rsi_weight'],
        'macd_divergence_weight': params['scoring']['macd_divergence_weight'],
        'hammer_weight': params['scoring']['hammer_weight'],
        'support_proximity_weight': params['scoring']['support_proximity_weight'],
        
        # 阈值参数
        'strong_buy_threshold': params['thresholds']['strong_buy'],
        'buy_threshold': params['thresholds']['buy'],
        'watch_threshold': params['thresholds']['watch']
    }


def list_param_history() -> list[dict[str, Any]]:
    """
    列出参数历史版本
    
    Returns:
        历史版本列表，按时间倒序
    """
    if not PARAMS_HISTORY_DIR.exists():
        return []
    
    history = []
    for f in sorted(PARAMS_HISTORY_DIR.glob('wave_params_*.json'), reverse=True):
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            history.append({
                'file': f.name,
                'timestamp': data.get('_meta', {}).get('last_updated', 'unknown'),
                'version': data.get('_meta', {}).get('version', 'unknown'),
                'performance': data.get('_meta', {}).get('performance', {})
            })
    return history


def rollback_to_version(timestamp: str) -> bool:
    """
    回滚到指定版本的参数
    
    Args:
        timestamp: 时间戳，格式如 '20260320_163000'
        
    Returns:
        是否成功回滚
    """
    backup_file = PARAMS_HISTORY_DIR / f'wave_params_{timestamp}.json'
    if not backup_file.exists():
        print(f"❌ 未找到版本: {timestamp}")
        return False
    
    # 备份当前版本
    save_wave_params(get_wave_params(), backup=True)
    
    # 恢复指定版本
    with open(backup_file, 'r', encoding='utf-8') as src:
        params = json.load(src)
        params['_meta']['restored_from'] = timestamp
        save_wave_params(params, backup=False)
    
    print(f"✅ 已回滚到版本: {timestamp}")
    return True


# CLI 接口
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='回测参数管理器')
    parser.add_argument('--show', action='store_true', help='显示当前参数')
    parser.add_argument('--history', action='store_true', help='显示参数历史')
    parser.add_argument('--rollback', type=str, metavar='TIMESTAMP', help='回滚到指定版本')
    
    args = parser.parse_args()
    
    if args.show:
        params = get_wave_params()
        print(json.dumps(params, indent=2, ensure_ascii=False))
    elif args.history:
        history = list_param_history()
        for h in history[:10]:  # 只显示最近10个
            perf = h.get('performance', {})
            print(f"{h['timestamp']} | v{h['version']} | "
                  f"收益:{perf.get('annual_return', 0):.2f}% | "
                  f"回撤:{perf.get('max_drawdown', 0):.2f}% | "
                  f"胜率:{perf.get('win_rate', 0):.1f}%")
    elif args.rollback:
        rollback_to_version(args.rollback)
    else:
        parser.print_help()
