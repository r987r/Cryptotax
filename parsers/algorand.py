"""
Algorand transaction parser using the Algorand Indexer (AlgoNode free tier).
"""

from __future__ import annotations

import csv
import os
import time
from typing import Any

import requests

from config import ALGORAND_INDEXER_URL, ALGORAND_API_KEY, DATA_DIR
from parsers.price import get_historical_price

_RATE_LIMIT = 0.25
ALGO_COINGECKO_ID = "algorand"
ALGO_DECIMALS = 6


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    headers: dict[str, str] = {}
    if ALGORAND_API_KEY:
        headers["X-API-Key"] = ALGORAND_API_KEY
    time.sleep(_RATE_LIMIT)
    url = f"{ALGORAND_INDEXER_URL}{endpoint}"
    resp = requests.get(url, params=params, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _microalgo_to_algo(micro: int) -> float:
    return micro / (10 ** ALGO_DECIMALS)


def _classify(tx: dict, address: str) -> str:
    tx_type = tx.get("tx-type", "")
    sender = tx.get("sender", "")
    payment = tx.get("payment-transaction", {})
    asset_tx = tx.get("asset-transfer-transaction", {})
    receiver = payment.get("receiver", asset_tx.get("receiver", ""))

    if tx_type == "pay":
        if sender == address and receiver == address:
            return "self_transfer"
        if sender == address:
            return "send"
        return "receive"
    if tx_type == "axfer":
        if asset_tx.get("close-to"):
            return "opt_out"
        if sender == address and receiver == address and asset_tx.get("amount", 0) == 0:
            return "opt_in"
        if sender == address:
            return "token_send"
        return "token_receive"
    if tx_type == "appl":
        return "app_call"
    if tx_type == "acfg":
        return "asset_config"
    if tx_type == "afrz":
        return "asset_freeze"
    if tx_type == "keyreg":
        return "key_registration"
    return "unknown"


def fetch_algorand_transactions(address: str) -> list[dict]:
    """Fetch all transactions for an Algorand *address*."""
    rows: list[dict] = []
    next_token: str | None = None

    while True:
        params: dict[str, Any] = {"limit": 500}
        if next_token:
            params["next"] = next_token

        data = _get(f"/v2/accounts/{address}/transactions", params)
        txs = data.get("transactions", [])
        if not txs:
            break

        for tx in txs:
            ts = tx.get("round-time", 0)
            tx_type_str = _classify(tx, address)
            payment = tx.get("payment-transaction", {})
            asset_tx = tx.get("asset-transfer-transaction", {})
            fee_micro = tx.get("fee", 0)

            # Determine asset & amount
            if tx.get("tx-type") == "axfer":
                amount_raw = asset_tx.get("amount", 0)
                decimals = asset_tx.get("decimals", 0)  # may not be present
                asset_id = asset_tx.get("asset-id", "")
                asset_symbol = f"ASA-{asset_id}"
                amount = amount_raw / (10 ** decimals) if decimals else float(amount_raw)
                usd_value = ""  # ASA prices not resolved automatically
            else:
                amount = _microalgo_to_algo(payment.get("amount", 0))
                asset_symbol = "ALGO"
                price = get_historical_price(ALGO_COINGECKO_ID, ts) if ts else None
                usd_value = round(amount * price, 2) if price else ""

            fee = _microalgo_to_algo(fee_micro)
            fee_price = get_historical_price(ALGO_COINGECKO_ID, ts) if ts else None

            rows.append({
                "date": ts,
                "chain": "algorand",
                "tx_hash": tx.get("id", ""),
                "from": tx.get("sender", ""),
                "to": payment.get("receiver", asset_tx.get("receiver", "")),
                "asset": asset_symbol,
                "amount": amount,
                "fee": fee,
                "fee_asset": "ALGO",
                "type": tx_type_str,
                "usd_value": usd_value,
                "usd_fee": round(fee * fee_price, 2) if fee_price else "",
                "source": "algorand_indexer",
            })

        next_token = data.get("next-token")
        if not next_token:
            break

    rows.sort(key=lambda r: r["date"])
    return rows


# ── CSV ──────────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "date", "chain", "tx_hash", "from", "to", "asset", "amount",
    "fee", "fee_asset", "type", "usd_value", "usd_fee", "source",
]


def save_to_csv(rows: list[dict], filename: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path
