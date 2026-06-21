# 个人投资助手完整路线图

本文档用于沉淀当前仓库围绕“个人投资助手 / 机会发现 / 选股与 ETF 辅助决策”方向的完整计划，并作为后续持续更新的唯一进度跟踪文档。

适用范围：

- 基于当前 `daily_stock_analysis` 仓库继续演进
- 覆盖你最早提出的扩展目标、已完成基线、未完成事项、阶段计划、验收标准和进度记录方式
- 默认优先 A 股场景，港股/美股作为后续兼容层

## 1. 文档使用方式

建议把本文件当作“主任务看板”使用：

- 新阶段开始前：先把对应阶段状态改成 `进行中`
- 每做完一项：勾选对应 checklist，并在“进度记录”里补一条
- 遇到范围变化：优先更新本文件，再改代码
- 需要决定是否继续做某项时：看“优先级 / 依赖 / 风险 / 验收标准”

状态约定：

- `已完成`：代码、文档、最小验证都已落地
- `进行中`：已开始，但未达到阶段验收标准
- `未开始`：尚未实施
- `后置`：不是当前最优先，明确延后
- `放弃`：确认不做，保留记录

## 2. 背景与目标

### 2.1 初始诉求

你最早提出的目标，不是继续“堆一个通用股票分析网站”，而是做一个更适合你自己的个人投资辅助工作台，重点包括：

- 在现有开源项目基础上继续扩展，不推倒重来
- 修复或优化不顺手的输入/使用路径，例如股票代码输入体验
- 增加“基于最近新闻判断今日板块强弱”的能力
- 增加“实时监控新闻与板块异动，并通知”的能力
- 增加“一键扫描后给出短期 / 中期 / 长期判断”的能力
- 增加“帮你挑股票 / ETF”的能力
- 支持把另一个项目 `ai-pan` 融合进来
- 评估是否接入同花顺等更有价值的数据/内容入口
- 评估是否扩展一套更适合该场景的 skill / agent 能力
- 对标成熟股票分析 / 量化框架，找出当前系统缺口

### 2.2 用户画像

当前目标用户画像默认以你自己为主：

- 会编程
- 刚进入股票投资领域
- 启动资金约 `1.5W`
- 需要更多“可执行建议 + 风险约束 + 简明解释”，而不是纯技术名词堆叠
- 更关心：
  - 哪些板块值得关注
  - 更适合买 ETF 还是个股
  - 小资金仓位怎么控制
  - 什么时候该观察、什么时候该减少动作

### 2.3 总体产品目标

长期目标不是单一分析接口，而是一套“轻量个人投资工作台”：

- 今日机会摘要
- 实时异动监控
- 新闻催化与板块联动
- 自选 / 持仓 / 告警联动
- ETF / 个股可操作标的映射
- 短中长期判断
- 小资金风险控制建议

## 3. 当前已完成基线（截至 2026-06-21）

以下内容已经在仓库中落地：

### 3.1 已有基础能力（原仓库长期能力）

- 个股分析主流程
- 大盘复盘
- 历史报告与详情查看
- 持仓管理与风险分析
- 告警中心
- Web 前端与桌面端
- AlphaSift 选股集成

### 3.2 本轮已新增能力

#### 机会引擎 MVP

状态：`已完成`

已完成内容：

- 新增可选配置开关 `OPPORTUNITY_ENGINE_ENABLED`
- 新增机会引擎旁路能力，不侵入原主流程
- 新增接口：
  - `GET /api/v1/opportunities/overview`
  - `POST /api/v1/opportunities/scan`
  - `GET /api/v1/opportunities/tasks/{task_id}`
- 新增机会引擎核心实现：
  - `src/extensions/opportunity/schemas.py`
  - `src/extensions/opportunity/scoring.py`
  - `src/extensions/opportunity/service.py`
- Web `/screening` 页顶部新增“机会摘要”卡片
- 新增文档 `docs/opportunity-engine.md`

