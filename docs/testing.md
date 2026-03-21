# 测试文档

## 测试架构

```
tests/
├── unit/              # 单元测试 (50+文件)
│   ├── test_*.py      # 各模块单元测试
├── integration/       # 集成测试 (15+文件)
│   └── test_*.py      # 模块间协作测试
├── regression/        # 回归测试 (3+文件)
│   └── test_*.py      # 防止修复项回退
├── e2e/               # 端到端测试 (5+文件)
│   └── test_*.py      # 完整流程测试
├── fixtures/          # 测试数据
└── utils/             # 测试工具
```

---

## 测试分类

### 1. 单元测试 (Unit Tests)

测试单个函数/类/模块的正确性。

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行特定单元测试
python -m pytest tests/unit/test_elliott_wave.py -v
python -m pytest tests/unit/test_triangle_wave.py -v
python -m pytest tests/unit/test_entry_optimizer.py -v      # E1
python -m pytest tests/unit/test_resonance.py -v            # E2
python -m pytest tests/unit/test_volume_analyzer.py -v      # E5
```

**核心单元测试**:

| 测试文件 | 代码行数 | 测试内容 |
|---------|---------|---------|
| `test_elliott_wave.py` | 250+ | 波浪识别核心算法 |
| `test_triangle_wave.py` | 200+ | Triangle调整浪检测 (P2修复) |
| `test_entry_optimizer.py` | 300+ | E1: 买点评分优化 |
| `test_resonance.py` | 250+ | E2: 多指标共振 |
| `test_volume_analyzer.py` | 280+ | E5: 三维量能分析 |
| `test_adaptive_params.py` | 220+ | 自适应参数优化 |
| `test_wave_backtester.py` | 350+ | 回测引擎 |
| `test_api_fastapi.py` | 200+ | FastAPI接口 (P3) |
| `test_ai_subagents.py` | 200+ | AI子代理适配器 |
| `test_coverage_round2.py` | 688 | 第二轮覆盖率测试 |
| `test_coverage_round3.py` | 797 | 第三轮覆盖率测试 |

---

### 2. 集成测试 (Integration Tests)

测试多个模块间的协作。

```bash
# 运行所有集成测试
python tests/integration/test_audit_fixes.py
python tests/integration/test_agents.py
python tests/integration/test_data_flow.py
```

**集成测试覆盖**:

| 测试文件 | 代码行数 | 测试内容 |
|---------|---------|---------|
| `test_audit_fixes.py` | 300+ | N-01~N-07审计修复验证 |
| `test_agents.py` | 250+ | 智能体协作测试 |
| `test_data_flow.py` | 200+ | 数据流完整性测试 |
| `test_wave_params.py` | 180+ | 参数回传系统测试 |

**审计修复验证 (N-01~N-07)**:

| 问题ID | 级别 | 测试内容 | 状态 |
|--------|------|---------|------|
| N-01 | P0 | API Key环境变量化 | ✅ 通过 |
| N-02 | P0 | 数据库密码环境变量化 | ✅ 通过 |
| N-03 | P1 | DB连接池优化 | ✅ 通过 |
| N-04 | P1 | AI子代理架构 | ✅ 通过 |
| N-05 | P2 | Triangle调整浪检测 | ✅ 通过 |
| N-06 | P3 | FastAPI接口完整性 | ✅ 通过 |
| N-07 | P3 | 代码整洁度检查 | ✅ 通过 |

---

### 3. 回归测试 (Regression Tests)

防止已修复的问题再次出现。

```bash
# 运行回归测试
python tests/regression/test_audit_fixes.py
```

**回归测试覆盖**:

- **P0 安全**: API Key硬编码检测
- **P1 代码质量**: DB连接模式、AI子代理存在性
- **P2 算法**: Triangle检测完整性
- **P3 FastAPI**: API层代码完整性
- **P3 代码整洁**: sys.path清理状态

---

### 4. 端到端测试 (E2E Tests)

完整系统流程测试。

```bash
# 运行E2E测试
python tests/e2e/test_full_workflow.py
python tests/e2e/test_backtest_pipeline.py
```

**E2E测试覆盖**:

| 测试文件 | 测试内容 |
|---------|---------|
| `test_full_workflow.py` | 完整分析流程 |
| `test_backtest_pipeline.py` | 回测流水线 |
| `test_data_sync.py` | 数据同步流程 |
| `test_api_endpoints.py` | API端点测试 |
| `test_multi_agent.py` | 多智能体协作 |

---

## 快速测试

### 一键运行所有测试

```bash
./tests/run_all_tests.sh
```

### 手动运行

```bash
cd 智能体系统

echo "=== 运行单元测试 ==="
python -m pytest tests/unit/ -v --tb=short

echo "=== 运行集成测试 ==="
python tests/integration/test_audit_fixes.py
python tests/integration/test_agents.py

echo "=== 运行回归测试 ==="
python tests/regression/test_audit_fixes.py

echo "=== 运行E2E测试 ==="
python tests/e2e/test_full_workflow.py
```

---

## 测试覆盖率

### 生成覆盖率报告

```bash
# 生成HTML报告
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term

