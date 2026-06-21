# ai-pan Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `ai-pan` 里真正有价值的扫描、新闻证据、外部证据和复盘思路吸收进 `daily_stock_analysis`，并停止维护 `ai-pan` 独立运行链路。

**Architecture:** 以 DSA 现有机会引擎和页面为唯一落点。先扩展后端机会概览 payload，让它能够承载 `ai-pan` 风格的市场判断、新闻状态、证据摘要和复盘快照；再在 `/screening` 与 `/portfolio` 页面上复用这些字段，形成统一扫描台。复盘指标落入 DSA 内部服务，不保留 `ai-pan` 的独立前后端、缓存和数据库。

**Tech Stack:** Python, FastAPI, dataclasses, existing DSA opportunity services, existing DSA web frontend, TypeScript, React, Vitest/unittest, existing docs.

---

## File Structure

- Modify: `src/extensions/opportunity/schemas.py`
- Modify: `src/extensions/opportunity/enhancements.py`
- Modify: `src/extensions/opportunity/service.py`
- Modify: `api/v1/endpoints/opportunities.py`
- Create: `src/services/opportunity_review_service.py`
- Create: `tests/test_opportunity_review_service.py`
- Modify: `tests/test_opportunity_service_phase234.py`
- Modify: `tests/test_opportunities_api.py`
- Modify: `apps/dsa-web/src/api/opportunities.ts`
- Modify: `apps/dsa-web/src/api/__tests__/opportunities.test.ts`
- Modify: `apps/dsa-web/src/pages/StockScreeningPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx`
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`
- Modify: `docs/personal-investment-roadmap.md`
- Modify: `docs/CHANGELOG.md`

> Note: 仓库规则禁止未经确认直接 `git commit`。本计划不包含 commit 步骤。

### Task 1: 扩展机会概览 payload，承载 ai-pan 风格扫描摘要

**Files:**
- Modify: `src/extensions/opportunity/schemas.py`
- Modify: `src/extensions/opportunity/enhancements.py`
- Modify: `src/extensions/opportunity/service.py`
- Modify: `tests/test_opportunity_service_phase234.py`
- Modify: `tests/test_opportunities_api.py`

- [ ] **Step 1: 写失败测试，锁定新 payload 结构**

```python
def test_overview_exposes_market_outlook_news_status_and_evidence_summary(self) -> None:
    fetcher = unittest.mock.MagicMock()
    fetcher.get_sector_rankings.return_value = (
        [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
        [],
    )
    fetcher.get_concept_rankings.return_value = ([], [])
    fetcher.get_hot_stocks.return_value = [
        {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 80},
    ]

    with patch.object(OpportunityService, "_watchlist_symbols", return_value=["300750"]), patch.object(
        OpportunityService, "_holding_symbols", return_value=["300750"]
    ), patch(
        "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
        return_value=[
            {
                "title": "AI 算力景气度提升",
                "description": "AI 算力景气度提升",
                "source": "news_search",
                "published_at": "2026-06-20",
                "url": "https://example.invalid/ai",
            }
        ],
    ):
        payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
            market="cn",
            scope="balanced",
            limit=5,
            risk_profile="balanced",
        )

    self.assertEqual(payload["news_status"], "success")
    self.assertIn("market_outlook", payload)
    self.assertIn("predicted_direction", payload["market_outlook"])
    self.assertIn("evidence_summary", payload)
    self.assertTrue(payload["evidence_summary"]["decision_signal_band"])
    self.assertIn("review_snapshot", payload)
```

```python
def test_overview_forwards_new_payload_without_dropping_market_outlook(self) -> None:
    config = self._config(enabled=True)
    with patch.object(
        opportunities_endpoint.OpportunityService,
        "overview",
        return_value={"enabled": True, "market_outlook": {"predicted_direction": "看多"}, "opportunities": []},
    ) as overview:
        payload = opportunities_endpoint.opportunity_overview(
            config=config,
            market="cn",
            scope="balanced",
            limit=6,
            risk_profile="balanced",
        )

    self.assertEqual(payload["market_outlook"]["predicted_direction"], "看多")
    overview.assert_called_once()
