# 智能体系统优化方案

## 优化目标
- 统一波浪分析入口，提升分析质量
- 消除技术债务（sys.path、双重IO类型）
- 统一配置管理
- 保持向后兼容

---

## 优化项 1: WaveAnalystAgent 升级到 UnifiedWaveAnalyzer

### 问题
`WaveAnalystAgent` 使用旧版 `ElliottWaveAnalyzer`，缺少：
- 入场质量评分 (EntryOptimizer)
- 多指标共振分析 (ResonanceAnalyzer)
- 自适应参数 (AdaptiveParameterOptimizer)

### 优化方案

#### 步骤 1: 修改 `agents/wave_analyst.py`

```python
# 修改前 (第9行)
from analysis.wave.elliott_wave import ElliottWaveAnalyzer

# 修改后
from analysis.wave.unified_analyzer import UnifiedWaveAnalyzer, UnifiedWaveSignal
from analysis.wave.elliott_wave import ElliottWaveAnalyzer  # 保留兼容性
```

#### 步骤 2: 修改 `__init__` 方法 (第23-57行)

```python
def __init__(
    self,
    config_path: Path | None = None,
    use_ai: bool = False,
    ai_model: str = "deepseek/deepseek-reasoner",
    use_unified: bool = True,  # 新增: 是否使用统一分析器
):
    super().__init__(
        agent_name="wave_analyst",
        analysis_type=AnalysisType.WAVE,
        config_path=config_path
    )

    # 分析器选择
    self.use_unified = use_unified
    if use_unified:
        self.analyzer = UnifiedWaveAnalyzer()
        self.logger.info("使用 UnifiedWaveAnalyzer (含入场优化+共振分析)")
    else:
        self.analyzer = ElliottWaveAnalyzer()
        self.logger.info("使用 ElliottWaveAnalyzer (基础波浪分析)")
    
    # AI子代理...
```

#### 步骤 3: 修改 `analyze` 方法 (第59-138行)

```python
def analyze(self, input_data: AgentInput) -> AgentOutput:
    from data.optimized_data_manager import get_optimized_data_manager

    start_time = time.time()
    symbol = input_data.symbol

    try:
        # 获取数据
        data_mgr = get_optimized_data_manager()
        df = data_mgr.get_stock_data(symbol)

        # 日期过滤...
        if df is None or df.empty:
            return AgentOutput(...)

        # 执行分析
        if self.use_unified:
            # 新版分析流程
            signals = self.analyzer.detect(df, mode='all')
            
            if not signals:
                return AgentOutput(
                    agent_type=self.analysis_type.value,
                    symbol=symbol,
                    analysis_date=datetime.now().strftime('%Y-%m-%d'),
                    result={'signals': [], 'message': '未检测到波浪信号'},
                    confidence=0.0,
                    state=AgentState.COMPLETED,
                    execution_time=time.time() - start_time
                )
            
            # 选择最佳信号
            best_signal = max(signals, key=lambda s: s.confidence)
            
            result = {
                'signals': [self._signal_to_dict(s) for s in signals],
                'best_signal': self._signal_to_dict(best_signal),
                'entry_type': best_signal.entry_type.value,
                'entry_price': best_signal.entry_price,
                'target_price': best_signal.target_price,
                'stop_loss': best_signal.stop_loss,
                'confidence': best_signal.confidence,
                'quality_score': best_signal.quality_score,
                'resonance_score': best_signal.resonance_score,
            }
            confidence = best_signal.confidence
            
        else:
            # 旧版分析流程（保持兼容）
            pattern = self.analyzer.detect_wave_pattern(df)
            
            if not pattern:
                return AgentOutput(...)
            
            result = {
                'pattern': pattern.to_dict() if hasattr(pattern, 'to_dict') else str(pattern),
                'wave_type': pattern.wave_type if hasattr(pattern, 'wave_type') else None,
            }
            confidence = getattr(pattern, 'confidence', 0.5)
        
        # AI增强...
        if self.use_ai and self.ai_agent:
            # ... 现有AI调用逻辑
            pass
        
        return AgentOutput(
            agent_type=self.analysis_type.value,
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            result=result,
            confidence=confidence,
            state=AgentState.COMPLETED,
            execution_time=time.time() - start_time
        )
        
    except Exception as e:
        return AgentOutput(...)

# 新增辅助方法
def _signal_to_dict(self, signal: UnifiedWaveSignal) -> dict:
    """将信号转换为字典"""
    return {
        'entry_type': signal.entry_type.value,
        'entry_price': signal.entry_price,
        'target_price': signal.target_price,
        'stop_loss': signal.stop_loss,
        'confidence': signal.confidence,
        'quality_score': signal.quality_score,
        'resonance_score': signal.resonance_score,
        'direction': signal.direction,
    }
```

### 收益
- 分析质量提升：入场评分 + 共振分析
- 向后兼容：通过 `use_unified=False` 保留旧行为
- 风险： UnifiedWaveAnalyzer 依赖配置文件，需确保 `config/wave_params.json` 存在

---

## 优化项 2: 清理 sys.path 操作

### 问题
多处使用 `sys.path.insert` 处理导入，代码冗余。

### 优化方案

#### 步骤 1: 确保项目根目录可通过 PYTHONPATH 访问

