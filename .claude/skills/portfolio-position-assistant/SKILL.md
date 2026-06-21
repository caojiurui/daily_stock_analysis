# Portfolio Position Assistant

围绕持仓、行业集中度、机会反查和仓位控制做组合辅助，适用于小资金和新手场景。

## Usage

```text
/portfolio-position-assistant <account_or_snapshot>
```

## Instructions

分析时使用简洁中文，优先遵循仓库根目录 `AGENTS.md`。

### Step 1: 先看组合，再看单标的

优先读取：

- `portfolio_snapshot`
- 行业集中度
- 持仓关联机会
- 关联板块风险与机会提示

### Step 2: 回答 4 个问题

- 当前是否过于集中
- 哪些持仓在跟主线共振
- 哪些持仓只是在被动跟涨或已经转弱
- 更适合加仓、维持还是先控仓

### Step 3: 保持小资金约束

- 优先控制持仓数
- 优先降低单主题集中度
- 没有明显边际优势时，优先观察而不是加复杂动作

## Output Format

```markdown
## 组合与仓位结论

- 当前组合状态：
- 主要机会：
- 主要风险：
- 仓位建议：
- 下一步：
```
