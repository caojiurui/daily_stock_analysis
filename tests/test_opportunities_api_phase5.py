# -*- coding: utf-8 -*-
"""Additional API tests for opportunity workbench fields."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from api.v1.endpoints import opportunities as opportunities_endpoint
from src.config import Config


class OpportunityApiPhase5TestCase(unittest.TestCase):
    def _config(self) -> Config:
        return Config(opportunity_engine_enabled=True)

    def test_overview_exposes_portfolio_context_and_action_fields(self) -> None:
        payload = {
            "enabled": True,
            "market": "cn",
            "scope": "balanced",
            "generated_at": "2026-06-20T10:00:00",
            "market_temperature": {"score": 72, "label": "warm"},
            "top_sectors": [],
            "opportunities": [
                {
                    "code": "512480",
                    "name": "半导体ETF",
                    "instrument_type": "etf",
                    "market": "cn",
                    "score": 78,
                    "reason": "theme strength",
                    "sector": "AI算力",
                    "risk_budget": {"instrument_type": "etf"},
                    "chip_status": {"status": "unavailable", "reason": "chip_data_missing"},
                    "data_quality": "partial",
                    "review_entry": "backtest_pending",
                    "action_bias": "prepare",
                    "action_label": "准备跟踪",
                    "cycle_view": {"short_term": "偏强"},
                    "portfolio_advice": {"note": "优先小仓位试错"},
                    "tags": ["自选相关"],
                    "watchlist_match": True,
                    "holding_match": False,
                    "linked_etf_code": "512480",
                    "linked_etf_name": "半导体ETF",
                    "catalysts": [],
                    "raw": {},
                }
            ],
            "key_news": [],
            "portfolio_context": {"watchlist_count": 2, "holding_count": 1},
            "data_quality": {"level": "good", "warnings": []},
            "warnings": [],
        }

        with patch.object(opportunities_endpoint.OpportunityService, "overview", return_value=payload):
            result = opportunities_endpoint.opportunity_overview(config=self._config(), market="cn", scope="balanced", limit=5)

        self.assertEqual(result["portfolio_context"]["watchlist_count"], 2)
        self.assertEqual(result["opportunities"][0]["action_label"], "准备跟踪")
        self.assertEqual(result["opportunities"][0]["linked_etf_code"], "512480")


if __name__ == "__main__":
    unittest.main()
