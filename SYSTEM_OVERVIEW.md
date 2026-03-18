# 智能体量化分析系统 - 全景概览

## 📁 系统结构

```
quant_agent_system/
├── 📂 src/                          # 核心源代码
│   ├── 📂 agents/                   # 智能体模块
│   │   ├── base_agent.py           # 智能体基类
│   │   ├── wave_analyst.py         # 波浪分析智能体
│   │   ├── tech_analyst.py         # 技术分析智能体
│   │   └── rotation_analyst.py     # 板块轮动智能体
│   │
│   ├── 📂 data/                     # 数据层
│   │   ├── db_manager.py           # 数据库管理
│   │   ├── optimized_data_manager.py # 优化数据管理(内存缓存+向量化)
│   │   ├── data_collector.py       # 数据采集器
│   │   ├── cache.py                # 本地缓存
│   │   ├── ths_history_fetcher.py  # 同花顺历史数据
│   │   ├── ths_adapter.py          # 同花顺适配器
│   │   ├── tushare_adapter.py      # Tushare适配器
│   │   ├── akshare_adapter.py      # AKShare适配器
│   │   ├── multi_source.py         # 多数据源聚合
│   │   ├── quality_monitor.py      # 数据质量监控
│   │   └── data_api.py             # 统一数据接口
│   │
│   ├── 📂 analysis/                 # 分析模块
│   │   ├── 📂 wave/                 # 波浪分析
│   │   │   ├── wave_detector.py    # 波浪检测器
│   │   │   └── wave_structure.py   # 波浪结构分析
│   │   │
│   │   ├── 📂 technical/            # 技术指标
│   │   │   └── indicators.py       # 技术指标计算
│   │   │
│   │   ├── 📂 backtest/             # 回测系统
│   │   │   ├── wave_backtester.py  # 波浪策略回测
│   │   │   └── unified_backtest.py # 统一回测框架
│   │   │
│   │   └── 📂 optimization/         # 策略优化
│   │       └── parameter_optimizer.py # 参数优化器
│   │
│   └── 📂 utils/                    # 工具模块
│       ├── db_connector.py         # 数据库连接器
│       ├── config_loader.py        # 配置加载
│       └── logger.py               # 日志管理
│
├── 📂 tests/                        # 测试脚本
│   ├── check_and_supplement.py     # 数据完整性检查
│   ├── auto_supplement.py          # 自动补充数据
│   ├── db_performance_test.py      # 数据库性能测试
│   ├── db_optimization_simple.py   # 优化方案对比
│   └── results/                    # 测试结果
│
├── 📂 config/                       # 配置文件
├── 📂 docs/                         # 文档
├── 📂 scripts/                      # 脚本工具
├── 📂 memory/                       # 记忆文件
└── 📄 requirements.txt              # 依赖清单
```

## 📊 数据库状态

| 指标 | 数值 |
|------|------|
| 股票数量 | **588只** |
| 总记录数 | **1,076,926条** |
| 时间范围 | 1993-2026 |
| 表大小 | **200MB** |
| 数据完整率 | **~100%** |

## 🚀 核心功能

### 1. 数据采集
- ✅ 同花顺历史数据 (主)
- ✅ Tushare适配
- ✅ AKShare适配
- ✅ 多源聚合/自动切换

### 2. 数据存储
- ✅ PostgreSQL持久化
- ✅ Redis缓存
- ✅ 本地缓存(.cache/)
- ✅ 数据质量监控

### 3. 数据分析
- ✅ 波浪理论分析 (艾略特波浪)
- ✅ 技术指标计算 (MA/RSI/MACD/布林带等)
- ✅ 板块轮动分析

### 4. 回测系统
- ✅ 波浪策略回测
- ✅ 移动止盈/止损
- ✅ 分级参数 (科创板10%/主板8%)
- ✅ ATR自适应止损
- ✅ 完整交易日志

### 5. 性能优化
- ✅ 内存缓存 (查询加速400x)
- ✅ 向量化计算 (计算加速10-100x)
- ✅ 数据库物理排序
- ✅ 批量数据导入

## 📈 回测结果概览

| 板块 | 股票数 | 平均收益 | 胜率 | 盈亏比 |
|------|--------|----------|------|--------|
| 科技板块 | 40只 | **+82.25%** | 33.2% | 2.5:1 |
| 食品饮料 | 39只 | **+37.60%** | 30.8% | 1.8:1 |
| 产业链 | 514只 | 验证中 | - | - |

## 🛠️ 技术栈

- **Python 3.12**
- **PostgreSQL 16** (主存储)
- **Redis** (缓存)
- **Pandas/NumPy** (向量化计算)
- **psycopg2** (PostgreSQL连接)

## 💡 优化亮点

### 查询性能
- 单股查询: **0.05ms** (400倍加速)
- 100只批量: **14ms** (140倍加速)
- 全表加载: **8秒** (681MB内存)

### 计算性能
- MA20计算: **100ms** /50只
- MACD计算: **157ms** /50只
- 全指标计算: **1.2秒** /50只

## 🔧 关键文件

| 文件 | 用途 |
|------|------|
| `src/data/optimized_data_manager.py` | 组合优化核心 |
| `src/analysis/backtest/wave_backtester.py` | 回测引擎 |
| `src/data/db_manager.py` | 数据库管理 |
| `tests/check_and_supplement.py` | 数据完整性 |
| `all_industry_stocks.txt` | 目标股票列表 |

---
*系统已就绪，可运行全量回测*
