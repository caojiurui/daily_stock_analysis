# -*- coding: utf-8 -*-
"""Runtime helpers for opportunity-engine alert rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.extensions.opportunity import OpportunityService
from src.services.market_light_service import normalize_market_region
from src.services.portfolio_alerts import RuntimeAlertPayload


OPPORTUNITY_ALERT_TYPES = frozenset({"sector_move", "news_catalyst", "opportunity_score_cross"})
OPPORTUNITY_ALERT_DATA_SOURCE = "opportunity_overview"
OPPORTUNITY_REGION_LABELS = {
    "cn": "A股机会引擎",
    "hk": "港股机会引擎",
    "us": "美股机会引擎",
}


@dataclass
class OpportunityAlert:
    """Runtime alert for market-level opportunity rules."""

    target_scope: str
    target: str
    alert_type: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    stock_code: str = ""

    def __post_init__(self) -> None:
        self.target = normalize_market_region(self.target)
        self.stock_code = f"market:{self.target}"


def make_opportunity_payload(
    *,
    parent_key: str,
    data: Dict[str, Any],
    config: Optional[Any] = None,
) -> RuntimeAlertPayload:
    region = normalize_market_region(data["target"])
    display_target = OPPORTUNITY_REGION_LABELS.get(region, f"机会引擎 {region}")
    rule = OpportunityAlert(
        target_scope=data["target_scope"],
        target=region,
        alert_type=data["alert_type"],
        parameters=dict(data.get("parameters") or {}),
        metadata={
            "persisted_rule_id": data["id"],
            "effective_target": f"market:{region}",
            "display_target": display_target,
            "config": config,
        },
        description=data.get("name") or data["alert_type"],
    )
    return RuntimeAlertPayload(
        key=f"{parent_key}|market:{region}",
        rule=rule,
        effective_target=f"market:{region}",
        display_target=display_target,
    )


def evaluate_opportunity_alert(
    rule: OpportunityAlert,
    *,
    current_overview: Optional[Dict[str, Any]] = None,
    cache: Optional[Dict[Any, Any]] = None,
    opportunity_service: Optional[OpportunityService] = None,
) -> Dict[str, Any]:
    try:
        overview = current_overview or _cached_overview(rule, cache=cache, opportunity_service=opportunity_service)
    except Exception as exc:
        return _result(
            rule,
            triggered=False,
            observed_value=None,
            threshold=_threshold(rule),
            message=f"opportunity overview unavailable: {exc}",
            record_status="degraded",
        )

    generated_at = _parse_datetime(overview.get("generated_at"))
    if not overview.get("enabled", False):
        return _result(
            rule,
            triggered=False,
            observed_value=None,
            threshold=_threshold(rule),
            message="opportunity engine disabled",
            record_status="skipped",
            data_timestamp=generated_at,
            diagnostics={"market": rule.target},
        )

    if rule.alert_type == "sector_move":
        return _evaluate_sector_move(rule, overview, generated_at)
    if rule.alert_type == "news_catalyst":
        return _evaluate_news_catalyst(rule, overview, generated_at)
    if rule.alert_type == "opportunity_score_cross":
        return _evaluate_score_cross(rule, overview, generated_at)

    return _result(
        rule,
        triggered=False,
        observed_value=None,
        threshold=None,
        message=f"unsupported opportunity alert_type: {rule.alert_type}",
        record_status="failed",
    )


def _cached_overview(
    rule: OpportunityAlert,
    *,
    cache: Optional[Dict[Any, Any]],
    opportunity_service: Optional[OpportunityService],
) -> Dict[str, Any]:
    if cache is None:
        return _service_for_rule(rule, opportunity_service).overview(market=rule.target, scope="balanced", limit=12)
    cache_key = ("opportunity_overview", rule.target)
    if cache_key not in cache:
        cache[cache_key] = _service_for_rule(rule, opportunity_service).overview(
            market=rule.target,
            scope="balanced",
            limit=12,
        )
    return cache[cache_key]


def _service_for_rule(
    rule: OpportunityAlert,
    opportunity_service: Optional[OpportunityService],
) -> OpportunityService:
    if opportunity_service is not None:
        return opportunity_service
    config = rule.metadata.get("config")
    return OpportunityService(config=config)


def _evaluate_sector_move(
    rule: OpportunityAlert,
    overview: Dict[str, Any],
    data_timestamp: Optional[datetime],
) -> Dict[str, Any]:
    min_score = float(rule.parameters.get("min_score") or 0.0)
    min_change_pct = float(rule.parameters.get("min_change_pct") or 0.0)
    matches = [
        item
        for item in (overview.get("top_sectors") or [])
        if float(item.get("score") or 0.0) >= min_score
        and float(item.get("change_pct") or 0.0) >= min_change_pct
    ]
    if not matches:
        best = next(iter(overview.get("top_sectors") or []), {})
        return _result(
            rule,
            triggered=False,
            observed_value=float(best.get("score") or 0.0) if best else 0.0,
            threshold=min_score,
            message="no sector reached the configured score/change threshold",
            data_timestamp=data_timestamp,
            diagnostics={
                "market": rule.target,
                "top_sector": best.get("name"),
                "top_sector_score": float(best.get("score") or 0.0) if best else 0.0,
                "top_sector_change_pct": float(best.get("change_pct") or 0.0) if best else 0.0,
            },
        )

    matched = matches[0]
    return _result(
        rule,
        triggered=True,
        observed_value=float(matched.get("score") or 0.0),
        threshold=min_score,
        message=(
            f"sector {matched.get('name') or '-'} reached score {float(matched.get('score') or 0.0):.1f} "
            f"and change {float(matched.get('change_pct') or 0.0):.2f}%"
        ),
        data_timestamp=data_timestamp,
        diagnostics={
            "market": rule.target,
            "sector": matched.get("name"),
            "change_pct": float(matched.get("change_pct") or 0.0),
            "news_score": float(matched.get("news_score") or 0.0),
        },
    )


def _evaluate_news_catalyst(
    rule: OpportunityAlert,
    overview: Dict[str, Any],
    data_timestamp: Optional[datetime],
) -> Dict[str, Any]:
    min_score = float(rule.parameters.get("min_score") or 0.0)
    keywords = [str(item).strip().lower() for item in (rule.parameters.get("keywords") or []) if str(item).strip()]
    matches: List[Dict[str, Any]] = []
    for item in overview.get("key_news") or []:
        score = float(item.get("score") or 0.0)
        if score < min_score:
            continue
        text = " ".join(
            [
                str(item.get("title") or ""),
                " ".join(str(topic) for topic in (item.get("topics") or [])),
            ]
        ).lower()
        if keywords and not any(keyword in text for keyword in keywords):
            continue
        matches.append(item)

    if not matches:
        best = next(iter(overview.get("key_news") or []), {})
        return _result(
            rule,
            triggered=False,
            observed_value=float(best.get("score") or 0.0) if best else 0.0,
            threshold=min_score,
            message="no key news item matched the configured catalyst rule",
            data_timestamp=data_timestamp,
            diagnostics={
                "market": rule.target,
                "keywords": keywords,
                "top_title": best.get("title"),
            },
        )

    matched = matches[0]
    return _result(
        rule,
        triggered=True,
        observed_value=float(matched.get("score") or 0.0),
        threshold=min_score,
        message=f"news catalyst matched: {matched.get('title') or '-'}",
        data_timestamp=data_timestamp,
        diagnostics={
            "market": rule.target,
            "title": matched.get("title"),
            "topics": list(matched.get("topics") or []),
            "keywords": keywords,
        },
    )


def _evaluate_score_cross(
    rule: OpportunityAlert,
    overview: Dict[str, Any],
    data_timestamp: Optional[datetime],
) -> Dict[str, Any]:
    threshold = float(rule.parameters.get("threshold") or 0.0)
    candidates: List[Dict[str, Any]] = []
    for item in overview.get("opportunities") or []:
        candidates.append(
            {
                "kind": str(item.get("instrument_type") or "opportunity"),
                "name": item.get("name") or item.get("code") or "-",
                "score": float(item.get("score") or 0.0),
                "sector": item.get("sector"),
            }
        )
    for item in overview.get("top_sectors") or []:
        candidates.append(
            {
                "kind": "sector",
                "name": item.get("name") or "-",
                "score": float(item.get("score") or 0.0),
                "sector": item.get("name") or "-",
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0] if candidates else {"kind": "opportunity", "name": "-", "score": 0.0}
    if float(best["score"]) < threshold:
        return _result(
            rule,
            triggered=False,
            observed_value=float(best["score"]),
            threshold=threshold,
            message=f"top opportunity score stayed below threshold: {float(best['score']):.1f}",
            data_timestamp=data_timestamp,
            diagnostics={"market": rule.target, "top_item": best},
        )

    return _result(
        rule,
        triggered=True,
        observed_value=float(best["score"]),
        threshold=threshold,
        message=f"{best['kind']} {best['name']} crossed score threshold {threshold:.1f}",
        data_timestamp=data_timestamp,
        diagnostics={"market": rule.target, "top_item": best},
    )


def _threshold(rule: OpportunityAlert) -> Optional[float]:
    if rule.alert_type == "sector_move":
        return float(rule.parameters.get("min_score") or 0.0)
    if rule.alert_type == "news_catalyst":
        return float(rule.parameters.get("min_score") or 0.0)
    if rule.alert_type == "opportunity_score_cross":
        return float(rule.parameters.get("threshold") or 0.0)
    return None


def _result(
    rule: OpportunityAlert,
    *,
    triggered: bool,
    observed_value: Optional[float],
    threshold: Optional[float],
    message: str,
    record_status: Optional[str] = None,
    data_timestamp: Optional[datetime] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "rule_id": int(rule.metadata.get("persisted_rule_id", 0) or 0),
        "status": "triggered" if triggered else "not_triggered",
        "record_status": "triggered" if triggered else record_status,
        "triggered": triggered,
        "observed_value": observed_value,
        "threshold": threshold,
        "data_source": OPPORTUNITY_ALERT_DATA_SOURCE,
        "data_timestamp": data_timestamp,
        "reason": message,
        "message": message,
        "diagnostics": diagnostics or {},
    }


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
