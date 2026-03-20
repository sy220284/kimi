"""
统一配置管理器 - ConfigManager

统一加载和管理所有配置文件：
- config/config.yaml (核心配置)
- config/data_source.yaml (数据源配置)
- config/wave_params.json (波浪分析参数)

使用方式:
    from utils.config_manager import config
    
    # 获取配置值（支持点号路径）
    rsi_weight = config.get('wave.scoring.rsi_weight', 0.20)
    api_key = config.get('core.models.codeflow.api_key')
    
    # 获取整个配置块
    wave_params = config.get_wave_params()
    
    # 重新加载配置
    config.reload()
"""
import json
import os
from pathlib import Path
from typing import Any

import yaml


class ConfigManager:
    """配置管理器 - 统一加载所有配置文件"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is not None:
            return
        self._load_all()
    
    def _load_all(self):
        """加载所有配置文件"""
        config_dir = Path(__file__).parent.parent / 'config'
        
        self._config = {
            'core': self._load_yaml(config_dir / 'config.yaml'),
            'data_source': self._load_yaml(config_dir / 'data_source.yaml'),
            'wave': self._load_json(config_dir / 'wave_params.json'),
        }
    
    def _load_yaml(self, path: Path) -> dict:
        """加载 YAML 文件"""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 先进行环境变量替换
                    content = self._substitute_env_vars(content)
                    return yaml.safe_load(content) or {}
            except Exception as e:
                print(f"⚠️ 加载 YAML 失败 {path}: {e}")
                return {}
        return {}
    
    def _load_json(self, path: Path) -> dict:
        """加载 JSON 文件"""
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 加载 JSON 失败 {path}: {e}")
                return {}
        return {}
    
    def _substitute_env_vars(self, content: str) -> str:
        """替换内容中的环境变量 ${VAR_NAME}"""
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = match.group(2) if match.group(2) else ''
            return os.getenv(var_name, default_value)
        
        # 匹配 ${VAR_NAME} 或 ${VAR_NAME:-default}
        pattern = r'\$\{([^}:-]+)(?::-([^}]*))?\}'
        return re.sub(pattern, replace_var, content)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号路径
        
        Args:
            key: 配置路径，如 'wave.scoring.rsi_weight'
            default: 默认值，如果配置不存在则返回此值
            
        Returns:
            配置值，或默认值
            
        示例:
            config.get('wave.scoring.rsi_weight')  # -> 0.20
            config.get('core.models.codeflow.base_url')  # -> 'https://codeflow.asia'
            config.get('core.database.postgres.host')  # -> 'localhost'
        """
        keys = key.split('.')
        
        # 确定配置块 (core, data_source, wave)
        if keys[0] in self._config:
            value = self._config[keys[0]]
            keys = keys[1:]  # 去掉配置块前缀
        else:
            # 如果没有指定配置块，搜索所有配置
            for block in self._config.values():
                result = self._get_nested(block, keys)
                if result is not None:
                    return result
            return default
        
        # 在指定配置块中查找
        return self._get_nested(value, keys, default)
    
    def _get_nested(self, data: dict, keys: list[str], default: Any = None) -> Any:
        """在嵌套字典中查找值"""
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def get_wave_params(self) -> dict:
        """获取波浪分析参数（兼容旧接口）"""
        return self._config.get('wave', {})
    
    def get_core_config(self) -> dict:
        """获取核心配置"""
        return self._config.get('core', {})
    
    def get_data_source_config(self) -> dict:
        """获取数据源配置"""
        return self._config.get('data_source', {})
    
    def get_all(self) -> dict:
        """获取所有配置（谨慎使用）"""
        return self._config.copy()
    
    def reload(self):
        """重新加载所有配置"""
        self._load_all()
        print("✅ 配置已重新加载")
    
    def set(self, key: str, value: Any, persist: bool = False):
        """
        临时设置配置值（不会保存到文件）
        
        Args:
            key: 配置路径
            value: 配置值
            persist: 是否持久化到文件（默认否）
        """
        keys = key.split('.')
        
        if keys[0] in self._config:
            target = self._config[keys[0]]
            keys = keys[1:]
        else:
            return
        
        # 遍历并设置
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        
        target[keys[-1]] = value
        
        if persist:
            # 持久化到文件
            config_dir = Path(__file__).parent.parent / 'config'
            if keys[0] == 'wave':
                self._save_json(config_dir / 'wave_params.json', self._config['wave'])
            elif keys[0] == 'core':
                self._save_yaml(config_dir / 'config.yaml', self._config['core'])
    
    def _save_json(self, path: Path, data: dict):
        """保存 JSON 文件"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_yaml(self, path: Path, data: dict):
        """保存 YAML 文件"""
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


# 全局配置实例
config = ConfigManager()


# 便捷函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置值的便捷函数"""
    return config.get(key, default)


def reload_config():
    """重新加载配置的便捷函数"""
    config.reload()


if __name__ == '__main__':
    # 测试配置管理器
    print("=== 配置管理器测试 ===\n")
    
    # 测试获取配置
    print("1. 测试波浪参数:")
    print(f"   RSI权重: {config.get('wave.scoring.rsi_weight')}")
    print(f"   买入阈值: {config.get('wave.thresholds.buy')}")
    print(f"   RSI超卖阈值: {config.get('wave.scoring.rsi_oversold_threshold')}")
    
    print("\n2. 测试核心配置:")
    print(f"   CodeFlow Base URL: {config.get('core.models.codeflow.base_url')}")
    print(f"   Postgres Host: {config.get('core.database.postgres.host')}")
    
    print("\n3. 测试默认值:")
    print(f"   不存在的键: {config.get('wave.not_exist.key', 'default_value')}")
    
    print("\n4. 测试获取整个配置块:")
    wave_params = config.get_wave_params()
    print(f"   Wave配置版本: {wave_params.get('_meta', {}).get('version')}")
    
    print("\n✅ 配置管理器测试完成")


# ── 向后兼容：让 config_manager 也能提供 load_config() ──────────────────────
# 目的：消除 config_loader 与 config_manager 双轨，统一入口
# 用法：from utils.config_manager import load_config
def load_config(config_path=None) -> dict:
    """
    兼容 config_loader.load_config() 的入口。

    新代码建议直接使用：
        from utils.config_manager import config
        val = config.get('core.database.postgres.host')
    """
    from utils.config_loader import load_config as _load
    return _load(config_path)
