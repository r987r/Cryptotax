#!/usr/bin/env python3
"""
Copilot review helper.

Reads ``final/rpt.csv``, performs automated sanity checks, and writes
``final/copilot_rpt.csv`` with review annotations.

In the intended workflow a human or an AI copilot reviews the annotations,
adjusts rows as needed, and saves the result back as the authoritative
``final/copilot_rpt.csv``.

Checks performed
----------------
* Missing USD values
* Suspiciously large transactions
* Duplicate transaction hashes (across chains is OK, within a chain is not)
* Date gaps > 90 days between consecutive transactions
* Unlinked sends/receives

Usage
-----
  python scripts/copilot_review.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from config import FINAL_DIR

INPUT_FILE = os.path.join(FINAL_DIR, "rpt.csv")
OUTPUT_FILE = os.path.join(FINAL_DIR, "copilot_rpt.csv")

# Thresholds
LARGE_USD_THRESHOLD = 100_000
DATE_GAP_SECONDS = 90 * 86400  # 90 days


def _review(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["review_flags"] = ""

    flags: list[list[str]] = [[] for _ in range(len(df))]

    # 1. Missing USD values
    for i, row in df.iterrows():
        val = row.get("usd_value")
        if val is None or val == "" or pd.isna(val):
            flags[i].append("missing_usd_value")

    # 2. Large transactions
    usd = pd.to_numeric(df["usd_value"], errors="coerce")
    for i in usd[usd > LARGE_USD_THRESHOLD].index:
        flags[i].append(f"large_tx(>${LARGE_USD_THRESHOLD:,})")

    # 3. Duplicate tx_hash within same chain
    dupes = df[df["tx_hash"] != ""].duplicated(subset=["chain", "tx_hash"], keep=False)
    for i in dupes[dupes].index:
        flags[i].append("duplicate_tx_hash")

    # 4. Date gaps
    dates = pd.to_numeric(df["date"], errors="coerce")
    for i in range(1, len(dates)):
        if dates.iloc[i] and dates.iloc[i - 1]:
            gap = dates.iloc[i] - dates.iloc[i - 1]
            if gap > DATE_GAP_SECONDS:
                flags[i].append(f"date_gap({int(gap / 86400)}d)")

    # 5. Unlinked notes from consolidation
    if "link_note" in df.columns:
        for i, note in df["link_note"].items():
            if note and str(note).strip():
                flags[i].append(f"unlinked:{note}")

    df["review_flags"] = ["; ".join(f) for f in flags]

    return df


def main() -> None:
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run consolidate.py first.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Reading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE)
    print(f"  {len(df)} rows loaded.")

    print("Running automated review checks ...")
    df = _review(df)

    flagged = (df["review_flags"] != "").sum()
    print(f"  {flagged} row(s) flagged for review.")

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✓ Copilot review report written → {OUTPUT_FILE}")
    print()
    print("Next steps:")
    print("  1. Open final/copilot_rpt.csv and review flagged rows.")
    print("  2. Correct any issues, then save the file.")
    print("  3. Run  python scripts/generate_tax_forms.py  to produce tax forms.")


if __name__ == "__main__":
    main()
