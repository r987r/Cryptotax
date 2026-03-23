"""
Bitcoin transaction parser using the BlockCypher API.
"""

from __future__ import annotations

import csv
import os
import time
from typing import Any

import requests

from config import BLOCKCYPHER_API_URL, BLOCKCYPHER_TOKEN, DATA_DIR
from parsers.price import get_historical_price

_RATE_LIMIT = 0.35  # seconds between requests

BTC_COINGECKO_ID = "bitcoin"


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict:
    params = params or {}
    if BLOCKCYPHER_TOKEN:
        params["token"] = BLOCKCYPHER_TOKEN
    time.sleep(_RATE_LIMIT)
    url = f"{BLOCKCYPHER_API_URL}/{endpoint}"
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _satoshi_to_btc(sat: int) -> float:
    return sat / 1e8


def _classify(tx: dict, address: str) -> tuple[str, float]:
    """Return (type, net_amount_btc) for the transaction relative to *address*."""
    addr = address.strip().lower()
    received = 0
    sent = 0

    for inp in tx.get("inputs", []):
        for a in inp.get("addresses", []):
            if a.lower() == addr:
                sent += inp.get("output_value", 0)

    for out in tx.get("outputs", []):
        for a in out.get("addresses", []):
            if a.lower() == addr:
                received += out.get("value", 0)

    net = received - sent
    if net > 0:
        return "receive", _satoshi_to_btc(net)
    elif net < 0:
        return "send", _satoshi_to_btc(abs(net))
    else:
        return "self_transfer", 0.0


def _parse_iso(ts_str: str) -> int:
    """Best-effort ISO-8601 → UNIX timestamp."""
    from datetime import datetime, timezone

    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
    ):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    return 0


def fetch_bitcoin_transactions(address: str) -> list[dict]:
    """Fetch full transaction history for a Bitcoin *address*.

    Uses the BlockCypher ``/addrs/<addr>/full`` endpoint with pagination.
    """
    rows: list[dict] = []
    before_block: int | None = None

    while True:
        params: dict[str, Any] = {"limit": 50}
        if before_block is not None:
            params["before"] = before_block

        data = _get(f"addrs/{address}/full", params)
        txs = data.get("txs", [])
        if not txs:
            break

        for tx in txs:
            ts_str = tx.get("confirmed", tx.get("received", ""))
            ts = _parse_iso(ts_str) if ts_str else 0
            tx_type, amount = _classify(tx, address)
            fee_sat = tx.get("fees", 0)
            fee = _satoshi_to_btc(fee_sat) if tx_type == "send" else 0.0
            price = get_historical_price(BTC_COINGECKO_ID, ts) if ts else None

            rows.append({
                "date": ts,
                "chain": "bitcoin",
                "tx_hash": tx.get("hash", ""),
                "from": address if tx_type == "send" else "",
                "to": address if tx_type == "receive" else "",
                "asset": "BTC",
                "amount": amount,
                "fee": fee,
                "fee_asset": "BTC",
                "type": tx_type,
                "usd_value": round(amount * price, 2) if price else "",
                "usd_fee": round(fee * price, 2) if price and fee else "",
                "source": "blockcypher",
            })

        # Pagination: use the block height of the last tx
        last_height = txs[-1].get("block_height")
        if last_height and last_height != before_block:
            before_block = last_height
        else:
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
