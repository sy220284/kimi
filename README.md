# 智能体量化分析系统

A 股量化分析平台，整合艾略特波浪识别、多指标共振、行业轮动分析与事件驱动回测。

---

## 🆕 最近更新

### 2026-03-21 - 系统性深度增强 E1~E6 ✅

| 增强项 | 内容 | 状态 |
|--------|------|------|
| **E1** | 买点评分维度扩充（缩量+均线+布林带） | ✅ 已合并 |
| **E2** | 共振权重市场状态自适应 | ✅ 已合并 |
| **E3** | 出场逻辑补全（时间止损+保本止损） | ✅ 已合并 |
| **E4** | 信号召回率提升（参数优化） | ✅ 已合并 |
| **E5** | VolumeAnalyzer 三维量能升级 | ✅ 已合并 |
| **E6** | 信号置信度衰减机制 | ✅ 已合并 |

**数据更新**：
- 移除3只退市股票（002013/300023/873593）
- 股票池：588 → **646只**
- 数据库：267万条记录

### 2026-03-20 - 架构优化与审计修复

**审计报告修复 (N-01 ~ N-07)**：
- P0: API Key和数据库密码改用环境变量
- P1: DB连接优化、AI子代理架构、重试机制
- P2: Triangle调整浪检测
- P3: FastAPI接口 + 测试套件（96个测试文件）
- 系统健康度：85/100 → **90/100**

**回测参数回传系统**：
- 创建 `config/wave_params.json` 参数持久化
- 创建 `utils/param_manager.py` 参数管理器
- 解决"报告参数与代码不一致"问题

**申万行业数据恢复**：
- 清空同花顺数据（仅7个月历史）
- 恢复申万数据：123个行业，39.4万条记录
- 时间跨度：1999-2026（26年完整历史）

---

## ✨ 核心特性

- **🌊 艾略特波浪分析** - 自动识别推动浪、调整浪(Zigzag/Flat/Triangle)
- **📊 多指标共振** - MACD、RSI、KDJ、布林带综合信号
- **🏭 行业轮动** - 申万行业指数动量分析
- **🤖 AI增强分析** - LLM推理子代理提供深度解读
- **🌐 RESTful API** - FastAPI服务层支持外部调用

---

## 📊 数据管理

- **默认数据源**: 同花顺(THS) 前复权数据
- **数据流程**: 批量拉取 → 本地缓存 → 导入数据库 → 自动清理
- **详细策略**: [docs/data_strategy.md](docs/data_strategy.md)

---

## 📁 项目结构

```
智能体系统/
├── agents/                  # 智能体层
│   ├── base_agent.py        # BaseAgent 抽象基类
│   ├── wave_analyst.py      # 波浪分析智能体
│   ├── tech_analyst.py      # 技术分析智能体
│   ├── rotation_analyst.py  # 行业轮动智能体
│   └── ai_subagents/        # AI推理子代理
│       ├── base_ai_agent.py
│       └── adapter.py
│
├── analysis/                # 分析引擎
│   ├── wave/                # 艾略特波浪
│   │   ├── elliott_wave.py      # 波浪识别算法
│   │   ├── unified_analyzer.py  # 统一入口
│   │   ├── resonance.py         # 多指标共振
│   │   ├── entry_optimizer.py   # 入场优化
│   │   └── adaptive_params.py   # 自适应参数
│   ├── technical/
│   │   └── indicators.py        # 技术指标
│   ├── backtest/
│   │   └── wave_backtester.py   # 回测引擎
│   └── optimization/
│       └── param_optimizer.py   # 参数优化
│
├── api/                     # FastAPI服务层
│   └── main.py              # API入口
│
├── data/                    # 数据层
│   ├── db_manager.py
│   ├── optimized_data_manager.py  # 内存缓存
│   └── mx_data_provider.py
│
├── scripts/                 # 运维脚本
│   ├── data_sync/           # 数据同步
│   ├── backtest/            # 回测执行
│   ├── analysis/            # 分析工具
│   └── maintenance/         # 维护工具
│
├── tests/                   # 测试套件
│   ├── unit/                # 单元测试 (50+)
│   ├── integration/         # 集成测试 (15+)
│   ├── regression/          # 回归测试 (3+)
│   ├── e2e/                 # 端到端测试 (5+)
│   └── run_all_tests.sh     # 测试运行脚本
│
├── docs/                    # 文档
│   ├── api.md
│   ├── data_strategy.md
│   ├── testing.md
│   └── ai_subagent_design.md
│
├── config/
│   ├── config.yaml          # 全局配置
│   ├── wave_params.json     # 波浪参数
│   └── wave_params_history/ # 参数历史
│
├── main.py                  # 系统主入口
└── requirements.txt
```

---

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

---

## 📊 数据库状态

| 指标 | 数值 |
|------|------|
| 股票数量 | **646 只** |
| 总记录数 | **2,670,000+ 条** |
| 时间范围 | 1993–2026 |
| 查询速度 | **0.05 ms** / 只（内存缓存）|

---

## 🏗️ 技术栈

| 层次 | 技术 |
|------|------|
| 运行时 | Python 3.12 |
| 主存储 | PostgreSQL 16 |
| 缓存 | Redis 7.3 |
| Web框架 | FastAPI 0.135 |
| AI模型 | DeepSeek-R1 / Claude Sonnet |
| 数据处理 | pandas 3.0 / numpy 2.4 |

---

## 📚 文档

- [API使用文档](docs/api.md) - RESTful API详细说明
- [测试文档](docs/testing.md) - 测试套件使用指南
- [AI子代理设计](docs/ai_subagent_design.md) - AI架构设计
- [数据策略](docs/data_strategy.md) - 数据管理策略
- [架构分析](docs/architecture_review.md) - 系统架构分析

---

## 🔑 安全提示

- API Key通过环境变量注入，配置中使用 `${VAR_NAME}` 占位符
- 切勿将真实Key提交到版本库
- 详见 `.env.example` 模板

---

## 📝 开发规范

- 提交格式：`fix(module):` / `feat(module):` / `test(module):`
- 提交前运行测试：`./tests/run_all_tests.sh`
- 代码格式化：`ruff format .`

---

## 📈 测试覆盖

| 测试类型 | 文件数 | 说明 |
|---------|-------|------|
| 单元测试 | 50+ | 核心功能测试 |
| 集成测试 | 15+ | 模块协作测试 |
| E2E测试 | 5+ | 端到端测试 |
| 回归测试 | 3+ | 防回退测试 |
| **总计** | **96** | 全面覆盖 |

---

## 📊 项目统计

- **Python文件**: 200+
- **代码行数**: 30,000+
- **测试文件**: 96
- **脚本工具**: 59+
- **文档页数**: 3000+ 行

---

*最后更新：2026-03-21*
