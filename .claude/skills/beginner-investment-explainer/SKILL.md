# Beginner Investment Explainer

把系统输出翻译成更适合新手用户的行动建议、风险提示和简明解释，避免只堆技术术语。

## Usage

```text
/beginner-investment-explainer <analysis_or_question>
```

## Instructions

解释时使用简洁中文，优先遵循仓库根目录 `AGENTS.md`。

### Step 1: 先翻译结论，再解释术语

按以下顺序组织：

- 先说“现在更适合做什么”
- 再说“为什么”
- 最后补术语解释

### Step 2: 行动建议必须带边界

至少说明：

- 现在更适合观察 / 分批 / 暂不动作
- 风险来自哪里
- 需要等什么确认条件

### Step 3: 避免 3 类表达

- 避免收益承诺
- 避免过度精确的点位暗示
- 避免只报指标名不解释用途

## Output Format

```markdown
## 新手版解释

- 一句话结论：
- 为什么：
- 风险提示：
- 下一步观察什么：
- 术语解释：
```
