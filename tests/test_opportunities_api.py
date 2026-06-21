# -*- coding: utf-8 -*-
"""Tests for the opt-in opportunity API endpoints."""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from src.config import Config
from src.services.task_queue import TaskStatus as QueueTaskStatus
from api.v1.endpoints import opportunities as opportunities_endpoint


class OpportunityApiTestCase(unittest.TestCase):
    def _config(self, *, enabled: bool) -> Config:
        return Config(opportunity_engine_enabled=enabled)

    def test_overview_returns_disabled_payload_without_touching_data_sources(self) -> None:
        config = self._config(enabled=False)

        with patch(
            "src.extensions.opportunity.service.DataFetcherManager",
            side_effect=AssertionError("data source should not be used when disabled"),
        ):
            payload = opportunities_endpoint.opportunity_overview(config=config)

        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["data_quality"]["level"], "disabled")
        self.assertEqual(payload["opportunities"], [])
        self.assertIn("opportunity_engine_disabled", payload["warnings"])

    def test_overview_returns_structured_candidates_when_enabled(self) -> None:
        config = self._config(enabled=True)
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 6.2, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [{"code": "300750", "name": "宁德时代", "change_pct": 3.1}]

        with patch("src.extensions.opportunity.service.DataFetcherManager", return_value=fetcher), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[
                {
                    "title": "消息催化",
                    "description": "AI算力订单与景气度共振。",
                    "source": "news_search",
                    "published_at": "2026-06-20",
                    "url": "https://example.invalid/ai",
                }
            ],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value={"industry_rows": [], "concept_rows": [], "stock_signals": {}, "warnings": []},
        ):
            payload = opportunities_endpoint.opportunity_overview(config=config, market="cn", scope="balanced", limit=5)

        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["market"], "cn")
        self.assertGreaterEqual(payload["market_temperature"]["score"], 0)
        self.assertEqual(payload["top_sectors"][0]["name"], "AI算力")
        self.assertTrue(payload["key_news"])
        self.assertTrue(
            any(item["risk_budget"]["instrument_type"] == "stock" for item in payload["opportunities"])
        )
        self.assertTrue(any(item.get("catalysts") for item in payload["opportunities"]))
        self.assertIn("data_quality", payload)

    def test_overview_forwards_account_id_and_risk_profile_to_service(self) -> None:
        config = self._config(enabled=True)

        with patch.object(
            opportunities_endpoint.OpportunityService,
            "overview",
            return_value={"enabled": True, "opportunities": []},
        ) as overview:
            payload = opportunities_endpoint.opportunity_overview(
                config=config,
                market="us",
                scope="balanced",
                limit=6,
                account_id=2,
                risk_profile="aggressive",
            )

        self.assertTrue(payload["enabled"])
        overview.assert_called_once_with(
            market="us",
            scope="balanced",
            limit=6,
            account_id=2,
            risk_profile="aggressive",
        )

    def test_overview_forwards_new_payload_without_dropping_market_outlook(self) -> None:
        config = self._config(enabled=True)

        with patch.object(
            opportunities_endpoint.OpportunityService,
            "overview",
            return_value={
                "enabled": True,
                "market_outlook": {"predicted_direction": "看多"},
                "review_history": [{"trade_date": "2026-06-20", "success_pct": 75.0}],
                "opportunities": [],
            },
        ) as overview:
            payload = opportunities_endpoint.opportunity_overview(
                config=config,
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        self.assertEqual(payload["market_outlook"]["predicted_direction"], "看多")
        self.assertEqual(payload["review_history"][0]["trade_date"], "2026-06-20")
        overview.assert_called_once()

    def test_scan_submits_background_opportunity_task(self) -> None:
        config = self._config(enabled=True)

        with patch.object(
            opportunities_endpoint.OpportunityService,
            "scan",
            return_value={
                "enabled": True,
                "market": "cn",
                "scope": "balanced",
                "risk_profile": "aggressive",
                "limit": 3,
                "opportunities": [],
            },
        ):
            accepted = opportunities_endpoint.opportunity_start_scan_task(
                opportunities_endpoint.OpportunityScanRequest(
                    market="cn",
                    scope="balanced",
                    risk_profile="aggressive",
                    watchlist_only=False,
                    max_results=3,
                ),
                config=config,
            )

            self.assertEqual(accepted.status, "pending")
            self.assertEqual(accepted.market, "cn")
            self.assertEqual(accepted.risk_profile, "aggressive")

            deadline = time.time() + 3
            status = opportunities_endpoint.opportunity_scan_task_status(accepted.task_id)
            while status.status in {QueueTaskStatus.PENDING.value, QueueTaskStatus.PROCESSING.value} and time.time() < deadline:
                time.sleep(0.05)
                status = opportunities_endpoint.opportunity_scan_task_status(accepted.task_id)

            self.assertEqual(status.status, QueueTaskStatus.COMPLETED.value)
            self.assertIsNotNone(status.result)
            self.assertEqual(status.risk_profile, "aggressive")


if __name__ == "__main__":
    unittest.main()
