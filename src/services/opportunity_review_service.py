# -*- coding: utf-8 -*-
"""Lightweight review summary service for opportunity snapshots."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Dict, Iterable, List


class OpportunityReviewService:
    """Build a compact review snapshot without adding new persistence."""

    @staticmethod
    def _coerce_mapping(value: Any) -> Dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if not isinstance(value, str) or not value.strip():
            return {}
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}

    @staticmethod
    def _normalize_label(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_hit_rate(value: object) -> float:
        try:
            rate = float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
        if 0.0 <= rate <= 1.0:
            rate *= 100.0
        return max(0.0, min(100.0, round(rate, 2)))

    def build_review_rows_from_sector_snapshots(self, snapshots: Iterable[Any]) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for snapshot in snapshots or []:
            raw = self._coerce_mapping(snapshot) if isinstance(snapshot, Mapping) else dict(getattr(snapshot, "raw", {}) or {})
            hit_rate = raw.get("review_hit_rate") if isinstance(snapshot, Mapping) else getattr(snapshot, "review_hit_rate", None)
            if hit_rate is None:
                hit_rate = raw.get("review_hit_rate", raw.get("hit_rate"))
            normalized_hit_rate = self._normalize_hit_rate(hit_rate)

            attempts_raw = (
                raw.get("review_attempts")
                or raw.get("hit_rate_attempts")
                or raw.get("review_sample_count")
                or raw.get("sample_count")
            )
            try:
                attempts = int(attempts_raw or 0)
            except (TypeError, ValueError):
                attempts = 0

            if attempts <= 0 or normalized_hit_rate <= 0.0:
                continue

            success_count_raw = raw.get("review_success_count", raw.get("success_count"))
            failure_count_raw = raw.get("review_failure_count", raw.get("failure_count"))
            try:
                success_count = int(success_count_raw) if success_count_raw is not None else round(attempts * normalized_hit_rate / 100.0)
            except (TypeError, ValueError):
                success_count = round(attempts * normalized_hit_rate / 100.0)
            try:
                failure_count = int(failure_count_raw) if failure_count_raw is not None else max(attempts - success_count, 0)
            except (TypeError, ValueError):
                failure_count = max(attempts - success_count, 0)

            rows.append(
                {
                    "label": self._normalize_label(
                        raw.get("name") if isinstance(snapshot, Mapping) else getattr(snapshot, "name", "")
                    ) or self._normalize_label(raw.get("name")),
                    "focus_total": attempts,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_pct": normalized_hit_rate,
                }
            )
        return rows

    def build_review_rows_from_history_records(
        self,
        records: Iterable[Any],
        *,
        region: str = "",
    ) -> List[Dict[str, object]]:
        aggregates: Dict[str, Dict[str, object]] = {}
        normalized_region = str(region or "").strip().lower()
        for record in records or []:
            snapshot = self._coerce_mapping(getattr(record, "context_snapshot", None))
            if not snapshot:
                continue

            market_review_payload = self._coerce_mapping(snapshot.get("market_review_payload"))
            if normalized_region and not self._history_record_matches_region(
                snapshot=snapshot,
                market_review_payload=market_review_payload,
                region=normalized_region,
            ):
                continue

            history_rows = self._extract_history_review_rows(snapshot, market_review_payload)
            for row in history_rows:
                label = self._normalize_label(row.get("label"))
                if not label:
                    continue
                bucket = aggregates.setdefault(
                    label,
                    {
                        "label": label,
                        "focus_total": 0,
                        "success_count": 0,
                        "failure_count": 0,
                    },
                )
                bucket["focus_total"] = int(bucket.get("focus_total") or 0) + int(row.get("focus_total") or 0)
                bucket["success_count"] = int(bucket.get("success_count") or 0) + int(row.get("success_count") or 0)
                bucket["failure_count"] = int(bucket.get("failure_count") or 0) + int(row.get("failure_count") or 0)

        rows: List[Dict[str, object]] = []
        for bucket in aggregates.values():
            focus_total = int(bucket.get("focus_total") or 0)
            success_count = int(bucket.get("success_count") or 0)
            failure_count = int(bucket.get("failure_count") or 0)
            if focus_total <= 0:
                continue
            rows.append(
                {
                    "label": str(bucket.get("label") or ""),
                    "focus_total": focus_total,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_pct": round(success_count * 100.0 / focus_total, 2),
                }
            )
        rows.sort(key=lambda item: (-float(item.get("success_pct") or 0.0), -int(item.get("focus_total") or 0), str(item.get("label") or "")))
        return rows

    def merge_review_rows_into_sector_snapshots(
        self,
        snapshots: Iterable[Any],
        history_rows: Iterable[Dict[str, object]],
    ) -> List[Dict[str, object]]:
        stats_by_label: Dict[str, Dict[str, object]] = {}
        for row in history_rows or []:
            if not isinstance(row, Mapping):
                continue
            label = self._normalize_label(row.get("label"))
            match_key = self._normalize_match_key(label)
            if not match_key:
                continue
            focus_total = self._coerce_int(row.get("focus_total"))
            success_count = self._coerce_int(row.get("success_count"))
            failure_count = self._coerce_int(row.get("failure_count"))
            if focus_total <= 0:
                continue
            stats_by_label[match_key] = {
                "review_attempts": focus_total,
                "review_success_count": success_count,
                "review_failure_count": failure_count,
                "review_hit_rate": round(success_count * 100.0 / focus_total, 2),
            }

        merged: List[Dict[str, object]] = []
        for snapshot in snapshots or []:
            raw = self._coerce_mapping(snapshot) if isinstance(snapshot, Mapping) else dict(getattr(snapshot, "raw", {}) or {})
            name = self._normalize_label(
                raw.get("name") if isinstance(snapshot, Mapping) else getattr(snapshot, "name", "")
            ) or self._normalize_label(raw.get("name"))
            payload = dict(raw)
            if isinstance(snapshot, Mapping):
                payload.update(dict(snapshot))
            else:
                payload["name"] = name

            stats = stats_by_label.get(self._normalize_match_key(name))
            if stats:
                payload.update(stats)
            merged.append(payload)
        return merged

    @staticmethod
    def _history_record_matches_region(
        *,
        snapshot: Dict[str, Any],
        market_review_payload: Dict[str, Any],
        region: str,
    ) -> bool:
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
        return not region

    def _extract_history_review_rows(
        self,
        snapshot: Dict[str, Any],
        market_review_payload: Dict[str, Any],
    ) -> List[Dict[str, object]]:
        direct_rows = self._extract_direct_history_rows(snapshot, market_review_payload)
        if direct_rows:
            return direct_rows

        prediction_rows = self._extract_rows_from_review_predictions(snapshot, market_review_payload)
        if prediction_rows:
            return prediction_rows

        sectors = self._coerce_mapping(market_review_payload.get("sectors"))
        top_sectors = sectors.get("top")
        if isinstance(top_sectors, list):
            return self.build_review_rows_from_sector_snapshots(top_sectors)
        return []

    def _extract_direct_history_rows(
        self,
        snapshot: Dict[str, Any],
        market_review_payload: Dict[str, Any],
    ) -> List[Dict[str, object]]:
        candidate_lists: List[Any] = [
            snapshot.get("opportunity_review_rows"),
            snapshot.get("review_rows"),
            market_review_payload.get("opportunity_review_rows"),
            market_review_payload.get("review_rows"),
        ]
        opportunity_review = self._coerce_mapping(snapshot.get("opportunity_review"))
        payload_review = self._coerce_mapping(market_review_payload.get("opportunity_review"))
        candidate_lists.extend(
            [
                opportunity_review.get("rows"),
                opportunity_review.get("sector_success_rates"),
                payload_review.get("rows"),
                payload_review.get("sector_success_rates"),
            ]
        )

        for candidate in candidate_lists:
            rows = self._normalize_history_rows(candidate)
            if rows:
                return rows
        return []

    def _extract_rows_from_review_predictions(
        self,
        snapshot: Dict[str, Any],
        market_review_payload: Dict[str, Any],
    ) -> List[Dict[str, object]]:
        candidate_mappings = [
            self._coerce_mapping(snapshot.get("opportunity_review")),
            self._coerce_mapping(snapshot.get("review_payload")),
            self._coerce_mapping(market_review_payload.get("opportunity_review")),
            self._coerce_mapping(market_review_payload.get("review_payload")),
        ]
        aggregates: Dict[str, Dict[str, int]] = {}
        for candidate in candidate_mappings:
            predictions = candidate.get("predictions")
            if not isinstance(predictions, list):
                continue
            for item in predictions:
                if not isinstance(item, Mapping) or not item.get("is_focus"):
                    continue
                label = self._normalize_label(item.get("sector_name") or item.get("label") or item.get("name"))
                if not label:
                    continue
                review_status = str(item.get("review_status") or "").strip().lower()
                if review_status not in {"success", "failure"}:
                    actual_change_pct = item.get("actual_change_pct")
                    try:
                        review_status = "success" if float(actual_change_pct or 0.0) > 0 else "failure"
                    except (TypeError, ValueError):
                        continue
                bucket = aggregates.setdefault(label, {"focus_total": 0, "success_count": 0, "failure_count": 0})
                bucket["focus_total"] += 1
                if review_status == "success":
                    bucket["success_count"] += 1
                else:
                    bucket["failure_count"] += 1

        rows: List[Dict[str, object]] = []
        for label, bucket in aggregates.items():
            focus_total = int(bucket.get("focus_total") or 0)
            if focus_total <= 0:
                continue
            success_count = int(bucket.get("success_count") or 0)
            failure_count = int(bucket.get("failure_count") or 0)
            rows.append(
                {
                    "label": label,
                    "focus_total": focus_total,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_pct": round(success_count * 100.0 / focus_total, 2),
                }
            )
        rows.sort(key=lambda item: (-float(item.get("success_pct") or 0.0), -int(item.get("focus_total") or 0), str(item.get("label") or "")))
        return rows

    def _normalize_history_rows(self, value: Any) -> List[Dict[str, object]]:
        if not isinstance(value, list):
            return []
        rows: List[Dict[str, object]] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            label = self._normalize_label(item.get("label") or item.get("sector_name") or item.get("name"))
            if not label:
                continue
            focus_total = self._coerce_int(
                item.get("focus_total")
                or item.get("attempts")
                or item.get("review_attempts")
                or item.get("sample_count")
            )
            success_count = self._coerce_int(item.get("success_count"))
            failure_count = self._coerce_int(item.get("failure_count"))
            success_pct = self._normalize_hit_rate(
                item.get("success_pct")
                or item.get("success_rate")
                or item.get("review_hit_rate")
                or item.get("hit_rate")
            )
            if focus_total <= 0:
                focus_total = success_count + failure_count
            if success_count <= 0 and focus_total > 0 and success_pct > 0.0:
                success_count = round(focus_total * success_pct / 100.0)
            if failure_count <= 0 and focus_total > 0:
                failure_count = max(focus_total - success_count, 0)
            if focus_total <= 0:
                continue
            rows.append(
                {
                    "label": label,
                    "focus_total": focus_total,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_pct": round(success_count * 100.0 / focus_total, 2) if focus_total else 0.0,
                }
            )
        return rows

    @staticmethod
    def _normalize_match_key(value: object) -> str:
        return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())

    @staticmethod
    def _coerce_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def build_review_snapshot(self, history_rows: Iterable[Dict[str, object]]) -> Dict[str, object]:
        rows = list(history_rows or [])
        if not rows:
            return {
                "status": "pending",
                "label": "待复盘",
                "focus_total": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_pct": 0.0,
            }

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
