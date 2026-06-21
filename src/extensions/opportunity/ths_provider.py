"""Tonghuashun (THS) external info provider for the opportunity engine.

This module keeps THS integration in a small, optional adapter instead of
spreading provider-specific logic across the scoring and API layers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from queue import Queue
import re
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests


_THS_FLASHNEWS_API_URL = "https://news.10jqka.com.cn/app/flash/flashnews/v1/list"
_THS_FLASHNEWS_HEADERS = {
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "User-Agent": "Mozilla/5.0",
}
_THS_FLASHNEWS_TAG_PATTERNS = (
    r"flashnews/v1/list[^\"'\s>]*tagId=(\d{4,})",
    r"[?&]tagId=(\d{4,})",
    r"tagId[\"'\s:=]+(\d{4,})",
    r"tag_id[\"'\s:=]+(\d{4,})",
)


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    text = str(value).strip().replace("%", "").replace(",", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip().replace(",", "")))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _rank_heat_score(index: int, total: int, *, floor: float, ceiling: float) -> float:
    if total <= 1:
        return round(ceiling, 2)
    ratio = max(0.0, min(1.0, float(index) / float(total - 1)))
    return round(ceiling - (ceiling - floor) * ratio, 2)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_ths_flashnews_tag_id(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if text.isdigit():
        return text
    for pattern in _THS_FLASHNEWS_TAG_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _parse_ths_flashnews_datetime(value: Any) -> Optional[str]:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        timestamp = int(float(text))
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 10**12:
        timestamp //= 1000
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone()
    except (OverflowError, OSError, ValueError):
        return None
    return dt.isoformat(timespec="seconds")


def _truncate_text(text: str, *, limit: int) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "..."


def extract_ths_flashnews_tag_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in (
            "ths_flashnews_tag_id",
            "flashnews_tag_id",
            "tagId",
            "tag_id",
            "快讯分类ID",
            "快讯标签ID",
            "标签ID",
        ):
            tag_id = _normalize_ths_flashnews_tag_id(payload.get(key))
            if tag_id:
                return tag_id
        for value in payload.values():
            tag_id = _normalize_ths_flashnews_tag_id(value)
            if tag_id:
                return tag_id
    return _normalize_ths_flashnews_tag_id(payload)


def normalize_ths_flashnews_item(item: Dict[str, Any]) -> Dict[str, Any]:
    published_at = (
        _parse_ths_flashnews_datetime(item.get("createTime"))
        or _parse_ths_flashnews_datetime(item.get("updateTime"))
        or None
    )
    return {
        "id": _normalize_text(item.get("id")),
        "seq": _normalize_text(item.get("seq")),
        "title": _normalize_text(item.get("title")),
        "summary": _normalize_text(item.get("summary")),
        "url": _normalize_text(item.get("shareUrl") or item.get("url") or item.get("appUrl")),
        "published_at": published_at,
        "tag_id": extract_ths_flashnews_tag_id(item),
    }


def fetch_ths_flashnews_items(
    *,
    tag_id: str,
    seq: Optional[int] = None,
    limit: int = 3,
    timeout_seconds: float = 6.0,
    session: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    normalized_tag_id = _normalize_ths_flashnews_tag_id(tag_id)
    if not normalized_tag_id:
        return []
    params: Dict[str, Any] = {"tagId": normalized_tag_id}
    if seq is not None:
        params["seq"] = int(seq)
    requester = session.get if session is not None else requests.get
    response = requester(
        _THS_FLASHNEWS_API_URL,
        params=params,
        headers=dict(_THS_FLASHNEWS_HEADERS),
        timeout=max(1.0, float(timeout_seconds)),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or int(payload.get("status_code") or -1) != 0:
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    items = data.get("list")
    if not isinstance(items, list):
        return []
    normalized_items = [
        normalize_ths_flashnews_item(item)
        for item in items
        if isinstance(item, dict)
    ]
    return [
        item
        for item in normalized_items[: max(0, int(limit or 0))]
        if item.get("title")
    ]


def format_ths_flashnews_event(item: Dict[str, Any], *, max_chars: int = 120) -> str:
    title = _normalize_text(item.get("title"))
    summary = _normalize_text(item.get("summary"))
    if not title and not summary:
        return ""
    body = title or summary
    if summary and summary not in body:
        body = f"{body}；{summary}"
    body = _truncate_text(body, limit=max_chars)
    published_at = _normalize_text(item.get("published_at"))
    if published_at:
        return f"{published_at[:10]}：{body}"
    return body


class ThsExternalInfoProvider:
    """Best-effort THS adapter with local timeout and safe degradation."""

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = max(1.0, float(timeout_seconds))

    def collect(self, *, limit: int = 10) -> Dict[str, Any]:
        safe_limit = max(1, min(int(limit), 20))
        industry_rows, industry_warning = self._run_with_timeout(
            "ths_industry_summary",
            lambda: self._load_industry_rows(limit=safe_limit),
        )
        concept_rows, concept_warning = self._run_with_timeout(
            "ths_concept_summary",
            lambda: self._load_concept_rows(limit=safe_limit),
        )
        stock_signals, stock_warning = self._run_with_timeout(
            "ths_stock_rankings",
            lambda: self._load_stock_signals(limit=safe_limit),
        )
        concept_rows = self._enrich_concept_rows_with_flashnews(
            concept_rows or [],
            limit=min(safe_limit, 3),
        )

        warnings = [
            warning
            for warning in (industry_warning, concept_warning, stock_warning)
            if warning
        ]
        return {
            "industry_rows": industry_rows or [],
            "concept_rows": concept_rows or [],
            "stock_signals": stock_signals or {},
            "warnings": warnings,
        }

    def _run_with_timeout(
        self,
        name: str,
        callback: Callable[[], Any],
    ) -> Tuple[Optional[Any], str]:
        result_queue: "Queue[Tuple[str, Any]]" = Queue(maxsize=1)

        def runner() -> None:
            try:
                result_queue.put(("ok", callback()))
            except Exception as exc:
                result_queue.put(("error", exc))

        thread = Thread(target=runner, daemon=True)
        thread.start()
        thread.join(self.timeout_seconds)
        if thread.is_alive():
            return None, f"ths_provider_timeout:{name}"
        if result_queue.empty():
            return None, f"ths_provider_empty:{name}"
        status, payload = result_queue.get()
        if status == "error":
            return None, f"ths_provider_failed:{name}:{type(payload).__name__}"
        return payload, ""

    def _enrich_concept_rows_with_flashnews(
        self,
        rows: List[Dict[str, Any]],
        *,
        limit: int,
    ) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for index, row in enumerate(rows or []):
            if not isinstance(row, dict):
                continue
            payload = dict(row)
            flashnews_tag_id = extract_ths_flashnews_tag_id(payload)
            flashnews_item: Dict[str, Any] = {}
            if flashnews_tag_id and index < max(0, limit):
                try:
                    flashnews_rows = fetch_ths_flashnews_items(
                        tag_id=flashnews_tag_id,
                        limit=1,
                        timeout_seconds=min(self.timeout_seconds, 3.0),
                    )
                except Exception:
                    flashnews_rows = []
                if flashnews_rows:
                    flashnews_item = flashnews_rows[0]
            if flashnews_item.get("title"):
                payload["ths_flashnews_tag_id"] = flashnews_tag_id
                payload["ths_flashnews_title"] = flashnews_item.get("title") or ""
                payload["ths_flashnews_summary"] = flashnews_item.get("summary") or ""
                payload["ths_flashnews_published_at"] = flashnews_item.get("published_at") or ""
                payload["ths_flashnews_url"] = flashnews_item.get("url") or ""
                payload["ths_flashnews_event"] = format_ths_flashnews_event(flashnews_item)
                payload["news_score"] = max(float(payload.get("news_score") or 0.0), 68.0)
                payload["external_score"] = max(
                    float(payload.get("external_score") or 0.0),
                    float(payload.get("heat_score") or 0.0),
                    float(payload.get("news_score") or 0.0),
                )
            elif flashnews_tag_id:
                payload["ths_flashnews_tag_id"] = flashnews_tag_id
            enriched.append(payload)
        return enriched

    @staticmethod
    def _load_industry_rows(*, limit: int) -> List[Dict[str, Any]]:
        import akshare as ak

        df = ak.stock_board_industry_summary_ths()
        if df is None or df.empty or "板块" not in df.columns:
            return []
        rows = df.copy()
        if "涨跌幅" in rows.columns:
            rows = rows.sort_values(by="涨跌幅", ascending=False)
        total = len(rows.index)
        items: List[Dict[str, Any]] = []
        for index, (_, row) in enumerate(rows.head(limit).iterrows()):
            change_pct = _to_float(row.get("涨跌幅"))
            heat_score = _rank_heat_score(index, total, floor=60.0, ceiling=92.0)
            if change_pct > 0:
                heat_score = _clamp(heat_score + min(change_pct * 1.5, 8.0))
            items.append(
                {
                    "name": str(row.get("板块") or "").strip(),
                    "change_pct": change_pct,
                    "heat_score": heat_score,
                    "external_score": heat_score,
                    "ths_source": "stock_board_industry_summary_ths",
                    "ths_board_type": "industry",
                    "ths_total_amount": row.get("总成交额"),
                    "ths_component_count": row.get("公司家数"),
                    "ths_leading_stock": row.get("领涨股"),
                }
            )
        return [item for item in items if item.get("name")]

    @staticmethod
    def _load_concept_rows(*, limit: int) -> List[Dict[str, Any]]:
        import akshare as ak

        df = ak.stock_board_concept_summary_ths()
        if df is None or df.empty or "概念名称" not in df.columns:
            return []
        rows = df.copy()
        if "成分股数量" in rows.columns:
            rows = rows.sort_values(by="成分股数量", ascending=False)
        total = len(rows.index)
        items: List[Dict[str, Any]] = []
        for index, (_, row) in enumerate(rows.head(limit).iterrows()):
            component_count = _to_int(row.get("成分股数量"))
            has_event = bool(str(row.get("驱动事件") or "").strip())
            news_score = 62.0 if has_event else 0.0
            heat_score = _rank_heat_score(index, total, floor=58.0, ceiling=86.0)
            if component_count >= 30:
                heat_score = _clamp(heat_score + 5.0)
            items.append(
                {
                    "name": str(row.get("概念名称") or "").strip(),
                    "change_pct": 0.0,
                    "heat_score": heat_score,
                    "news_score": news_score,
                    "external_score": max(heat_score, news_score),
                    "ths_source": "stock_board_concept_summary_ths",
                    "ths_board_type": "concept",
                    "ths_summary_date": str(row.get("日期") or "").strip(),
                    "ths_summary_event": str(row.get("驱动事件") or "").strip(),
                    "ths_leading_stock": str(row.get("龙头股") or "").strip(),
                    "ths_component_count": component_count,
                }
            )
        return [item for item in items if item.get("name")]

    @staticmethod
    def _load_stock_signals(*, limit: int) -> Dict[str, Dict[str, Any]]:
        import akshare as ak

        mapping: Dict[str, Dict[str, Any]] = {}
        specs = (
            ("stock_rank_cxg_ths", "THS创新高", 8.0),
            ("stock_rank_ljqd_ths", "THS量价齐跌", -6.0),
        )
        for api_name, label, boost in specs:
            df = getattr(ak, api_name)()
            if df is None or df.empty:
                continue
            for _, row in df.head(limit * 3).iterrows():
                code = str(row.get("股票代码") or row.get("code") or "").strip().upper()
                if not code:
                    continue
                signal = mapping.setdefault(
                    code,
                    {
                        "score_boost": 0.0,
                        "tags": [],
                        "sources": [],
                    },
                )
                signal["score_boost"] = round(float(signal["score_boost"]) + boost, 2)
                if label not in signal["tags"]:
                    signal["tags"].append(label)
                if api_name not in signal["sources"]:
                    signal["sources"].append(api_name)
        return mapping
