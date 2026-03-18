#!/bin/bash
# fix_naming.sh - 一键修复命名规范问题
# 使用方法: ./scripts/fix_naming.sh

set -e

echo "=========================================="
echo "🔧 修复命名规范问题"
echo "=========================================="

# 检查是否在项目根目录
if [ ! -f "pyproject.toml" ]; then
    echo "❌ 请在项目根目录运行此脚本"
    exit 1
fi

# 要修复的模式
# 格式: "旧模式|新模式"
patterns=(
    "load_alldata|load_all_data"
    "calculatereturns|calculate_returns"
    "calculatema|calculate_ma"
    "missingvalues|missing_values"
    "duplicatevalues|duplicate_values"
    "outliervalues|outlier_values"
    "priceanomalies|price_anomalies"
    "volumespikes|volume_spikes"
    "totaltrades|total_trades"
    "totaltrades|total_trades"
    "macdsignal|macd_signal"
    "marketdata|market_data"
    "get_batchdata|get_batch_data"
    "get_cachestats|get_cache_stats"
    "get_datalist|get_data_list"
    "use_adaptiveparams|use_adaptive_params"
    "use_adaptive=|use_adaptive_params="
    "loadalldata|load_all_data"
    "getstockdata|get_stock_data"
    "symboldf|symbol_df"
    "testdf|test_df"
    "w2df|w2_df"
    "w3df|w3_df"
    "w4df|w4_df"
    "w5df|w5_df"
    "wcdf|wc_df"
    "wadf|wa_df"
    "wbdf|wb_df"
)

# 修复 src/ 目录
echo "📁 修复 src/ 目录..."
for pattern in "${patterns[@]}"; do
    old="${pattern%%|*}"
    new="${pattern##*|}"
    find src/ -name "*.py" -exec sed -i "s/$old/$new/g" {} \; 2>/dev/null || true
done

# 修复 tests/ 目录
echo "📁 修复 tests/ 目录..."
for pattern in "${patterns[@]}"; do
    old="${pattern%%|*}"
    new="${pattern##*|}"
    find tests/ -name "*.py" -exec sed -i "s/$old/$new/g" {} \; 2>/dev/null || true
done

# 修复类名
echo "🏗️  修复类名..."
find . -name "*.py" -path "./src/*" -o -path "./tests/*" | xargs sed -i \
    -e 's/EnhancedWaveAnalyzer/UnifiedWaveAnalyzer/g' \
    -e 's/WaveDetector/UnifiedWaveAnalyzer/g' \
    2>/dev/null || true

echo "✅ 命名修复完成"
echo ""

# 运行 ruff 检查
echo "🔍 运行 ruff 检查..."
if command -v ./venv/bin/ruff &> /dev/null; then
    ./venv/bin/ruff check . --fix --quiet 2>/dev/null || true
    errors=$(./venv/bin/ruff check . --output-format=text 2>/dev/null | wc -l)
    if [ "$errors" -gt 0 ]; then
        echo "⚠️  仍有 $errors 个问题需要手动修复"
        ./venv/bin/ruff check . --output-format=concise 2>/dev/null | head -20
    else
        echo "✅ ruff 检查通过"
    fi
else
    echo "⚠️  ruff 未安装，跳过检查"
fi

echo ""
echo "=========================================="
echo "🎉 修复完成"
echo "=========================================="
echo "建议运行: ./venv/bin/pytest tests/ --tb=no -q"