```

- [ ] **Step 2: 运行失败测试，确认当前尚未提供这些字段**

Run: `venv\Scripts\python.exe -m unittest tests.test_opportunity_service_phase234 tests.test_opportunities_api`  
Expected: `FAIL` or `ERROR` mentioning missing `news_status` / `market_outlook` / `evidence_summary` / `review_snapshot`

- [ ] **Step 3: 在机会引擎中实现新字段**

```python
@dataclass(frozen=True)
class OpportunityEvidenceSummary:
    decision_signal_band: List[Dict[str, Any]] = field(default_factory=list)
    execution_mode: Dict[str, Any] = field(default_factory=dict)
    comparison_highlights: List[Dict[str, Any]] = field(default_factory=list)
```

```python
def _build_market_outlook(self, *, top_snapshots: List[Any], opportunities: List[OpportunityItem]) -> Dict[str, Any]:
    temperature_score = round(
        sum(item.score for item in top_snapshots[:3]) / max(1, min(3, len(top_snapshots))),
        2,
    ) if top_snapshots else 0.0
    predicted_direction = "看多" if temperature_score >= 70 else ("观望" if temperature_score >= 55 else "防守")
    predicted_bias = "bullish" if temperature_score >= 70 else ("neutral" if temperature_score >= 55 else "bearish")
    return {
        "predicted_direction": predicted_direction,
        "predicted_bias": predicted_bias,
        "confidence_pct": min(90.0, max(52.0, round(52.0 + abs(temperature_score - 55.0), 1))),
        "signal_strength": "顺势进攻" if predicted_bias == "bullish" else ("耐心观察" if predicted_bias == "neutral" else "谨慎防守"),
        "action_text": "先看主线、再看证据，不直接追涨。",
    }
```

```python
def _build_evidence_summary(self, *, opportunities: List[OpportunityItem], key_news: List[Dict[str, Any]], market_outlook: Dict[str, Any]) -> Dict[str, Any]:
    top_names = [item.name for item in opportunities[:3] if item.name]
    return {
        "decision_signal_band": [
            {"label": "方向", "value": market_outlook.get("predicted_direction", "观望"), "tone": market_outlook.get("predicted_bias", "neutral")},
            {"label": "候选", "value": f"{len(opportunities)} 个", "tone": "neutral"},
            {"label": "新闻", "value": f"{len(key_news)} 条", "tone": "bullish" if key_news else "neutral"},
        ],
        "execution_mode": {
            "label": market_outlook.get("signal_strength", "耐心观察"),
            "detail": market_outlook.get("action_text", ""),
            "tone": market_outlook.get("predicted_bias", "neutral"),
        },
        "comparison_highlights": [
            {"label": "主线", "value": " / ".join(top_names[:2]) or "--", "tone": "bullish" if top_names else "neutral"},
        ],
    }
