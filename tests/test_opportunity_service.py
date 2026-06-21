# -*- coding: utf-8 -*-
"""Regression tests for opportunity overview news-catalyst enrichment."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.config import Config
from src.extensions.opportunity.service import OpportunityService


class OpportunityServiceOverviewTestCase(unittest.TestCase):
    def _config(self) -> Config:
        return Config(
            opportunity_engine_enabled=True,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

    def test_overview_populates_key_news_and_reason_when_topic_news_exists(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 3.8, "heat_score": 86}],
            [],
        )
        fetcher.get_concept_rankings.return_value = (
            [{"name": "算力租赁", "change_pct": 2.4, "heat_score": 79}],
            [],
        )
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 2.1, "sector": "AI算力", "heat_score": 72},
        ]

        with patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            side_effect=lambda topic, _config: [{
                "title": "消息催化",
                "description": f"{topic} 景气度抬升，订单与算力需求共振。",
                "source": "news_search",
                "published_at": "2026-06-20",
                "url": f"https://example.invalid/{topic}",
            }],
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
            )

        self.assertTrue(payload["enabled"])
        self.assertTrue(payload["key_news"])
        self.assertEqual(payload["key_news"][0]["topics"][0], "AI算力")
        self.assertGreater(payload["top_sectors"][0]["news_score"], 0)
        matching = next(item for item in payload["opportunities"] if item["sector"] == "AI算力")
        self.assertTrue(matching["catalysts"])
        self.assertIn("消息催化", matching["reason"])

    def test_overview_degrades_gracefully_when_topic_news_lookup_fails(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 3.8, "heat_score": 86}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [{"code": "300750", "name": "宁德时代", "change_pct": 2.1, "sector": "AI算力"}]

        with patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            side_effect=RuntimeError("news unavailable"),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
            )

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["key_news"], [])
        self.assertTrue(payload["opportunities"])
        self.assertTrue(any(str(item).startswith("topic_news_failed:AI算力:") for item in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
