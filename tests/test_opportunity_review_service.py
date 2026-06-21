# -*- coding: utf-8 -*-
"""Tests for the lightweight opportunity review summary service."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.services.opportunity_review_service import OpportunityReviewService


class OpportunityReviewServiceTestCase(unittest.TestCase):
    def test_build_review_snapshot_aggregates_success_rate(self) -> None:
        service = OpportunityReviewService()

        snapshot = service.build_review_snapshot(
            [
                {"date": "2026-06-20", "focus_total": 5, "success_count": 3, "failure_count": 2},
                {"date": "2026-06-19", "focus_total": 4, "success_count": 2, "failure_count": 2},
            ]
        )

        self.assertEqual(snapshot["status"], "reviewed")
        self.assertEqual(snapshot["focus_total"], 9)
        self.assertEqual(snapshot["success_count"], 5)
        self.assertEqual(snapshot["success_pct"], 55.56)

    def test_build_review_snapshot_handles_empty_history(self) -> None:
        service = OpportunityReviewService()

        snapshot = service.build_review_snapshot([])

        self.assertEqual(snapshot["status"], "pending")
        self.assertEqual(snapshot["success_pct"], 0.0)

    def test_build_review_rows_from_sector_snapshots_uses_attempts_and_hit_rate(self) -> None:
        service = OpportunityReviewService()

        rows = service.build_review_rows_from_sector_snapshots(
            [
                SimpleNamespace(
                    name="AI-Compute",
                    review_hit_rate=0.8,
                    raw={"review_attempts": 5},
                ),
                SimpleNamespace(
                    name="Robotics",
                    review_hit_rate=40,
                    raw={"review_attempts": 5},
                ),
            ]
        )

        self.assertEqual(rows[0]["focus_total"], 5)
        self.assertEqual(rows[0]["success_count"], 4)
        self.assertEqual(rows[0]["failure_count"], 1)
        self.assertEqual(rows[1]["success_count"], 2)

    def test_build_review_rows_from_history_records_uses_persisted_market_review_payload(self) -> None:
        service = OpportunityReviewService()

        rows = service.build_review_rows_from_history_records(
            [
                SimpleNamespace(
                    context_snapshot={
                        "market_review_region": "cn",
                        "market_review_payload": {
                            "sectors": {
                                "top": [
                                    {"name": "AI-Compute", "review_hit_rate": 0.75, "review_attempts": 4},
                                    {"name": "Robotics", "review_hit_rate": 40, "review_attempts": 5},
                                ]
                            }
                        },
                    }
                )
            ],
            region="cn",
        )

        self.assertEqual(rows[0]["label"], "AI-Compute")
        self.assertEqual(rows[0]["focus_total"], 4)
        self.assertEqual(rows[0]["success_count"], 3)
        self.assertEqual(rows[1]["label"], "Robotics")
        self.assertEqual(rows[1]["failure_count"], 3)


if __name__ == "__main__":
    unittest.main()
