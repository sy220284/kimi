# 智能体量化分析系统

A股量化分析平台，整合艾略特波浪识别、多指标共振、行业轮动分析与事件驱动回测。

---

## 🆕 最新更新 (2026-03-21)

### ✅ E1~E6 系统性增强

| 增强 | 功能 | 状态 |
|------|------|------|
| **E1** | 买点评分维度扩充 | ✅ 完成 |
| **E2** | 共振权重市场状态自适应 | ✅ 完成 |
| **E3** | 出场逻辑补全 | ✅ 完成 |
| **E4** | 信号召回率提升 | ✅ 完成 |
| **E5** | VolumeAnalyzer 三维量能 | ✅ 完成 |
| **E6** | 信号置信度衰减机制 | ✅ 完成 |

### ✅ 审计修复 (N-01~N-07)

所有P0-P3问题已修复，系统健康度 **90/100**

---

## 📊 系统状态

| 指标 | 数值 |
|------|------|
| 股票数量 | **646只** |
| 申万行业 | **123个** |
| 总记录数 | **267万条** |
| 内存缓存 | 681MB |
| 测试文件 | 96个 |
| 系统健康度 | 90/100 |

---

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动API服务
python api/main.py

# 运行测试
./tests/run_all_tests.sh
```

---

## 📚 文档导航

- [项目方案](docs/project_specification.md)
- [API文档](docs/api.md)
- [架构分析](docs/architecture_review.md)
- [测试文档](docs/testing.md)
- [数据策略](docs/data_strategy.md)
- [AI子代理设计](docs/ai_subagent_design.md)
- [优化方案](docs/optimization_plan.md)
- [代码审计](docs/code_quality_audit_2026-03-21.md)

---

*最后更新: 2026-03-21*
