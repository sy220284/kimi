# 测试文档

## 测试架构

```
tests/
├── unit/              # 单元测试
│   ├── test_*.py      # 各模块单元测试
├── integration/       # 集成测试
│   └── test_*.py      # 模块间协作测试
├── regression/        # 回归测试
│   └── test_*.py      # 防止修复项回退
├── e2e/               # 端到端测试
├── fixtures/          # 测试数据
└── utils/             # 测试工具
```

## 测试分类

### 1. 单元测试 (Unit Tests)

测试单个函数/类/模块的正确性。

```bash
# 运行所有单元测试
python -m pytest tests/unit/ -v

# 运行特定单元测试
python -m pytest tests/unit/test_ai_subagents.py -v
python -m pytest tests/unit/test_triangle_wave.py -v
python -m pytest tests/unit/test_elliott_wave.py -v
python -m pytest tests/unit/test_api_fastapi.py -v
```

**已有单元测试**:
- `test_ai_subagents.py` - AI子代理测试（200行）
- `test_triangle_wave.py` - Triangle调整浪测试（200行）
- `test_elliott_wave.py` - 波浪分析器测试（250行）
- `test_api_fastapi.py` - FastAPI接口测试（200行）

### 2. 集成测试 (Integration Tests)

测试多个模块间的协作。

```bash
# 运行所有集成测试
python tests/integration/test_audit_fixes.py
python tests/integration/test_agents.py
```

**已有集成测试**:
- `test_audit_fixes.py` - 审计修复验证（250行）
- `test_agents.py` - 智能体协作测试（200行）

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

### 4. 端到端测试 (E2E Tests)

完整系统流程测试。

```bash
# 端到端测试在 tests/e2e/ 目录下
```

## 快速测试

```bash
# 一键运行所有测试套件
./tests/run_all_tests.sh
```

或手动运行:

```bash
cd 智能体系统

echo "=== 运行单元测试 ==="
python -m pytest tests/unit/ -v --tb=short

echo "=== 运行集成测试 ==="
python tests/integration/test_audit_fixes.py
python tests/integration/test_agents.py

echo "=== 运行回归测试 ==="
python tests/regression/test_audit_fixes.py
```

## 测试覆盖率

```bash
# 生成覆盖率报告
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term

# 查看HTML报告
open htmlcov/index.html
```

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

## 测试数据

测试数据放在 `tests/fixtures/` 目录:

```
fixtures/
├── sample_stock_data.csv    # 样本股票数据
├── mock_wave_patterns.json  # 模拟波浪模式
└── mock_indicators.json     # 模拟技术指标
```

使用示例:

```python
import pandas as pd

df = pd.read_csv('tests/fixtures/sample_stock_data.csv')
```

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
      - name: Run tests
        run: |
          python -m pytest tests/unit/ -v
          python tests/integration/test_audit_fixes.py
          python tests/regression/test_audit_fixes.py
```

## 常见问题

### 1. 导入错误

确保项目根目录在Python路径中:

```python
import sys
sys.path.insert(0, '/path/to/智能体系统')
```

### 2. 环境变量缺失

测试会自动设置mock环境变量，如需真实值:

```bash
export DEEPSEEK_API_KEY=your_key
```

### 3. 数据库连接

集成测试使用mock数据库，如需真实连接:

```python
# 在test方法中设置
os.environ['DATABASE_URL'] = 'postgresql://...'
```

## 测试统计

| 测试类型 | 文件数 | 测试用例 | 代码行数 |
|---------|-------|---------|---------|
| 单元测试 | 4 | 20+ | 850+ |
| 集成测试 | 2 | 15+ | 500+ |
| 回归测试 | 1 | 12+ | 300+ |
| **总计** | **7** | **47+** | **1650+** |
