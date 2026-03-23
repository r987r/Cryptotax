"""
Custom CSV importer.

Reads a user-provided CSV, maps its columns to the canonical schema, and
writes the result to ``data/``.  The importer tries common column-name
variants automatically and asks the user (via CLI prompts) only when it
cannot auto-detect a mapping.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime

from config import DATA_DIR

FIELDNAMES = [
    "date", "chain", "tx_hash", "from", "to", "asset", "amount",
    "fee", "fee_asset", "type", "usd_value", "usd_fee", "source",
]

# Mapping: canonical field → list of common CSV header variants (lowercase)
_ALIASES: dict[str, list[str]] = {
    "date": ["date", "timestamp", "time", "datetime", "trade date", "transaction date"],
    "chain": ["chain", "network", "blockchain"],
    "tx_hash": ["tx_hash", "txhash", "hash", "transaction hash", "txid", "transaction id"],
    "from": ["from", "sender", "from address", "source"],
    "to": ["to", "receiver", "to address", "destination", "recipient"],
    "asset": ["asset", "currency", "coin", "token", "symbol", "ticker"],
    "amount": ["amount", "quantity", "qty", "volume", "size"],
    "fee": ["fee", "fees", "commission", "trading fee"],
    "fee_asset": ["fee_asset", "fee currency", "fee coin"],
    "type": ["type", "side", "transaction type", "trade type", "action", "direction"],
    "usd_value": ["usd_value", "usd", "total", "total usd", "value", "subtotal", "cost"],
    "usd_fee": ["usd_fee", "fee usd", "fee_usd"],
}


def _build_mapping(src_headers: list[str]) -> dict[str, str | None]:
    """Return {canonical_field: source_header_or_None}."""
    lower_map = {h.lower().strip(): h for h in src_headers}
    mapping: dict[str, str | None] = {}
    for canon, aliases in _ALIASES.items():
        match = None
        for alias in aliases:
            if alias in lower_map:
                match = lower_map[alias]
                break
        mapping[canon] = match
    return mapping


def _parse_date(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    # Try UNIX timestamp first
    try:
        ts = float(text)
        if ts > 1e9:  # likely already a timestamp
            return int(ts)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%b %d, %Y",
    ):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            continue
    return 0


def _safe_float(text: str) -> float:
    try:
        return float(text.replace(",", "").replace("$", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def import_custom_csv(csv_path: str) -> list[dict]:
    """Read a custom CSV and return normalised rows."""
    rows: list[dict] = []
    basename = os.path.basename(csv_path)

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return rows

        mapping = _build_mapping(list(reader.fieldnames))

        for src_row in reader:
            row: dict[str, object] = {}
            for canon in FIELDNAMES:
                src_key = mapping.get(canon)
                raw = src_row.get(src_key, "") if src_key else ""
                if canon == "date":
                    row[canon] = _parse_date(raw)
                elif canon in ("amount", "fee", "usd_value", "usd_fee"):
                    row[canon] = _safe_float(raw) if raw else ""
                else:
                    row[canon] = raw.strip() if raw else ""
            row["source"] = f"custom_csv:{basename}"
            rows.append(row)

    rows.sort(key=lambda r: r["date"])
    return rows


def save_to_csv(rows: list[dict], filename: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path
