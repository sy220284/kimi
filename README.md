# 智能体量化分析系统

A 股量化分析平台，整合艾略特波浪识别、多指标共振、行业轮动分析与事件驱动回测。

## 📁 项目结构

```
kimi/
├── agents/                  # 智能体层
│   ├── base_agent.py        # BaseAgent 抽象基类（状态机 / AgentInput / AgentOutput）
│   ├── wave_analyst.py      # 波浪分析智能体
│   ├── tech_analyst.py      # 技术分析智能体
│   └── rotation_analyst.py  # 行业轮动智能体（申万行业指数 + 板块回退）
│
├── analysis/                # 分析引擎
│   ├── wave/                # 艾略特波浪
│   │   ├── elliott_wave.py      # ATR ZigZag + 推动浪 / ZigZag / Flat 识别
│   │   ├── unified_analyzer.py  # 统一信号入口（C/2/4浪 + 共振 + 趋势过滤）
│   │   ├── entry_optimizer.py   # 入场质量评分（量价 / 时间 / MACD）
│   │   ├── resonance.py         # 多指标共振（MACD / RSI / 布林带 / KDJ）
│   │   └── adaptive_params.py   # 自适应参数（四种市场状态）
│   ├── technical/
│   │   └── indicators.py    # MA / EMA / MACD / RSI / KDJ / ATR / OBV（向量化）
│   ├── backtest/
│   │   └── wave_backtester.py  # 回测引擎（资金加权收益 / 正确 Sharpe / 移动止盈）
│   └── optimization/
│       └── param_optimizer.py  # 随机搜索参数优化
│
├── data/                    # 数据层
│   ├── optimized_data_manager.py  # 全量内存缓存（681 MB，O(1) 查询）
│   ├── db_manager.py        # PostgreSQL 数据库管理
│   ├── ths_adapter.py       # 同花顺 HTTP 适配器（主力数据源）
│   ├── multi_source.py      # 多源聚合 + 自动降级
│   └── quality_monitor.py   # 数据质量监控
│
├── utils/                   # 工具层
│   ├── db_connector.py      # PostgreSQL / Redis 连接池
│   ├── config_loader.py     # YAML 配置 + 环境变量替换
│   └── logger.py            # 结构化日志
│
├── scripts/                 # 运维脚本
│   ├── data_sync/           # 数据同步
│   │   ├── incremental_update_ths.py   # 每日增量更新（含节假日日历）
│   │   ├── fill_missing_data.py        # 补全缺失日期数据
│   │   ├── fetch_sw_industry.py        # 拉取申万行业指数历史
│   │   ├── init_database.py            # 初始化数据库表结构
│   │   └── check_db.py / check_yesterday.py  # 数据诊断
│   ├── analysis/            # 分析脚本
│   │   └── analyze_trades.py  # 回测交易明细分析报告
│   └── maintenance/         # 维护脚本
│
├── tests/                   # 测试套件
│   ├── unit/                # 单元测试（50+ 文件）
│   ├── integration/         # 集成测试
│   ├── e2e/                 # 端到端回测验证
│   ├── debug/               # 调试脚本
│   ├── data_download/       # 数据下载工具
│   ├── reports/             # 报告生成
│   └── utils/               # 测试工具 / 回测运行
│
├── config/config.yaml       # 全局配置（DB / AI模型 / 调度 / 分析参数）
├── main.py                  # 系统主入口（demo/data/tech/batch/full 模式）
├── requirements.txt         # 依赖（Python 3.12，已锁定最新稳定版）
└── pyproject.toml           # ruff / pytest / mypy 配置
```

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/data_sync/init_database.py

# 拉取申万行业指数（可选，供轮动分析使用）
python scripts/data_sync/fetch_sw_industry.py

# 运行系统演示
python main.py --mode demo

# 每日数据增量更新
python scripts/data_sync/incremental_update_ths.py

# 运行回测
python tests/utils/run_tech_backtest.py

# 分析回测结果
python scripts/analysis/analyze_trades.py
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
| 数据处理 | pandas 3.0 / numpy 2.4 |
| AI 模型配置 | Claude Sonnet 4.6 / DeepSeek-R1（待接入） |
| Lint | ruff 0.15 |

## 📝 开发规范

- 提交格式：`fix(module):` / `feat(module):` / `chore:` / `refactor:`
- 提交前运行：`scripts/maintenance/` 下的 pre-commit 脚本
- API Key 通过环境变量注入，禁止明文写入代码
- 回测结果 CSV 已加入 `.gitignore`，不追踪到仓库

## 🔑 安全提示

`config/config.yaml` 中包含 API Key 配置项，请确保通过环境变量 `${CODEFLOW_API_KEY}` 等方式注入，
切勿将真实 Key 提交到版本库。
