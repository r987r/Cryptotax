"""
Coinbase PDF transaction-history parser.

Extracts tabular transaction data from Coinbase statement PDFs using
``pdfplumber``.  The exact layout may vary across Coinbase PDF versions;
this parser handles the most common statement format.
"""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime

import pdfplumber

from config import DATA_DIR

# Canonical output columns (same schema used everywhere)
FIELDNAMES = [
    "date", "chain", "tx_hash", "from", "to", "asset", "amount",
    "fee", "fee_asset", "type", "usd_value", "usd_fee", "source",
]


def _normalise_type(raw: str) -> str:
    """Map Coinbase-style labels to our canonical types."""
    raw = raw.strip().lower()
    mapping = {
        "buy": "buy",
        "sell": "sell",
        "send": "send",
        "receive": "receive",
        "convert": "swap",
        "reward": "reward",
        "staking reward": "staking_reward",
        "earn": "reward",
        "advanced trade buy": "buy",
        "advanced trade sell": "sell",
        "deposit": "receive",
        "withdrawal": "send",
    }
    return mapping.get(raw, raw.replace(" ", "_"))


def _parse_date(text: str) -> int:
    """Best-effort parse of a date string → UNIX timestamp."""
    for fmt in (
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%m/%d/%y",
    ):
        try:
            return int(datetime.strptime(text.strip(), fmt).timestamp())
        except ValueError:
            continue
    return 0


def _extract_amount_asset(text: str) -> tuple[float, str]:
    """Parse strings like '0.012 BTC' or '$125.30'."""
    text = text.strip()
    m = re.match(r"([0-9.,]+)\s+([A-Za-z]+)", text)
    if m:
        return float(m.group(1).replace(",", "")), m.group(2).upper()
    m = re.match(r"\$?([0-9.,]+)", text)
    if m:
        return float(m.group(1).replace(",", "")), "USD"
    return 0.0, "UNKNOWN"


def parse_coinbase_pdf(pdf_path: str) -> list[dict]:
    """Parse a Coinbase PDF statement and return normalised rows."""
    rows: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                # Try to locate a header row
                header_row = None
                for i, row in enumerate(table):
                    cells = [c.strip().lower() if c else "" for c in row]
                    if "date" in cells and ("type" in cells or "transaction" in cells):
                        header_row = i
                        break

                if header_row is None:
                    continue

                headers = [
                    c.strip().lower() if c else "" for c in table[header_row]
                ]

                for row in table[header_row + 1:]:
                    if not row or all(not c for c in row):
                        continue
                    cell = dict(zip(headers, [c if c else "" for c in row]))

                    date_str = cell.get("date", cell.get("timestamp", ""))
                    tx_type_raw = cell.get("type", cell.get("transaction", ""))
                    amount_str = cell.get("amount", cell.get("quantity", ""))
                    asset_str = cell.get("asset", cell.get("currency", ""))
                    usd_str = cell.get("total", cell.get("usd", cell.get("subtotal", "")))
                    fee_str = cell.get("fee", cell.get("fees", ""))

                    amount, asset_parsed = _extract_amount_asset(amount_str)
                    asset = asset_str.strip().upper() if asset_str.strip() else asset_parsed

                    fee_val = 0.0
                    if fee_str:
                        fee_val, _ = _extract_amount_asset(fee_str)

                    usd_val = ""
                    if usd_str:
                        try:
                            usd_val = float(usd_str.replace("$", "").replace(",", ""))
                        except ValueError:
                            pass

                    rows.append({
                        "date": _parse_date(date_str),
                        "chain": "",
                        "tx_hash": "",
                        "from": "coinbase" if _normalise_type(tx_type_raw) in ("sell", "send") else "",
                        "to": "coinbase" if _normalise_type(tx_type_raw) in ("buy", "receive", "reward") else "",
                        "asset": asset,
                        "amount": amount,
                        "fee": fee_val,
                        "fee_asset": "USD",
                        "type": _normalise_type(tx_type_raw),
                        "usd_value": usd_val,
                        "usd_fee": fee_val if fee_val else "",
                        "source": f"coinbase_pdf:{os.path.basename(pdf_path)}",
                    })

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
