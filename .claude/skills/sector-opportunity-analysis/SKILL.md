# Sector Opportunity Analysis

围绕板块 / 概念机会做轻量分析，适用于机会引擎、AlphaSift 热点题材、市场复盘与告警中心之间的联动判断。

## Usage

```text
/sector-opportunity-analysis <topic_or_scope>
```

## Instructions

分析时使用简洁中文，优先遵循仓库根目录 `AGENTS.md`。

### Step 1: 先确认入口与范围

- 优先检查 `GET /api/v1/opportunities/overview`
- 如用户给的是题材名，再检查 AlphaSift 热点题材与最近 `market_review` history
- 如用户给的是账户或持仓上下文，再补看 `/portfolio` 相关机会联动

### Step 2: 收集 4 类证据

至少覆盖：

- 板块/概念强度：`top_sectors`
- 新闻/催化：`key_news`、题材 route、THS 驱动事件
- 前排候选：`opportunities`
- 复盘胜率：`review_snapshot`、`review_history`

### Step 3: 输出统一判断

至少回答：

- 当前是否属于主线 / 跟风 / 观察项
- 催化是否新、是否强、是否仍在扩散
- 更适合 ETF 观察还是个股跟踪
- 如果继续跟踪，最小下一步是什么

### Step 4: 风险约束

必须显式说明：

- 是否存在追高风险
- 是否存在高拥挤 / 高波动 / 题材退潮风险
- 若证据不足，优先给出“观察条件”而不是强行动建议

## Output Format

```markdown
## 板块机会结论

- 结论：
- 证据：
- 风险：
- 更适合：ETF / 个股 / 继续观察
- 下一步：
```
