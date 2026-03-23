"""
Tests for document importers.
"""

import csv
import os
import tempfile
import unittest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCustomCSVImporter(unittest.TestCase):
    def test_import_basic_csv(self):
        from importers.custom_csv import import_custom_csv

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Type", "Asset", "Amount", "USD"])
            writer.writerow(["2024-06-15", "buy", "BTC", "0.5", "30000"])
            writer.writerow(["2024-07-01", "sell", "BTC", "0.25", "16000"])
            tmp_path = f.name

        try:
            rows = import_custom_csv(tmp_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["asset"], "BTC")
            self.assertEqual(rows[0]["type"], "buy")
            self.assertAlmostEqual(rows[0]["amount"], 0.5)
            self.assertAlmostEqual(rows[0]["usd_value"], 30000.0)
            self.assertIn("custom_csv:", rows[0]["source"])
        finally:
            os.unlink(tmp_path)

    def test_import_with_aliases(self):
        from importers.custom_csv import import_custom_csv

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Side", "Currency", "Quantity", "Total USD"])
            writer.writerow(["1700000000", "buy", "ETH", "1.0", "2000"])
            tmp_path = f.name

        try:
            rows = import_custom_csv(tmp_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["asset"], "ETH")
            self.assertEqual(rows[0]["type"], "buy")
            self.assertEqual(rows[0]["date"], 1700000000)
        finally:
            os.unlink(tmp_path)

    def test_empty_csv(self):
        from importers.custom_csv import import_custom_csv

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Amount"])
            tmp_path = f.name

        try:
            rows = import_custom_csv(tmp_path)
            self.assertEqual(len(rows), 0)
        finally:
            os.unlink(tmp_path)


class TestCoinbasePDFHelpers(unittest.TestCase):
    def test_normalise_type(self):
        from importers.coinbase_pdf import _normalise_type
        self.assertEqual(_normalise_type("Buy"), "buy")
        self.assertEqual(_normalise_type("Sell"), "sell")
        self.assertEqual(_normalise_type("Convert"), "swap")
        self.assertEqual(_normalise_type("Staking Reward"), "staking_reward")

    def test_parse_date(self):
        from importers.coinbase_pdf import _parse_date
        self.assertGreater(_parse_date("01/15/2024"), 0)
        self.assertGreater(_parse_date("2024-01-15"), 0)
        self.assertGreater(_parse_date("Jan 15, 2024"), 0)
        self.assertEqual(_parse_date("not-a-date"), 0)

    def test_extract_amount_asset(self):
        from importers.coinbase_pdf import _extract_amount_asset
        amount, asset = _extract_amount_asset("0.012 BTC")
        self.assertAlmostEqual(amount, 0.012)
        self.assertEqual(asset, "BTC")

        amount, asset = _extract_amount_asset("$125.30")
        self.assertAlmostEqual(amount, 125.30)
        self.assertEqual(asset, "USD")


if __name__ == "__main__":
    unittest.main()
