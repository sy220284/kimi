# 数据管理策略

## 📊 数据源策略（2026-03-21更新）

### 默认数据源

| 优先级 | 数据源 | 复权类型 | 用途 | 状态 |
|--------|--------|----------|------|------|
| **1** | 同花顺(THS) | **前复权** | 默认数据拉取 | ✅ 主力 |
| 2 | 东方财富 | 前复权 | 备选方案 | ✅ 可用 |
| 3 | Baostock | 前复权 | 退市股票补全 | ✅ 备用 |

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
│   ├── optimized_data_manager.py  # 优化数据管理（内存缓存 + 向量化）
│   ├── ths_data_manager.py        # THS数据管理（主）
│   ├── cache_manager.py           # 缓存管理
│   └── quality_monitor.py         # 数据质量监控
│
├── scripts/data_sync/
│   ├── sync_selfselect_ths.py     # 自选股同步
│   ├── sync_full_history.py       # 全量历史同步
│   ├── incremental_update_ths.py  # 增量更新
│   ├── fetch_sw_industry.py       # 申万行业数据获取
│   └── cache_cleanup.py           # 缓存清理脚本
│
└── config/
    ├── config.yaml                # 主配置
    ├── data_source.yaml           # 数据源配置
    └── all_industry_stocks.txt    # 全量股票列表
```

---

## 📊 数据规模（2026-03-21）

| 指标 | 数值 | 备注 |
|------|------|------|
| 股票数量 | **646只** | 已清理3只退市股 |
| 申万行业 | **123个** | 完整行业分类 |
| 股票记录 | **228万条** | 日线数据 |
| 行业记录 | **39.4万条** | 行业指数数据 |
| **总记录数** | **267万条** | - |
| 时间跨度 | 1999-2026 | 26年历史 |
| 内存占用 | 681MB | 全量预加载 |
| 查询速度 | 0.05ms | O(1)内存访问 |

### 申万行业数据

| 指标 | 数值 |
|------|------|
| 行业数量 | 123个 |
| 记录总数 | 39.4万条 |
| 时间跨度 | 1999-2026 |
| 数据完整性 | 100% |

**恢复记录**（2026-03-20）：
- 清空同花顺行业数据（仅7个月历史）
- 恢复申万数据：26年完整历史
- 定时更新：工作日15:30

---

## 🔧 核心配置

### data_source.yaml

```yaml
# 数据源配置
data_source:
  primary: THS                    # 主数据源
  fallback: EastMoney             # 备选数据源
  backup: Baostock                # 退市股票补全

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

# 行业数据
industry:
  source: SW                      # 申万行业指数
  update_time: "15:30"            # 更新时间
  workdays_only: true             # 仅工作日更新
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

### 4. 申万行业数据更新

```bash
# 获取申万行业数据
python scripts/data_sync/fetch_sw_industry.py

# 继续获取（断点续传）
python scripts/data_sync/fetch_sw_industry_continue.py
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
|--------|------|---------|
| 价格范围 | 0 < price < 10000 | 异常值标记 |
| 涨跌幅 | -20% ~ +20% (单日) | 除权日特殊处理 |
| 成交量 | volume >= 0 | 负值过滤 |
| 日期连续 | 交易日无缺失 | 填充或标记 |
| 复权一致性 | 无负价格 | 异常标记 |

### 复权校验

- ✅ 前复权数据无负价格
- ✅ 除权缺口平滑处理
- ✅ 分红送股比例正确

### 质量监控

```python
from data.quality_monitor import DataQualityMonitor

monitor = DataQualityMonitor()

# 检查数据质量
report = monitor.check_symbol('600519')
print(f"完整性: {report.completeness}")
print(f"异常值: {report.anomalies}")
print(f"缺失天数: {report.missing_days}")
```

---

## ⏰ 定时任务

### Cron配置

```bash
# 申万行业数据更新（工作日15:30）
30 15 * * 1-5 /usr/bin/python3 /path/to/fetch_sw_industry.py

# 股票数据增量更新（工作日18:00）
0 18 * * 1-5 /usr/bin/python3 /path/to/incremental_update_ths.py

# 缓存清理（每天凌晨3:00）
0 3 * * * /usr/bin/python3 /path/to/cache_cleanup.py --older-than 1
```

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

5. **退市股票处理**
   - 自动检测退市股票
   - 从股票池中移除
   - 保留历史数据供回测

---

## 📝 变更历史

| 日期 | 变更内容 |
|------|---------|
| 2026-03-21 | 数据规模扩展至267万条（股票228万 + 行业39万） |
| 2026-03-20 | 申万行业数据恢复（26年完整历史） |
| 2026-03-20 | 统一使用THS前复权数据，删除Tushare/AKShare |
| 2026-03-19 | 建立批量拉取→缓存→导入→清理流程 |
| 2026-03-18 | 清理3只退市股票（002013/300023/873593） |

---

*最后更新：2026-03-21*
