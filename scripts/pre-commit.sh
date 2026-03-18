#!/bin/bash
# pre-commit hook - 提交前强制检查
# 安装: cp scripts/pre-commit.sh .git/hooks/pre-commit

set -e

echo "=========================================="
echo "🔍 预提交检查"
echo "=========================================="

# 获取项目根目录
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

# 检查 ruff
if [ -f "./venv/bin/ruff" ]; then
    echo "📋 运行 ruff 检查..."
    if ! ./venv/bin/ruff check . --quiet 2>/dev/null; then
        echo ""
        echo "❌ ruff 检查失败"
        echo ""
        echo "请修复以下问题:"
        ./venv/bin/ruff check . --output-format=concise 2>/dev/null | head -20
        echo ""
        echo "💡 提示: 运行 './venv/bin/ruff check . --fix' 自动修复部分问题"
        exit 1
    fi
    echo "✅ ruff 检查通过"
else
    echo "⚠️  ruff 未安装，跳过代码风格检查"
fi

# 检查测试可收集（发现导入错误）
if [ -f "./venv/bin/pytest" ]; then
    echo "📋 检查测试导入..."
    if ! ./venv/bin/pytest tests/ --collect-only -q 2>/dev/null | grep -q "passed\|collected"; then
        echo ""
        echo "❌ 测试收集失败，存在导入错误"
        echo ""
        ./venv/bin/pytest tests/ --collect-only 2>&1 | grep "ERROR\|ImportError\|AttributeError" | head -10
        exit 1
    fi
    echo "✅ 测试导入检查通过"
else
    echo "⚠️  pytest 未安装，跳过测试检查"
fi

echo ""
echo "=========================================="
echo "✅ 预提交检查通过，可以提交"
echo "=========================================="