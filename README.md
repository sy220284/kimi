# 智能体量化分析系统

A 股量化分析平台，整合艾略特波浪识别、多指标共振、行业轮动分析与事件驱动回测。

## ✨ 核心特性

- **🌊 艾略特波浪分析** - 自动识别推动浪、调整浪(Zigzag/Flat/Triangle)
- **📊 多指标共振** - MACD、RSI、KDJ、布林带综合信号
- **🏭 行业轮动** - 申万行业指数动量分析
- **🤖 AI增强分析** - LLM推理子代理提供深度解读
- **🌐 RESTful API** - FastAPI服务层支持外部调用

## 📁 项目结构

```
kimi/
├── agents/                  # 智能体层
│   ├── base_agent.py        # BaseAgent 抽象基类
│   ├── wave_analyst.py      # 波浪分析智能体
│   ├── tech_analyst.py      # 技术分析智能体
│   ├── rotation_analyst.py  # 行业轮动智能体
│   └── ai_subagents/        # AI推理子代理
│       ├── base_ai_agent.py
│       ├── wave_reasoning_agent.py
│       └── __init__.py
│
├── analysis/                # 分析引擎
│   ├── wave/                # 艾略特波浪
│   │   ├── elliott_wave.py      # 波浪识别算法
│   │   ├── unified_analyzer.py
│   │   └── resonance.py
│   ├── technical/
│   │   └── indicators.py
│   └── backtest/
│
├── api/                     # FastAPI服务层
│   ├── __init__.py
│   └── main.py              # API入口
│
├── data/                    # 数据层
│   ├── db_manager.py
│   └── optimized_data_manager.py
│
├── scripts/                 # 运维脚本
│   └── data_sync/
│
├── tests/                   # 测试套件
│   ├── unit/                # 单元测试
│   ├── integration/         # 集成测试
│   ├── regression/          # 回归测试
│   └── run_all_tests.sh     # 测试运行脚本
│
├── docs/                    # 文档
│   ├── api.md               # API文档
│   ├── ai_subagent_design.md
│   └── testing.md           # 测试文档
│
├── config/config.yaml       # 全局配置
├── main.py                  # 系统主入口
└── requirements.txt
```

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件填入你的API Key
vim .env
```

### 启动API服务

```bash
# 启动FastAPI服务
python api/main.py

# 服务运行在 http://localhost:8000
# API文档: http://localhost:8000/docs
```

### 使用API

```bash
# 波浪分析
curl -X POST http://localhost:8000/api/v1/analysis/wave \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH", "use_ai": true}'

# 技术分析
curl -X POST http://localhost:8000/api/v1/analysis/technical \
  -d '{"symbol": "000001.SZ"}'

# 行业轮动
curl "http://localhost:8000/api/v1/analysis/rotation?use_ai=true"
```

### 运行测试

```bash
# 运行所有测试
./tests/run_all_tests.sh

# 或分别运行
python tests/integration/test_audit_fixes.py  # 集成测试
python tests/regression/test_audit_fixes.py   # 回归测试
```

## 📊 数据库状态

| 指标 | 数值 |
|------|------|
| 股票数量 | 588 只 |
| 总记录数 | 1,076,926 条 |
| 时间范围 | 1993–2026 |
| 查询速度 | 0.05 ms / 只（内存缓存） |

## 🏗️ 技术栈

| 层次 | 技术 |
|------|------|
| 运行时 | Python 3.12 |
| 主存储 | PostgreSQL 16 |
| 缓存 | Redis 7.3 |
| Web框架 | FastAPI 0.135 |
| AI模型 | DeepSeek-R1 / Claude Sonnet |
| 数据处理 | pandas 3.0 / numpy 2.4 |

## 📚 文档

- [API使用文档](docs/api.md) - RESTful API详细说明
- [测试文档](docs/testing.md) - 测试套件使用指南
- [AI子代理设计](docs/ai_subagent_design.md) - AI架构设计

## 🔑 安全提示

- API Key通过环境变量注入，配置中使用 `${VAR_NAME}` 占位符
- 切勿将真实Key提交到版本库
- 详见 `.env.example` 模板

## 📝 开发规范

- 提交格式：`fix(module):` / `feat(module):` / `test(module):`
- 提交前运行测试：`./tests/run_all_tests.sh`
- 代码格式化：`ruff format .`

## 📈 测试覆盖

| 测试类型 | 文件数 | 测试用例 | 代码行数 |
|---------|-------|---------|---------|
| 单元测试 | 4 | 20+ | 850+ |
| 集成测试 | 2 | 15+ | 500+ |
| 回归测试 | 1 | 12+ | 300+ |
| **总计** | **7** | **47+** | **1650+** |
