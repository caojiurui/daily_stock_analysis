import { beforeEach, describe, expect, it, vi } from 'vitest';
import { opportunitiesApi } from '../opportunities';

const { get, post } = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('../index', () => ({
  default: {
    get,
    post,
  },
}));

describe('opportunitiesApi', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it('loads overview and normalizes response keys', async () => {
    get.mockResolvedValueOnce({
      data: {
        enabled: true,
        market_temperature: { score: 66, label: 'warm' },
        news_status: 'success',
        market_outlook: { predicted_direction: '看多', predicted_bias: 'bullish', confidence_pct: 68 },
        evidence_summary: {
          decision_signal_band: [{ label: '方向', value: '看多', tone: 'bullish' }],
          execution_mode: { label: '顺势进攻', detail: '先看主线、再看证据，不直接追涨。', tone: 'bullish' },
          comparison_highlights: [{ label: '主线', value: 'AI算力', tone: 'bullish' }],
        },
        review_snapshot: { status: 'reviewed', label: '已复盘', success_pct: 60, focus_total: 5 },
        top_sectors: [{ name: 'AI算力', change_pct: 3.2 }],
        opportunities: [
          {
            code: '300750',
            name: '宁德时代',
            risk_budget: { instrument_type: 'stock', position_max_pct: 20 },
            chip_status: { status: 'unavailable' },
          },
        ],
        data_quality: { level: 'partial' },
      },
    });

    const result = await opportunitiesApi.getOverview({
      market: 'cn',
      scope: 'balanced',
      limit: 5,
      riskProfile: 'aggressive',
    });

    expect(get).toHaveBeenCalledWith('/api/v1/opportunities/overview', {
      params: { market: 'cn', scope: 'balanced', limit: 5, risk_profile: 'aggressive' },
      timeout: 60000,
    });
    expect(result.newsStatus).toBe('success');
    expect(result.marketOutlook?.predictedDirection).toBe('看多');
    expect(result.evidenceSummary?.decisionSignalBand?.[0]?.label).toBe('方向');
    expect(result.reviewSnapshot?.label).toBe('已复盘');
    expect(result.marketTemperature.score).toBe(66);
    expect(result.topSectors[0].changePct).toBe(3.2);
    expect(result.opportunities).toHaveLength(1);
    expect(result.opportunities[0]?.riskBudget.positionMaxPct).toBe(20);
    expect(result.opportunities[0]?.chipStatus?.status).toBe('unavailable');
  });

  it('starts an async scan task', async () => {
    post.mockResolvedValueOnce({
      data: {
        task_id: 'op-task-1',
        trace_id: 'op-task-1',
        status: 'pending',
        message: '机会扫描任务已提交',
        market: 'cn',
        scope: 'balanced',
        risk_profile: 'aggressive',
        max_results: 5,
      },
    });

    const result = await opportunitiesApi.startScan({
      market: 'cn',
      scope: 'balanced',
      riskProfile: 'aggressive',
      watchlistOnly: false,
      maxResults: 5,
    });

    expect(post).toHaveBeenCalledWith('/api/v1/opportunities/scan', {
      market: 'cn',
      scope: 'balanced',
      risk_profile: 'aggressive',
      watchlist_only: false,
      max_results: 5,
    });
    expect(result.taskId).toBe('op-task-1');
    expect(result.riskProfile).toBe('aggressive');
    expect(result.maxResults).toBe(5);
  });

  it('loads async scan task status', async () => {
    get.mockResolvedValueOnce({
      data: {
        task_id: 'op-task-1',
        trace_id: 'op-task-1',
        status: 'completed',
        progress: 100,
        message: '机会扫描完成',
        market: 'cn',
        scope: 'balanced',
        risk_profile: 'balanced',
        max_results: 6,
        result: {
          enabled: true,
          market_temperature: { score: 70, label: 'warm' },
          top_sectors: [],
          opportunities: [],
          data_quality: { level: 'partial' },
        },
      },
    });

    const result = await opportunitiesApi.getScanTask('op-task-1');

    expect(get).toHaveBeenCalledWith('/api/v1/opportunities/tasks/op-task-1');
    expect(result.status).toBe('completed');
    expect(result.riskProfile).toBe('balanced');
    expect(result.result?.marketTemperature.score).toBe(70);
  });
});
