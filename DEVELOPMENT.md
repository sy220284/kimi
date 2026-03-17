# Development Guide

## Git Workflow

```bash
# 1. 创建功能分支
git checkout -b feature/xxx

# 2. 工作完成后提交
git add .
git commit -m "feat: xxx"

# 3. 合并到master
git checkout master
git merge feature/xxx
git branch -d feature/xxx
```

## 禁止事项

❌ **不要** 创建带版本号的文件名 (test_v1.py → test_v2.py)
❌ **不要** 复制整个文件做"备份"
❌ **不要** 在文件名中标注日期 (test_20250317.py)

## 正确做法

✅ 使用 `git checkout` 回滚到历史版本
✅ 使用配置文件区分不同参数 (config.yaml)
✅ 使用 Git 分支管理并行开发

## 目录结构

```
quant_agent_system/
├── src/                 # 核心代码
│   ├── analysis/wave/   # 波浪分析 (8个核心文件)
│   ├── data/            # 数据层
│   └── backtest/        # 回测框架
├── tests/               # 测试文件 (27个核心)
├── config/              # 配置文件
└── scripts/             # 工具脚本
```

## 需要恢复旧文件?

```bash
# 查看历史文件列表
git log --all --full-history -- src/analysis/wave/archive/

# 恢复特定文件到临时目录
git show HEAD~1:src/analysis/wave/archive/wave_detector.py > /tmp/wave_detector.py
```
