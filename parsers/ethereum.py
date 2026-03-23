"""
Ethereum & EVM-compatible chain transaction parser.

Supports any chain that exposes an Etherscan-compatible API:
Ethereum, Polygon, Arbitrum, Optimism, Base, etc.
"""

from __future__ import annotations

import csv
import os
import time
from typing import Any

import requests

from config import DATA_DIR, EVM_CHAINS
from parsers.price import get_historical_price

# Minimum seconds between explorer API calls (free-tier friendly)
_RATE_LIMIT = 0.25


def _get(url: str, params: dict[str, Any], api_key: str) -> list[dict]:
    """Make a rate-limited GET to an Etherscan-compatible API."""
    if api_key:
        params["apikey"] = api_key
    time.sleep(_RATE_LIMIT)
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "1" and isinstance(data.get("result"), list):
        return data["result"]
    return []


def _classify_tx(tx: dict, address: str) -> str:
    """Return a human-readable transaction type."""
    addr = address.lower()
    from_addr = tx.get("from", "").lower()
    to_addr = tx.get("to", "").lower()
    func = tx.get("functionName", "")
    if tx.get("isError") == "1":
        return "failed"
    if to_addr == "" and tx.get("contractAddress"):
        return "contract_creation"
    if "swap" in func.lower():
        return "swap"
    if "transfer" in func.lower() or "send" in func.lower():
        if from_addr == addr:
            return "send"
        return "receive"
    if "approve" in func.lower():
        return "approve"
    if "claim" in func.lower() or "harvest" in func.lower():
        return "claim"
    if "stake" in func.lower() or "deposit" in func.lower():
        return "stake"
    if "unstake" in func.lower() or "withdraw" in func.lower():
        return "unstake"
    if "mint" in func.lower():
        return "mint"
    if "bridge" in func.lower():
        return "bridge"
    if from_addr == addr and to_addr != addr:
        return "send"
    if to_addr == addr and from_addr != addr:
        return "receive"
    return "contract_interaction"


def _classify_internal(tx: dict, address: str) -> str:
    addr = address.lower()
    if tx.get("from", "").lower() == addr:
        return "internal_send"
    return "internal_receive"


def _classify_token(tx: dict, address: str) -> str:
    addr = address.lower()
    if tx.get("from", "").lower() == addr:
        return "token_send"
    return "token_receive"


def _wei_to_eth(wei: str) -> float:
    try:
        return int(wei) / 1e18
    except (ValueError, TypeError):
        return 0.0


def _token_value(raw: str, decimals: str) -> float:
    try:
        return int(raw) / (10 ** int(decimals))
    except (ValueError, TypeError):
        return 0.0


def fetch_evm_transactions(
    address: str,
    chain: str = "ethereum",
) -> list[dict]:
    """Fetch all normal, internal, and ERC-20 transactions for *address*.

    Returns a list of normalised dicts suitable for CSV output.
    """
    chain_cfg = EVM_CHAINS.get(chain)
    if chain_cfg is None:
        raise ValueError(
            f"Unknown chain '{chain}'. Supported: {list(EVM_CHAINS)}"
        )

    api_url = chain_cfg["api_url"]
    api_key = chain_cfg["api_key"]
    native = chain_cfg["native_symbol"]
    cg_id = chain_cfg["coingecko_id"]

    rows: list[dict] = []

    # ── Normal transactions ──────────────────────────────────────────────
    normal = _get(api_url, {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
    }, api_key)

    for tx in normal:
        ts = int(tx.get("timeStamp", 0))
        value = _wei_to_eth(tx.get("value", "0"))
        gas_used = int(tx.get("gasUsed", 0))
        gas_price = int(tx.get("gasPrice", 0))
        fee = gas_used * gas_price / 1e18
        price = get_historical_price(cg_id, ts)
        rows.append({
            "date": ts,
            "chain": chain,
            "tx_hash": tx.get("hash", ""),
            "from": tx.get("from", ""),
            "to": tx.get("to", ""),
            "asset": native,
            "amount": value,
            "fee": fee,
            "fee_asset": native,
            "type": _classify_tx(tx, address),
            "usd_value": round(value * price, 2) if price else "",
            "usd_fee": round(fee * price, 2) if price else "",
            "source": f"{chain}_explorer",
        })

    # ── Internal transactions ────────────────────────────────────────────
    internal = _get(api_url, {
        "module": "account",
        "action": "txlistinternal",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
    }, api_key)

    for tx in internal:
        ts = int(tx.get("timeStamp", 0))
        value = _wei_to_eth(tx.get("value", "0"))
        price = get_historical_price(cg_id, ts)
        rows.append({
            "date": ts,
            "chain": chain,
            "tx_hash": tx.get("hash", ""),
            "from": tx.get("from", ""),
            "to": tx.get("to", ""),
            "asset": native,
            "amount": value,
            "fee": 0.0,
            "fee_asset": native,
            "type": _classify_internal(tx, address),
            "usd_value": round(value * price, 2) if price else "",
            "usd_fee": "",
            "source": f"{chain}_explorer",
        })

    # ── ERC-20 token transfers ───────────────────────────────────────────
    tokens = _get(api_url, {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
    }, api_key)

    for tx in tokens:
        ts = int(tx.get("timeStamp", 0))
        value = _token_value(
            tx.get("value", "0"),
            tx.get("tokenDecimal", "18"),
        )
        # Token USD prices are best-effort; we don't have coingecko IDs
        # for every token.  Leave blank for now.
        rows.append({
            "date": ts,
            "chain": chain,
            "tx_hash": tx.get("hash", ""),
            "from": tx.get("from", ""),
            "to": tx.get("to", ""),
            "asset": tx.get("tokenSymbol", "UNKNOWN"),
            "amount": value,
            "fee": 0.0,
            "fee_asset": native,
            "type": _classify_token(tx, address),
            "usd_value": "",
            "usd_fee": "",
            "source": f"{chain}_explorer",
        })

    rows.sort(key=lambda r: r["date"])
    return rows


# ── CSV helpers ──────────────────────────────────────────────────────────────

FIELDNAMES = [
    "date",
    "chain",
    "tx_hash",
    "from",
    "to",
    "asset",
    "amount",
    "fee",
    "fee_asset",
    "type",
    "usd_value",
    "usd_fee",
    "source",
]


def save_to_csv(rows: list[dict], filename: str) -> str:
    """Write *rows* to ``data/<filename>`` and return the full path."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path
