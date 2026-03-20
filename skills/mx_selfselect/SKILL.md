---
name: mx_selfselect
description: 本 Skill 基于东方财富通行证账户数据及行情底层数据构建，支持通过自然语言查询我的自选股列表、添加指定股票到我的自选股列表、从我的自选股列表中删除指定股票。
---

# 妙想自选股管理 Skill (mx_selfselect)

通过自然语言查询或操作我在东方财富通行证账户下的自选股数据，接口返回 JSON 格式内容。

## 使用方式

1. 在东方财富妙想 Skills 页面获取 apikey。
2. 将 apikey 存到环境变量，命名为 `MX_APIKEY`，检查本地 api 是否存在，若存在可直接用。
3. 使用 POST 请求如下接口，务必使用 POST 请求。

### 查询自选股

使用以下请求查询自选股列表：

```bash
curl -X POST --location 'https://mkapi2.dfcfs.com/finskillshub/api/claw/self-select/get' \
  --header 'Content-Type: application/json' \
  --header "apikey:${MX_APIKEY}"
```

### 添加/删除自选股

使用以下请求添加或删除自选股：

```bash
curl -X POST --location 'https://mkapi2.dfcfs.com/finskillshub/api/claw/self-select/manage' \
  --header 'Content-Type: application/json' \
  --header "apikey:${MX_APIKEY}" \
  --data '{"query": "把东方财富加入自选"}'
```

## 问句示例

| 类型 | query |
|------|-------|
| 查询自选股 | 查询我的自选股列表 |
| 添加自选股 | 把贵州茅台添加到我的自选股列表 |
| 删除自选股 | 把贵州茅台从我的自选股列表删除 |

## 接口结果释义

### 一、查询自选股接口

#### 1. 根节点 (Root Level)

这些是接口最外层的通用状态响应字段。

| 字段路径 | 类型 | 核心释义 |
|----------|------|----------|
| `status` / `code` | 数字 | 接口全局状态，0 = 成功 |
| `message` | 字符串 | 接口全局提示，ok = 成功 |
| `requestId` | 字符串 | 请求的唯一标识 ID（当前为空） |
| `data` | 对象 | **核心业务数据**，包含具体的选股结果和配置 |
| `stack` | 字符串 | 错误堆栈信息，报错时用于排查问题 |

#### 2. 核心数据对象 (`data`)

包含了本次股票筛选的具体条件、统计结果以及格式化后的数据。

| 字段名 | 说明 |
|--------|------|
| `allResults` | 完整的结构化数据对象（见下方详情）。 |
| `title` | 搜索/查询的标题或意图（`"我的自选"`）。 |

#### 3. 完整结果对象 (`data.allResults.result`)

这里包含了用于前端动态渲染数据表格（Table）所需的"表头定义"和"具体数据"。

##### 3.1 表头列定义 (`columns` 数组)

该数组定义了表格每一列的属性，每个对象代表一列。关键字段包括：

- `title`: 列名（如："最新价(元)"、"涨跌幅(%)"）。
- `key` / `indexName`: 数据绑定的字段键值或指标代码（如 `NEWEST_PRICE`、`CHG`）。
- `dataType`: 数据类型（如 `String`, `Double`, `Long`）。
- `sortable`: 是否支持排序（`true`/`false`）。
- `redGreenAble`: 是否需要支持红绿涨跌变色显示（如涨跌幅 `CHG` 为 `true`）。
- `unit`: 数据单位（如 `元`, `%`, `股`, `倍`）。
- `hide`: 是否默认隐藏该列。

##### 3.2 实际股票数据 (`dataList` 数组)

包含了符合条件的股票详细指标。

| 字段 Key | 含义说明 |
|----------|----------|
| `SECURITY_CODE` | 股票代码 |
| `SECURITY_SHORT_NAME` | 股票简称 |
| `MARKET_SHORT_NAME` | 所在市场简称（SZ：深交所，SH：上交所） |
| `NEWEST_PRICE` | 最新价（元） |
| `CHG` | 涨跌幅（%） |
| `PCHG` | 涨跌额（元） |
| `010000_TURNOVER_RATE...` | 换手率（%） |
| `010000_LIANGBI...` | 量比 |
| `010000_VOLUME...` | 成交量（股） |
| `010000_TRADING_VOLUMES...` | 成交额（元） |
| `010000_PE_D...` | 动态市盈率（倍） |
| `010000_PB...` | 市净率（倍） |
| `010000_TOAL_MARKET_VALUE...` | 总市值（元） |
| `010000_CIRCULATION_MARKET_...` | 流通市值（元） |

#### 数据结果为空

提示用户到东方财富 App 查询。

### 二、添加/删除自选股接口

#### 根节点 (Root Level)

这些是接口最外层的通用状态响应字段。

| 字段路径 | 类型 | 核心释义 |
|----------|------|----------|
| `status` / `code` | 数字 | 接口全局状态，0 = 成功 |
| `message` | 字符串 | 接口全局提示，ok = 成功 |
| `requestId` | 字符串 | 请求的唯一标识 ID（当前为空） |