```

```python
return {
    "enabled": True,
    "market": market,
    "scope": scope,
    "risk_profile": risk_profile,
    "news_status": "success" if key_news else ("fallback" if warnings else "deferred"),
    "market_outlook": market_outlook,
    "evidence_summary": evidence_summary,
    "review_snapshot": {"status": "pending", "label": "待复盘", "success_pct": 0.0, "focus_total": 0},
    ...
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `venv\Scripts\python.exe -m unittest tests.test_opportunity_service_phase234 tests.test_opportunities_api`  
Expected: `OK`

- [ ] **Step 5: 运行最小静态校验**

Run: `venv\Scripts\python.exe -m py_compile src/extensions/opportunity/schemas.py src/extensions/opportunity/enhancements.py src/extensions/opportunity/service.py api/v1/endpoints/opportunities.py tests/test_opportunity_service_phase234.py tests/test_opportunities_api.py`  
Expected: no output, exit code `0`

### Task 2: 新建 DSA 内部复盘服务，替代 ai-pan 独立复盘逻辑

**Files:**
- Create: `src/services/opportunity_review_service.py`
- Create: `tests/test_opportunity_review_service.py`
- Modify: `src/extensions/opportunity/service.py`

- [ ] **Step 1: 写失败测试，定义复盘摘要输出**

```python
def test_build_review_snapshot_aggregates_success_rate() -> None:
    service = OpportunityReviewService()
    snapshot = service.build_review_snapshot(
        [
            {"date": "2026-06-20", "focus_total": 5, "success_count": 3, "failure_count": 2},
            {"date": "2026-06-19", "focus_total": 4, "success_count": 2, "failure_count": 2},
        ]
    )

    assert snapshot["status"] == "reviewed"
    assert snapshot["focus_total"] == 9
    assert snapshot["success_count"] == 5
    assert snapshot["success_pct"] == 55.56
```

```python
def test_build_review_snapshot_handles_empty_history() -> None:
    service = OpportunityReviewService()
    snapshot = service.build_review_snapshot([])

    assert snapshot["status"] == "pending"
    assert snapshot["label"] == "待复盘"
    assert snapshot["success_pct"] == 0.0
```

- [ ] **Step 2: 运行测试，确认服务尚不存在**

Run: `venv\Scripts\python.exe -m unittest tests.test_opportunity_review_service`  
Expected: `ERROR` mentioning missing module or missing `OpportunityReviewService`

- [ ] **Step 3: 添加最小复盘服务并接到机会概览**

```python
class OpportunityReviewService:
    def build_review_snapshot(self, history_rows: Iterable[Dict[str, object]]) -> Dict[str, object]:
        rows = list(history_rows or [])
        if not rows:
            return {"status": "pending", "label": "待复盘", "focus_total": 0, "success_count": 0, "failure_count": 0, "success_pct": 0.0}

        focus_total = sum(int(item.get("focus_total", 0) or 0) for item in rows)
        success_count = sum(int(item.get("success_count", 0) or 0) for item in rows)
        failure_count = sum(int(item.get("failure_count", 0) or 0) for item in rows)
        success_pct = round(success_count * 100.0 / focus_total, 2) if focus_total else 0.0
        return {
            "status": "reviewed",
            "label": "已复盘",
            "focus_total": focus_total,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_pct": success_pct,
        }
```

```python
review_snapshot = self._review_service.build_review_snapshot([])
payload["review_snapshot"] = review_snapshot
```

- [ ] **Step 4: 运行测试确认服务行为稳定**

Run: `venv\Scripts\python.exe -m unittest tests.test_opportunity_review_service tests.test_opportunity_service_phase234`  
Expected: `OK`

- [ ] **Step 5: 运行最小静态校验**

Run: `venv\Scripts\python.exe -m py_compile src/services/opportunity_review_service.py tests/test_opportunity_review_service.py src/extensions/opportunity/service.py`  
Expected: no output, exit code `0`

### Task 3: 在 `/screening` 页面落地 ai-pan 风格证据面板与新闻工具栏

**Files:**
- Modify: `apps/dsa-web/src/api/opportunities.ts`
- Modify: `apps/dsa-web/src/api/__tests__/opportunities.test.ts`
- Modify: `apps/dsa-web/src/pages/StockScreeningPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx`

- [ ] **Step 1: 写失败测试，锁定前端新增 UI**

```tsx
it('shows decision signal band, review snapshot, and news filters from opportunity overview', async () => {
  getOpportunityOverview.mockResolvedValueOnce({
    enabled: true,
    marketTemperature: { score: 72, label: 'warm' },
    newsStatus: 'success',
    marketOutlook: { predictedDirection: '看多', predictedBias: 'bullish', confidencePct: 68 },
    evidenceSummary: {
      decisionSignalBand: [{ label: '方向', value: '看多', tone: 'bullish' }],
      executionMode: { label: '顺势进攻', detail: '先看主线、再看证据', tone: 'bullish' },
      comparisonHighlights: [{ label: '主线', value: 'AI算力', tone: 'bullish' }],
    },
    reviewSnapshot: { status: 'reviewed', label: '已复盘', successPct: 60, focusTotal: 5 },
    keyNews: [{ title: 'AI算力景气度提升', source: 'news_search', topics: ['AI算力'] }],
    opportunities: [],
    topSectors: [],
    dataQuality: { level: 'partial', warnings: [] },
    warnings: [],
  });

  render(<StockScreeningPage />);

  expect(await screen.findByText('方向')).toBeInTheDocument();
  expect(screen.getByText('看多')).toBeInTheDocument();
  expect(screen.getByText('已复盘')).toBeInTheDocument();
  expect(screen.getByPlaceholderText('搜索新闻标题或摘要')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'AI算力' })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行前端测试，确认 UI 尚未存在**

Run: `node_modules\.bin\vitest.cmd run src/pages/__tests__/StockScreeningPage.test.tsx src/api/__tests__/opportunities.test.ts`  
Expected: current environment may still hit the known `html-encoding-sniffer` / `@exodus/bytes` error; if so, record that the new test is present and continue with `tsc` / `eslint`

- [ ] **Step 3: 扩展 API 类型和页面状态**

```ts
export type OpportunityOverview = {
  ...
  newsStatus?: 'success' | 'fallback' | 'deferred' | string;
  marketOutlook?: {
    predictedDirection?: string;
    predictedBias?: string;
    confidencePct?: number;
    signalStrength?: string;
    actionText?: string;
  };
  evidenceSummary?: {
    decisionSignalBand?: Array<{ label: string; value: string; tone?: string }>;
    executionMode?: { label?: string; detail?: string; tone?: string };
    comparisonHighlights?: Array<{ label: string; value: string; detail?: string; tone?: string }>;
  };
  reviewSnapshot?: {
    status?: string;
    label?: string;
    successPct?: number;
    focusTotal?: number;
  };
};
```

```tsx
const [newsSearchQuery, setNewsSearchQuery] = useState('');
const [newsTagFilter, setNewsTagFilter] = useState('all');

const newsTagOptions = useMemo(
  () =>
    [...new Set((opportunityOverview?.keyNews || []).flatMap((item) => item.topics || []).filter(Boolean))],
  [opportunityOverview],
);

const filteredNewsItems = useMemo(() => {
  const keyword = newsSearchQuery.trim().toLowerCase();
  return (opportunityOverview?.keyNews || []).filter((item) => {
    const tags = item.topics || [];
    if (newsTagFilter !== 'all' && !tags.includes(newsTagFilter)) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    return [item.title, item.source, ...tags].filter(Boolean).join(' ').toLowerCase().includes(keyword);
  });
}, [newsSearchQuery, newsTagFilter, opportunityOverview]);
```

```tsx
{opportunityOverview?.evidenceSummary?.decisionSignalBand?.length ? (
  <div className="grid gap-2 sm:grid-cols-3">
    {opportunityOverview.evidenceSummary.decisionSignalBand.map((item) => (
      <div key={item.label} className="rounded-xl border border-border bg-surface/70 p-3">
        <p className="text-[11px] text-secondary-text">{item.label}</p>
        <p className="mt-1 text-sm font-semibold text-foreground">{item.value}</p>
      </div>
    ))}
  </div>
) : null}
```

```tsx
<input
  value={newsSearchQuery}
  onChange={(event) => setNewsSearchQuery(event.target.value)}
  type="text"
  placeholder="搜索新闻标题或摘要"
  className="h-10 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground"
/>
```

- [ ] **Step 4: 运行类型和 lint 校验**

Run: `node_modules\.bin\tsc.cmd --noEmit`  
Expected: exit code `0`

Run: `node_modules\.bin\eslint.cmd src/api/opportunities.ts src/api/__tests__/opportunities.test.ts src/pages/StockScreeningPage.tsx src/pages/__tests__/StockScreeningPage.test.tsx`  
Expected: exit code `0`

- [ ] **Step 5: 记录前端测试现状**

Run: `node_modules\.bin\vitest.cmd run src/pages/__tests__/StockScreeningPage.test.tsx src/api/__tests__/opportunities.test.ts`  
Expected: either passing tests, or the known `ERR_REQUIRE_ESM` worker error from `html-encoding-sniffer` / `@exodus/bytes`; if it still fails, note that the limitation is environmental rather than specific to this feature

### Task 4: 在 `/portfolio` 页面复用证据摘要与复盘信息

**Files:**
- Modify: `apps/dsa-web/src/pages/PortfolioPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/PortfolioPage.test.tsx`

- [ ] **Step 1: 写失败测试，锁定持仓页共享证据区块**

```tsx
it('shows shared market outlook and review snapshot for holding-linked opportunities', async () => {
  getOpportunityOverview.mockResolvedValueOnce({
    enabled: true,
    marketTemperature: { score: 71, label: 'warm' },
    marketOutlook: { predictedDirection: '看多', predictedBias: 'bullish', confidencePct: 66 },
    reviewSnapshot: { status: 'reviewed', label: '已复盘', successPct: 58, focusTotal: 12 },
    evidenceSummary: {
      comparisonHighlights: [{ label: '主线', value: 'AI算力', tone: 'bullish' }],
    },
    opportunities: [],
    topSectors: [],
    dataQuality: { level: 'partial', warnings: [] },
    warnings: [],
  });

  render(<PortfolioPage />);

  expect(await screen.findByText('看多')).toBeInTheDocument();
  expect(screen.getByText('已复盘')).toBeInTheDocument();
  expect(screen.getByText(/58/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行前端测试，确认当前持仓页还未消费这些字段**

Run: `node_modules\.bin\vitest.cmd run src/pages/__tests__/PortfolioPage.test.tsx`  
Expected: current environment may still hit the known worker error; if so, continue with type/lint verification

- [ ] **Step 3: 在持仓页增加共享信息块**

```tsx
{holdingOpportunityOverview?.marketOutlook ? (
  <div className="rounded-xl border border-border bg-surface/70 p-4">
    <p className="text-xs text-secondary-text">Market outlook</p>
    <p className="mt-1 text-sm font-semibold text-foreground">
      {holdingOpportunityOverview.marketOutlook.predictedDirection || '观望'}
    </p>
    <p className="mt-2 text-xs text-secondary-text">
      {holdingOpportunityOverview.reviewSnapshot?.label || '待复盘'} ·
      成功率 {Number(holdingOpportunityOverview.reviewSnapshot?.successPct || 0).toFixed(1)}%
    </p>
  </div>
) : null}
```

```tsx
{holdingOpportunityOverview?.evidenceSummary?.comparisonHighlights?.length ? (
  <div className="space-y-2">
    {holdingOpportunityOverview.evidenceSummary.comparisonHighlights.map((item) => (
      <div key={item.label} className="rounded-lg border border-border bg-card px-3 py-2">
        <p className="text-xs text-secondary">{item.label}</p>
        <p className="text-sm font-medium text-foreground">{item.value}</p>
      </div>
    ))}
  </div>
) : null}
```

- [ ] **Step 4: 运行类型和 lint 校验**

Run: `node_modules\.bin\tsc.cmd --noEmit`  
Expected: exit code `0`

Run: `node_modules\.bin\eslint.cmd src/pages/PortfolioPage.tsx src/pages/__tests__/PortfolioPage.test.tsx`  
Expected: exit code `0`

- [ ] **Step 5: 记录页面测试现状**

Run: `node_modules\.bin\vitest.cmd run src/pages/__tests__/PortfolioPage.test.tsx`  
Expected: either passing tests, or the known `ERR_REQUIRE_ESM` worker error already seen elsewhere in this repo

### Task 5: 文档与路线图收口，明确只维护 DSA

**Files:**
- Modify: `docs/personal-investment-roadmap.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 写文档改动前的核对清单**

```markdown
- `5.8 ai-pan 集成` 必须从“外部系统集成”改成“单仓吸收”
- 明确“只保留 DSA，停止维护 ai-pan 独立运行链路”
- 列出吸收项：扫描、新闻证据、复盘
- 列出舍弃项：ai-pan 独立前后端、数据库、缓存、脚本
```

- [ ] **Step 2: 更新 roadmap 和 changelog**

```markdown
### 5.8 `ai-pan` 集成

状态：`进行中`

- [x] 明确 `ai-pan` 集成目标为单仓吸收，不保留外部运行时
- [x] 梳理 `ai-pan` 与本仓库的重复能力
- [x] 明确最小集成边界
- [ ] 扫描层并入 `src/extensions/opportunity/`
- [ ] 证据层并入 `/screening` 与 `/portfolio`
- [ ] 复盘层并入 DSA 内部统计链路
```

```markdown
- [改进] 启动 `ai-pan` 能力并仓计划：以 DSA 为唯一运行时，逐步吸收扫描、新闻证据和复盘能力，不再维护 `ai-pan` 独立链路。
```

- [ ] **Step 3: 校对文档一致性**

Run: `rg -n "ai-pan|外部系统集成|单仓吸收" docs/personal-investment-roadmap.md docs/CHANGELOG.md docs/superpowers/specs/2026-06-21-ai-pan-consolidation-design.md docs/superpowers/plans/2026-06-21-ai-pan-consolidation-plan.md`  
Expected: 这些文件中的表述一致，都指向“DSA 单仓吸收”

- [ ] **Step 4: 若治理文件受影响，运行治理校验**

Run: `venv\Scripts\python.exe scripts/check_ai_assets.py`  
Expected: `OK` or exit code `0`

- [ ] **Step 5: 最终验证本轮改动面**

Run: `venv\Scripts\python.exe -m unittest tests.test_opportunity_service_phase234 tests.test_opportunities_api tests.test_opportunity_review_service`  
Expected: `OK`

Run: `venv\Scripts\python.exe -m py_compile src/extensions/opportunity/schemas.py src/extensions/opportunity/enhancements.py src/extensions/opportunity/service.py src/services/opportunity_review_service.py api/v1/endpoints/opportunities.py tests/test_opportunity_service_phase234.py tests/test_opportunities_api.py tests/test_opportunity_review_service.py`  
Expected: no output, exit code `0`

Run: `apps/dsa-web\node_modules\.bin\tsc.cmd --noEmit`  
Expected: exit code `0`

Run: `apps/dsa-web\node_modules\.bin\eslint.cmd src/api/opportunities.ts src/api/__tests__/opportunities.test.ts src/pages/StockScreeningPage.tsx src/pages/__tests__/StockScreeningPage.test.tsx src/pages/PortfolioPage.tsx src/pages/__tests__/PortfolioPage.test.tsx`  
Expected: exit code `0`

## Self-Review

- Spec coverage: 覆盖了扫描层、证据层、复盘层、文档收口和“只维护 DSA”的边界。
- Placeholder scan: 计划中没有 `TODO` / `TBD` / “稍后处理” 这类占位。
- Type consistency: 统一使用 `marketOutlook`、`evidenceSummary`、`reviewSnapshot` 作为前后端字段名，后端 snake_case 由已有 camel-case 转换层处理。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-21-ai-pan-consolidation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
