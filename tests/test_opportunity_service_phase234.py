# -*- coding: utf-8 -*-
"""Additional tests for opportunity phase 2-4 enhancements."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.config import Config
from src.extensions.opportunity.service import OpportunityService


class OpportunityServicePhase234TestCase(unittest.TestCase):
    def _config(self) -> Config:
        return Config(
            opportunity_engine_enabled=True,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

    @staticmethod
    def _empty_ths_payload() -> dict:
        return {
            "industry_rows": [],
            "concept_rows": [],
            "stock_signals": {},
            "warnings": [],
        }

    def test_overview_adds_action_cycle_portfolio_and_etf_fields(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 80},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=["300750", "512480"]), patch.object(
            OpportunityService, "_holding_symbols", return_value=["300750"]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[
                {
                    "title": "AI 算力景气度提升",
                    "description": "AI 算力景气度提升",
                    "source": "news_search",
                    "published_at": "2026-06-20",
                    "url": "https://example.invalid/ai",
                }
            ],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
            )

        stock_item = next(item for item in payload["opportunities"] if item["instrument_type"] == "stock")
        self.assertIn(stock_item["action_bias"], {"prepare", "watch", "avoid"})
        self.assertTrue(stock_item["action_label"])
        self.assertTrue(stock_item["watchlist_match"])
        self.assertTrue(stock_item["holding_match"])
        self.assertTrue(stock_item["cycle_view"])
        self.assertTrue(stock_item["portfolio_advice"]["note"])
        self.assertEqual(stock_item["linked_etf_code"], "512480")
        self.assertTrue(stock_item["linked_etf_name"])

        etf_item = next(item for item in payload["opportunities"] if item["instrument_type"] == "etf")
        self.assertEqual(etf_item["code"], "512480")
        self.assertEqual(etf_item["linked_etf_code"], "512480")
        self.assertTrue(etf_item["watchlist_match"])

    def test_scan_watchlist_only_filters_non_watchlist_opportunities(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 80},
            {"code": "600519", "name": "贵州茅台", "change_pct": 1.1, "sector": "消费", "heat_score": 60},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=["300750"]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).scan(
                market="cn",
                scope="stock",
                watchlist_only=True,
                max_results=5,
            )

        self.assertTrue(payload["watchlist_only"])
        self.assertEqual([item["code"] for item in payload["opportunities"]], ["300750"])

    def test_overview_uses_account_scoped_holdings_when_account_id_is_provided(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = ([], [])
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = []

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch(
            "src.extensions.opportunity.service.PortfolioService.get_portfolio_snapshot",
            return_value={
                "accounts": [
                    {
                        "account_id": 2,
                        "positions": [
                            {"symbol": "300750"},
                        ],
                    }
                ]
            },
        ) as get_snapshot, patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="us",
                scope="balanced",
                limit=5,
                account_id=2,
            )

        self.assertEqual(payload["portfolio_context"]["holding_count"], 1)
        get_snapshot.assert_called_once_with(account_id=2, cost_method="fifo")

    def test_overview_applies_scope_and_risk_profile_preferences(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 80},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="stock",
                limit=5,
                risk_profile="conservative",
            )

        self.assertEqual(payload["scope"], "stock")
        self.assertEqual(payload["risk_budget"]["risk_profile"], "conservative")
        self.assertEqual(payload["risk_budget"]["single_trade_risk_pct"], 1.0)
        self.assertTrue(payload["opportunities"])
        self.assertTrue(all(item["instrument_type"] == "stock" for item in payload["opportunities"]))
        stock_item = payload["opportunities"][0]
        self.assertEqual(stock_item["risk_budget"]["risk_profile"], "conservative")
        self.assertEqual(stock_item["risk_budget"]["position_min_pct"], 8)
        self.assertEqual(stock_item["risk_budget"]["position_max_pct"], 15)
        self.assertEqual(stock_item["risk_budget"]["single_trade_risk_pct"], 1.0)

    def test_overview_merges_ths_external_rows_and_key_news(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = []

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value={
                "industry_rows": [{"name": "机器人", "change_pct": 3.1, "heat_score": 76, "external_score": 76}],
                "concept_rows": [
                    {
                        "name": "AI算力",
                        "heat_score": 80,
                        "news_score": 62,
                        "external_score": 80,
                        "ths_summary_date": "2026-06-21",
                        "ths_summary_event": "服务器需求持续提升",
                    }
                ],
                "stock_signals": {},
                "warnings": [],
            },
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
            )

        top_sector_names = [item["name"] for item in payload["top_sectors"]]
        self.assertIn("AI算力", top_sector_names)
        self.assertIn("机器人", top_sector_names)
        self.assertTrue(any(item["source"] == "ths_summary" for item in payload["key_news"]))

    def test_overview_applies_ths_stock_signal_boosts_to_hot_stocks(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI算力", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 50},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value={
                "industry_rows": [],
                "concept_rows": [],
                "stock_signals": {
                    "300750": {
                        "score_boost": 8.0,
                        "tags": ["THS创新高"],
                        "sources": ["stock_rank_cxg_ths"],
                    }
                },
                "warnings": [],
            },
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="stock",
                limit=5,
            )

        self.assertTrue(payload["opportunities"])
        stock_item = payload["opportunities"][0]
        self.assertIn("external_signal_tags", stock_item["raw"])
        self.assertIn("THS创新高", stock_item["raw"]["external_signal_tags"])


    def test_overview_exposes_market_outlook_news_status_and_evidence_summary(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [{"name": "AI绠楀姏", "change_pct": 5.6, "heat_score": 88}],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "瀹佸痉鏃朵唬", "change_pct": 3.2, "sector": "AI绠楀姏", "heat_score": 80},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=["300750"]), patch.object(
            OpportunityService, "_holding_symbols", return_value=["300750"]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[
                {
                    "title": "AI 绠楀姏鏅皵搴︽彁鍗?",
                    "description": "AI 绠楀姏鏅皵搴︽彁鍗?",
                    "source": "news_search",
                    "published_at": "2026-06-20",
                    "url": "https://example.invalid/ai",
                }
            ],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        self.assertEqual(payload["news_status"], "success")
        self.assertIn("market_outlook", payload)
        self.assertIn("predicted_direction", payload["market_outlook"])
        self.assertTrue(payload["market_outlook"].get("reasoning"))
        self.assertIn("evidence_summary", payload)
        self.assertTrue(payload["evidence_summary"]["decision_signal_band"])
        self.assertIn("review_snapshot", payload)

    def test_overview_aggregates_sector_review_signals_into_review_snapshot(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [
                {
                    "name": "AI算力",
                    "change_pct": 5.6,
                    "heat_score": 88,
                    "review_hit_rate": 0.8,
                    "review_attempts": 5,
                },
                {
                    "name": "机器人",
                    "change_pct": 4.1,
                    "heat_score": 76,
                    "review_hit_rate": 0.4,
                    "review_attempts": 5,
                },
            ],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "宁德时代", "change_pct": 3.2, "sector": "AI算力", "heat_score": 80},
            {"code": "002747", "name": "埃斯顿", "change_pct": 2.8, "sector": "机器人", "heat_score": 74},
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        self.assertEqual(payload["review_snapshot"]["status"], "reviewed")
        self.assertEqual(payload["review_snapshot"]["focus_total"], 10)
        self.assertEqual(payload["review_snapshot"]["success_count"], 6)
        self.assertEqual(payload["review_snapshot"]["failure_count"], 4)
        self.assertEqual(payload["review_snapshot"]["success_pct"], 60.0)
        comparison_items = payload["evidence_summary"]["comparison_highlights"]
        comparison_labels = [item["label"] for item in comparison_items]
        self.assertIn("主线", comparison_labels)
        self.assertIn("前排", comparison_labels)
        self.assertIn("板块胜率", comparison_labels)
        self.assertTrue(next(item for item in comparison_items if item["label"] == "主线")["detail"])
        self.assertTrue(next(item for item in comparison_items if item["label"] == "前排")["detail"])

    def test_overview_prefers_persisted_review_history_rows_when_available(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [
                {
                    "name": "AI-Compute",
                    "change_pct": 5.6,
                    "heat_score": 88,
                    "review_hit_rate": 0.2,
                    "review_attempts": 5,
                },
                {
                    "name": "Robotics",
                    "change_pct": 4.1,
                    "heat_score": 76,
                    "review_hit_rate": 0.2,
                    "review_attempts": 5,
                },
            ],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "CATL", "change_pct": 3.2, "sector": "AI-Compute", "heat_score": 80},
            {"code": "002747", "name": "Estun", "change_pct": 2.8, "sector": "Robotics", "heat_score": 74},
        ]
        history_db = unittest.mock.MagicMock()
        history_db.get_analysis_history.return_value = [
            unittest.mock.Mock(
                context_snapshot={
                    "market_review_region": "cn",
                    "market_review_payload": {
                        "sectors": {
                            "top": [
                                {"name": "AI-Compute", "review_hit_rate": 0.75, "review_attempts": 4},
                                {"name": "Robotics", "review_hit_rate": 0.5, "review_attempts": 2},
                            ]
                        }
                    },
                }
            )
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.DatabaseManager.get_instance",
            return_value=history_db,
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        self.assertEqual(payload["review_snapshot"]["status"], "reviewed")
        self.assertEqual(payload["review_snapshot"]["focus_total"], 6)
        self.assertEqual(payload["review_snapshot"]["success_count"], 4)
        self.assertEqual(payload["review_snapshot"]["failure_count"], 2)
        self.assertEqual(payload["review_snapshot"]["success_pct"], 66.67)

    def test_overview_market_outlook_reasoning_prefers_persisted_breadth_context(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [
                {
                    "name": "AI-Compute",
                    "change_pct": 5.6,
                    "heat_score": 88,
                },
            ],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "CATL", "change_pct": 3.2, "sector": "AI-Compute", "heat_score": 80},
        ]
        history_db = unittest.mock.MagicMock()
        history_db.get_analysis_history.return_value = [
            unittest.mock.Mock(
                context_snapshot={
                    "market_review_region": "cn",
                    "market_review_payload": {
                        "region": "cn",
                        "date": "2026-06-20",
                        "breadth": {
                            "up_count": 3200,
                            "down_count": 1800,
                            "flat_count": 200,
                        },
                        "sectors": {"top": [{"name": "AI-Compute", "review_hit_rate": 0.75, "review_attempts": 4}]},
                    },
                }
            )
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.DatabaseManager.get_instance",
            return_value=history_db,
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        reasoning = payload["market_outlook"]["reasoning"]
        self.assertIn("3200", reasoning)
        self.assertIn("1800", reasoning)
        self.assertIn("2026-06-20", reasoning)

    def test_overview_exposes_recent_review_history_from_persisted_market_reviews(self) -> None:
        fetcher = unittest.mock.MagicMock()
        fetcher.get_sector_rankings.return_value = (
            [
                {
                    "name": "AI-Compute",
                    "change_pct": 5.6,
                    "heat_score": 88,
                },
            ],
            [],
        )
        fetcher.get_concept_rankings.return_value = ([], [])
        fetcher.get_hot_stocks.return_value = [
            {"code": "300750", "name": "CATL", "change_pct": 3.2, "sector": "AI-Compute", "heat_score": 80},
        ]
        history_db = unittest.mock.MagicMock()
        history_db.get_analysis_history.return_value = [
            unittest.mock.Mock(
                context_snapshot={
                    "market_review_region": "cn",
                    "market_review_payload": {
                        "region": "cn",
                        "date": "2026-06-20",
                        "opportunity_review": {
                            "rows": [
                                {"label": "AI-Compute", "focus_total": 4, "success_count": 3, "failure_count": 1},
                            ]
                        },
                    },
                }
            ),
            unittest.mock.Mock(
                context_snapshot={
                    "market_review_region": "cn",
                    "market_review_payload": {
                        "region": "cn",
                        "date": "2026-06-19",
                        "opportunity_review": {
                            "rows": [
                                {"label": "Robotics", "focus_total": 2, "success_count": 1, "failure_count": 1},
                            ]
                        },
                    },
                }
            ),
        ]

        with patch.object(OpportunityService, "_watchlist_symbols", return_value=[]), patch.object(
            OpportunityService, "_holding_symbols", return_value=[]
        ), patch(
            "src.extensions.opportunity.service._build_hotspot_event_routes_from_search",
            return_value=[],
        ), patch(
            "src.extensions.opportunity.service.DatabaseManager.get_instance",
            return_value=history_db,
        ), patch(
            "src.extensions.opportunity.service.ThsExternalInfoProvider.collect",
            return_value=self._empty_ths_payload(),
        ):
            payload = OpportunityService(config=self._config(), fetcher_manager=fetcher).overview(
                market="cn",
                scope="balanced",
                limit=5,
                risk_profile="balanced",
            )

        self.assertEqual(payload["review_history"][0]["trade_date"], "2026-06-20")
        self.assertEqual(payload["review_history"][0]["focus_total"], 4)
        self.assertEqual(payload["review_history"][0]["success_pct"], 75.0)
        self.assertEqual(payload["review_history"][1]["trade_date"], "2026-06-19")
        self.assertEqual(payload["review_history"][1]["success_pct"], 50.0)

if __name__ == "__main__":
    unittest.main()
