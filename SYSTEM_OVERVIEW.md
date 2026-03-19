# 智能体量化分析系统 - 全景概览

## 📁 系统结构

```
kimi/
├── 📂 src/                          # 核心源代码
│   ├── 📂 agents/                   # 智能体模块
│   │   ├── base_agent.py           # 智能体基类（AgentInput/AgentOutput/状态机）
│   │   ├── wave_analyst.py         # 波浪分析智能体
│   │   ├── tech_analyst.py         # 技术分析智能体
│   │   └── rotation_analyst.py     # 板块轮动智能体（申万行业指数 + 板块回退）
│   │
│   ├── 📂 data/                     # 数据层
│   │   ├── db_manager.py           # 数据库管理
│   │   ├── optimized_data_manager.py # 优化数据管理（内存缓存 + 向量化）
│   │   ├── data_collector.py       # 数据采集器
│   │   ├── cache.py                # 本地缓存
│   │   ├── ths_history_fetcher.py  # 同花顺历史数据
│   │   ├── ths_adapter.py          # 同花顺适配器（主力数据源）
│   │   ├── tushare_adapter.py      # Tushare 适配器（备用）
│   │   ├── akshare_adapter.py      # AKShare 适配器（备用）
│   │   ├── multi_source.py         # 多数据源聚合
│   │   ├── quality_monitor.py      # 数据质量监控
│   │   └── data_api.py             # 统一数据接口
│   │
│   ├── 📂 analysis/                 # 分析模块
│   │   ├── 📂 wave/                 # 波浪分析
│   │   │   ├── elliott_wave.py     # 核心算法（ATR ZigZag + 推动浪/ZigZag/Flat 识别）
│   │   │   ├── unified_analyzer.py # 统一入口（C/2/4 浪检测 + 共振 + 趋势过滤）
│   │   │   ├── enhanced_detector.py # 增强极值点检测
│   │   │   ├── resonance.py        # 多指标共振（MACD/RSI/布林带/KDJ）
│   │   │   ├── adaptive_params.py  # 自适应参数（趋势/震荡/高低波动四状态）
│   │   │   ├── entry_optimizer.py  # 入场质量优化（量价/时间评分）
│   │   │   ├── wave2_detector.py   # 2 浪专项检测
│   │   │   ├── wave4_detector.py   # 4 浪专项检测
│   │   │   └── pattern_library.py  # 形态库
│   │   │
│   │   ├── 📂 technical/            # 技术指标
│   │   │   └── indicators.py       # MA/EMA/MACD/RSI/KDJ/布林带/ATR/OBV/MFI
│   │   │
│   │   ├── 📂 backtest/             # 回测系统
│   │   │   └── wave_backtester.py  # 波浪策略回测（资金加权收益/正确 Sharpe）
│   │   │
│   │   └── 📂 optimization/         # 策略优化
│   │       ├── param_optimizer.py  # 随机搜索参数优化
│   │       └── adaptive_backtest.py # 自适应回测
│   │
│   └── 📂 utils/                    # 工具模块
│       ├── db_connector.py         # 数据库连接器（连接池）
│       ├── config_loader.py        # 配置加载（环境变量替换）
│       └── logger.py               # 结构化日志
│
├── 📂 tests/                        # 测试脚本（74 个）
├── 📂 config/                       # 配置文件
│   └── config.yaml                 # 全局配置（DB / 模型 / 调度 / 分析参数）
├── 📂 docs/                         # 文档
├── 📂 scripts/                      # 脚本工具
│   ├── market_scanner.py           # 大盘扫描
│   ├── init_database.py            # 数据库初始化
│   └── sync_*.py                   # 数据同步脚本
├── 📂 memory/                       # 开发日志
├── requirements.txt                # 依赖（已更新至 2026-03-18 最新稳定版）
└── pyproject.toml                  # 工具配置（ruff / pytest / mypy）
```

## 📊 数据库状态

| 指标 | 数值 |
|------|------|
| 股票数量 | **588 只** |
| 总记录数 | **1,076,926 条** |
| 时间范围 | 1993–2026 |
| 表大小 | **200 MB** |
| 数据完整率 | **~100%** |

## 🚀 核心功能

### 1. 数据采集
- ✅ 同花顺历史数据（主力，支持 1993 年起全量历史）
- ✅ Tushare / AKShare 备用降级
- ✅ 多源聚合 + 字段标准化

