# ETF Selection

围绕 ETF 优先级、主题映射、宽基/行业/主题取舍和小资金仓位约束做辅助判断。

## Usage

```text
/etf-selection <theme_or_goal>
```

## Instructions

分析时使用简洁中文，优先遵循仓库根目录 `AGENTS.md`。

### Step 1: 先确认问题类型

把用户问题先归为以下之一：

- 想跟一个主题，但不想承担个股波动
- 想在多个 ETF 之间做取舍
- 想知道当前更适合买 ETF 还是个股
- 想做小资金分配与仓位控制

### Step 2: 复用仓库现有判断

优先读取：

- 机会引擎中的 ETF 映射
- `risk_profile`
- `risk_budget`
- `cycle_view`
- `portfolio_advice`

### Step 3: 输出取舍理由

至少回答：

- 为什么当前更适合 ETF，而不是个股
- 更偏宽基、行业还是主题 ETF
- 单笔仓位建议区间
- 何时从 ETF 观察切换到个股跟踪

### Step 4: 不做的事

- 不把 ETF 选择伪装成收益承诺
- 不在证据不足时给出过度精确的买卖点
- 不脱离当前 `risk_profile` 给激进行动建议

## Output Format

```markdown
## ETF 选择建议

- 当前更适合：
- 原因：
- 候选方向：
- 仓位约束：
- 切换条件：
```
