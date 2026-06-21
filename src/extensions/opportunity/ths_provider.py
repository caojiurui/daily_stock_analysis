"""Tonghuashun (THS) external info provider for the opportunity engine.

This module keeps THS integration in a small, optional adapter instead of
spreading provider-specific logic across the scoring and API layers.
"""

from __future__ import annotations

from queue import Queue
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Tuple


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