创建 `.env` 文件（项目根目录）：
```bash
PYTHONPATH=/root/.openclaw/workspace/智能体_system:${PYTHONPATH}
```

或在启动脚本中设置：
```bash
export PYTHONPATH=/root/.openclaw/workspace/智能体_system:$PYTHONPATH
python main.py
```

#### 步骤 2: 修改 `analysis/wave/unified_analyzer.py` (第1-30行)

```python
# 修改前
#!/usr/bin/env python3
"""..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dataclasses import dataclass
...

try:
    from .adaptive_params import ...
    from .elliott_wave import ...
except ImportError:
    from adaptive_params import ...
    from elliott_wave import ...

# 修改后
#!/usr/bin/env python3
"""..."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

# 统一使用相对导入
from .adaptive_params import AdaptiveParameterOptimizer, MarketCondition
from .elliott_wave import WaveDirection, WaveType
from .enhanced_detector import PivotPoint, enhanced_pivot_detection
from .entry_optimizer import WaveEntryOptimizer
from .resonance import ResonanceAnalyzer, SignalDirection
```

#### 步骤 3: 对其他文件执行同样清理

需要清理的文件列表：
- `analysis/wave/elliott_wave.py`
- `analysis/wave/unified_analyzer.py`
- `analysis/technical/indicators.py`
- `analysis/backtest/wave_backtester.py`
- `data/data_collector.py`
- `data/multi_source.py`
- `data/concurrent_data_manager.py`
- `data/data_api.py`
- `data/optimized_data_manager.py`

### 收益
- 代码简洁，消除冗余
- 避免运行时路径修改带来的不确定性

---

## 优化项 3: 统一 AI 子代理输入输出

### 问题
两套输入输出类型：`AgentInput/Output` vs `AIAgentInput/Output`

### 优化方案

#### 步骤 1: 创建适配器 `agents/ai_subagents/adapter.py`

```python
"""AI子代理与主智能体之间的适配器"""
from typing import Any

from agents.base_agent import AgentInput, AgentOutput, AgentState
from .base_ai_agent import AIAgentInput, AIAgentOutput


def to_ai_input(agent_input: AgentInput, context: dict[str, Any] | None = None) -> AIAgentInput:
    """将 AgentInput 转换为 AIAgentInput"""
    return AIAgentInput(
        symbol=agent_input.symbol,
        data={},  # 由具体调用方填充
        context={
            'start_date': agent_input.start_date,
            'end_date': agent_input.end_date,
            'parameters': agent_input.parameters,
            **(context or {})
        }
    )


def to_agent_output(
    ai_output: AIAgentOutput,
    agent_type: str,
    symbol: str,
    execution_time: float
) -> AgentOutput:
    """将 AIAgentOutput 转换为 AgentOutput"""
    return AgentOutput(
        agent_type=agent_type,
        symbol=symbol,
        analysis_date=ai_output.timestamp or datetime.now().strftime('%Y-%m-%d'),
        result=ai_output.result,
        confidence=ai_output.confidence,
        state=AgentState.COMPLETED if ai_output.success else AgentState.ERROR,
        execution_time=execution_time,
        error_message=ai_output.error_message
    )
```

#### 步骤 2: 修改 `agents/wave_analyst.py` 使用适配器

```python
from .ai_subagents.adapter import to_ai_input, to_agent_output

# 在 analyze 方法中
if self.use_ai and self.ai_agent:
    ai_input = to_ai_input(input_data, context={
        'pattern': result.get('best_signal') or result.get('pattern'),
        'raw_data': df.tail(20).to_dict()
    })
    
    ai_start = time.time()
    ai_output = self.ai_agent.analyze(ai_input)
    ai_time = time.time() - ai_start
    
    # 合并AI结果
    result['ai_analysis'] = ai_output.result
    result['ai_reasoning'] = ai_output.reasoning
```

### 收益
- 单一转换点，易于维护
- 类型安全，减少手动字段映射错误

---

## 优化项 4: 统一配置管理

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

## 实施优先级

| 优先级 | 优化项 | 工作量 | 风险 | 收益 |
|--------|--------|--------|------|------|
| P0 | 优化项 1 (UnifiedWaveAnalyzer) | 2小时 | 中 | 高 |
| P1 | 优化项 4 (统一配置) | 2小时 | 低 | 中 |
| P2 | 优化项 3 (AI适配器) | 1小时 | 低 | 中 |
| P3 | 优化项 2 (清理sys.path) | 3小时 | 低 | 低 |

---

## 回滚方案

每个优化项都保持向后兼容：

1. **WaveAnalystAgent**: 通过 `use_unified=False` 参数回退
2. **配置管理**: 保留原有文件读取逻辑作为 fallback
3. **sys.path**: 保留原有代码（注释掉），紧急时可恢复

---

## 测试清单

- [ ] WaveAnalystAgent 使用 UnifiedWaveAnalyzer 分析股票
- [ ] WaveAnalystAgent 使用旧版 ElliottWaveAnalyzer 分析股票（向后兼容）
- [ ] 所有导入语句正常工作（无 sys.path）
- [ ] AI子代理输入输出转换正常
- [ ] 配置管理器正确加载所有配置文件
- [ ] WaveEntryOptimizer.from_config() 使用配置管理器
- [ ] 回测引擎正常运行
