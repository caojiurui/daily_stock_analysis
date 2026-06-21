# ai-pan Consolidation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ai-pan` 扫描里真正有用的能力、创意和工具吸收进 `daily_stock_analysis`，并停止维护 `ai-pan` 的独立运行链路。

**Architecture:** 保留 DSA 作为唯一运行时，把 `ai-pan` 的价值拆成“扫描/候选组织”“新闻与外部证据”“复盘与校准”三组能力，分别并入现有机会引擎、页面和复盘统计链路。所有新能力都必须以 DSA 的现有路由、服务和页面为落点，不新增跨仓桥接，也不保留第二套前后端或存储。

**Tech Stack:** Python, FastAPI, Vue, existing DSA opportunity/portfolio services, existing news and external quote adapters.

---

## Scope

### Must keep
- 09:30 / 15:00 扫描思路
- 候选排序与“主线/前排”组织方式
- 新闻增强、标签过滤、可见板块联动
- 外部证据面板思路（雪球/行情/新闻）
- 复盘指标：关注样本、命中率、板块成功率

### Must drop
- `ai-pan` 独立后端、前端、数据库、缓存、启动脚本
- 双维护的跨仓同步链路
- 重复的抓取与展示实现

### DSA landing zones
- `src/extensions/opportunity/`：候选、风险预算、周期、外证字段
- `src/services/`：新闻、外部证据、复盘统计
- `api/v1/endpoints/`：现有机会/持仓/分析入口
- `apps/dsa-web/src/pages/`：`StockScreeningPage`、`PortfolioPage`
- `docs/personal-investment-roadmap.md`：把 5.8 后续拆解记录为 DSA 内部能力

## Design

### 1. Scanning layer
Use `ai-pan` 的扫描组织方式增强 DSA 的机会候选输出：先给出主线候选，再补充说明为什么上榜、为什么优先跟踪、当前偏向个股还是 ETF。这个层只做“排序和解释”，不新增独立扫描产品页。

### 2. Evidence layer
把 `ai-pan` 的新闻增强和外部证据组织方式并入 DSA：按可见板块刷新新闻、保留新闻状态分级、支持标签过滤，并用外部行情/雪球类证据补强候选解释。证据层只做辅助，不替代现有排序结论。

### 3. Review layer
吸收 `ai-pan` 的复盘指标，但落到 DSA 现有统计链路里：关注样本、成功率、板块成功率、日内/收盘验证结果都继续写入 DSA 的历史和汇总，不单独维护 ai-pan 的数据库口径。

## Non-goals

- 不复刻 `ai-pan` 整个页面
- 不把 `ai-pan` 变成 DSA 的外部依赖
- 不把所有 AI/证据能力一次性重写成新框架
- 不新增与当前页面职责重复的入口

## Acceptance Criteria

- DSA 可以独立运行，`ai-pan` 不是必需项
- 有用的扫描/新闻/复盘能力都能在 DSA 现有页面或 API 中找到落点
- 设计上没有跨仓调用、双存储、双前端
- roadmap 里 `5.8` 的边界与后续步骤清晰

