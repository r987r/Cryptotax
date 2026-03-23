"""
Tests for blockchain address parsers.

These tests mock external API calls so they run offline and fast.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEthereumClassify(unittest.TestCase):
    """Test the transaction classification logic (no network calls)."""

    def setUp(self):
        from parsers.ethereum import _classify_tx
        self.classify = _classify_tx
        self.addr = "0xabc123"

    def test_send(self):
        tx = {"from": "0xabc123", "to": "0xother", "isError": "0", "functionName": ""}
        self.assertEqual(self.classify(tx, self.addr), "send")

    def test_receive(self):
        tx = {"from": "0xother", "to": "0xabc123", "isError": "0", "functionName": ""}
        self.assertEqual(self.classify(tx, self.addr), "receive")

    def test_swap(self):
        tx = {"from": "0xabc123", "to": "0xrouter", "isError": "0",
              "functionName": "swapExactTokensForETH(uint256,uint256,address[],address,uint256)"}
        self.assertEqual(self.classify(tx, self.addr), "swap")

    def test_failed(self):
        tx = {"from": "0xabc123", "to": "0xother", "isError": "1", "functionName": ""}
        self.assertEqual(self.classify(tx, self.addr), "failed")

    def test_contract_creation(self):
        tx = {"from": "0xabc123", "to": "", "contractAddress": "0xnew",
              "isError": "0", "functionName": ""}
        self.assertEqual(self.classify(tx, self.addr), "contract_creation")

    def test_approve(self):
        tx = {"from": "0xabc123", "to": "0xtoken", "isError": "0",
              "functionName": "approve(address,uint256)"}
        self.assertEqual(self.classify(tx, self.addr), "approve")

    def test_stake(self):
        tx = {"from": "0xabc123", "to": "0xstaking", "isError": "0",
              "functionName": "stake(uint256)"}
        self.assertEqual(self.classify(tx, self.addr), "stake")

    def test_mint(self):
        tx = {"from": "0xabc123", "to": "0xnft", "isError": "0",
              "functionName": "mint(uint256)"}
        self.assertEqual(self.classify(tx, self.addr), "mint")


class TestEthereumHelpers(unittest.TestCase):
    def test_wei_to_eth(self):
        from parsers.ethereum import _wei_to_eth
        self.assertAlmostEqual(_wei_to_eth("1000000000000000000"), 1.0)
        self.assertAlmostEqual(_wei_to_eth("0"), 0.0)
        self.assertAlmostEqual(_wei_to_eth("bad"), 0.0)

    def test_token_value(self):
        from parsers.ethereum import _token_value
        self.assertAlmostEqual(_token_value("1000000", "6"), 1.0)  # USDC
        self.assertAlmostEqual(_token_value("1000000000000000000", "18"), 1.0)


class TestEthereumFetch(unittest.TestCase):
    """Test the full fetch pipeline with mocked HTTP responses."""

    @patch("parsers.ethereum.get_historical_price", return_value=2000.0)
    @patch("parsers.ethereum._get")
    def test_fetch_evm_transactions(self, mock_get, mock_price):
        mock_get.side_effect = [
            # normal txs
            [{"hash": "0xaaa", "from": "0xother", "to": "0xme",
              "value": "1000000000000000000", "timeStamp": "1700000000",
              "gasUsed": "21000", "gasPrice": "20000000000",
              "isError": "0", "functionName": ""}],
            # internal txs
            [],
            # token txs
            [],
        ]

        from parsers.ethereum import fetch_evm_transactions
        rows = fetch_evm_transactions("0xme", chain="ethereum")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "receive")
        self.assertEqual(rows[0]["asset"], "ETH")
        self.assertAlmostEqual(rows[0]["amount"], 1.0)
        self.assertEqual(rows[0]["usd_value"], 2000.0)


class TestBitcoinClassify(unittest.TestCase):
    def test_receive(self):
        from parsers.bitcoin import _classify
        tx = {
            "inputs": [{"addresses": ["other"], "output_value": 50000}],
            "outputs": [{"addresses": ["myaddr"], "value": 50000}],
        }
        tx_type, amount = _classify(tx, "myaddr")
        self.assertEqual(tx_type, "receive")
        self.assertAlmostEqual(amount, 0.0005)

    def test_send(self):
        from parsers.bitcoin import _classify
        tx = {
            "inputs": [{"addresses": ["myaddr"], "output_value": 100000}],
            "outputs": [{"addresses": ["other"], "value": 90000},
                        {"addresses": ["myaddr"], "value": 5000}],  # change
        }
        tx_type, amount = _classify(tx, "myaddr")
        self.assertEqual(tx_type, "send")


class TestBitcoinParseISO(unittest.TestCase):
    def test_iso_formats(self):
        from parsers.bitcoin import _parse_iso
        self.assertGreater(_parse_iso("2024-01-15T12:00:00Z"), 0)
        self.assertGreater(_parse_iso("2024-01-15T12:00:00.123Z"), 0)
        self.assertEqual(_parse_iso("garbage"), 0)


class TestAlgorandClassify(unittest.TestCase):
    def test_pay_receive(self):
        from parsers.algorand import _classify
        tx = {"tx-type": "pay", "sender": "other",
              "payment-transaction": {"receiver": "myaddr"}}
        self.assertEqual(_classify(tx, "myaddr"), "receive")

    def test_pay_send(self):
        from parsers.algorand import _classify
        tx = {"tx-type": "pay", "sender": "myaddr",
              "payment-transaction": {"receiver": "other"}}
        self.assertEqual(_classify(tx, "myaddr"), "send")

    def test_app_call(self):
        from parsers.algorand import _classify
        tx = {"tx-type": "appl", "sender": "myaddr",
              "payment-transaction": {}}
        self.assertEqual(_classify(tx, "myaddr"), "app_call")

    def test_opt_in(self):
        from parsers.algorand import _classify
        tx = {"tx-type": "axfer", "sender": "myaddr",
              "asset-transfer-transaction": {"receiver": "myaddr", "amount": 0},
              "payment-transaction": {}}
        self.assertEqual(_classify(tx, "myaddr"), "opt_in")


if __name__ == "__main__":
    unittest.main()
