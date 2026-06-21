# Intraday Anomaly Monitoring

围绕机会类告警、盘中异动和降噪策略做检查与调优，适用于 `sector_move`、`news_catalyst`、`opportunity_score_cross` 等机会规则。

## Usage

```text
/intraday-anomaly-monitoring <market_or_rule>
```

## Instructions

分析时使用简洁中文，优先遵循仓库根目录 `AGENTS.md`。

### Step 1: 确认规则与开关

- 检查 `OPPORTUNITY_ENGINE_ENABLED`
- 检查规则类型、`target_scope` 与 worker 是否接线正确

### Step 2: 优先看闭环而不是单点

至少检查：

- evaluator 是否真实触发
- snapshot / cache 是否更新
- `alert_triggers` 是否落库
- 通知是否降噪与节流

### Step 3: 判断是“有用提醒”还是“噪音”

重点看：

- 是否重复触发
- 是否由单一波动噪音造成
- 是否能回溯到真实机会摘要变化

### Step 4: 输出调优建议

优先建议：

- 提升阈值
- 缩小范围
- 增加节流
- 改为观察而非通知

## Output Format

```markdown
## 盘中异动监控结论

- 规则状态：
- 是否真实有效：
- 主要噪音来源：
- 调优建议：
- 风险：
```
