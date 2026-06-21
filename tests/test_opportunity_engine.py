# -*- coding: utf-8 -*-
"""Pure-function tests for the opt-in opportunity engine."""

from src.extensions.opportunity.scoring import (
    build_risk_budget,
    classify_chip_status,
    normalize_sector_snapshots,
    score_sector,
)
from src.extensions.opportunity import ths_provider
from src.extensions.opportunity.ths_provider import ThsExternalInfoProvider


def test_risk_budget_caps_stock_and_etf_for_small_account():
    stock_budget = build_risk_budget("stock", volatility_level="normal", data_quality="good")
    etf_budget = build_risk_budget("etf", volatility_level="normal", data_quality="good")

    assert stock_budget.position_min_pct == 10
    assert stock_budget.position_max_pct == 20
    assert etf_budget.position_min_pct == 20
    assert etf_budget.position_max_pct == 35
    assert "止损" in stock_budget.stop_loss


def test_risk_budget_downgrades_when_volatility_or_data_quality_is_weak():
    budget = build_risk_budget("stock", volatility_level="high", data_quality="poor")

    assert budget.position_min_pct == 5
    assert budget.position_max_pct == 10
    assert budget.quality_adjustment == "downgraded"


def test_classify_chip_status_marks_non_a_share_and_missing_data():
    assert classify_chip_status("159915", instrument_type="etf", chip_data=None).status == "not_supported"
    assert classify_chip_status("HK00700", instrument_type="stock", chip_data=None).status == "not_supported"
    assert classify_chip_status("600519", instrument_type="stock", chip_data=None).status == "unavailable"
    assert classify_chip_status("600519", instrument_type="stock", chip_data={"avg_cost": 120}).status == "available"


def test_sector_score_uses_trend_heat_news_and_review_hit_rate():
    hot = score_sector(
        {
            "name": "AI算力",
            "change_pct": 5.0,
            "heat_score": 80,
            "news_score": 70,
            "review_hit_rate": 0.6,
        }
    )
    cold = score_sector({"name": "冷门板块", "change_pct": -2.0, "heat_score": 10})

    assert hot.score > cold.score
    assert 0 <= cold.score <= 100
    assert 0 <= hot.score <= 100


def test_sector_score_accepts_external_provider_score():
    base = score_sector({"name": "AI算力", "change_pct": 2.0, "heat_score": 55})
    enriched = score_sector({"name": "AI算力", "change_pct": 2.0, "heat_score": 55, "external_score": 80})

    assert enriched.score > base.score


def test_normalize_sector_snapshots_sorts_and_limits_results():
    snapshots = normalize_sector_snapshots(
        [
            {"板块名称": "低分", "涨跌幅": 0.2},
            {"name": "高分", "change_pct": 7.5, "heat_score": 90},
        ],
        snapshot_type="sector",
        limit=1,
    )

    assert len(snapshots) == 1
    assert snapshots[0].name == "高分"
    assert snapshots[0].snapshot_type == "sector"


def test_ths_provider_collect_returns_safe_empty_payload_when_loader_fails(monkeypatch):
    provider = ThsExternalInfoProvider(timeout_seconds=1)

    monkeypatch.setattr(
        ThsExternalInfoProvider,
        "_load_industry_rows",
        staticmethod(lambda limit: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    monkeypatch.setattr(ThsExternalInfoProvider, "_load_concept_rows", staticmethod(lambda limit: []))
    monkeypatch.setattr(ThsExternalInfoProvider, "_load_stock_signals", staticmethod(lambda limit: {}))

    payload = provider.collect(limit=5)

    assert payload["industry_rows"] == []
    assert payload["concept_rows"] == []
    assert payload["stock_signals"] == {}
    assert any(str(item).startswith("ths_provider_failed:ths_industry_summary:") for item in payload["warnings"])


def test_fetch_ths_flashnews_items_parses_response_shape(monkeypatch):
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status_code": 0,
                "data": {
                    "list": [
                        {
                            "id": 1,
                            "seq": 677558987,
                            "title": "碳酸锂期货主力合约跌超4%",
                            "summary": "看跌期权大涨",
                            "shareUrl": "https://example.test/item",
                            "createTime": 1781751613,
                        }
                    ]
                },
            }

    def _fake_get(url, *, params, headers, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("src.extensions.opportunity.ths_provider.requests.get", _fake_get)

    items = ths_provider.fetch_ths_flashnews_items(tag_id="62857", limit=1, timeout_seconds=2)

    assert captured["params"]["tagId"] == "62857"
    assert captured["headers"]["Pragma"] == "no-cache"
    assert captured["timeout"] == 2
    assert len(items) == 1
    assert items[0]["title"] == "碳酸锂期货主力合约跌超4%"
    assert items[0]["url"] == "https://example.test/item"
    assert items[0]["published_at"]


def test_collect_enriches_concept_rows_with_flashnews(monkeypatch):
    provider = ThsExternalInfoProvider(timeout_seconds=1)
    monkeypatch.setattr(
        ThsExternalInfoProvider,
        "_load_industry_rows",
        staticmethod(lambda limit: []),
    )
    monkeypatch.setattr(
        ThsExternalInfoProvider,
        "_load_concept_rows",
        staticmethod(
            lambda limit: [
                {
                    "name": "AI算力",
                    "heat_score": 80,
                    "news_score": 62,
                    "external_score": 80,
                    "ths_summary_date": "2026-06-21",
                    "ths_summary_event": "服务器需求持续提升",
                    "ths_flashnews_tag_id": "62857",
                }
            ]
        ),
    )
    monkeypatch.setattr(ThsExternalInfoProvider, "_load_stock_signals", staticmethod(lambda limit: {}))
    monkeypatch.setattr(
        "src.extensions.opportunity.ths_provider.fetch_ths_flashnews_items",
        lambda **kwargs: [
            {
                "title": "同花顺重要快讯",
                "summary": "AI算力板块盘中活跃",
                "url": "https://example.test/flash",
                "published_at": "2026-06-21T10:00:00+08:00",
            }
        ],
    )

    payload = provider.collect(limit=5)

    assert payload["concept_rows"][0]["ths_flashnews_title"] == "同花顺重要快讯"
    assert payload["concept_rows"][0]["ths_flashnews_url"] == "https://example.test/flash"
    assert payload["concept_rows"][0]["news_score"] >= 68.0
