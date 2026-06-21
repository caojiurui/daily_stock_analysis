# -*- coding: utf-8 -*-
"""Pure scoring helpers for the opportunity engine."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from .schemas import ChipSignalStatus, RiskBudgetAdvice, SectorOpportunitySnapshot

SUBSTITUTE_FACTORS = ["price_volume", "money_flow", "volatility", "turnover", "news_catalyst"]
SUPPORTED_RISK_PROFILES = {"conservative", "balanced", "aggressive"}


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_value(data: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def normalize_risk_profile(value: Any) -> str:
    profile = str(value or "balanced").strip().lower()
    return profile if profile in SUPPORTED_RISK_PROFILES else "balanced"


def _trend_score(change_pct: float) -> float:
    # Map roughly -5%..+8% to 0..100 while keeping ordinary days near neutral.
    return _clamp(50.0 + change_pct * 6.0)


def _normalize_fraction_score(value: Any) -> float:
    score = _to_float(value, 0.0)
    if 0 <= score <= 1:
        return score * 100
    return _clamp(score)


def score_sector(raw: Dict[str, Any]) -> SectorOpportunitySnapshot:
    """Score a sector/concept using trend, heat, news and review-hit signals."""
    name = str(_first_value(raw, ["name", "板块名称", "行业名称", "概念名称", "sector"], "")).strip()
    change_pct = _to_float(_first_value(raw, ["change_pct", "涨跌幅", "pct_change", "changePercent"], 0.0))
    heat_score = _normalize_fraction_score(_first_value(raw, ["heat_score", "热度", "hot_score"], 0.0))
    news_score = _normalize_fraction_score(_first_value(raw, ["news_score", "新闻分", "catalyst_score"], 0.0))
    review_raw = _first_value(raw, ["review_hit_rate", "复盘命中率", "hit_rate"], None)
    review_score = 50.0 if review_raw is None else _normalize_fraction_score(review_raw)
    external_raw = _first_value(raw, ["external_score", "ths_score", "external_heat_score"], 0.0)
    external_score = _normalize_fraction_score(external_raw)
    score = round(
        _trend_score(change_pct) * 0.35
        + heat_score * 0.23
        + news_score * 0.18
        + review_score * 0.14
        + external_score * 0.10,
        2,
    )
    return SectorOpportunitySnapshot(
        name=name or "未知板块",
        snapshot_type=str(raw.get("snapshot_type") or "sector"),
        score=_clamp(score),
        change_pct=change_pct,
        heat_score=heat_score,
        news_score=news_score,
        review_hit_rate=None if review_raw is None else _to_float(review_raw),
        raw=dict(raw),
    )


def normalize_sector_snapshots(
    rows: Iterable[Dict[str, Any]],
    *,
    snapshot_type: str,
    limit: int,
) -> List[SectorOpportunitySnapshot]:
    snapshots = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        payload = dict(row)
        payload["snapshot_type"] = snapshot_type
        snapshots.append(score_sector(payload))
    snapshots.sort(key=lambda item: item.score, reverse=True)
    return snapshots[: max(0, int(limit))]


def build_risk_budget(
    instrument_type: str,
    *,
    volatility_level: str = "normal",
    data_quality: str = "good",
    risk_profile: str = "balanced",
) -> RiskBudgetAdvice:
    kind = "etf" if str(instrument_type).lower() == "etf" else "stock"
    profile = normalize_risk_profile(risk_profile)
    profile_limits = {
        "stock": {
            "conservative": (8, 15, 1.0),
            "balanced": (10, 20, 1.5),
            "aggressive": (15, 25, 2.0),
        },
        "etf": {
            "conservative": (15, 25, 1.0),
            "balanced": (20, 35, 1.5),
            "aggressive": (25, 40, 2.0),
        },
    }
    min_pct, max_pct, single_trade_risk_pct = profile_limits[kind][profile]
    quality_adjustment = "none"
    if volatility_level == "high" or data_quality in {"poor", "unavailable", "disabled"}:
        min_pct = max(5, min_pct // 2)
        max_pct = max(10, max_pct // 2)
        single_trade_risk_pct = max(0.5, round(single_trade_risk_pct - 0.5, 1))
        quality_adjustment = "downgraded"
    return RiskBudgetAdvice(
        instrument_type=kind,
        position_min_pct=min_pct,
        position_max_pct=max_pct,
        stop_loss="跌破关键支撑或回撤 8%-10% 时复核/止损" if kind == "stock" else "跌破板块趋势或回撤 5%-8% 时降仓/止损",
        invalidation="板块热度回落、量能失效或核心催化证伪",
        quality_adjustment=quality_adjustment,
        risk_profile=profile,
        single_trade_risk_pct=single_trade_risk_pct,
    )


def _is_a_share_code(stock_code: str) -> bool:
    normalized = stock_code.upper().strip()
    return bool(re.match(r"^(SH|SZ)?[036]\d{5}(\.(SH|SZ))?$", normalized))


def classify_chip_status(
    stock_code: str,
    *,
    instrument_type: str,
    chip_data: Optional[Any],
) -> ChipSignalStatus:
    if instrument_type == "etf" or not _is_a_share_code(stock_code):
        return ChipSignalStatus(
            status="not_supported",
            reason="chip_distribution_only_supported_for_a_share_stocks",
            substitute_factors=SUBSTITUTE_FACTORS,
        )
    if chip_data is None:
        return ChipSignalStatus(
            status="unavailable",
            reason="chip_distribution_unavailable",
            substitute_factors=SUBSTITUTE_FACTORS,
        )
    return ChipSignalStatus(status="available", reason="chip_distribution_available", substitute_factors=[])