#### 机会类告警与监控闭环

状态：`已完成`

已完成内容：

- 新增机会类告警类型：
  - `sector_move`
  - `news_catalyst`
  - `opportunity_score_cross`
- 仅允许在 `OPPORTUNITY_ENGINE_ENABLED=true` 时创建
- 仅允许 `target_scope=market`
- 已接入真实 evaluator、worker 触发、`alert_triggers` 写入与通知闭环
- 内置快照缓存、降噪与节流策略
- 不会误接入旧 `EventMonitor` 实时循环

#### 后端验证

状态：`已完成`

已完成内容：

- 补齐机会引擎与机会告警相关后端测试
- 定向 unittest 已通过
- 定向 `py_compile` 已通过

## 4. 初始计划与当前完成度总表

| 初始想法 | 当前状态 | 备注 |
| --- | --- | --- |
| 在现有项目基础上扩展，而不是大改主流程 | 已完成 | 已采用 sidecar / opt-in 方式接入 |
| 机会摘要 / 板块机会概览 | 已完成 MVP | 仅实现轻量版 |
| 小资金风险预算建议 | 已完成 MVP | 仅基础规则 |
| 机会类告警入口 | 已完成 | 已接入真实 evaluator、worker 与通知闭环 |
| 股票代码 / 输入体验优化 | 已完成 | 已补齐输入容错、联想、别名归一与低门槛选股入口 |
| 每日根据最近新闻判断板块涨跌 | 已完成 | 已补齐 `key_news`、板块新闻催化加分与页面解释闭环 |
| 实时新闻监控并通知板块异动 | 已完成 | 依托机会 worker 轮询 overview 与 `news_catalyst` 规则闭环，不是独立新闻 crawler |
| 一键扫描并给短中长期判断 | 已完成 | 扫描结果已输出 `cycle_view`、`action_label` 与组合辅助字段 |
| 真正帮你挑股票 / ETF | 已完成 | 当前已形成“主题 -> ETF / 个股候选 -> 风险预算 -> 周期判断 -> 自选/告警联动”的轻量推荐闭环，但不承诺收益、也不扩展到完整投顾系统 |
| `watchlist_only` 真正生效 | 已完成 | 扫描结果已按自选列表过滤 |
| 真实 ETF 映射 | 已完成 | 已补齐主题 ETF 映射与候选联动 |
| 接入同花顺等更高价值信息源 | 已完成 | 已补齐机会引擎侧车内的正式 THS 适配层，补充板块/概念摘要、驱动事件与个股异动信号，且保持可降级 |
| 吸收 `ai-pan` 有价值能力 | 已完成 | 已完成单仓吸收方案、扫描/证据/复盘能力落地，`/screening` 与 `/portfolio` 已统一复用且不再依赖 `ai-pan` 运行时 |
| 扩展更适合该场景的 skill 体系 | 已完成 | 已补齐 6 个仓库级专用 skill，覆盖板块机会、ETF 选择、新闻催化、盘中异动、新手解释与组合辅助 |
| 对标成熟股票分析 / 量化架构并补缺 | 已完成 | 已新增能力缺口与对标文档，明确值得复制与不值得复制的模块边界 |
| 构建完整个人投资工作台 | 已完成 | 当前已通过 `/screening`、`/portfolio`、`/alerts` 三页联动形成最小工作台闭环，后续重点转向增强而非补主线缺口 |

## 5. 明确未完成事项（完整清单）

下面是所有尚未完成、但和初始计划直接相关的事项，按主题分类。

### 5.1 输入与交互体验

状态：`已完成`

- [x] 股票代码输入容错
- [x] 股票简称 / 别名 / 大小写归一
- [x] 港股、美股、A 股输入统一规范
- [x] 输入联想与自动补全
- [x] ETF / 板块 / 概念词快捷搜索
- [x] 扫描参数的低门槛 UI（适合非量化用户）

