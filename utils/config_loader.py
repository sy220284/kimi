"""
基础工具模块 - YAML配置加载器
支持环境变量替换
"""
import os
import re
from pathlib import Path
from typing import Any

import yaml

# 尝试加载python-dotenv，如果安装了的话
try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False


class ConfigLoaderError(Exception):
    """配置加载错误"""
    pass



class ConfigLoader:
    """YAML配置加载器，支持环境变量替换"""

    # 环境变量替换模式: ${VAR_NAME} 或 ${VAR_NAME:default_value}
    ENV_PATTERN = re.compile(r'\$\{([^}]+)\}')

    def __init__(self, config_path: Path | None = None):
        """
        初始化配置加载器

        Args:
            config_path: 配置文件路径，默认为项目根目录下的config/config.yaml
        """
        if config_path is None:
            # 从当前文件位置推断项目根目录
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent  # utils -> 项目根目录
            config_path = project_root / "config" / "config.yaml"
            # 加载.env文件（如果存在）
            self._load_env_file(project_root)
            # 加载.env文件（如果存在）
            self._load_env_file(project_root)

        self.config_path = config_path
        self._config: dict[str, Any] | None = None
    def _load_env_file(self, project_root: Path) -> None:
        """
        加载.env文件到环境变量
        
        Args:
            project_root: 项目根目录
        """
        if _DOTENV_AVAILABLE:
            env_file = project_root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
        else:
            # 手动读取.env文件
            env_file = project_root / ".env"
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"\'')
                            if key and key not in os.environ:
                                os.environ[key] = value

    def _replace_env_vars(self, value: Any) -> Any:
        """
        递归替换值中的环境变量

        Args:
            value: 需要替换的值（可以是字符串、字典、列表等）

        Returns:
            替换后的值
        """
        if isinstance(value, str):
            def replace_match(match):
                env_expr = match.group(1)
                if ':' in env_expr:
                    # 有默认值: ${VAR:default}
                    var_name, default = env_expr.split(':', 1)
                    return os.environ.get(var_name.strip(), default)
                else:
                    # 无默认值: ${VAR}
                    return os.environ.get(env_expr, '')

            return self.ENV_PATTERN.sub(replace_match, value)

        elif isinstance(value, dict):
            return {key: self._replace_env_vars(val) for key, val in value.items()}

        elif isinstance(value, list):
            return [self._replace_env_vars(item) for item in value]

        else:
            return value

    def load(self, force_reload: bool = False) -> dict[str, Any]:
        """
        加载配置文件

        Args:
            force_reload: 是否强制重新加载

        Returns:
            配置字典

        Raises:
            ConfigLoaderError: 配置文件加载失败时抛出
        """
        if self._config is not None and not force_reload:
            return self._config

        try:
            # 确保config_path是Path对象
            if isinstance(self.config_path, str):
                self.config_path = Path(self.config_path)

            if not self.config_path.exists():
                raise ConfigLoaderError(f"配置文件不存在: {self.config_path}")

            with open(self.config_path, encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)

            if raw_config is None:
                raw_config = {}

            # 替换环境变量
            self._config = self._replace_env_vars(raw_config)
            return self._config

        except yaml.YAMLError as e:
            raise ConfigLoaderError(f"YAML解析错误: {e}")
        except Exception as e:
            raise ConfigLoaderError(f"加载配置文件失败: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        通过点分隔的路径获取配置值

        Args:
            key_path: 配置路径，如 'database.postgres.host'
            default: 默认值，当路径不存在时返回

        Returns:
            配置值或默认值
        """
        config = self.load()
        keys = key_path.split('.')

        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def get_database_config(self, db_type: str = 'postgres') -> dict[str, Any]:
        """
        获取数据库配置

        Args:
            db_type: 数据库类型 (postgres/redis/mongodb)

        Returns:
            数据库配置字典
        """
        return self.get(f'database.{db_type}', {})

    def get_data_source_config(self, source: str) -> dict[str, Any]:
        """
        获取数据源配置

        Args:
            source: 数据源名称 (tushare/akshare/baostock)

        Returns:
            数据源配置字典
        """
        return self.get(f'data_sources.{source}', {})

    def get_agent_config(self, agent_name: str) -> dict[str, Any]:
        """
        获取智能体配置

        Args:
            agent_name: 智能体名称

        Returns:
            智能体配置字典
        """
        return self.get(f'agents.{agent_name}', {})

    def get_logging_config(self) -> dict[str, Any]:
        """
        获取日志配置

        Returns:
            日志配置字典
        """
        return self.get('logging', {})

    def reload(self) -> dict[str, Any]:
        """重新加载配置"""
        self._config = None
        return self.load()


# 全局配置加载器实例
_config_loader: ConfigLoader | None = None


def get_config_loader(config_path: Path | None = None) -> ConfigLoader:
    """
    获取全局配置加载器实例

    Args:
        config_path: 配置文件路径

    Returns:
        配置加载器实例
    """
    global _config_loader
    if _config_loader is None or config_path is not None:
        _config_loader = ConfigLoader(config_path)
    return _config_loader


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    快速加载配置的便捷函数

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    return get_config_loader(config_path).load()
