# -*- coding: utf-8 -*-
"""Regression tests for Akshare chip distribution retry behavior."""

import importlib.util
import sys
import unittest
from unittest.mock import patch

import pandas as pd
import requests

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

try:
    akshare_available = importlib.util.find_spec("akshare") is not None
except ValueError:
    akshare_available = "akshare" in sys.modules

if not akshare_available and "akshare" not in sys.modules:
    from unittest.mock import MagicMock

    sys.modules["akshare"] = MagicMock()

from data_provider.akshare_fetcher import AkshareFetcher


class TestAkshareChipRetry(unittest.TestCase):
    def test_get_chip_distribution_retries_once_after_transient_error(self) -> None:
        fetcher = AkshareFetcher(sleep_min=0, sleep_max=0)
        retryable_error = requests.exceptions.ConnectionError(
            "Remote end closed connection without response"
        )
        chip_frame = pd.DataFrame(
            [
                {
                    "日期": "2026-06-16",
                    "获利比例": 0.61,
                    "平均成本": 12.3,
                    "90成本-低": 11.8,
                    "90成本-高": 12.8,
                    "90集中度": 0.13,
                    "70成本-低": 12.0,
                    "70成本-高": 12.6,
                    "70集中度": 0.08,
                }
            ]
        )

        with patch.object(fetcher, "_set_random_user_agent"), patch.object(fetcher, "_enforce_rate_limit"), patch(
            "data_provider.akshare_fetcher.time.sleep"
        ) as sleep_mock, patch(
            "akshare.stock_cyq_em",
            side_effect=[retryable_error, chip_frame],
        ) as chip_mock:
            chip = fetcher.get_chip_distribution("301055")

        self.assertIsNotNone(chip)
        if chip is None:
            self.fail("expected chip distribution data after retry")
        self.assertEqual(chip.code, "301055")
        self.assertEqual(chip.date, "2026-06-16")
        self.assertEqual(chip.profit_ratio, 0.61)
        self.assertEqual(chip_mock.call_count, 2)
        sleep_mock.assert_called_once_with(1.0)


if __name__ == "__main__":
    unittest.main()