### 5.2 新闻驱动的板块理解

状态：`已完成`

- [x] 聚合最近新闻并形成统一结构
- [x] 新闻去重
- [x] 新闻时效过滤
- [x] 标题 / 摘要关键词映射到板块 / 概念
- [x] 生成 `key_news`
- [x] 根据新闻催化给板块加分
- [x] 在页面展示“为什么这个板块上榜”

### 5.3 实时机会监控与通知

状态：`已完成`

- [x] 独立机会评估 worker（复用现有 AlertWorker 执行链路）
- [x] `sector_move` 真实 evaluator
- [x] `news_catalyst` 真实 evaluator
- [x] `opportunity_score_cross` 真实 evaluator
- [x] 机会快照缓存
- [x] 真实写入 `alert_triggers`
- [x] 真实通知闭环
- [x] 降噪与节流策略

### 5.4 可操作标的层

状态：`已完成`

- [x] 真实 ETF 映射
- [x] 主题 ETF / 行业 ETF / 宽基 ETF 分类
- [x] 机会项映射到真实 ETF 代码
- [x] `watchlist_only` 真正过滤
- [x] 候选排序逻辑从“摘要”升级为“可执行候选”
- [x] 候选结果增加可操作说明

### 5.5 个股 / ETF 推荐与仓位辅助

状态：`已完成`

已完成：

- [x] 小资金基础仓位建议
- [x] stock / etf 基础风险预算分流
- [x] 最大持仓数建议
- [x] 仓位分配建议
- [x] 再平衡建议
- [x] “先观察、后行动”的解释性文案

- [x] 个股 vs ETF 的策略偏好切换
- [x] 稳健 / 平衡 / 激进模式
- [x] 单笔风险限制建议

### 5.6 短期 / 中期 / 长期判断

状态：`已完成`

- [x] 短期判断规则
- [x] 中期判断规则
- [x] 长期判断规则
- [x] 周期判断的解释字段
- [x] 与市场温度 / 板块强度 / 新闻催化联动
- [x] 在页面中清晰展示周期判断

### 5.7 自选 / 持仓 / 告警联动

状态：`已完成`

- [x] 从机会项一键加入自选
- [x] 从机会项一键创建告警
- [x] 从持仓页反查当前板块机会
- [x] 基于持仓页做“关联板块风险与机会”提示
- [x] 自选列表驱动机会扫描
- [x] 自选与机会监控联动

### 5.8 `ai-pan` 集成

状态：`已完成`

- [x] 明确 `ai-pan` 集成目标改为“单仓吸收”，后续只维护 `daily_stock_analysis`
- [x] 梳理 `ai-pan` 与本仓库的重复能力，明确保留扫描、证据、复盘思路
- [x] 明确最小集成边界：先落在机会概览、`/screening` 与 `/portfolio`
- [x] 决定采用单仓吸收而不是弱耦合调用
- [x] 首轮补齐扫描层的主线 / 前排 / 排序解释摘要
- [x] 首轮补齐复盘层的板块胜率摘要与 review snapshot 聚合
- [x] 机会概览的 `review_snapshot` 可优先读取已落盘 `market_review` history 中的板块复盘样本，缺失时回退当前板块信号聚合
- [x] 新落盘的 `market_review_payload` 已补齐标准化 `opportunity_review` 结构，后续 DSA 读侧统一复用单仓历史格式
- [x] 机会概览的 `market_outlook` 已补齐轻量 `reasoning`，`/screening` 与 `/portfolio` 统一复用同一段判断解释
- [x] 机会概览的 `market_outlook.reasoning` 已补齐 `market_review` 历史宽度上下文，统一吸收 ai-pan 风格的上涨/下跌家数解释
- [x] 若历史快照未携带复盘行，`market_review` 写入侧会继续把历史聚合出的真实板块命中率 / 样本数回填到本次 `sectors.top`
- [x] 完成 roadmap / changelog / 相关测试验证收口，`5.8` 阶段闭环完成

