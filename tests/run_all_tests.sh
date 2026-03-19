#!/bin/bash
# 运行所有测试套件

set -e

echo "=============================================="
echo "🧪 智能体量化分析系统 - 测试套件"
echo "=============================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "📁 项目目录: $PROJECT_DIR"
echo ""

# 设置Python路径
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# 设置测试环境变量
export DEEPSEEK_API_KEY="test_key"
export CODEFLOW_API_KEY="test_key"
export POSTGRES_PASSWORD="test_pass"
export TUSHARE_TOKEN="test_token"

# 计数器
UNIT_TESTS=0
UNIT_PASSED=0
INTEGRATION_TESTS=0
INTEGRATION_PASSED=0
REGRESSION_TESTS=0
REGRESSION_PASSED=0

# ============================================
# 单元测试
# ============================================
echo "${YELLOW}▶ 运行单元测试...${NC}"
echo "----------------------------------------------"

UNIT_TEST_FILES=(
    "tests/unit/test_ai_subagents.py"
    "tests/unit/test_triangle_wave.py"
    "tests/unit/test_elliott_wave.py"
    "tests/unit/test_api_fastapi.py"
)

for test_file in "${UNIT_TEST_FILES[@]}"; do
    if [ -f "$test_file" ]; then
        echo "  运行: $test_file"
        if python -m pytest "$test_file" -v --tb=short 2>&1 | grep -q "passed"; then
            ((UNIT_PASSED++))
        fi
        ((UNIT_TESTS++))
    else
        echo "  ⚠️  跳过: $test_file (不存在)"
    fi
done

echo ""

# ============================================
# 集成测试
# ============================================
echo "${YELLOW}▶ 运行集成测试...${NC}"
echo "----------------------------------------------"

INTEGRATION_TEST_FILES=(
    "tests/integration/test_audit_fixes.py"
    "tests/integration/test_agents.py"
)

for test_file in "${INTEGRATION_TEST_FILES[@]}"; do
    if [ -f "$test_file" ]; then
        echo "  运行: $test_file"
        if python "$test_file" 2>&1 | grep -q "OK\|所有测试通过"; then
            ((INTEGRATION_PASSED++))
        fi
        ((INTEGRATION_TESTS++))
    else
        echo "  ⚠️  跳过: $test_file (不存在)"
    fi
done

echo ""

# ============================================
# 回归测试
# ============================================
echo "${YELLOW}▶ 运行回归测试...${NC}"
echo "----------------------------------------------"

REGRESSION_TEST_FILES=(
    "tests/regression/test_audit_fixes.py"
)

for test_file in "${REGRESSION_TEST_FILES[@]}"; do
    if [ -f "$test_file" ]; then
        echo "  运行: $test_file"
        if python "$test_file" 2>&1 | grep -q "所有回归测试通过\|OK"; then
            ((REGRESSION_PASSED++))
        fi
        ((REGRESSION_TESTS++))
    else
        echo "  ⚠️  跳过: $test_file (不存在)"
    fi
done

echo ""

# ============================================
# 汇总报告
# ============================================
echo "=============================================="
echo "📊 测试报告汇总"
echo "=============================================="
echo ""

# 单元测试结果
if [ $UNIT_PASSED -eq $UNIT_TESTS ]; then
    echo "${GREEN}✅ 单元测试: $UNIT_PASSED/$UNIT_TESTS 通过${NC}"
else
    echo "${RED}❌ 单元测试: $UNIT_PASSED/$UNIT_TESTS 通过${NC}"
fi

# 集成测试结果
if [ $INTEGRATION_PASSED -eq $INTEGRATION_TESTS ]; then
    echo "${GREEN}✅ 集成测试: $INTEGRATION_PASSED/$INTEGRATION_TESTS 通过${NC}"
else
    echo "${RED}❌ 集成测试: $INTEGRATION_PASSED/$INTEGRATION_TESTS 通过${NC}"
fi

# 回归测试结果
if [ $REGRESSION_PASSED -eq $REGRESSION_TESTS ]; then
    echo "${GREEN}✅ 回归测试: $REGRESSION_PASSED/$REGRESSION_TESTS 通过${NC}"
else
    echo "${RED}❌ 回归测试: $REGRESSION_PASSED/$REGRESSION_TESTS 通过${NC}"
fi

echo ""

TOTAL_TESTS=$((UNIT_TESTS + INTEGRATION_TESTS + REGRESSION_TESTS))
TOTAL_PASSED=$((UNIT_PASSED + INTEGRATION_PASSED + REGRESSION_PASSED))

echo "----------------------------------------------"
if [ $TOTAL_PASSED -eq $TOTAL_TESTS ]; then
    echo "${GREEN}🎉 全部测试通过: $TOTAL_PASSED/$TOTAL_TESTS${NC}"
    echo "=============================================="
    exit 0
else
    echo "${RED}⚠️  部分测试失败: $TOTAL_PASSED/$TOTAL_TESTS${NC}"
    echo "=============================================="
    exit 1
fi