# 查看HTML报告
open htmlcov/index.html
```

### 覆盖率统计

| 模块 | 覆盖率 | 备注 |
|------|--------|------|
| analysis/wave/ | 85% | 核心算法 |
| analysis/technical/ | 80% | 技术指标 |
| agents/ | 75% | 智能体层 |
| data/ | 70% | 数据层 |
| api/ | 65% | API层 (新增) |
| **总体** | **75%** | - |

---

## E1~E6 增强测试

### E1: 买点评分维度扩充

```python
# test_entry_optimizer.py
def test_entry_score_components():
    """测试买点评分多维度"""
    optimizer = WaveEntryOptimizer()
    
    # 测试缩量评分
    score = optimizer.calculate_volume_score(df)
    assert 0 <= score <= 1
    
    # 测试均线评分
    score = optimizer.calculate_ma_score(df)
    assert 0 <= score <= 1
    
    # 测试布林带评分
    score = optimizer.calculate_bollinger_score(df)
    assert 0 <= score <= 1
    
    # 测试综合评分
    final_score = optimizer.calculate_entry_score(df)
    assert 0 <= final_score <= 1
```

### E2: 共振权重自适应

```python
# test_resonance.py
def test_adaptive_resonance_weights():
    """测试共振权重市场状态自适应"""
    analyzer = ResonanceAnalyzer()
    
    # 趋势市场
    weights_trend = analyzer.get_weights(market_state='trending')
    assert weights_trend['macd'] > weights_trend['rsi']
    
    # 震荡市场
    weights_range = analyzer.get_weights(market_state='ranging')
    assert weights_range['rsi'] > weights_range['macd']
```

### E5: VolumeAnalyzer 三维量能

```python
# test_volume_analyzer.py
def test_volume_three_dimensions():
    """测试三维量能分析"""
    analyzer = VolumeAnalyzer()
    result = analyzer.analyze(df)
    
    # 相对量能
    assert 'relative_volume' in result
    
    # 趋势量能
    assert 'volume_trend' in result
    
    # 异常量能
    assert 'volume_anomaly' in result
```

---

## 测试数据

测试数据放在 `tests/fixtures/` 目录:

```
fixtures/
├── sample_stock_data.csv        # 样本股票数据
├── sample_industry_data.csv     # 样本行业数据
├── mock_wave_patterns.json      # 模拟波浪模式
├── mock_indicators.json         # 模拟技术指标
└── test_config.yaml             # 测试配置
```

使用示例:

```python
import pandas as pd
from pathlib import Path

# 加载测试数据
df = pd.read_csv(Path(__file__).parent / 'fixtures/sample_stock_data.csv')
```

---

## CI/CD集成

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run unit tests
        run: python -m pytest tests/unit/ -v
      
      - name: Run integration tests
        run: |
          python tests/integration/test_audit_fixes.py
          python tests/integration/test_agents.py
      
      - name: Run regression tests
        run: python tests/regression/test_audit_fixes.py
      
      - name: Generate coverage report
        run: python -m pytest tests/ --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
        with:
          file: ./coverage.xml
```

---

## 常见问题

### 1. 导入错误

确保项目根目录在Python路径中:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

### 2. 环境变量缺失

测试会自动设置mock环境变量，如需真实值:

```bash
export DEEPSEEK_API_KEY=your_key
export DATABASE_URL=postgresql://...
```

### 3. 数据库连接

集成测试使用mock数据库，如需真实连接:

```python
# 在test方法中设置
os.environ['DATABASE_URL'] = 'postgresql://...'
```

### 4. 测试数据缺失

确保fixtures目录存在:

```bash
mkdir -p tests/fixtures
```

---

## 测试统计 (2026-03-21)

| 测试类型 | 文件数 | 测试用例 | 代码行数 |
|---------|-------|---------|---------|
| 单元测试 | 50+ | 200+ | 3900+ |
| 集成测试 | 15+ | 60+ | 1500+ |
| 回归测试 | 3+ | 20+ | 500+ |
| E2E测试 | 5+ | 15+ | 600+ |
| **总计** | **96** | **295+** | **6500+** |

---

## 编写新测试

### 单元测试模板

```python
import unittest
from unittest.mock import Mock, patch

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        """每个测试前的准备"""
        pass
    
    def tearDown(self):
        """每个测试后的清理"""
        pass
    
    def test_feature_does_something(self):
        """测试功能正确性"""
        result = my_function()
        self.assertEqual(result, expected_value)
    
    def test_feature_handles_error(self):
        """测试错误处理"""
        with self.assertRaises(ValueError):
            my_function(invalid_input)

if __name__ == '__main__':
    unittest.main()
```

### 集成测试模板

```python
import unittest
from unittest.mock import patch

class TestIntegration(unittest.TestCase):
    def test_modules_work_together(self):
        """测试模块协作"""
        with patch('module.A', return_value=mock_a):
            with patch('module.B', return_value=mock_b):
                result = integrate_a_and_b()
                self.assertTrue(result.success)
```

### 回归测试模板

```python
class TestRegression(unittest.TestCase):
    def test_bug_does_not_reappear(self):
        """确保已修复的bug不再出现"""
        # 复现导致bug的场景
        result = potentially_buggy_function()
        
        # 验证bug已修复
        self.assertNotEqual(result, buggy_value)
```

---

*最后更新：2026-03-21*
