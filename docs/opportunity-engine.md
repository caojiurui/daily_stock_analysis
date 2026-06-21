# 机会引擎（Opportunity Engine）

本文档说明仓库中的可选机会引擎侧车能力。它的目标是基于现有数据抓取链路，补充一个“轻量机会摘要”层，而不是改写原有分析主流程、数据源优先级或 AlphaSift/告警主链路。

## 启用方式

- 默认关闭：`.env.example` 中默认值为 `OPPORTUNITY_ENGINE_ENABLED=false`
- 需要启用时，在 `.env` 中设置 `OPPORTUNITY_ENGINE_ENABLED=true` 后重启后端服务
- 关闭状态下：
  - `GET /api/v1/opportunities/overview` 会返回 `enabled=false` 的空载荷
  - Web `/screening` 页面只显示温和的关闭提示，不影响原有选股与分析流程
  - 机会类告警规则不允许创建

## 当前范围

机会引擎当前是一个 opt-in sidecar，核心实现位于：

- `src/extensions/opportunity/`
- `api/v1/endpoints/opportunities.py`
- `apps/dsa-web/src/api/opportunities.ts`
- `apps/dsa-web/src/pages/StockScreeningPage.tsx`

它复用现有 `DataFetcherManager` 读取板块、概念和热门股票数据，并在本地做轻量归一化和评分：

- 板块/概念机会分数：趋势、热度、新闻分数、复盘命中率
- 个股/ETF 风险预算：区分 `stock` 与 `etf` 的建议仓位与止损说明
- 筹码状态：A 股个股可标记为 `available/unavailable`，ETF、港股、美股默认 `not_supported`

当前还会额外接入一个轻量的外部信息源适配层：

- `src/extensions/opportunity/ths_provider.py`
- 通过 THS（同花顺）补充行业/概念摘要与个股异动榜单信号
- 默认只在机会引擎 overview / scan 侧车里消费，不改 `data_provider/` 主优先级
- 失败时只写入 `warnings`，不影响原有东财、AlphaSift、新闻搜索能力

当前实现明确保持以下边界：

- 不修改 `data_provider/` 的数据源优先级和 fallback
- 不改变主分析任务、报告生成、通知发送的既有流程
- 不新增依赖
- 关闭时不访问机会引擎数据源

## 外部信息源扩展（同花顺）

当前机会引擎已正式接入 THS 外部信息源，接入边界如下：

- 行业层：复用 THS 行业摘要，为 overview 提供额外行业热度参考
- 概念层：复用 THS 概念摘要与驱动事件，补充 `key_news` 与 `news_score`
- 个股层：复用 THS 部分异动榜单（如创新高、量价齐跌）为热门股候选补充外部信号标签

去重与职责约束：

- 东财 / `DataFetcherManager` 仍然是板块与概念排行的主来源
- AlphaSift 仍负责热点题材详情、题材路线与更重的外部证据整合
- 搜索新闻仍负责通用新闻检索与新闻催化解释
- THS 只补“东财没有、但对机会判断有帮助”的摘要信号，不复制主抓取链路

降级策略：

- THS 每个采集子任务都走独立超时保护
- 任一 THS 子源失败只会写入 `ths_provider_*` warning
- overview / scan 仍可继续返回东财 + 搜索新闻结果

补充说明：

- 当 THS 概念数据里能带出或解析出快讯分类 `tagId` 时，机会引擎会额外请求同花顺快讯分类接口，把最新一条分类快讯合并到 `key_news`，来源标记为 `ths_flashnews`
- 如果没有 `tagId`，或者接口不可用，则继续沿用原有 `ths_summary_event` 的摘要催化，不会阻断 overview / scan

## API

### `GET /api/v1/opportunities/overview`

返回轻量机会摘要，包含：

- `market_temperature`
- `top_sectors`
- `opportunities`
- `data_quality`
- `warnings`

这是一个“可空、可降级”的接口：

- 引擎关闭时返回 `enabled=false`
- 数据抓取失败时优先写入 `warnings`，而不是中断主系统

### `POST /api/v1/opportunities/scan`

提交后台扫描任务，返回 `task_id` / `trace_id`。当前扫描复用 overview 结果，并额外标记：

- `watchlist_only`
- `scan_mode=opportunity`

### `GET /api/v1/opportunities/tasks/{task_id}`

查询机会扫描任务状态，仅接受 `report_type=opportunity_scan` 的任务。

## Web 集成

当前只做最小接入：

- 在 `/screening` 页面顶部增加“机会摘要”卡片
- 不新增路由
- 不改 AlphaSift 原有操作入口
- 关闭时展示空态提示，开启时展示市场温度、板块摘要和少量机会项
- `/screening` 不会在进入页面时自动刷新机会摘要；需要用户手动点击“刷新机会摘要”后才会提交后台任务
- 机会摘要刷新走异步任务轮询，页面会继续展示上一次成功结果；刷新完成后自动替换，并在本地持久化最近一次成功内容与待恢复任务

## 机会告警（opt-in）

当 `OPPORTUNITY_ENGINE_ENABLED=true` 时，Alert API 允许创建以下 `target_scope=market` 的机会类规则：

- `sector_move`
- `news_catalyst`
- `opportunity_score_cross`

当前这三类规则的边界是：

- 仅在引擎开启时允许创建；关闭时返回 `unsupported_alert_type`
- 仅允许 `target_scope=market`
- 规则可以持久化保存
- `dry-run` 与当前 worker 只返回静态 `skipped` 结果，提示该规则已被存储，实时评估仍由后续机会引擎实现接管
- 不会因为这次接入而误接入旧的 `EventMonitor` 实时循环

这意味着本次交付先锁定“规则入口与存储契约”，而不是直接上线一套实时机会监控闭环。

## 风险与回滚

风险控制策略：

- 以配置开关为第一护栏，默认关闭
- 所有新能力都以旁路形式接入，不改变原主流程
- 失败优先降级为空结果或 warning，不扩散到原选股/分析链路

回滚方式：

1. 将 `OPPORTUNITY_ENGINE_ENABLED` 改回 `false` 并重启服务
2. 如需完全移除本次能力，revert 对 `src/extensions/opportunity/`、`api/v1/endpoints/opportunities.py`、前端机会摘要接入和相关文档/测试的改动
