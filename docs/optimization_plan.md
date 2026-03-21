# 智能体系统优化方案

**状态**: 2026-03-21 更新 - E1~E6增强已完成 ✅

---

## 优化目标
- ✅ 统一波浪分析入口，提升分析质量 (已完成)
- ✅ 消除技术债务（sys.path、双重IO类型） (已完成)
- 🔄 统一配置管理 (进行中)
- ✅ 保持向后兼容 (已保证)

---

## ✅ 已完成优化

### E1~E6 系统性增强 (2026-03-21)

| 增强 | 功能 | 状态 |
|------|------|------|
| **E1** | 买点评分维度扩充 | ✅ 完成 |
| **E2** | 共振权重市场状态自适应 | ✅ 完成 |
| **E3** | 出场逻辑补全 | ✅ 完成 |
| **E4** | 信号召回率提升 | ✅ 完成 |
| **E5** | VolumeAnalyzer 三维量能 | ✅ 完成 |
| **E6** | 信号置信度衰减机制 | ✅ 完成 |

### 审计修复 (N-01~N-07)

| 问题 | 级别 | 状态 |
|------|------|------|
| API Key环境变量化 | P0 | ✅ 完成 |
| 数据库密码环境变量化 | P0 | ✅ 完成 |
| DB连接池优化 | P1 | ✅ 完成 |
| AI子代理架构 | P1 | ✅ 完成 |
| Triangle调整浪检测 | P2 | ✅ 完成 |
| FastAPI接口 | P3 | ✅ 完成 |
| 代码整洁度 | P3 | ✅ 完成 |

---

## 🔄 进行中优化

### 优化项: 统一配置管理

### 问题
配置分散在 `config.yaml`, `data_source.yaml`, `wave_params.json`

### 优化方案

#### 步骤 1: 创建统一配置加载器 `utils/config_manager.py`

```python
"""统一配置管理器"""
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
        if path.exists():
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        return {}
    
    def _load_json(self, path: Path) -> dict:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号路径
        
        示例:
            get('wave.scoring.rsi_weight') -> 0.20
            get('core.models.codeflow.base_url') -> 'https://codeflow.asia'
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        # 处理环境变量替换
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            value = os.getenv(env_var, default)
        
        return value
    
    def get_wave_params(self) -> dict:
        """获取波浪分析参数（兼容旧接口）"""
        return self._config.get('wave', {})
    
    def reload(self):
        """重新加载配置"""
        self._load_all()


# 全局配置实例
config = ConfigManager()
```

#### 步骤 2: 修改 `WaveEntryOptimizer` 使用配置管理器

```python
# analysis/wave/entry_optimizer.py

@classmethod
def from_config(cls, config_manager=None) -> 'WaveEntryOptimizer':
    """从配置创建实例"""
    if config_manager is None:
        try:
            from utils.config_manager import config
            config_manager = config
        except ImportError:
            pass
    
    if config_manager:
        return cls(
            c_min_shrink_ratio=config_manager.get('wave.c_wave.min_shrink_ratio', 0.7),
            rsi_oversold_threshold=config_manager.get('wave.scoring.rsi_oversold_threshold', 35.0),
            rsi_weight=config_manager.get('wave.scoring.rsi_weight', 0.20),
            # ... 其他参数
        )
    
    # 回退到直接读取 JSON
    # ... 原有逻辑
```

### 收益
- 单一入口访问所有配置
- 支持环境变量替换
- 热重载支持

---

## 📋 后续优化建议

### 短期 (本周)

| 优化项 | 工作量 | 优先级 |
|--------|--------|--------|
| 完成配置管理器 | 2小时 | P1 |
| 清理剩余sys.path | 1小时 | P2 |
| 实现pattern_library TODO | 2小时 | P2 |

### 中期 (本月)

| 优化项 | 工作量 | 优先级 |
|--------|--------|--------|
| 类型注解覆盖提升至60% | 4小时 | P2 |
| 自定义异常类 | 3小时 | P2 |
| 性能基准测试 | 4小时 | P3 |

### 长期

| 优化项 | 工作量 | 优先级 |
|--------|--------|--------|
| mypy静态类型检查 | 8小时 | P3 |
| 代码复杂度监控 | 4小时 | P3 |
| 分布式回测支持 | 16小时 | P4 |

---

## 📊 系统当前状态

| 指标 | 数值 | 状态 |
|------|------|------|
| Python文件 | 200+ | ✅ |
| 代码行数 | 30,000+ | ✅ |
| 测试文件 | 96 | ✅ |
| 测试代码行 | 6,500+ | ✅ |
| 数据记录 | 267万条 | ✅ |
| 系统健康度 | 90/100 | ✅ |

---

*最后更新：2026-03-21*