### 5.9 外部信息源扩展（含同花顺）

状态：`已完成`

- [x] 评估同花顺的可接入方式与稳定性
- [x] 明确哪些信息值得引入
- [x] 与现有东财 / AlphaSift / 搜索新闻能力去重
- [x] 设计 provider 适配边界
- [x] 明确 fallback / timeout / 降级策略

已完成说明：

- 机会引擎新增 `src/extensions/opportunity/ths_provider.py`，作为独立 THS 适配层
- 已接入 THS 行业摘要、概念摘要与驱动事件，用于补充 `top_sectors`、`key_news` 与板块 `news_score`
- 已接入 THS 个股异动榜单中的轻量信号（当前先使用创新高、量价齐跌），用于增强热门股候选的外部标签与分数
- 保持东财 / `DataFetcherManager` 为主排行来源，THS 只作为补充信号，不改变原数据源优先级
- 每个 THS 子采集链路都带独立超时与失败降级，异常只写入 `warnings`，不会阻断 overview / scan

### 5.10 专用 skill / agent 体系

状态：`已完成`

- [x] 板块机会分析 skill
- [x] ETF 选择 skill
- [x] 新闻催化聚合 skill
- [x] 日内异动监控 skill
- [x] 新手解释型 skill
- [x] 组合与仓位辅助 skill

已完成说明：

- 已在 `.claude/skills/` 下补齐 6 个仓库级 skill
- 每个 skill 都围绕现有机会引擎、AlphaSift、持仓/告警联动能力设计
- 保持与仓库当前协作资产风格一致，不新增平行治理格式
- 重点目标是复用常见研究动作，而不是再造新的运行时

### 5.11 成熟架构对标与能力补缺

状态：`已完成`

- [x] 调研成熟股票分析产品的核心功能结构
- [x] 调研成熟量化 / research workflow 的模块分层
- [x] 对比本仓库现状和缺口
- [x] 输出能力缺口文档
- [x] 识别哪些能力适合复制，哪些不适合

已完成说明：

- 已新增 `docs/investment-capability-gap-analysis.md`
- 文档聚焦“个人投资助手”定位，不把券商交易、社交社区、机构量化云平台作为必须复制目标
- 已明确当前仓库优势、主要缺口、优先补强项与不建议复制的方向

## 6. 阶段路线图

本路线图默认按“先做最能形成闭环的能力，再做复杂整合”的原则推进。

### Phase 0：当前基线收口

状态：`已完成`

目标：

- 建立机会引擎旁路能力
- 补文档、测试和基础契约

已完成：

- [x] `opportunities` API
- [x] Web 顶部机会摘要
- [x] 机会告警契约
- [x] 文档与测试

### Phase 1：新闻 -> 板块 -> 机会摘要

状态：`已完成`

目标：

- 让机会引擎真正具备“新闻驱动板块判断”能力

核心任务：

- [x] 新闻聚合服务
- [x] 新闻去重与时效控制
- [x] 新闻映射到板块 / 概念
- [x] `key_news` 真实输出
- [x] 新闻催化分并入机会分数
- [x] 页面展示新闻催化解释

阶段验收：

- overview 返回非空 `key_news`
- 机会项能展示“上榜原因”
- 新闻失败时 overview 仍能返回

### Phase 2：实时机会监控闭环

状态：`已完成`

目标：

- 把机会告警从静态契约升级成真实实时评估能力

核心任务：

- [x] 机会评估 worker
- [x] 机会快照缓存
- [x] 机会类 alert evaluator
- [x] 触发历史与通知
- [x] 降噪与节流

阶段验收：

- 机会类规则可真实触发
- 告警中心可看到真实触发记录
- 关闭开关时无任何副作用

### Phase 3：可操作标的层

状态：`已完成`

目标：

- 把“板块机会”落到“具体 ETF / 个股候选”

核心任务：