### 2. 数据存储
- ✅ PostgreSQL 持久化（主表 + 申万行业指数表 + 分析结果表）
- ✅ Redis 缓存
- ✅ 本地文件缓存（`.cache/`）
- ✅ 数据质量监控（价格/成交量异常检测）

### 3. 波浪分析
- ✅ ATR 自适应 ZigZag 极值点检测（动态阈值，优于固定窗口）
- ✅ 推动浪（1-2-3-4-5）严格规则验证（浪3非最短/浪4不重叠等）
- ✅ ZigZag 调整浪（A-B-C）识别
- ✅ **Flat 平台型调整浪**识别（Regular / Expanded / Running，A 股最常见）
- ✅ 量价辅助验证（VolumeAnalyzer）
- ✅ 斐波那契比例验证（0.382 / 0.618 / 1.618）
- ✅ 多指标共振（MACD / RSI / 布林带 / KDJ 加权）
- ✅ 自适应参数（四种市场状态）
- ✅ 入场质量优化（量价/时间/MACD 综合评分，阈值 0.55）

### 4. 技术指标
- ✅ MA / EMA / MACD / RSI / KDJ / 布林带 / ATR / OBV / MFI（全部向量化）

### 5. 回测系统
- ✅ 前瞻偏差修复（仅使用当日前的历史数据）
- ✅ 涨跌停处理（科创板/创业板 20% / 主板 10% 分级阈值）
- ✅ 移动止盈 + ATR 动态止损
- ✅ 交易成本模型（佣金 0.03% + 印花税 0.1% + 滑点 0.1%）
- ✅ **资金加权总收益率**（修复原加总错误）
- ✅ **正确 Sharpe 比率**（基于日权益收益率 + 3% 无风险利率）
- ✅ 策略状态重置（防止批量回测污染）

### 6. 板块轮动分析
- ✅ 申万行业指数主路径（查询 sw_industry_index 表）
- ✅ 板块聚合回退路径（行业表为空时自动降级，覆盖全量个股）
- ✅ 行业动量 / 相对强弱 / 趋势判断 / 配置建议

### 7. 智能体层
- ✅ 三大智能体接口契约修复（analyze(AgentInput) → AgentOutput）
- ⏳ AI 推理接入（config.yaml 已配置 Claude / DeepSeek，代码待填充）

### 8. 性能优化
- ✅ 全量内存预加载（681 MB，O(1) 查询，0.05 ms/只）
- ✅ 向量化计算（10-100× 加速）

## 📈 回测结果概览

| 板块 | 股票数 | 总收益（资金加权） | 胜率 | 盈亏比 |
|------|--------|-------------------|------|--------|
| 科技板块 | 40 只 | 历史数据重新跑中 | ~33% | ~2.5:1 |
| 食品饮料 | 39 只 | 历史数据重新跑中 | ~31% | ~1.8:1 |

> 注：原 +82.25% / +37.60% 为收益率加总错误数值，收益率计算逻辑已于 2026-03-18 修正为资金加权，需重新跑回测。

## 🛠️ 技术栈

| 类别 | 选型 |
|------|------|
| 运行时 | Python 3.12 |
| 主存储 | PostgreSQL 16 |
| 缓存 | Redis 7.3 |
| 数据处理 | pandas 3.0 / numpy 2.4 |
| Web 框架 | FastAPI 0.135（规划中）|
| 调度 | Celery 5.6（规划中）|
| AI 模型 | Claude Sonnet 4.6 / DeepSeek-R1（配置已就绪）|
| Lint | ruff 0.15 / black 26.3 |

## 🔧 关键文件

| 文件 | 用途 |
|------|------|
| `src/data/optimized_data_manager.py` | 高速内存缓存核心 |
| `src/analysis/wave/unified_analyzer.py` | 波浪信号生成统一入口 |
| `src/analysis/wave/elliott_wave.py` | 艾略特波浪识别算法 |
| `src/analysis/wave/entry_optimizer.py` | 入场质量评分 |
| `src/analysis/backtest/wave_backtester.py` | 回测引擎 |
| `src/agents/rotation_analyst.py` | 行业轮动智能体 |
| `config/config.yaml` | 全局配置（含模型 API Key，注意脱密）|

## 📝 开发规范

- 所有提交按 `fix(module):` / `feat(module):` / `chore:` 前缀规范
- 每次提交前运行 `scripts/pre-commit.sh`（lint + 单测）
- API Key 通过环境变量注入，禁止明文写入代码
- 回测前必须调用 `strategy.reset()` 防止状态污染

---
*最后更新：2026-03-18*
