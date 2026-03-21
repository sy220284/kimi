# 智能体量化分析系统项目方案

**版本**: 2.0  
**状态**: 生产就绪 ✅  
**最后更新**: 2026-03-21

---

## 项目概述

基于智能体的A股量化分析系统，整合艾略特波浪识别、多指标共振、行业轮动分析与回测系统。

### 核心能力
- 🌊 **波浪分析** - 自动识别推动浪/调整浪(Zigzag/Flat/Triangle)
- 📊 **多指标共振** - MACD/RSI/KDJ/布林带综合信号
- 🏭 **行业轮动** - 申万行业指数动量分析
- 🤖 **AI增强** - LLM推理子代理提供深度解读
- 🔄 **回测系统** - 完整的策略回测与参数优化

---

## 系统架构 (V2.0)

### 1. 数据层

| 组件 | 技术 | 规模 | 状态 |
|------|------|------|------|
| **主存储** | PostgreSQL 16 | 267万条记录 | ✅ 运行中 |
| **缓存** | Redis 7.3 | 681MB内存 | ✅ 运行中 |
| **本地缓存** | CSV/Parquet | 414MB | ✅ 运行中 |

**数据源**:
- ✅ **主力**: 同花顺(THS) 前复权数据
- ✅ **备选**: 东方财富
- ✅ **退市补全**: Baostock

**数据规模** (2026-03-21):
- 股票数量: **646只**
- 行业数量: **123个申万行业**
- 总记录数: **267万条** (股票228万 + 行业39万)
- 时间跨度: **1993-2026** (33年)

### 2. 分析层

#### 波浪分析模块 (E1~E6增强)

| 组件 | 功能 | 状态 |
|------|------|------|
| `ElliottWaveAnalyzer` | 核心波浪识别算法 | ✅ 稳定 |
| `UnifiedWaveAnalyzer` | 统一入口 (推荐) | ✅ 稳定 |
| `WaveEntryOptimizer` | E1: 入场优化评分 | ✅ 已部署 |
| `ResonanceAnalyzer` | E2: 多指标共振 | ✅ 已部署 |
| `AdaptiveParameterOptimizer` | E2: 自适应参数 | ✅ 已部署 |
| `VolumeAnalyzer` | E5: 三维量能 | ✅ 已部署 |
| `ConfidenceDecay` | E6: 置信度衰减 | ✅ 已部署 |

**输出**: 波浪结构、目标位、止损位、入场评分、共振评分

#### 技术分析模块

| 指标类型 | 指标 | 状态 |
|----------|------|------|
| 趋势 | MA, EMA, MACD | ✅ |
| 动量 | RSI, KDJ, CCI | ✅ |
| 波动率 | Bollinger Bands, ATR | ✅ |
| 量能 | VolumeAnalyzer (E5) | ✅ |

#### 回测模块

| 功能 | 状态 |
|------|------|
| 资金加权总收益率 | ✅ |
| 动态止损 (ATR) | ✅ |
| 移动止盈 | ✅ |
| 时间止损 (E3) | ✅ |
| 保本止损 (E3) | ✅ |
| 参数优化 | ✅ |

### 3. 智能体层

| 智能体 | 功能 | AI增强 | 状态 |
|--------|------|--------|------|
| `WaveAnalystAgent` | 波浪分析 | ✅ 可选 | 运行中 |
| `TechnicalAnalystAgent` | 技术分析 | ✅ 可选 | 运行中 |
| `RotationAnalystAgent` | 行业轮动 | ✅ 可选 | 运行中 |

**AI子代理**:
- `WaveReasoningAgent` - 波浪形态深度推理
- `PatternInterpreterAgent` - 指标综合解读
- `MarketContextAgent` - 市场环境分析
- `StrategyAdvisorAgent` - 策略顾问

### 4. API层

- **框架**: FastAPI 0.135
- **地址**: `http://localhost:8000`
- **文档**: `http://localhost:8000/docs`
- **端点**: 健康检查、波浪分析、技术分析、行业轮动、批量分析

---

## 技术栈

| 层次 | 技术 | 版本 |
|------|------|------|
| 运行时 | Python | 3.12 |
| 主存储 | PostgreSQL | 16 |
| 缓存 | Redis | 7.3 |
| Web框架 | FastAPI | 0.135 |
| AI模型 | DeepSeek-R1 | - |
| 数据处理 | pandas | 3.0 |
| 数值计算 | numpy | 2.4 |

---

## E1~E6 系统性增强

### E1: 买点评分维度扩充 ✅