- [x] ETF 映射表
- [x] `watchlist_only` 生效
- [x] 候选排序增强
- [x] 个股与 ETF 的建议分流
- [x] 从机会到操作建议的解释

阶段验收：

- 至少主要板块能映射到真实 ETF
- 能只看自选范围内结果
- 页面能展示真实标的而不是占位项

### Phase 4：新手友好的周期判断与组合辅助

状态：`已完成`

目标：

- 给出短中长期判断和适合小资金的行动建议

核心任务：

- [x] 短中长期判断引擎
- [x] 风险偏好模式
- [x] 仓位分配建议
- [x] 最大持仓数建议
- [x] ETF / 个股比例建议
- [x] 再平衡与观察优先提示

阶段验收：

- 输出不只是“机会排序”，而是“适合怎么做”
- 对新手用户更易理解

### Phase 5：工作台化与跨模块联动

状态：`已完成`

目标：

- 做成真正的个人投资工作台，而不只是分析接口集合

核心任务：

- [x] 独立机会看板页面（评估后决定不单独拆页，保持三页联动）
- [x] 今日机会 / 实时异动 / 自选 / 告警视图
- [x] 自选 / 持仓 / 告警 / 机会联动
- [x] 操作快捷入口

阶段验收：

- 用户可以在一个页面里完成“看机会 -> 加自选 -> 设告警 -> 回看结果”

### Phase 6：吸收 `ai-pan` 能力并收口到单仓

状态：`已完成`

目标：

- 让当前系统吸收 `ai-pan` 里真正有用的扫描、证据、复盘能力，同时不保留第二套运行时

核心任务：

- [x] 梳理 `ai-pan` 能力边界
- [x] 确定最小集成层
- [x] 选择单仓吸收作为集成方式
- [x] 完成机会概览 payload、`/screening`、`/portfolio` 的首轮联动
- [x] 完成主线 / 前排 / 板块胜率摘要的首轮接线
- [x] 做复盘统计真实历史接线（优先读取已落盘 `market_review` history，缺失时回退当前信号）
- [x] 把标准化 `opportunity_review` 块写回 `market_review` history，统一后续复用结构
- [x] 完成剩余阶段验收与文档收口

阶段验收：

- DSA 单仓内可稳定使用吸收后的扫描 / 证据 / 复盘能力，且不依赖 `ai-pan` 运行时

已吸收能力：

- 扫描层：主线 / 前排 / 排序解释、个股 / ETF 偏好与风险模式统一落在机会概览与 `/screening`
- 证据层：`news_status`、`market_outlook`、`evidence_summary`、新闻标签过滤与外部证据摘要统一落在 `/screening` 与 `/portfolio`
- 复盘层：`review_snapshot`、`review_history`、`market_review` history 复用与标准化 `opportunity_review` 结构统一落在 DSA 历史链路

明确不保留项：

- `ai-pan` 独立前端、后端、数据库、缓存、启动脚本
- 跨仓调用、双维护同步链路、第二套页面与存储口径
- 与 DSA 现有扫描、证据、复盘职责重复的平行实现

### Phase 7：对标成熟产品与长期架构收敛

状态：`已完成`

目标：

- 补上系统性“产品设计 / 架构演进 / 能力优先级”的方法论

核心任务：

- [x] 对标成熟股票分析产品
- [x] 对标成熟量化 / research 架构
- [x] 输出能力缺口报告
- [x] 决定长期保留与不保留的模块

阶段验收：

- 有一份清晰的“我们为什么做 / 为什么不做”的长期架构文档

## 7. 建议优先级

推荐顺序：

1. `Phase 1` 新闻 -> 板块 -> 机会摘要
2. `Phase 2` 实时机会监控闭环
3. `Phase 3` 可操作标的层
4. `Phase 4` 周期判断与组合辅助
5. `Phase 5` 工作台化
6. `Phase 6` 吸收 `ai-pan` 能力并收口到单仓
7. `Phase 7` 长期架构收敛

