# 数据管理策略

## 📊 数据源策略（2026-03-20更新）

### 默认数据源

| 优先级 | 数据源 | 复权类型 | 用途 |
|--------|--------|----------|------|
| **1** | 同花顺(THS) | **前复权** | 默认数据拉取 |
| 2 | 东方财富 | 前复权 | 备选方案 |

**⚠️ 已弃用数据源：**
- ~~Tushare~~ - 数据不复权，已删除
- ~~AKShare~~ - 网络受限，已删除
- ~~TENCENT~~ - 数据质量不稳定，已删除

---

## 🔄 数据拉取流程

### 标准流程（批量拉取→缓存→导入→清理）

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  批量拉取    │ → │  本地缓存    │ → │  导入数据库  │ → │  删除缓存    │
│  (THS API)  │    │  (CSV/Par)  │    │  (Postgre)  │    │  (自动清理)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 流程说明

1. **批量拉取**
   - 使用THS接口一次性拉取多只股票
   - 默认拉取5年历史数据（2020年至今）
   - 数据自动前复权处理

2. **本地缓存**
   - 临时存储在 `/tmp/quant_cache/` 目录
   - 格式：CSV 或 Parquet
   - 文件名：`{symbol}_{start}_{end}.csv`

3. **导入数据库**
   - 批量插入 PostgreSQL
   - ON CONFLICT 自动去重
   - data_source 标记为 'THS'

4. **删除缓存**
   - 导入成功后自动清理临时文件
   - 异常时保留日志供排查

---

## 📁 目录结构

```
智能体系统/
├── data/
│   ├── __init__.py
│   ├── db_manager.py              # 数据库管理
│   ├── ths_data_manager.py        # THS数据管理（主）
│   └── cache_manager.py           # 缓存管理
│
├── scripts/data_sync/
│   ├── sync_selfselect_ths.py     # 自选股同步
│   ├── sync_full_history.py       # 全量历史同步
│   ├── incremental_update_ths.py  # 增量更新
│   └── cache_cleanup.py           # 缓存清理脚本
│
└── config/
    └── data_config.yaml           # 数据配置
```

---

## 🔧 核心配置

### data_config.yaml

```yaml
# 数据源配置
data_source:
  primary: THS                    # 主数据源
  fallback: EastMoney             # 备选数据源

# THS配置
ths:
  api_timeout: 30                 # API超时(秒)
  retry_count: 3                  # 重试次数
  batch_size: 50                  # 批量拉取数量
  
# 缓存配置
cache:
  enabled: true
  directory: /tmp/quant_cache/
  format: csv                     # csv / parquet
  auto_cleanup: true              # 自动清理
  retention_hours: 24             # 保留时间(小时)

# 数据范围
data_range:
  default_years: 5                # 默认拉取年数
  max_years: 10                   # 最大拉取年数
  
# 复权设置
adjustment:
  type: pre_adjusted              # pre_adjusted / none
  apply_to: [open, high, low, close]
```

---

## 🚀 使用方式

### 1. 同步自选股

```bash
python scripts/data_sync/sync_selfselect_ths.py
```

### 2. 同步指定股票

```python
from data.ths_data_manager import THSDataManager

manager = THSDataManager()

# 同步单只股票
manager.sync_symbol('600519', years=5)

# 批量同步
symbols = ['000001', '600519', '000858']
for symbol in symbols:
    manager.sync_symbol(symbol)

manager.close()
```

### 3. 增量更新

```bash
# 每天定时更新
python scripts/data_sync/incremental_update_ths.py
```

---

## 🧹 缓存管理

### 自动清理

缓存文件在导入成功后自动删除，保留规则：
- ✅ 导入成功 → 立即删除
- ⚠️ 导入失败 → 保留24小时
- ❌ 超过24小时 → 自动清理

### 手动清理

```bash
# 清理所有缓存
python scripts/data_sync/cache_cleanup.py --all

# 清理超过1天的缓存
python scripts/data_sync/cache_cleanup.py --older-than 1
```

---

## 📊 数据质量

### 校验规则

| 检查项 | 规则 | 处理方式 |
|--------|------|----------|
| 价格范围 | 0 < price < 10000 | 异常值标记 |
| 涨跌幅 | -20% ~ +20% (单日) | 除权日特殊处理 |
| 成交量 | volume >= 0 | 负值过滤 |
| 日期连续 | 交易日无缺失 | 填充或标记 |

### 复权校验

- ✅ 前复权数据无负价格
- ✅ 除权缺口平滑处理
- ✅ 分红送股比例正确

---

## ⚠️ 注意事项

1. **不要混用不同复权类型数据**
   - 数据库中统一使用前复权
   - 如需不复权数据，单独建表存储

2. **缓存目录权限**
   - 确保 `/tmp/quant_cache/` 可写
   - 定期检查磁盘空间

3. **API限流**
   - THS接口有频率限制
   - 批量拉取时控制并发数

4. **数据更新**
   - 每日收盘后执行增量更新
   - 全量同步建议每周执行一次

---

## 📝 变更历史

| 日期 | 变更内容 |
|------|----------|
| 2026-03-20 | 统一使用THS前复权数据，删除Tushare/AKShare |
| 2026-03-19 | 建立批量拉取→缓存→导入→清理流程 |
