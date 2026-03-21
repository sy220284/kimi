# API使用文档

## 概述

智能体量化分析系统提供RESTful API接口，支持波浪分析、技术分析、行业轮动分析等功能。

## 基础信息

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`
- **API文档**: `http://localhost:8000/docs` (Swagger UI)

---

## 端点列表

### 1. 健康检查

```http
GET /health
```

**响应示例**:
```json
{
  "status": "ok",
  "timestamp": "2026-03-21T12:00:00",
  "version": "2.0.0",
  "data_status": {
    "stocks": 646,
    "records": 2670000,
    "industries": 123
  }
}
```

---

### 2. 波浪分析

```http
POST /api/v1/analysis/wave
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 股票代码，如 `600519.SH` |
| start_date | string | 否 | 开始日期 `YYYY-MM-DD` |
| end_date | string | 否 | 结束日期 `YYYY-MM-DD` |
| use_ai | boolean | 否 | 是否启用AI增强，默认`false` |
| use_e1e6 | boolean | 否 | 是否启用E1~E6增强，默认`true` |

**请求示例**:
```json
{
  "symbol": "600519.SH",
  "start_date": "2024-01-01",
  "end_date": "2024-03-01",
  "use_ai": true,
  "use_e1e6": true
}
```

**响应示例**:
```json
{
  "symbol": "600519.SH",
  "status": "success",
  "wave_type": "impulse",
  "confidence": 0.85,
  "current_wave": "3",
  "target_price": 135.0,
  "stop_loss": 112.0,
  "entry_score": 0.78,
  "e1e6_enhancement": {
    "volume_score": 0.82,
    "ma_score": 0.75,
    "bollinger_score": 0.80,
    "resonance_weights": {
      "macd": 0.35,
      "rsi": 0.25,
      "kdj": 0.20,
      "bollinger": 0.20
    }
  },
  "ai_analysis": {
    "reasoning": "当前处于3浪主升浪，浪1长度10元...",
    "conclusion": "推动浪3浪进行中",
    "confidence": 0.82
  },
  "execution_time": 2.5
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| wave_type | string | 浪型：`impulse`/`zigzag`/`flat`/`triangle` |
| current_wave | string | 当前浪号：0-5或A-E |
| target_price | float | 目标价位 |
| stop_loss | float | 止损价位 |
| entry_score | float | E1: 买点评分 (0-1) |
| e1e6_enhancement | object | E1~E6增强详情 |

---

### 3. 技术分析

```http
POST /api/v1/analysis/technical
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbol | string | 是 | 股票代码 |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |
| use_ai | boolean | 否 | 是否启用AI增强 |

**请求示例**:
```json
{
  "symbol": "000001.SZ",
  "use_ai": false
}
```

**响应示例**:
```json
{
  "symbol": "000001.SZ",
  "status": "success",
  "signals": [
    {
      "indicator": "MACD",
      "signal": "buy",
      "score": 0.8
    },
    {
      "indicator": "RSI",
      "signal": "neutral",
      "score": 0.5
    },
    {
      "indicator": "KDJ",
      "signal": "buy",
      "score": 0.75
    },
    {
      "indicator": "Bollinger",
      "signal": "neutral",
      "score": 0.6
    }
  ],
  "combined_signal": {
    "score": 0.7,
    "signal": "buy",
    "strength": "moderate"
  },
  "confidence": 0.75,
  "ai_analysis": null,
  "execution_time": 0.8
}
```

---

### 4. 行业轮动分析

```http
POST /api/v1/analysis/rotation
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| use_ai | boolean | 否 | 是否启用AI增强 |

**请求示例**:
```http
POST /api/v1/analysis/rotation?use_ai=true
```

**响应示例**:
```json
{
  "status": "success",
  "strong_industries": [
    {
      "name": "半导体",
      "code": "801081",
      "momentum_20d": 15.5,
      "rank": 1
    }
  ],
  "weak_industries": [
    {
      "name": "房地产",
      "code": "801181",
      "momentum_20d": -8.5,
      "rank": 123
    }
  ],
  "buy_point_industries": [
    {
      "name": "新能源",
      "code": "801733",
      "buy_signal": {
        "type": "C浪",
        "confidence": 0.8
      }
    }
  ],
  "recommendation": "超配半导体、AI，低配房地产",
  "data_source": "SW",
  "industry_count": 123,
  "ai_analysis": {
    "market_style": "成长主导",
    "rotation_rhythm": "适合埋伏"
  },
  "confidence": 0.9,
  "execution_time": 3.2
}
```

---

### 5. 批量分析

```http
POST /api/v1/analysis/batch
```

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| symbols | array | 是 | 股票代码列表 |
| analysis_type | string | 是 | 分析类型：`wave`/`technical`/`both` |
| use_ai | boolean | 否 | 是否启用AI增强 |
| max_workers | int | 否 | 并发数，默认4 |

**请求示例**:
```json
{
  "symbols": ["600519.SH", "000001.SZ", "000858.SZ"],
  "analysis_type": "wave",
  "use_ai": false,
  "max_workers": 4
}
```

**响应示例**:
```json
{
  "status": "success",
  "results": [
    {
      "symbol": "600519.SH",
      "wave_type": "impulse",
      "confidence": 0.85
    },
    {
      "symbol": "000001.SZ",
      "wave_type": "flat",
      "confidence": 0.72
    }
  ],
  "summary": {
    "total": 3,
    "success": 3,
    "failed": 0,
    "execution_time": 5.2
  }
}
```

---

### 6. 股票搜索

```http
GET /api/v1/stocks/search?keyword={keyword}&limit={limit}
```

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| limit | int | 否 | 返回数量，默认10，最大50 |

**响应示例**:
```json
{
  "stocks": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "type": "stock"
    }
  ],
  "keyword": "茅台",
  "total": 1
}
```

---

### 7. 系统状态

```http
GET /api/v1/system/status
```

**响应示例**:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "data": {
    "stocks": 646,
    "industries": 123,
    "total_records": 2670000,
    "memory_usage": "681MB",
    "query_latency": "0.05ms"
  },
  "e1e6_status": {
    "enabled": true,
    "features": ["E1", "E2", "E3", "E4", "E5", "E6"]
  },
  "timestamp": "2026-03-21T12:00:00"
}
```

---

## AI增强模式

### 启用AI

在请求中设置 `use_ai: true` 可启用AI推理子代理：

- **WaveReasoningAgent**: 波浪形态深度推理
- **PatternInterpreterAgent**: 多指标共振解读
- **MarketContextAgent**: 市场环境分析

### AI响应格式

```json
{
  "ai_analysis": {
    "reasoning": "AI推理过程...",
    "conclusion": "核心结论",
    "confidence": 0.85,
    "action": "buy/hold/sell",
    "target_range": {
      "low": 110.0,
      "mid": 115.0,
      "high": 120.0
    }
  }
}
```

---

## E1~E6增强模式

默认启用E1~E6系统性增强，可通过 `use_e1e6: false` 关闭。

| 增强 | 功能 | 响应字段 |
|------|------|---------|
| E1 | 买点评分维度扩充 | `entry_score`, `volume_score`, `ma_score`, `bollinger_score` |
| E2 | 共振权重自适应 | `resonance_weights` |
| E3 | 出场逻辑补全 | `stop_loss`, `time_exit` |
| E4 | 信号召回率 | `recall_score` |
| E5 | 三维量能 | `volume_dimensions` |
| E6 | 置信度衰减 | `decay_factor` |

---

## 错误处理

### HTTP状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 422 | 验证错误 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（数据加载中）|

### 错误响应格式

```json
{
  "detail": "错误描述信息",
  "error_code": "WAVE_001",
  "suggestion": "建议解决方案"
}
```

---

## 启动服务

```bash
# 安装依赖
pip install fastapi uvicorn

