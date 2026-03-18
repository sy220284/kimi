# 完整代码规范与质量保障方案

## 问题复盘

### 根本原因
1. **历史遗留问题**: 项目早期没有统一的命名规范，导致 camelCase、snake_case、甚至无分隔符混用
2. **重构不同步**: 功能代码重构后，测试文件未及时更新
3. **缺乏强制检查**: 没有 pre-commit hook 阻止不规范代码提交
4. **修复不彻底**: 分批修复导致重复劳动

### 损失统计
- 3次提交修复同类问题
- 61个文件被反复修改
- 约3小时低效劳动
- 41处命名问题重复修复

---

## 解决方案

### 1. 已配置的工具

#### ruff (Python Linter & Formatter)
```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501", "E741", "F841"]
```

**关键规则**:
- `N` (pep8-naming): 强制 snake_case，禁止 camelCase
- `F821`: 未定义名称检查
- `E722`: 禁止裸 except
- `I`: 自动排序 import

#### pytest (测试框架)
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

#### mypy (类型检查)
```toml
[tool.mypy]
python_version = "3.12"
warn_return_any = true
```

---

### 2. 使用方式

#### 手动检查
```bash
# 检查所有问题
./venv/bin/ruff check .

# 自动修复可修复的问题
./venv/bin/ruff check . --fix

# 格式化代码
./venv/bin/ruff format .

# 运行测试
./venv/bin/pytest
```

#### IDE 集成
VSCode 配置 `.vscode/settings.json`:
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "ruff",
  "editor.formatOnSave": true
}
```

---

### 3. 命名规范检查清单

| 类型 | 规范 | 示例 | 反例 |
|-----|------|------|------|
| 函数 | snake_case | `get_stock_data` | `getStockData`, `getstockdata` |
| 类 | PascalCase | `WaveAnalyzer` | `waveAnalyzer`, `wave_analyzer` |
| 变量 | snake_case | `total_trades` | `totalTrades`, `totaltrades` |
| 常量 | UPPER_SNAKE | `MAX_RETRY` | `maxRetry`, `max_retry` |
| 私有 | _leading_underscore | `_internal` | `internal_` |

---

### 4. 防止复发的措施

#### A. 提交前强制检查
```bash
# 创建 git hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# 运行 ruff 检查
if ! ./venv/bin/ruff check . --quiet; then
    echo "❌ ruff 检查失败，请修复后提交"
    exit 1
fi

# 运行测试收集 (检查导入错误)
if ! ./venv/bin/pytest --collect-only -q 2>/dev/null; then
    echo "❌ 测试收集失败，存在导入错误"
    exit 1
fi

echo "✅ 预提交检查通过"
EOF
chmod +x .git/hooks/pre-commit
```

#### B. API 变更检查清单
当修改核心类时，同步检查：
```bash
# 查找所有使用旧 API 的文件
grep -r "EnhancedWaveAnalyzer" tests/ --include="*.py"
grep -r "load_alldata" tests/ --include="*.py"
grep -r "\.analyze(" tests/ --include="*.py"
```

#### C. 重构后强制同步测试
```bash
# 重构后运行全量测试收集，发现 API 不匹配
./venv/bin/pytest tests/ --collect-only 2>&1 | grep "ERROR\|AttributeError"
```

---

### 5. 修复脚本库

#### 一键修复命名问题
```bash
#!/bin/bash
# fix_naming.sh

echo "修复命名规范问题..."

# 批量替换
find tests/ -name "*.py" -exec sed -i \
    -e 's/load_alldata/load_all_data/g' \
    -e 's/calculatereturns/calculate_returns/g' \
    -e 's/calculatema/calculate_ma/g' \
    -e 's/missingvalues/missing_values/g' \
    -e 's/duplicatevalues/duplicate_values/g' \
    -e 's/outliervalues/outlier_values/g' \
    -e 's/totaltrades/total_trades/g' \
    -e 's/totaltrades/total_trades/g' \
    -e 's/macdsignal/macd_signal/g' \
    -e 's/marketdata/market_data/g' \
    -e 's/get_batchdata/get_batch_data/g' \
    -e 's/get_cachestats/get_cache_stats/g' \
    -e 's/get_datalist/get_data_list/g' \
    -e 's/use_adaptive=/use_adaptive_params=/g' \
    -e 's/use_adaptiveparams/use_adaptive_params/g' \
    -e 's/EnhancedWaveAnalyzer/UnifiedWaveAnalyzer/g' \
    -e 's/WaveDetector/UnifiedWaveAnalyzer/g' \
    {} \;

echo "完成!"
```

#### 检查缩进错误
```bash
#!/bin/bash
# check_indent.sh

echo "检查缩进错误..."

# 查找 try/for 后无缩进的模式
for file in tests/*.py; do
    # 检查 try: 后空行或立即跟非缩进行
    if grep -n "^\s*try:\s*$" "$file" | head -1 | grep -q "try:"; then
        echo "检查: $file"
    fi
done

# Python 语法检查
python -m py_compile tests/*.py 2>&1 | grep "IndentationError"
```

---

### 6. CI/CD 集成建议

#### GitHub Actions 工作流
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      
      - name: Lint with ruff
        run: ruff check . --output-format=github
      
      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports
      
      - name: Test collection
        run: pytest --collect-only -q
      
      - name: Run tests
        run: pytest --tb=short -q
```

---

### 7. 团队规范

#### 提交信息规范
```
feat: 新增功能
test: 新增测试
fix: 修复bug
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
perf: 性能优化
```

#### 代码审查清单
- [ ] ruff 检查通过
- [ ] 测试可收集（无导入错误）
- [ ] 命名符合 snake_case
- [ ] 无裸 except
- [ ] 新增代码有对应测试

---

## 验证

运行以下命令验证配置：

```bash
# 1. 检查所有代码
cd /root/.openclaw/workspace/quant_agent_system
./venv/bin/ruff check .

# 2. 检查测试可收集
./venv/bin/pytest tests/ --collect-only -q

# 3. 运行全量测试
./venv/bin/pytest tests/ --tb=no -q
```

预期结果：
- ruff: 0 errors
- pytest collect: 175 items
- pytest run: 173 passed, 2 skipped