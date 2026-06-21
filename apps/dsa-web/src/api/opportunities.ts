import apiClient from './index';
import { toCamelCase } from './utils';

export type OpportunityRiskBudget = {
  instrumentType: 'stock' | 'etf' | string;
  positionMinPct?: number;
  positionMaxPct?: number;
  stopLoss?: string;
  invalidation?: string;
  qualityAdjustment?: string;
  riskProfile?: 'conservative' | 'balanced' | 'aggressive' | string;
  singleTradeRiskPct?: number;
};

export type OpportunityChipStatus = {
  status: 'available' | 'unavailable' | 'not_supported' | string;
  reason?: string;
  substituteFactors?: string[];
};

export type OpportunityNewsCatalyst = {
  title: string;
  source?: string;
  url?: string;
  publishedAt?: string | null;
  score?: number;
};

export type OpportunityKeyNewsItem = OpportunityNewsCatalyst & {
  topics?: string[];
};

export type OpportunitySectorSnapshot = {
  name: string;
  snapshotType?: string;
  score?: number;
  changePct?: number;
  heatScore?: number;
  newsScore?: number;
  raw?: Record<string, unknown>;
};

export type OpportunityItem = {
  code: string;
  name: string;
  instrumentType: 'stock' | 'etf' | string;
  market?: string;
  score?: number;
  reason?: string;
  sector?: string;
  riskBudget: OpportunityRiskBudget;
  chipStatus?: OpportunityChipStatus;
  dataQuality?: string;
  reviewEntry?: string;
  catalysts?: OpportunityNewsCatalyst[];
  actionBias?: string;
  actionLabel?: string;
  cycleView?: Record<string, unknown>;
  portfolioAdvice?: Record<string, unknown>;
  tags?: string[];
  watchlistMatch?: boolean;
  holdingMatch?: boolean;
  linkedEtfCode?: string;
  linkedEtfName?: string;
};

export type OpportunityOverview = {
  enabled: boolean;
  market?: string;
  scope?: string;
  riskProfile?: 'conservative' | 'balanced' | 'aggressive' | string;
  newsStatus?: 'success' | 'fallback' | 'deferred' | string;
  marketOutlook?: {
    predictedDirection?: string;
    predictedBias?: string;
    confidencePct?: number;
    signalStrength?: string;
    actionText?: string;
    reasoning?: string;
    leadSector?: string;
    leadInstrument?: string;
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
    successCount?: number;
    failureCount?: number;
  };
  reviewHistory?: Array<{
    tradeDate?: string;
    focusTotal?: number;
    successCount?: number;
    failureCount?: number;
    successPct?: number;
    marketReviewStatus?: string;
    marketReviewResult?: string;
  }>;
  marketTemperature: {
    score: number;
    label: string;
  };
  topSectors: OpportunitySectorSnapshot[];
  opportunities: OpportunityItem[];
  keyNews?: OpportunityKeyNewsItem[];
  portfolioContext?: {
    watchlistCount?: number;
    holdingCount?: number;
  };
  riskBudget?: {
    accountSizeCny?: number;
    stockPositionPct?: string;
    etfPositionPct?: string;
    riskProfile?: 'conservative' | 'balanced' | 'aggressive' | string;
    singleTradeRiskPct?: number;
    note?: string;
  };
  dataQuality: {
    level: string;
    warnings?: string[];
  };
  warnings?: string[];
};

export type OpportunityScanAccepted = {
  taskId: string;
  traceId?: string | null;
  status: string;
  message: string;
  market: string;
  scope: string;
  riskProfile: 'conservative' | 'balanced' | 'aggressive' | string;
  maxResults: number;
};

export type OpportunityScanTaskStatus = {
  taskId: string;
  traceId?: string | null;
  status: string;
  progress: number;
  message?: string | null;
  error?: string | null;
  result?: OpportunityOverview | null;
  market?: string | null;
  scope?: string | null;
  riskProfile?: 'conservative' | 'balanced' | 'aggressive' | string | null;
  maxResults?: number | null;
};

export const opportunitiesApi = {
  async getOverview(payload: {
    market?: string;
    scope?: string;
    limit?: number;
    accountId?: number;
    riskProfile?: 'conservative' | 'balanced' | 'aggressive' | string;
  } = {}): Promise<OpportunityOverview> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/opportunities/overview', {
      params: {
        market: payload.market || 'cn',
        scope: payload.scope || 'balanced',
        limit: payload.limit ?? 6,
        account_id: payload.accountId,
        risk_profile: payload.riskProfile || 'balanced',
      },
    });
    return toCamelCase<OpportunityOverview>(response.data);
  },

  async startScan(payload: {
    market: string;
    scope: string;
    riskProfile: 'conservative' | 'balanced' | 'aggressive' | string;
    watchlistOnly: boolean;
    maxResults: number;
  }): Promise<OpportunityScanAccepted> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/opportunities/scan', {
      market: payload.market,
      scope: payload.scope,
      risk_profile: payload.riskProfile,
      watchlist_only: payload.watchlistOnly,
      max_results: payload.maxResults,
    });
    return toCamelCase<OpportunityScanAccepted>(response.data);
  },

  async getScanTask(taskId: string): Promise<OpportunityScanTaskStatus> {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/opportunities/tasks/${taskId}`);
    return toCamelCase<OpportunityScanTaskStatus>(response.data);
  },
};
