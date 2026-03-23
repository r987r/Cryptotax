"""
Tax-form PDF importer (1099-MISC, 1099-B, etc.).

Attempts to extract transaction data from common crypto tax-form PDFs.
Because PDF layouts vary wildly, this module uses a best-effort heuristic
approach and falls back to raw text extraction when table parsing fails.
"""

from __future__ import annotations

import csv
import os
import re
from datetime import datetime

import pdfplumber

from config import DATA_DIR

FIELDNAMES = [
    "date", "chain", "tx_hash", "from", "to", "asset", "amount",
    "fee", "fee_asset", "type", "usd_value", "usd_fee", "source",
]


def _parse_date(text: str) -> int:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%m/%d/%y"):
        try:
            return int(datetime.strptime(text.strip(), fmt).timestamp())
        except ValueError:
            continue
    return 0


def _extract_dollar(text: str) -> float:
    m = re.search(r"\$?([\d,]+\.?\d*)", text)
    if m:
        return float(m.group(1).replace(",", ""))
    return 0.0


def parse_tax_form_pdf(pdf_path: str) -> list[dict]:
    """Extract transaction-like rows from a crypto tax-form PDF."""
    rows: list[dict] = []
    basename = os.path.basename(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Strategy 1: Try tables
            for table in page.extract_tables() or []:
                if not table or len(table) < 2:
                    continue

                headers = [
                    (c or "").strip().lower() for c in table[0]
                ]

                for row in table[1:]:
                    if not row or all(not c for c in row):
                        continue
                    cell = dict(zip(headers, [c if c else "" for c in row]))

                    date_str = ""
                    for k in ("date acquired", "date sold", "date", "transaction date"):
                        if k in cell and cell[k]:
                            date_str = cell[k]
                            break

                    proceeds_str = cell.get("proceeds", cell.get("amount", ""))
                    cost_str = cell.get("cost basis", cell.get("cost", ""))
                    desc = cell.get("description", cell.get("asset", ""))

                    proceeds = _extract_dollar(proceeds_str) if proceeds_str else 0.0
                    cost = _extract_dollar(cost_str) if cost_str else 0.0

                    asset_match = re.search(r"([A-Z]{2,10})", desc.upper()) if desc else None
                    asset = asset_match.group(1) if asset_match else "UNKNOWN"

                    rows.append({
                        "date": _parse_date(date_str),
                        "chain": "",
                        "tx_hash": "",
                        "from": "",
                        "to": "",
                        "asset": asset,
                        "amount": proceeds or cost,
                        "fee": 0.0,
                        "fee_asset": "USD",
                        "type": "tax_form_entry",
                        "usd_value": proceeds if proceeds else cost,
                        "usd_fee": "",
                        "source": f"tax_form:{basename}",
                    })

            # Strategy 2: Fallback text extraction for 1099-MISC
            text = page.extract_text() or ""
            if "1099" in text and not rows:
                amounts = re.findall(r"\$\s*([\d,]+\.?\d*)", text)
                for amt_str in amounts:
                    val = float(amt_str.replace(",", ""))
                    if val > 0:
                        rows.append({
                            "date": 0,
                            "chain": "",
                            "tx_hash": "",
                            "from": "",
                            "to": "",
                            "asset": "UNKNOWN",
                            "amount": val,
                            "fee": 0.0,
                            "fee_asset": "USD",
                            "type": "1099_entry",
                            "usd_value": val,
                            "usd_fee": "",
                            "source": f"tax_form:{basename}",
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