原因：

- 先把“今天哪些板块值得看”做对，价值最高
- 再做“什么时候提醒我”，形成实时闭环
- 再把结果变成“可以买什么”
- 最后才是更复杂的多系统整合与长期架构优化

## 8. 风险与边界

### 8.1 需要持续遵守的边界

- 不破坏原主分析流程
- 不修改现有 `data_provider` 优先级，除非明确决定
- 默认通过配置开关控制新能力
- 失败优先降级，不影响原有分析、通知、历史和持仓功能

### 8.2 当前最大风险

- 新闻驱动链路如果做得太重，容易拖慢系统
- 实时监控如果没有节流，容易产生大量噪音
- 外部系统集成如果边界不清，容易把仓库复杂度拉高
- 新手导向功能如果解释不够清楚，仍然会变成“懂的人才会用”的系统

### 8.3 回滚原则

- 每个阶段都优先做成可开关、可旁路、可回退
- 能通过配置关闭的，不要求立刻删代码
- 真正失败的阶段，优先 revert 该阶段改动，不牵连其他模块

## 9. 每阶段通用验收模板

每个阶段都至少回答以下问题：

- 改了什么
- 为什么要这样改
- 是否保持默认关闭或安全降级
- 验证做了哪些
- 哪些没有验证
- 风险点是什么
- 如何回滚

## 10. 进度记录模板

后续建议直接在本节持续追加。

### 10.1 进度日志