# 启动服务
python api/main.py

# 或使用uvicorn直接启动
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 使用示例

### Python

```python
import requests

# 波浪分析（带E1~E6增强）
response = requests.post(
    'http://localhost:8000/api/v1/analysis/wave',
    json={
        'symbol': '600519.SH',
        'use_ai': True,
        'use_e1e6': True
    }
)
data = response.json()
print(f"浪型: {data['wave_type']}, 目标价: {data['target_price']}")
print(f"买点评分: {data['entry_score']}")

# 批量分析
response = requests.post(
    'http://localhost:8000/api/v1/analysis/batch',
    json={
        'symbols': ['600519.SH', '000001.SZ'],
        'analysis_type': 'wave'
    }
)
```

### cURL

```bash
# 波浪分析
curl -X POST http://localhost:8000/api/v1/analysis/wave \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519.SH",
    "use_ai": true,
    "use_e1e6": true
  }'

# 行业轮动
curl "http://localhost:8000/api/v1/analysis/rotation?use_ai=true"

# 系统状态
curl http://localhost:8000/api/v1/system/status
```

---

## 注意事项

1. **API限制**: 建议本地使用，生产环境需添加限流
2. **AI成本**: 启用AI会增加API调用成本，建议合理使用缓存
3. **数据延迟**: 分析基于历史数据，非实时行情
4. **E1~E6增强**: 默认启用，会增加计算时间但提升信号质量

---

*最后更新：2026-03-21*
