# 智能体量化分析系统

## 📁 项目结构

```
智能体系统/
├── 📂 src/                          # 核心源代码
│   ├── 📂 agents/                   # 智能体模块
│   │   ├── base_agent.py           # 智能体基类
│   │   ├── wave_analyst.py         # 波浪分析智能体
│   │   ├── tech_analyst.py         # 技术分析智能体
│   │   └── rotation_analyst.py     # 板块轮动智能体
│   │
│   ├── 📂 data/                     # 数据层
│   │   ├── db_manager.py           # 数据库管理
│   │   ├── data_collector.py       # 数据采集器
│   │   └── ...
│   │
│   ├── 📂 analysis/                 # 分析模块
│   │   ├── 📂 wave/                 # 波浪分析
│   │   ├── 📂 technical/            # 技术指标
│   │   ├── 📂 backtest/             # 回测系统
│   │   └── 📂 optimization/         # 策略优化
│   │
│   └── 📂 utils/                    # 工具模块
│       ├── db_connector.py         # 数据库连接器
│       └── ...
│
├── 📂 tests/                        # 测试目录
│   ├── 📂 unit/                     # 单元测试
│   ├── 📂 integration/              # 集成测试
│   ├── 📂 e2e/                      # 端到端测试
│   ├── 📂 debug/                    # 调试脚本
│   ├── 📂 data_download/            # 数据下载脚本
│   ├── 📂 reports/                  # 报告生成脚本
│   ├── 📂 utils/                    # 测试工具
│   └── 📂 fixtures/                 # 测试数据
│
├── 📂 scripts/                      # 工具脚本
│   ├── 📂 data_sync/                # 数据同步脚本
│   ├── 📂 analysis/                 # 分析脚本
│   ├── 📂 maintenance/              # 维护脚本
│   └── 📂 deploy/                   # 部署脚本
│
├── 📂 config/                       # 配置文件
├── 📂 docs/                         # 文档
├── 📂 data/                         # 数据目录
│   ├── 📂 raw/                      # 原始数据
│   ├── 📂 processed/                # 处理后数据
│   └── 📂 cache/                    # 缓存数据
│
├── 📂 memory/                       # 开发日志
├── main.py                          # 主入口
├── requirements.txt                 # 依赖
└── pyproject.toml                   # 项目配置
```

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行主程序
python main.py

# 运行测试
pytest tests/
```

## 📝 开发规范

- 所有代码提交前运行 `./scripts/maintenance/pre-commit.sh`
- 单元测试放在 `tests/unit/`
- 集成测试放在 `tests/integration/`
- 数据同步脚本放在 `scripts/data_sync/`