| 日期 | 阶段 | 状态 | 变更摘要 | 验证 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 2026-06-20 | Phase 0 | 已完成 | 机会引擎 MVP、机会告警契约、Web 摘要卡片、基础文档与测试已落地 | 定向 unittest + py_compile | 前端完整构建未在本轮重跑 |
| 2026-06-20 | Phase 1 | 已完成 | 分析入口补齐股票代码输入容错，支持括号包裹代码、名称附带代码、代码附带名称等常见手工输入 | 定向 unittest | 本轮仅收敛到后端分析入口，未扩展前端联想与别名体系 |
| 2026-06-20 | Phase 1 | 已完成 | 输入与交互体验整组收口：首页补快捷分析入口，自动补全透出 ETF/指数类型，选股页补低门槛参数预设与机会摘要联动 | 后端 unittest + 前端 tsc --noEmit | vitest 当前受本地 ESM/CJS 环境影响未跑通；后端 alias 独立测试依赖 pytest 未安装 |
| 2026-06-20 | Phase 1 | 已完成 | 补齐“新闻 -> 板块 -> 机会摘要”闭环：机会引擎复用热点题材新闻催化生成 `key_news`，将催化分并入板块分数，并在 `/screening` 展示新闻催化与“为什么上榜”解释 | `venv\Scripts\python.exe -m unittest tests.test_opportunity_service tests.test_opportunities_api tests.test_opportunity_engine` + `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit` | 复用现有 AlphaSift 热点新闻能力，未额外新增实时 worker 或独立新闻服务 |
| 2026-06-21 | Roadmap audit | 已完成 | 按当前仓库现状复核路线图，收敛 Phase 2/3/4/5 与输入/告警/ETF 映射等状态，并补回仍未完成的真实缺口 | 人工对照 `src/extensions/opportunity/**`、`src/services/opportunity_alerts.py`、`apps/dsa-web/src/pages/StockScreeningPage.tsx`、现有测试与 `docs/CHANGELOG.md` | 本轮仅更新路线图文档，未新增代码或重跑自动化验证 |
| 2026-06-21 | Phase 5 | 已完成 | `/screening` 机会卡片接入现有 watchlist 动作，支持个股与 ETF 一键加入/移除自选，并在卡片内展示复用的操作反馈 | `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit` + `apps/dsa-web\node_modules\.bin\eslint.cmd src/pages/StockScreeningPage.tsx src/pages/__tests__/StockScreeningPage.test.tsx` | 新增页面测试已补，但本机 vitest 仍受 `html-encoding-sniffer`/`@exodus/bytes` ESM 兼容问题影响未跑通；`vite build` 受本机 Node 20.15 与 `static/assets` 文件占用影响未完成 |
| 2026-06-21 | Phase 4 | 已完成 | `/screening` 机会摘要补齐个股 / ETF 偏好切换、稳健 / 平衡 / 激进风险模式和单笔风险限制建议，后端同步支持 `risk_profile` 输出差异化仓位与提示文案 | `venv\Scripts\python.exe -m unittest tests.test_opportunity_service_phase234 tests.test_opportunities_api` + `venv\Scripts\python.exe -m py_compile src/extensions/opportunity/schemas.py src/extensions/opportunity/scoring.py src/extensions/opportunity/enhancements.py src/extensions/opportunity/service.py api/v1/endpoints/opportunities.py tests/test_opportunity_service_phase234.py tests/test_opportunities_api.py` + `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit` + `apps/dsa-web\node_modules\.bin\eslint.cmd src/api/opportunities.ts src/api/__tests__/opportunities.test.ts src/pages/StockScreeningPage.tsx src/pages/__tests__/StockScreeningPage.test.tsx` | `vitest` 仍受 `html-encoding-sniffer` / `@exodus/bytes` ESM 兼容问题阻塞，新增前端测试已补但未在本机实际跑通 |
| 2026-06-21 | Phase 5 | 已完成 | 持仓页新增“持仓关联机会”卡片，按当前账户或组合范围调用机会概览，并基于 account-scoped holdings 反查与当前持仓直接关联的机会项 | `venv\Scripts\python.exe -m unittest tests.test_opportunities_api.OpportunityApiTestCase.test_overview_forwards_account_id_to_service tests.test_opportunity_service_phase234.OpportunityServicePhase234TestCase.test_overview_uses_account_scoped_holdings_when_account_id_is_provided` + `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit` + `apps/dsa-web\node_modules\.bin\eslint.cmd src/api/opportunities.ts src/pages/PortfolioPage.tsx src/pages/__tests__/PortfolioPage.test.tsx` | `vitest` 仍受 `html-encoding-sniffer` / `@exodus/bytes` ESM 兼容问题影响未实际执行测试；本轮未重跑前端完整构建 |
| 2026-06-21 | Phase 5 | 已完成 | 持仓页在“持仓关联机会”下补齐“关联板块风险与机会”提示，把已命中的持仓机会与行业集中度合并展示，帮助判断继续跟踪还是先控仓 | `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit` + `apps/dsa-web\node_modules\.bin\eslint.cmd src/api/opportunities.ts src/pages/PortfolioPage.tsx src/pages/__tests__/PortfolioPage.test.tsx` | 新增页面测试已先写入，但 `vitest` 仍受 `html-encoding-sniffer` / `@exodus/bytes` ESM 兼容问题影响未能实际跑通 |
| 2026-06-21 | Phase 5 | 已完成 | 评估独立机会看板页后决定不单独拆页，保持 `/screening`、`/portfolio`、`/alerts` 三页联动作为当前机会工作台的最小闭环 | 人工复核现有路由、导航与页面职责分布 | 当前闭环已覆盖看机会、看持仓、看告警三类入口；后续优先补强联动内容而不是新增独立入口 |
| 2026-06-21 | Phase 5.9 | 已完成 | 机会引擎新增 THS 外部信息源适配层，正式接入同花顺行业/概念摘要、驱动事件与个股异动信号，并保持独立 timeout / warning 降级 | `venv\Scripts\python.exe -m unittest tests.test_opportunity_engine tests.test_opportunity_service_phase234` + `venv\Scripts\python.exe -m py_compile src/extensions/opportunity/ths_provider.py src/extensions/opportunity/service.py src/extensions/opportunity/scoring.py tests/test_opportunity_engine.py tests/test_opportunity_service_phase234.py` | 本轮仅验证后端侧车与文档收口，未新增前端展示位；THS 仍作为补充信号而非主数据源 |
| 2026-06-21 | Phase 5.10 / 5.11 / 7 | 已完成 | 新增 6 个仓库级专用 skill，并补齐 `docs/investment-capability-gap-analysis.md`，正式收口 skill 体系与成熟架构对标/能力缺口文档，同时修复 `CLAUDE.md` 软链接与 `check_ai_assets.py` 的 Windows 路径兼容问题 | `venv\Scripts\python.exe -m py_compile scripts/check_ai_assets.py` + `venv\Scripts\python.exe scripts/check_ai_assets.py` + 人工复核 `.claude/skills/*/SKILL.md`、`docs/investment-capability-gap-analysis.md`、`docs/personal-investment-roadmap.md` | 本机 `git` 不可用时 `check_ai_assets.py` 会给出 warning 并跳过 `git ls-files` 检查；CI 中仍保留原阻断校验 |