```python
entry_score = weighted_average([
    volume_score,      # 缩量评分
    ma_score,          # 均线评分 (MA20/MA60)
    bollinger_score,   # 布林带评分
])
```

### E2: 共振权重市场状态自适应 ✅

| 市场状态 | MACD权重 | RSI权重 | KDJ权重 | 布林带权重 |
|----------|----------|---------|---------|-----------|
| 趋势市场 | 35% | 25% | 20% | 20% |
| 震荡市场 | 25% | 35% | 25% | 15% |
| 高波动 | 30% | 20% | 20% | 30% |

### E3: 出场逻辑补全 ✅

- 时间止损: N周期无盈利离场
- 保本止损: 成本价止损保护

### E4: 信号召回率提升 ✅

- 参数历史管理 `wave_params_history/`
- 回测参数回传系统

### E5: VolumeAnalyzer 三维量能 ✅

| 维度 | 计算方式 |
|------|----------|
| 相对量能 | 当前成交量 / 历史均值 |
| 趋势量能 | 量能趋势方向 |
| 异常量能 | 突发放量/缩量检测 |

### E6: 信号置信度衰减机制 ✅

```python
decayed_confidence = original_confidence * time_decay * volatility_decay
```

---

## 数据库设计

### 1. 股票行情表
```sql
CREATE TABLE stock_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    date DATE,
    open DECIMAL(10, 4),
    high DECIMAL(10, 4),
    low DECIMAL(10, 4),
    close DECIMAL(10, 4),
    volume BIGINT,
    amount DECIMAL(15, 2),
    data_source VARCHAR(50) DEFAULT 'THS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stock_symbol_date ON stock_data(symbol, date);
```

### 2. 申万行业指数表
```sql
CREATE TABLE sw_industry_index (
    id SERIAL PRIMARY KEY,
    industry_code VARCHAR(20),
    industry_name VARCHAR(100),
    date DATE,
    open DECIMAL(10, 4),
    high DECIMAL(10, 4),
    low DECIMAL(10, 4),
    close DECIMAL(10, 4),
    volume BIGINT,
    amount DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sw_industry_date ON sw_industry_index(industry_code, date);
```

### 3. 分析结果表
```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    analyst_type VARCHAR(50),
    symbol VARCHAR(20),
    analysis_date DATE,
    result_json JSONB,
    confidence_score DECIMAL(5, 2),
    ai_enhanced BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_type_date ON analysis_results(analyst_type, analysis_date);
```

---

## 性能指标

| 指标 | 数值 | 状态 |
|------|------|------|
| 回测单股耗时 | 3.5ms | ✅ 优秀 |
| 批量分析速度 | 286股/秒 | ✅ 优秀 |
| 数据缓存命中率 | 98% | ✅ 优秀 |
| 内存查询延迟 | 0.05ms | ✅ 优秀 |
| 系统健康度 | 90/100 | ✅ 良好 |

---

## 测试覆盖

| 测试类型 | 文件数 | 代码行数 | 状态 |
|----------|--------|----------|------|
| 单元测试 | 50+ | 3900+ | ✅ |
| 集成测试 | 15+ | 1500+ | ✅ |
| 回归测试 | 3+ | 500+ | ✅ |
| E2E测试 | 5+ | 600+ | ✅ |
| **总计** | **96** | **6500+** | ✅ |

---

## 定时任务

| 任务 | 时间 | 功能 |
|------|------|------|
| 申万行业更新 | 15:30 (工作日) | 同步行业指数数据 |
| 股票数据更新 | 18:00 (工作日) | 增量更新股票数据 |
| 缓存清理 | 03:00 (每日) | 清理过期缓存文件 |

---

## API使用

```bash
# 启动服务
python api/main.py

# 波浪分析
curl -X POST http://localhost:8000/api/v1/analysis/wave \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH", "use_ai": true, "use_e1e6": true}'

# 行业轮动
curl "http://localhost:8000/api/v1/analysis/rotation?use_ai=true"
```

---

## 项目统计

| 指标 | 数值 |
|------|------|
| Python文件 | 200+ |
| 代码行数 | 30,000+ |
| 测试文件 | 96 |
| 脚本工具 | 59+ |
| 文档页数 | 3000+ 行 |

---

## 后续扩展

1. **机器学习集成** - 深度学习预测模型
2. **实时分析** - 流式数据处理
3. **多市场支持** - 港股、美股、加密货币
4. **自动化交易** - 与交易系统集成
5. **分布式回测** - 多进程/集群化

---

**项目负责人**: OpenClaw智能体系统  
**开始时间**: 2026年3月16日  
**当前状态**: ✅ **生产就绪**

---

*最后更新: 2026-03-21*
