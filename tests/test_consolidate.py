"""
Tests for the consolidation and tax-form generation pipeline.
"""

import csv
import os
import tempfile
import unittest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConsolidation(unittest.TestCase):
    """Test the consolidation logic using temp CSV files."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Patch DATA_DIR and FINAL_DIR
        import config
        self._orig_data = config.DATA_DIR
        self._orig_final = config.FINAL_DIR
        config.DATA_DIR = self._tmpdir
        config.FINAL_DIR = self._tmpdir

    def tearDown(self):
        import config
        config.DATA_DIR = self._orig_data
        config.FINAL_DIR = self._orig_final
        # Cleanup temp files
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_csv(self, filename, rows):
        path = os.path.join(self._tmpdir, filename)
        fieldnames = [
            "date", "chain", "tx_hash", "from", "to", "asset", "amount",
            "fee", "fee_asset", "type", "usd_value", "usd_fee", "source",
        ]
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        return path

    def test_consolidate_merges_files(self):
        from scripts.consolidate import consolidate

        self._write_csv("chain_a.csv", [
            {"date": 1700000000, "chain": "ethereum", "tx_hash": "0xa",
             "from": "0x1", "to": "0x2", "asset": "ETH", "amount": 1.0,
             "fee": 0.001, "fee_asset": "ETH", "type": "send",
             "usd_value": 2000, "usd_fee": 2, "source": "ethereum_explorer"},
        ])
        self._write_csv("chain_b.csv", [
            {"date": 1700003600, "chain": "polygon", "tx_hash": "0xb",
             "from": "0x3", "to": "0x2", "asset": "ETH", "amount": 0.99,
             "fee": 0.0, "fee_asset": "MATIC", "type": "receive",
             "usd_value": 1980, "usd_fee": 0, "source": "polygon_explorer"},
        ])

        out_path = consolidate()
        self.assertTrue(os.path.exists(out_path))

        import pandas as pd
        df = pd.read_csv(out_path)
        self.assertEqual(len(df), 2)
        # Should be sorted by date
        self.assertLessEqual(df.iloc[0]["date"], df.iloc[1]["date"])
        # The send and receive should be linked
        self.assertTrue((df["link_id"] != "").any())

    def test_consolidate_no_files(self):
        """consolidate exits cleanly when data/ is empty."""
        from scripts.consolidate import consolidate
        with self.assertRaises(SystemExit):
            consolidate()


class TestFIFOTracker(unittest.TestCase):
    def test_basic_fifo(self):
        from scripts.generate_tax_forms import FIFOTracker

        t = FIFOTracker()
        t.acquire("BTC", 1000, 1.0, 30000)  # 1 BTC at $30k
        t.acquire("BTC", 2000, 0.5, 20000)  # 0.5 BTC at $40k

        cost, acq_date = t.dispose("BTC", 0.5)
        self.assertAlmostEqual(cost, 15000)  # 0.5 * $30k
        self.assertEqual(acq_date, 1000)

    def test_fifo_across_lots(self):
        from scripts.generate_tax_forms import FIFOTracker

        t = FIFOTracker()
        t.acquire("ETH", 1000, 2.0, 4000)   # 2 ETH at $2k each
        t.acquire("ETH", 2000, 1.0, 3000)   # 1 ETH at $3k

        cost, acq_date = t.dispose("ETH", 2.5)
        # First 2 ETH from lot 1 = $4000, then 0.5 from lot 2 = $1500
        self.assertAlmostEqual(cost, 5500)
        self.assertEqual(acq_date, 1000)

    def test_dispose_unknown_asset(self):
        from scripts.generate_tax_forms import FIFOTracker

        t = FIFOTracker()
        cost, acq_date = t.dispose("DOGE", 100)
        self.assertAlmostEqual(cost, 0.0)
        self.assertIsNone(acq_date)


class TestCopilotReview(unittest.TestCase):
    def test_flags_missing_usd(self):
        import pandas as pd
        from scripts.copilot_review import _review

        df = pd.DataFrame([{
            "date": 1700000000, "chain": "ethereum", "tx_hash": "0xa",
            "from": "0x1", "to": "0x2", "asset": "ETH", "amount": 1.0,
            "fee": 0.001, "fee_asset": "ETH", "type": "send",
            "usd_value": "", "usd_fee": "",
            "source": "test", "link_id": "", "link_note": "",
        }])
        result = _review(df)
        self.assertIn("missing_usd_value", result.iloc[0]["review_flags"])


if __name__ == "__main__":
    unittest.main()
