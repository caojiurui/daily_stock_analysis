# -*- coding: utf-8 -*-
"""Schemas for the opt-in opportunity engine.

The extension deliberately uses plain dataclasses so the core analysis and
storage contracts remain untouched.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RiskBudgetAdvice:
    instrument_type: str
    position_min_pct: int
    position_max_pct: int
    stop_loss: str
    invalidation: str
    quality_adjustment: str = "none"
    risk_profile: str = "balanced"
    single_trade_risk_pct: float = 1.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChipSignalStatus:
    status: str
    reason: str
    substitute_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NewsCatalystSignal:
    title: str
    source: str = ""
    url: str = ""
    published_at: Optional[str] = None
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectorOpportunitySnapshot:
    name: str
    snapshot_type: str
    score: float
    change_pct: float = 0.0
    heat_score: float = 0.0
    news_score: float = 0.0
    review_hit_rate: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpportunityItem:
    code: str
    name: str
    instrument_type: str
    market: str
    score: float
    reason: str
    sector: str = ""
    risk_budget: RiskBudgetAdvice = field(default_factory=lambda: RiskBudgetAdvice(
        instrument_type="stock",
        position_min_pct=10,
        position_max_pct=20,
        stop_loss="跌破关键支撑或回撤 8%-10% 时复核/止损",
        invalidation="板块热度回落、量能失效或核心催化证伪",
    ))
    chip_status: ChipSignalStatus = field(default_factory=lambda: ChipSignalStatus(
        status="unavailable",
        reason="chip_data_missing",
        substitute_factors=["price_volume", "turnover", "volatility", "news_catalyst"],
    ))
    data_quality: str = "partial"
    catalysts: List[NewsCatalystSignal] = field(default_factory=list)
    review_entry: str = "backtest_pending"
    action_bias: str = "watch"
    action_label: str = "先观察"
    cycle_view: Dict[str, Any] = field(default_factory=dict)
    portfolio_advice: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    watchlist_match: bool = False
    holding_match: bool = False
    linked_etf_code: str = ""
    linked_etf_name: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["risk_budget"] = self.risk_budget.to_dict()
        payload["chip_status"] = self.chip_status.to_dict()
        payload["catalysts"] = [item.to_dict() for item in self.catalysts]
        return payload