### 10.2 当前下一步

默认下一步：

- [x] 从持仓页反查当前板块机会
- [x] 基于持仓页补“关联板块风险与机会”提示
- [x] 评估是否需要独立机会看板页面
- [x] 正式接入 THS 外部信息源适配层并收口路线图 5.9
- [x] 补齐专用 skill / agent 体系与能力缺口对标文档

### 10.3 临时决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-06-20 | 机会引擎先走 sidecar / opt-in | 避免影响原主流程 | 新能力默认关闭，可逐步推进 |
| 2026-06-20 | 机会告警先只做规则契约，不做实时 evaluator | 降低复杂度与回归风险 | 后续需单独补 worker 闭环 |

### 10.4 最新收口

- 2026-06-20：`Phase 2` 机会告警已补齐真实 evaluator、dry-run、worker 触发与通知闭环。
- 2026-06-20：`Phase 3` 已补齐机会项的 ETF 映射、自选/持仓匹配、`watchlist_only` 过滤和可操作字段。
- 2026-06-21：`Phase 4` 已补齐个股 / ETF 偏好切换、`risk_profile` 三档风险模式与单笔风险限制建议，`/screening` 机会摘要现已形成完整的周期与组合辅助闭环。
- 2026-06-20：`Phase 5` 已在现有 `/screening` 与告警中心内完成轻量工作台化，无新增平行页面架构。
- 2026-06-21：`Phase 5` 已补齐机会项一键加入/移除自选，继续剩余持仓反查与风险提示联动。
- 2026-06-21：`Phase 5` 已补齐持仓页“持仓关联机会”反查，为后续板块风险/机会合并提示打通账户范围与机会范围的一致性。
- 2026-06-21：`Phase 5` 已补齐持仓页“关联板块风险与机会”提示，并评估确认当前不需要单独的机会看板页面，继续保持 `/screening`、`/portfolio`、`/alerts` 三页联动闭环。
- 2026-06-21：`Phase 5.9` 已正式接入 THS 外部信息源适配层，机会引擎可补充同花顺行业/概念摘要、驱动事件与个股异动信号，并通过 warning + timeout 保持安全降级。
- 2026-06-21：`Phase 5.10` 已补齐 6 个仓库级专用 skill，覆盖板块机会、ETF 选择、新闻催化、盘中异动、新手解释与组合辅助。
- 2026-06-21：`Phase 5.11 / 7` 已新增 `docs/investment-capability-gap-analysis.md`，明确当前仓库能力边界、主要缺口、值得复制与不值得复制的长期方向。

## 11. 文档维护原则

- 本文件是该方向的主路线图，优先持续更新它
- 具体单一能力的实现说明，仍写回对应专题文档
- 如果某一阶段实际 scope 变化较大，先更新本文件，再开工
- 如后续新增英文版本，可单独补 `*_EN.md`；当前文档默认服务于中文开发协作，不强制同步英文
