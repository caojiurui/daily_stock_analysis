# -*- coding: utf-8 -*-
"""Opportunity engine service kept as an opt-in sidecar."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from data_provider.base import DataFetcherManager
from src.config import Config, get_config, resolve_news_window_days
from src.services.portfolio_service import PortfolioService
from src.services.opportunity_review_service import OpportunityReviewService
from src.services.alphasift_service import _build_hotspot_event_routes_from_search
from src.storage import DatabaseManager

from .enhancements import build_cycle_view, build_portfolio_advice, build_tags, map_theme_etf
from .schemas import NewsCatalystSignal, OpportunityItem
from .scoring import (
    build_risk_budget,
    classify_chip_status,
    normalize_risk_profile,
    normalize_sector_snapshots,
    score_sector,
)
from .ths_provider import ThsExternalInfoProvider

_MAX_NEWS_TOPICS = 6
_MAX_KEY_NEWS = 6


class OpportunityService:
    """Build balanced opportunity snapshots without changing core flows."""

    def __init__(self, config: Optional[Config] = None, fetcher_manager: Optional[Any] = None) -> None:
        self.config = config or get_config()
        self._fetcher_manager = fetcher_manager
        self._review_service = OpportunityReviewService()

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.config, "opportunity_engine_enabled", False))

    def _disabled_payload(self, *, market: str, scope: str, limit: int, risk_profile: str) -> Dict[str, Any]:
        return {
            "enabled": False,
            "market": market,
            "scope": scope,
            "limit": limit,
            "generated_at": datetime.now().isoformat(),
            "market_temperature": {"score": 0, "label": "disabled"},
            "top_sectors": [],
            "opportunities": [],
            "key_news": [],
            "news_status": "deferred",
            "market_outlook": self._build_market_outlook(top_snapshots=[], opportunities=[]),
            "evidence_summary": self._build_evidence_summary(
                opportunities=[],
                key_news=[],
                market_outlook=self._build_market_outlook(top_snapshots=[], opportunities=[]),
                top_snapshots=[],
                review_snapshot=self._review_service.build_review_snapshot([]),
            ),
            "review_snapshot": self._review_service.build_review_snapshot([]),
            "risk_budget": {
                "account_size_cny": 15000,
                "stock_position_pct": "10-20",
                "etf_position_pct": "20-35",
                "risk_profile": risk_profile,
                "single_trade_risk_pct": 1.5,
                "note": "机会引擎未开启，仅保留默认风险预算说明。",
            },
            "data_quality": {"level": "disabled", "warnings": ["opportunity_engine_disabled"]},
            "warnings": ["opportunity_engine_disabled"],
        }

    def _manager(self) -> Any:
        if self._fetcher_manager is None:
            self._fetcher_manager = DataFetcherManager()
        return self._fetcher_manager

    def _watchlist_symbols(self) -> List[str]:
        refresh = getattr(self.config, "refresh_stock_list", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        return [str(item).strip().upper() for item in (getattr(self.config, "stock_list", []) or []) if str(item).strip()]

    @staticmethod
    def _holding_symbols(*, account_id: Optional[int] = None) -> List[str]:
        try:
            snapshot = PortfolioService().get_portfolio_snapshot(account_id=account_id, cost_method="fifo")
        except Exception:
            return []
        symbols: List[str] = []
        for account in snapshot.get("accounts") or []:
            for position in account.get("positions") or []:
                symbol = str(position.get("symbol") or "").strip().upper()
                if symbol:
                    symbols.append(symbol)
        return symbols

    def overview(
        self,
        *,
        market: str = "all",
        scope: str = "balanced",
        limit: int = 10,
        account_id: Optional[int] = None,
        risk_profile: str = "balanced",
    ) -> Dict[str, Any]:
        market = self._normalize_market(market)
        scope = self._normalize_scope(scope)
        risk_profile = normalize_risk_profile(risk_profile)
        limit = max(1, min(int(limit), 50))
        if not self.enabled:
            return self._disabled_payload(market=market, scope=scope, limit=limit, risk_profile=risk_profile)

        warnings: List[str] = []
        sectors = []
        concepts = []
        hot_stocks = []
        watchlist_symbols = self._watchlist_symbols()
        holding_symbols = self._holding_symbols(account_id=account_id)
        manager = self._manager()
        ths_payload: Dict[str, Any] = {"industry_rows": [], "concept_rows": [], "stock_signals": {}, "warnings": []}

        try:
            top_sectors, _bottom_sectors = manager.get_sector_rankings(n=min(limit, 20))
            sectors = top_sectors or []
        except Exception as exc:  # pragma: no cover - defensive fallback
            warnings.append(f"sector_rankings_failed:{type(exc).__name__}")

        try:
            top_concepts, _bottom_concepts = manager.get_concept_rankings(n=min(limit, 20))
            concepts = top_concepts or []
        except Exception as exc:
            warnings.append(f"concept_rankings_failed:{type(exc).__name__}")

        try:
            hot_stocks = manager.get_hot_stocks(n=min(limit, 20)) or []
        except Exception as exc:
            warnings.append(f"hot_stocks_failed:{type(exc).__name__}")

        ths_payload = ThsExternalInfoProvider().collect(limit=min(limit, 10))
        for warning in list(ths_payload.get("warnings") or []):
            if warning and warning not in warnings:
                warnings.append(warning)
        sectors = self._merge_snapshot_rows(
            primary_rows=sectors,
            external_rows=ths_payload.get("industry_rows") or [],
        )
        concepts = self._merge_snapshot_rows(
            primary_rows=concepts,
            external_rows=ths_payload.get("concept_rows") or [],
        )
        hot_stocks = self._apply_stock_signal_boosts(
            hot_stocks,
            signal_map=ths_payload.get("stock_signals") or {},
        )

        sector_snapshots = normalize_sector_snapshots(sectors, snapshot_type="sector", limit=limit)
        concept_snapshots = normalize_sector_snapshots(concepts, snapshot_type="concept", limit=limit)
        top_snapshots, key_news = self._enrich_snapshots_with_news(
            [*sector_snapshots, *concept_snapshots],
            limit=limit,
            warnings=warnings,
        )
        key_news = self._merge_ths_key_news(
            key_news,
            concept_rows=ths_payload.get("concept_rows") or [],
            limit=min(limit, _MAX_KEY_NEWS),
        )
        opportunities = self._build_opportunities(
            hot_stocks=hot_stocks,
            sectors=top_snapshots,
            market=market,
            scope=scope,
            limit=limit,
            warnings=warnings,
            watchlist_symbols=watchlist_symbols,
            holding_symbols=holding_symbols,
            risk_profile=risk_profile,
        )
        temperature_score = round(
            sum(item.score for item in top_snapshots[:5]) / max(1, min(5, len(top_snapshots))),
            2,
        ) if top_snapshots else 0
        data_quality_level = "good" if not warnings and (top_snapshots or opportunities) else "partial"
        if not top_snapshots and not opportunities:
            data_quality_level = "unavailable"
        history_rows, history_market_review_payload, review_history = self._load_market_review_history_context(market=market)
        market_outlook = self._build_market_outlook(
            top_snapshots=top_snapshots,
            opportunities=opportunities,
            history_market_review_payload=history_market_review_payload,
        )
        review_snapshot = self._build_review_snapshot_for_overview(
            top_snapshots=top_snapshots,
            history_rows=history_rows,
        )
        evidence_summary = self._build_evidence_summary(
            opportunities=opportunities,
            key_news=key_news,
            market_outlook=market_outlook,
            top_snapshots=top_snapshots,
            review_snapshot=review_snapshot,
        )

        return {
            "enabled": True,
            "market": market,
            "scope": scope,
            "limit": limit,
            "risk_profile": risk_profile,
            "generated_at": datetime.now().isoformat(),
            "news_status": self._build_news_status(key_news=key_news, warnings=warnings),
            "market_outlook": market_outlook,
            "evidence_summary": evidence_summary,
            "review_snapshot": review_snapshot,
            "review_history": review_history,
            "market_temperature": {
                "score": temperature_score,
                "label": self._temperature_label(temperature_score),
            },
            "top_sectors": [item.to_dict() for item in top_snapshots],
            "opportunities": [item.to_dict() for item in opportunities],
            "key_news": key_news,
            "portfolio_context": {
                "watchlist_count": len(watchlist_symbols),
                "holding_count": len(holding_symbols),
            },
            "risk_budget": self._build_overview_risk_budget(risk_profile=risk_profile),
            "data_quality": {"level": data_quality_level, "warnings": warnings},
            "warnings": warnings,
        }

    @staticmethod
    def _merge_snapshot_rows(
        *,
        primary_rows: List[Dict[str, Any]],
        external_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for source_rows, source_priority in ((primary_rows, "primary"), (external_rows, "external")):
            for row in source_rows or []:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or row.get("板块名称") or row.get("行业名称") or row.get("概念名称") or "").strip()
                if not name:
                    continue
                key = OpportunityService._normalize_match_key(name)
                if key not in merged:
                    merged[key] = dict(row)
                    merged[key]["name"] = name
                    merged[key]["source_priority"] = source_priority
                    order.append(key)
                    continue
                existing = merged[key]
                if source_priority == "external":
                    if not existing.get("heat_score") and row.get("heat_score") not in (None, ""):
                        existing["heat_score"] = row.get("heat_score")
                    if not existing.get("news_score") and row.get("news_score") not in (None, ""):
                        existing["news_score"] = row.get("news_score")
                    for field in (
                        "ths_source",
                        "ths_board_type",
                        "ths_summary_date",
                        "ths_summary_event",
                        "ths_leading_stock",
                        "ths_component_count",
                        "ths_total_amount",
                    ):
                        if row.get(field) not in (None, "") and field not in existing:
                            existing[field] = row.get(field)
                else:
                    merged[key] = {**row, **existing}
                    merged[key]["name"] = name
        return [merged[key] for key in order]

    @staticmethod
    def _merge_ths_key_news(
        key_news: List[Dict[str, Any]],
        *,
        concept_rows: List[Dict[str, Any]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        combined = list(key_news or [])
        for row in concept_rows or []:
            event = str(row.get("ths_summary_event") or "").strip()
            topic = str(row.get("name") or "").strip()
            published_at = str(row.get("ths_summary_date") or "").strip()
            if not event or not topic:
                continue
            combined.append(
                {
                    "title": event,
                    "source": "ths_summary",
                    "url": "",
                    "published_at": published_at or None,
                    "score": float(row.get("news_score") or 0.0),
                    "topics": [topic],
                }
            )
        return OpportunityService._dedupe_key_news(combined, limit=limit)

    @staticmethod
    def _apply_stock_signal_boosts(
        hot_stocks: List[Dict[str, Any]],
        *,
        signal_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not hot_stocks or not signal_map:
            return hot_stocks
        boosted: List[Dict[str, Any]] = []
        for row in hot_stocks:
            if not isinstance(row, dict):
                continue
            payload = dict(row)
            code = str(payload.get("code") or payload.get("代码") or payload.get("symbol") or "").strip().upper()
            signal = signal_map.get(code)
            if signal:
                payload["heat_score"] = float(payload.get("heat_score") or payload.get("hot_score") or 50.0) + float(
                    signal.get("score_boost") or 0.0
                )
                payload["external_signal_tags"] = list(signal.get("tags") or [])
                payload["external_signal_sources"] = list(signal.get("sources") or [])
            boosted.append(payload)
        return boosted

    def _build_review_snapshot_for_overview(
        self,
        *,
        top_snapshots: List[Any],
        history_rows: List[Dict[str, object]],
    ) -> Dict[str, Any]:
        if history_rows:
            return self._review_service.build_review_snapshot(history_rows)
        return self._review_service.build_review_snapshot(
            self._review_service.build_review_rows_from_sector_snapshots(top_snapshots[:3])
        )

    def _load_market_review_history_context(
        self,
        *,
        market: str,
    ) -> Tuple[List[Dict[str, object]], Dict[str, Any], List[Dict[str, object]]]:
        try:
            records = DatabaseManager.get_instance().get_analysis_history(
                code="MARKET",
                days=30,
                limit=20,
            )
        except Exception:
            return [], {}, []
        history_region = "" if market == "all" else market
        history_rows = self._review_service.build_review_rows_from_history_records(
            records,
            region=history_region,
        )
        history_market_review_payload = self._extract_market_review_payload_from_history_records(
            records,
            region=history_region,
        )
        review_history = self._build_review_history_from_records(records, region=history_region)
        return history_rows, history_market_review_payload, review_history

    def _extract_market_review_payload_from_history_records(
        self,
        records: List[Any],
        *,
        region: str,
    ) -> Dict[str, Any]:
        for record in records or []:
            snapshot = self._review_service._coerce_mapping(getattr(record, "context_snapshot", None))
            if not snapshot:
                continue
            market_review_payload = self._review_service._coerce_mapping(snapshot.get("market_review_payload"))
            if not market_review_payload:
                continue
            if region and not self._history_record_matches_region(
                snapshot=snapshot,
                market_review_payload=market_review_payload,
                region=region,
            ):
                continue
            return market_review_payload
        return {}

    def _build_review_history_from_records(
        self,
        records: List[Any],
        *,
        region: str,
    ) -> List[Dict[str, object]]:
        items: List[Dict[str, object]] = []
        for record in records or []:
            snapshot = self._review_service._coerce_mapping(getattr(record, "context_snapshot", None))
            if not snapshot:
                continue
            market_review_payload = self._review_service._coerce_mapping(snapshot.get("market_review_payload"))
            if not market_review_payload:
                continue
            if region and not self._history_record_matches_region(
                snapshot=snapshot,
                market_review_payload=market_review_payload,
                region=region,
            ):
                continue
            rows = self._review_service.build_review_rows_from_history_records([record], region=region)
            if not rows:
                continue
            summary = self._review_service.build_review_snapshot(rows)
            items.append(
                {
                    "trade_date": str(market_review_payload.get("date") or ""),
                    "focus_total": int(summary.get("focus_total") or 0),
                    "success_count": int(summary.get("success_count") or 0),
                    "failure_count": int(summary.get("failure_count") or 0),
                    "success_pct": float(summary.get("success_pct") or 0.0),
                    "market_review_status": str(
                        self._review_service._coerce_mapping(market_review_payload.get("market_outlook")).get("review_status") or ""
                    ),
                    "market_review_result": str(
                        self._review_service._coerce_mapping(market_review_payload.get("market_outlook")).get("review_result") or ""
                    ),
                }
            )
        return items[:5]

    @staticmethod
    def _history_record_matches_region(
        *,
        snapshot: Dict[str, Any],
        market_review_payload: Dict[str, Any],
        region: str,
    ) -> bool:
        if not region:
            return True
        for value in (
            snapshot.get("market_review_region"),
            market_review_payload.get("region"),
        ):
            text = str(value or "").strip().lower()
            if not text:
                continue
            if text == region:
                return True
            if "," in text and region in {part.strip() for part in text.split(",") if part.strip()}:
                return True
        return False

    def scan(
        self,
        *,
        market: str = "all",
        scope: str = "balanced",
        watchlist_only: bool = False,
        max_results: int = 10,
        risk_profile: str = "balanced",
    ) -> Dict[str, Any]:
        payload = self.overview(market=market, scope=scope, limit=max_results, risk_profile=risk_profile)
        if watchlist_only and payload.get("enabled"):
            watchlist = set(self._watchlist_symbols())
            filtered = []
            for item in payload.get("opportunities") or []:
                code = str(item.get("code") or "").strip().upper()
                if code and code in watchlist:
                    filtered.append(item)
            payload["opportunities"] = filtered
        payload["watchlist_only"] = bool(watchlist_only)
        payload["scan_mode"] = "opportunity"
        return payload

    @staticmethod
    def _build_overview_risk_budget(*, risk_profile: str) -> Dict[str, Any]:
        stock_budget = build_risk_budget("stock", risk_profile=risk_profile)
        etf_budget = build_risk_budget("etf", risk_profile=risk_profile)
        notes = {
            "conservative": "稳健模式优先压缩单笔风险，个股更偏向分批确认，主题机会可先用 ETF 观察。",
            "balanced": "平衡模式兼顾机会与回撤，先看仓位纪律，再决定是否跟踪个股或 ETF。",
            "aggressive": "激进模式允许更宽仓位与更高单笔风险，但仍要等待放量或催化确认。",
        }
        return {
            "account_size_cny": 15000,
            "risk_profile": risk_profile,
            "stock_position_pct": f"{stock_budget.position_min_pct}-{stock_budget.position_max_pct}",
            "etf_position_pct": f"{etf_budget.position_min_pct}-{etf_budget.position_max_pct}",
            "single_trade_risk_pct": stock_budget.single_trade_risk_pct,
            "note": notes.get(risk_profile, notes["balanced"]),
        }

    @staticmethod
    def _build_news_status(*, key_news: List[Dict[str, Any]], warnings: List[str]) -> str:
        if key_news:
            return "success"
        if warnings:
            return "fallback"
        return "deferred"

    @staticmethod
    def _build_market_outlook(
        *,
        top_snapshots: List[Any],
        opportunities: List[OpportunityItem],
        history_market_review_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        leading_scores = [float(item.score or 0.0) for item in top_snapshots[:3]]
        if not leading_scores:
            leading_scores = [float(item.score or 0.0) for item in opportunities[:3]]
        score = round(sum(leading_scores) / len(leading_scores), 2) if leading_scores else 0.0

        if score >= 70:
            predicted_direction = "看多"
            predicted_bias = "bullish"
            signal_strength = "顺势进攻"
        elif score >= 55:
            predicted_direction = "观望"
            predicted_bias = "neutral"
            signal_strength = "耐心观察"
        else:
            predicted_direction = "防守"
            predicted_bias = "bearish"
            signal_strength = "谨慎防守"

        lead_sector = str(getattr(top_snapshots[0], "name", "")).strip() if top_snapshots else ""
        lead_instrument = opportunities[0].instrument_type if opportunities else ""
        lead_opportunity = str(getattr(opportunities[0], "name", "")).strip() if opportunities else ""
        lead_score_text = f"{score:.0f}分" if score else "待确认"
        reasoning_parts = []
        history_payload = history_market_review_payload if isinstance(history_market_review_payload, dict) else {}
        breadth = history_payload.get("breadth") if isinstance(history_payload.get("breadth"), dict) else {}
        up_count = OpportunityService._coerce_int(breadth.get("up_count"))
        down_count = OpportunityService._coerce_int(breadth.get("down_count"))
        flat_count = OpportunityService._coerce_int(breadth.get("flat_count"))
        history_date = str(history_payload.get("date") or "").strip()
        if up_count > 0 or down_count > 0:
            breadth_total = up_count + down_count + flat_count
            if breadth_total > 0:
                breadth_pct = round(up_count * 100.0 / breadth_total, 1)
                breadth_text = f"上涨家数 {up_count} / 下跌家数 {down_count}，市场宽度 {breadth_pct}%"
            else:
                breadth_text = f"上涨家数 {up_count} / 下跌家数 {down_count}"
            if history_date:
                breadth_text = f"{history_date} {breadth_text}"
            reasoning_parts.append(breadth_text)
        if lead_sector:
            reasoning_parts.append(f"主线聚焦 {lead_sector}")
        if lead_opportunity:
            reasoning_parts.append(f"前排候选是 {lead_opportunity}")
        if score:
            reasoning_parts.append(f"综合强度约 {lead_score_text}")
        reasoning = "，".join(reasoning_parts) if reasoning_parts else "暂无明确主线，等待更清晰的机会信号"
        return {
            "predicted_direction": predicted_direction,
            "predicted_bias": predicted_bias,
            "confidence_pct": min(90.0, max(52.0, round(52.0 + abs(score - 55.0), 1))) if score else 52.0,
            "signal_strength": signal_strength,
            "action_text": "先看主线、再看证据，不直接追涨。",
            "reasoning": reasoning,
            "lead_sector": lead_sector,
            "lead_instrument": lead_instrument,
        }

    @staticmethod
    def _build_evidence_summary(
        *,
        opportunities: List[OpportunityItem],
        key_news: List[Dict[str, Any]],
        market_outlook: Dict[str, Any],
        top_snapshots: List[Any],
        review_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        tone = str(market_outlook.get("predicted_bias") or "neutral")
        top_names = [item.name for item in opportunities[:3] if getattr(item, "name", "")]
        top_sectors = []
        for item in opportunities[:3]:
            sector_name = str(getattr(item, "sector", "")).strip()
            if sector_name and sector_name not in top_sectors:
                top_sectors.append(sector_name)

        comparison_highlights: List[Dict[str, Any]] = []
        if top_sectors:
            comparison_highlights.append(
                {
                    "label": "主线",
                    "value": " / ".join(top_sectors[:2]),
                    "detail": " · ".join(
                        [
                            f'{getattr(item, "name", "")} 热度{float(getattr(item, "heat_score", 0.0) or 0.0):.0f}/新闻{float(getattr(item, "news_score", 0.0) or 0.0):.0f}'
                            for item in top_snapshots[:2]
                            if getattr(item, "name", "")
                        ]
                    ),
                    "tone": tone,
                }
            )
        if top_names:
            comparison_highlights.append(
                {
                    "label": "前排",
                    "value": " / ".join(top_names[:2]),
                    "detail": " · ".join(
                        [
                            f'{item.name} {float(item.score or 0.0):.0f}分/{str(item.action_label or item.action_bias or "观察")}'
                            for item in opportunities[:2]
                            if getattr(item, "name", "")
                        ]
                    ),
                    "tone": tone,
                }
            )
        if key_news:
            comparison_highlights.append(
                {
                    "label": "证据",
                    "value": str(key_news[0].get("title") or "--"),
                    "detail": str(key_news[0].get("source") or ""),
                    "tone": "bullish",
                }
            )
        if str(review_snapshot.get("status") or "") == "reviewed":
            comparison_highlights.append(
                {
                    "label": "板块胜率",
                    "value": f'{float(review_snapshot.get("success_pct") or 0.0):.1f}%',
                    "detail": f'样本 {int(review_snapshot.get("focus_total") or 0)}',
                    "tone": "bullish" if float(review_snapshot.get("success_pct") or 0.0) >= 55.0 else "neutral",
                }
            )

        return {
            "decision_signal_band": [
                {
                    "label": "方向",
                    "value": str(market_outlook.get("predicted_direction") or "观望"),
                    "tone": tone,
                },
                {
                    "label": "候选",
                    "value": f"{len(opportunities)} 个",
                    "tone": "neutral",
                },
                {
                    "label": "新闻",
                    "value": f"{len(key_news)} 条",
                    "tone": "bullish" if key_news else "neutral",
                },
            ],
            "execution_mode": {
                "label": str(market_outlook.get("signal_strength") or "耐心观察"),
                "detail": str(market_outlook.get("action_text") or ""),
                "tone": tone,
            },
            "comparison_highlights": comparison_highlights,
        }

    def _enrich_snapshots_with_news(
        self,
        snapshots: List[Any],
        *,
        limit: int,
        warnings: List[str],
    ) -> Tuple[List[Any], List[Dict[str, Any]]]:
        sorted_snapshots = sorted(snapshots, key=lambda item: item.score, reverse=True)
        if not sorted_snapshots:
            return [], []

        topic_limit = min(max(limit, 1), _MAX_NEWS_TOPICS)
        topic_names: List[str] = []
        for snapshot in sorted_snapshots:
            name = str(getattr(snapshot, "name", "")).strip()
            if not name or name in topic_names:
                continue
            topic_names.append(name)
            if len(topic_names) >= topic_limit:
                break

        catalysts_by_topic: Dict[str, List[NewsCatalystSignal]] = {}
        news_score_by_topic: Dict[str, float] = {}
        key_news: List[Dict[str, Any]] = []
        news_window_days = self._effective_news_window_days()

        for topic in topic_names:
            try:
                routes = _build_hotspot_event_routes_from_search(topic, self.config)
            except Exception as exc:  # pragma: no cover - defensive fallback
                warnings.append(f"topic_news_failed:{topic}:{type(exc).__name__}")
                continue

            catalysts = self._routes_to_catalysts(topic, routes, news_window_days=news_window_days)
            if not catalysts:
                continue

            catalysts_by_topic[topic] = catalysts
            news_score_by_topic[topic] = self._score_topic_news(catalysts)
            for item in catalysts:
                key_news.append(
                    {
                        "title": item.title,
                        "source": item.source,
                        "url": item.url,
                        "published_at": item.published_at,
                        "score": item.score,
                        "topics": [topic],
                    }
                )

        enriched = []
        for snapshot in sorted_snapshots:
            catalysts = catalysts_by_topic.get(snapshot.name, [])
            if not catalysts:
                enriched.append(snapshot)
                continue

            raw = dict(getattr(snapshot, "raw", {}) or {})
            raw["catalysts"] = [item.to_dict() for item in catalysts]
            raw["news_topic"] = snapshot.name
            payload = {
                **raw,
                "name": snapshot.name,
                "snapshot_type": snapshot.snapshot_type,
                "change_pct": snapshot.change_pct,
                "heat_score": snapshot.heat_score,
                "news_score": max(float(getattr(snapshot, "news_score", 0.0)), news_score_by_topic.get(snapshot.name, 0.0)),
            }
            if getattr(snapshot, "review_hit_rate", None) is not None:
                payload["review_hit_rate"] = snapshot.review_hit_rate
            enriched.append(score_sector(payload))

        enriched.sort(key=lambda item: item.score, reverse=True)
        return enriched[:limit], self._dedupe_key_news(key_news, limit=min(limit, _MAX_KEY_NEWS))

    def _build_opportunities(
        self,
        *,
        hot_stocks: List[Dict[str, Any]],
        sectors: List[Any],
        market: str,
        scope: str,
        limit: int,
        warnings: List[str],
        watchlist_symbols: List[str],
        holding_symbols: List[str],
        risk_profile: str,
    ) -> List[OpportunityItem]:
        if scope == "etf":
            return self._build_sector_etf_opportunities(
                sectors,
                market=market,
                limit=limit,
                watchlist_symbols=watchlist_symbols,
                holding_symbols=holding_symbols,
                risk_profile=risk_profile,
            )

        stock_limit = limit if scope == "stock" else max(1, limit // 2)
        opportunities: List[OpportunityItem] = []
        sector_context = self._build_sector_context(sectors)
        watchlist_set = {str(item).strip().upper() for item in watchlist_symbols if str(item).strip()}
        holding_set = {str(item).strip().upper() for item in holding_symbols if str(item).strip()}
        for rank, raw in enumerate(hot_stocks[:stock_limit], start=1):
            if not isinstance(raw, dict):
                continue
            code = str(raw.get("code") or raw.get("代码") or raw.get("symbol") or "").strip()
            name = str(raw.get("name") or raw.get("名称") or code or f"候选{rank}").strip()
            change_pct = float(raw.get("change_pct") or raw.get("涨跌幅") or 0)
            sector_name = str(raw.get("industry") or raw.get("sector") or (sectors[0].name if sectors else "")).strip()
            matched_sector = self._match_sector_context(sector_name, sector_context) or {}
            sector_news_score = float(matched_sector.get("news_score") or 0.0)
            catalysts = list(matched_sector.get("catalysts") or [])
            score = score_sector(
                {
                    "name": sector_name or name,
                    "change_pct": change_pct,
                    "heat_score": raw.get("heat_score") or raw.get("hot_score") or 50,
                    "news_score": raw.get("news_score") or sector_news_score,
                }
            ).score
            chip_status = classify_chip_status(code, instrument_type="stock", chip_data=None)
            data_quality = "partial" if chip_status.status != "available" else "good"
            symbol = (code or f"hot-{rank}").strip().upper()
            watchlist_match = symbol in watchlist_set
            holding_match = symbol in holding_set
            linked_etf_code, linked_etf_name = map_theme_etf(sector_name or name)
            cycle_view = build_cycle_view(
                score=score,
                change_pct=change_pct,
                catalyst_scores=[float(item.score or 0.0) for item in catalysts],
                risk_profile=risk_profile,
            )
            portfolio_advice = build_portfolio_advice(
                instrument_type="stock",
                score=score,
                data_quality=data_quality,
                watchlist_match=watchlist_match,
                holding_match=holding_match,
                risk_profile=risk_profile,
            )
            tags = build_tags(
                watchlist_match=watchlist_match,
                holding_match=holding_match,
                has_catalysts=bool(catalysts),
            )
            opportunities.append(
                OpportunityItem(
                    code=code or f"hot-{rank}",
                    name=name,
                    instrument_type="stock",
                    market=market,
                    score=score,
                    sector=sector_name,
                    reason=self._build_opportunity_reason(
                        sector_name=sector_name,
                        catalysts=catalysts,
                        fallback="人气股与板块热度共振，需结合个股分析确认量价与基本面。",
                    ),
                    risk_budget=build_risk_budget("stock", data_quality=data_quality, risk_profile=risk_profile),
                    chip_status=chip_status,
                    data_quality=data_quality,
                    catalysts=catalysts,
                    action_bias=str(cycle_view.get("action_bias") or "watch"),
                    action_label=str(cycle_view.get("action_label") or "observe"),
                    cycle_view=cycle_view,
                    portfolio_advice=portfolio_advice,
                    tags=tags,
                    watchlist_match=watchlist_match,
                    holding_match=holding_match,
                    linked_etf_code=linked_etf_code,
                    linked_etf_name=linked_etf_name,
                    raw=dict(raw),
                )
            )

        if scope == "balanced":
            opportunities.extend(
                self._build_sector_etf_opportunities(
                    sectors,
                    market=market,
                    limit=limit - len(opportunities),
                    watchlist_symbols=watchlist_symbols,
                    holding_symbols=holding_symbols,
                    risk_profile=risk_profile,
                )
            )
        opportunities.sort(key=lambda item: item.score, reverse=True)
        if not opportunities and warnings:
            return []
        return opportunities[:limit]

    def _build_sector_etf_opportunities(
        self,
        sectors: List[Any],
        *,
        market: str,
        limit: int,
        watchlist_symbols: List[str],
        holding_symbols: List[str],
        risk_profile: str,
    ) -> List[OpportunityItem]:
        items: List[OpportunityItem] = []
        watchlist_set = {str(item).strip().upper() for item in watchlist_symbols if str(item).strip()}
        holding_set = {str(item).strip().upper() for item in holding_symbols if str(item).strip()}
        for index, sector in enumerate(sectors[: max(0, limit)], start=1):
            name = getattr(sector, "name", f"板块{index}")
            score = float(getattr(sector, "score", 0.0))
            sector_raw = dict(getattr(sector, "raw", {}) or {})
            catalysts = self._raw_catalysts_to_signals(sector_raw)
            linked_etf_code, linked_etf_name = map_theme_etf(name)
            etf_code = linked_etf_code or f"ETF-{index}"
            etf_name = linked_etf_name or f"{name} ETF观察"
            watchlist_match = etf_code.strip().upper() in watchlist_set
            holding_match = etf_code.strip().upper() in holding_set
            cycle_view = build_cycle_view(
                score=score,
                change_pct=float(getattr(sector, "change_pct", 0.0) or 0.0),
                catalyst_scores=[float(item.score or 0.0) for item in catalysts],
                risk_profile=risk_profile,
            )
            portfolio_advice = build_portfolio_advice(
                instrument_type="etf",
                score=score,
                data_quality="partial",
                watchlist_match=watchlist_match,
                holding_match=holding_match,
                risk_profile=risk_profile,
            )
            tags = build_tags(
                watchlist_match=watchlist_match,
                holding_match=holding_match,
                has_catalysts=bool(catalysts),
            )
            items.append(
                OpportunityItem(
                    code=etf_code,
                    name=etf_name,
                    instrument_type="etf",
                    market=market,
                    score=score,
                    sector=name,
                    reason=self._build_opportunity_reason(
                        sector_name=name,
                        catalysts=catalysts,
                        fallback="板块强度靠前，优先用 ETF 做低个股风险的主题观察。",
                    ),
                    risk_budget=build_risk_budget("etf", data_quality="partial", risk_profile=risk_profile),
                    chip_status=classify_chip_status(etf_code, instrument_type="etf", chip_data=None),
                    data_quality="partial",
                    catalysts=catalysts,
                    action_bias=str(cycle_view.get("action_bias") or "watch"),
                    action_label=str(cycle_view.get("action_label") or "observe"),
                    cycle_view=cycle_view,
                    portfolio_advice=portfolio_advice,
                    tags=tags,
                    watchlist_match=watchlist_match,
                    holding_match=holding_match,
                    linked_etf_code=etf_code,
                    linked_etf_name=etf_name,
                    raw=getattr(sector, "raw", {}),
                )
            )
        return items

    def _effective_news_window_days(self) -> int:
        if hasattr(self.config, "get_effective_news_window_days"):
            try:
                return int(self.config.get_effective_news_window_days())
            except Exception:
                pass
        return resolve_news_window_days(
            news_max_age_days=int(getattr(self.config, "news_max_age_days", 3) or 3),
            news_strategy_profile=getattr(self.config, "news_strategy_profile", "short"),
        )

    @staticmethod
    def _score_topic_news(catalysts: List[NewsCatalystSignal]) -> float:
        if not catalysts:
            return 0.0
        base_score = max(float(item.score or 0.0) for item in catalysts)
        return min(100.0, max(55.0, base_score))

    def _routes_to_catalysts(
        self,
        topic: str,
        routes: Any,
        *,
        news_window_days: int,
    ) -> List[NewsCatalystSignal]:
        if not isinstance(routes, list):
            return []

        catalysts: List[NewsCatalystSignal] = []
        seen: set[str] = set()
        for route in routes:
            if not isinstance(route, dict):
                continue
            source = str(route.get("source") or "").strip()
            title = str(route.get("description") or route.get("title") or "").strip()
            url = str(route.get("url") or "").strip()
            published_at = str(route.get("published_at") or route.get("date") or "").strip() or None
            if not title or title == "等待发酵":
                continue
            if published_at and not self._is_recent_news(published_at, news_window_days=news_window_days):
                continue
            dedupe_key = url or f"{source}:{title}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            catalysts.append(
                NewsCatalystSignal(
                    title=title if topic in title else f"{topic}：{title}",
                    source=source,
                    url=url,
                    published_at=published_at,
                    score=self._score_single_catalyst(title=title, source=source, published_at=published_at),
                )
            )
        catalysts.sort(key=lambda item: item.score, reverse=True)
        return catalysts[:2]

    @staticmethod
    def _score_single_catalyst(*, title: str, source: str, published_at: Optional[str]) -> float:
        score = 55.0
        title_text = title.strip()
        if len(title_text) >= 18:
            score += 8.0
        if source:
            score += 4.0
        if published_at:
            score += 6.0
        return min(100.0, score)

    def _is_recent_news(self, published_at: str, *, news_window_days: int) -> bool:
        published_time = self._parse_news_datetime(published_at)
        if published_time is None:
            return True
        if published_time.tzinfo is not None:
            published_time = published_time.astimezone().replace(tzinfo=None)
        cutoff = datetime.now() - timedelta(days=max(1, news_window_days))
        return published_time >= cutoff

    @staticmethod
    def _parse_news_datetime(value: str) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        for parser in (datetime.fromisoformat,):
            try:
                return parser(normalized)
            except ValueError:
                continue
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _dedupe_key_news(items: List[Dict[str, Any]], *, limit: int) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            key = str(item.get("url") or "").strip() or title
            topics = [str(topic).strip() for topic in (item.get("topics") or []) if str(topic).strip()]
            if key in merged:
                existing_topics = list(merged[key].get("topics") or [])
                for topic in topics:
                    if topic not in existing_topics:
                        existing_topics.append(topic)
                merged[key]["topics"] = existing_topics
                merged[key]["score"] = max(float(merged[key].get("score") or 0.0), float(item.get("score") or 0.0))
                continue
            merged[key] = {
                "title": title,
                "source": item.get("source") or "",
                "url": item.get("url") or "",
                "published_at": item.get("published_at"),
                "score": float(item.get("score") or 0.0),
                "topics": topics,
            }
        ordered = sorted(merged.values(), key=lambda item: float(item.get("score") or 0.0), reverse=True)
        return ordered[: max(0, limit)]

    @staticmethod
    def _build_sector_context(sectors: List[Any]) -> Dict[str, Dict[str, Any]]:
        context: Dict[str, Dict[str, Any]] = {}
        for sector in sectors:
            name = str(getattr(sector, "name", "")).strip()
            if not name:
                continue
            context[name] = {
                "score": float(getattr(sector, "score", 0.0) or 0.0),
                "news_score": float(getattr(sector, "news_score", 0.0) or 0.0),
                "catalysts": OpportunityService._raw_catalysts_to_signals(dict(getattr(sector, "raw", {}) or {})),
            }
        return context

    @staticmethod
    def _match_sector_context(sector_name: str, context: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        name = str(sector_name or "").strip()
        if not context:
            return None
        if not name:
            return next(iter(context.values()), None)
        if name in context:
            return context[name]
        normalized = OpportunityService._normalize_match_key(name)
        if normalized:
            for key, value in context.items():
                key_normalized = OpportunityService._normalize_match_key(key)
                if normalized == key_normalized or normalized in key_normalized or key_normalized in normalized:
                    return value
        return None

    @staticmethod
    def _normalize_match_key(value: str) -> str:
        return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())

    @staticmethod
    def _coerce_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _raw_catalysts_to_signals(raw: Dict[str, Any]) -> List[NewsCatalystSignal]:
        catalysts = raw.get("catalysts")
        if not isinstance(catalysts, list):
            return []
        normalized: List[NewsCatalystSignal] = []
        for item in catalysts:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            normalized.append(
                NewsCatalystSignal(
                    title=title,
                    source=str(item.get("source") or "").strip(),
                    url=str(item.get("url") or "").strip(),
                    published_at=str(item.get("published_at") or "").strip() or None,
                    score=float(item.get("score") or 0.0),
                )
            )
        return normalized

    @staticmethod
    def _build_opportunity_reason(
        *,
        sector_name: str,
        catalysts: List[NewsCatalystSignal],
        fallback: str,
    ) -> str:
        if not catalysts:
            return fallback
        lead = catalysts[0].title
        if sector_name:
            return f"{sector_name}近期有消息催化：{lead}"
        return f"近期有消息催化：{lead}"

    @staticmethod
    def _normalize_market(value: str) -> str:
        value = (value or "all").lower()
        return value if value in {"cn", "hk", "us", "all"} else "all"

    @staticmethod
    def _normalize_scope(value: str) -> str:
        value = (value or "balanced").lower()
        return value if value in {"balanced", "etf", "stock"} else "balanced"

    @staticmethod
    def _temperature_label(score: float) -> str:
        if score >= 75:
            return "hot"
        if score >= 55:
            return "warm"
        if score > 0:
            return "cool"
        return "unknown"
