#!/usr/bin/env python3
"""
Generate US tax forms (Form 8949, Schedule D summary) from the reviewed
``final/copilot_rpt.csv``.

This script produces:
* ``final/form_8949.csv``  – one row per disposal (sell / swap / send of
  appreciated asset).  Columns match IRS Form 8949 Part I & II.
* ``final/schedule_d_summary.csv`` – short-term vs long-term totals.

Assumptions
-----------
* Tax year = 2026 (configurable via ``--year``).
* A "disposal" is any row whose type is sell, swap, send, or token_send.
* Cost basis is looked up by matching earlier acquisitions of the same asset
  using FIFO (First-In, First-Out).
* If cost basis cannot be determined the row is flagged.

Usage
-----
  python scripts/generate_tax_forms.py
  python scripts/generate_tax_forms.py --year 2026
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from config import FINAL_DIR

INPUT_FILE = os.path.join(FINAL_DIR, "copilot_rpt.csv")
FORM_8949_FILE = os.path.join(FINAL_DIR, "form_8949.csv")
SCHEDULE_D_FILE = os.path.join(FINAL_DIR, "schedule_d_summary.csv")

DISPOSAL_TYPES = {"sell", "swap", "send", "token_send"}
ACQUISITION_TYPES = {"buy", "receive", "token_receive", "reward", "staking_reward", "mint", "claim"}

SECONDS_PER_YEAR = 365.25 * 86400


# ── FIFO lot tracking ────────────────────────────────────────────────────────

class FIFOTracker:
    """Track cost-basis lots per asset using FIFO."""

    def __init__(self) -> None:
        # asset → list of (date, remaining_amount, cost_per_unit)
        self.lots: dict[str, list[list]] = {}

    def acquire(self, asset: str, date: int, amount: float, usd_value: float) -> None:
        if amount <= 0:
            return
        cpu = usd_value / amount if amount else 0.0
        self.lots.setdefault(asset, []).append([date, amount, cpu])

    def dispose(self, asset: str, amount: float) -> tuple[float, int | None]:
        """Remove *amount* from the oldest lots.

        Returns (total_cost_basis, acquisition_date_of_first_lot_used).
        """
        lots = self.lots.get(asset, [])
        remaining = amount
        total_cost = 0.0
        first_date: int | None = None

        while remaining > 1e-12 and lots:
            lot = lots[0]
            if first_date is None:
                first_date = lot[0]
            if lot[1] <= remaining:
                total_cost += lot[1] * lot[2]
                remaining -= lot[1]
                lots.pop(0)
            else:
                total_cost += remaining * lot[2]
                lot[1] -= remaining
                remaining = 0

        return total_cost, first_date


def _ts_to_date(ts: int) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%m/%d/%Y")


def _is_long_term(acquire_ts: int, dispose_ts: int) -> bool:
    return (dispose_ts - acquire_ts) > SECONDS_PER_YEAR


# ── Main logic ───────────────────────────────────────────────────────────────

def generate(year: int) -> None:
    if not os.path.exists(INPUT_FILE):
        print(
            f"Error: {INPUT_FILE} not found. Run copilot_review.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading {INPUT_FILE} ...")
    df = pd.read_csv(INPUT_FILE)
    df["date"] = pd.to_numeric(df["date"], errors="coerce").fillna(0).astype(int)
    df.sort_values("date", inplace=True)

    year_start = int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())
    year_end = int(datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())

    tracker = FIFOTracker()

    # Pass 1: build lots from all acquisitions (including prior years for basis)
    for _, row in df.iterrows():
        rtype = str(row.get("type", "")).lower()
        if rtype in ACQUISITION_TYPES:
            usd = row.get("usd_value", 0)
            try:
                usd = float(usd)
            except (ValueError, TypeError):
                usd = 0.0
            tracker.acquire(
                str(row.get("asset", "UNKNOWN")),
                int(row["date"]),
                float(row.get("amount", 0)),
                usd,
            )

    # Pass 2: process disposals in the target tax year
    form_rows: list[dict] = []

    for _, row in df.iterrows():
        rtype = str(row.get("type", "")).lower()
        if rtype not in DISPOSAL_TYPES:
            continue
        ts = int(row["date"])
        if ts < year_start or ts > year_end:
            # Still need to remove from lots to keep FIFO accurate
            if rtype in DISPOSAL_TYPES:
                tracker.dispose(str(row.get("asset", "")), float(row.get("amount", 0)))
            continue

        asset = str(row.get("asset", "UNKNOWN"))
        amount = float(row.get("amount", 0))
        proceeds_usd = row.get("usd_value", 0)
        try:
            proceeds_usd = float(proceeds_usd)
        except (ValueError, TypeError):
            proceeds_usd = 0.0

        cost_basis, acq_date = tracker.dispose(asset, amount)
        gain = proceeds_usd - cost_basis
        term = "long" if (acq_date and _is_long_term(acq_date, ts)) else "short"
        note = ""
        if acq_date is None:
            note = "cost_basis_unknown"

        form_rows.append({
            "description": f"{amount} {asset}",
            "date_acquired": _ts_to_date(acq_date) if acq_date else "VARIOUS",
            "date_sold": _ts_to_date(ts),
            "proceeds": round(proceeds_usd, 2),
            "cost_basis": round(cost_basis, 2),
            "gain_or_loss": round(gain, 2),
            "term": term,
            "tx_hash": row.get("tx_hash", ""),
            "chain": row.get("chain", ""),
            "note": note,
        })

    if not form_rows:
        print("No disposals found in the target tax year.  Nothing to generate.")
        return

    form_df = pd.DataFrame(form_rows)

    # ── Form 8949 ────────────────────────────────────────────────────────
    form_df.to_csv(FORM_8949_FILE, index=False)
    print(f"✓ Form 8949 → {FORM_8949_FILE}  ({len(form_df)} rows)")

    # ── Schedule D summary ───────────────────────────────────────────────
    summary_rows = []
    for term in ("short", "long"):
        subset = form_df[form_df["term"] == term]
        summary_rows.append({
            "term": term,
            "total_proceeds": round(subset["proceeds"].sum(), 2),
            "total_cost_basis": round(subset["cost_basis"].sum(), 2),
            "total_gain_or_loss": round(subset["gain_or_loss"].sum(), 2),
            "num_transactions": len(subset),
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(SCHEDULE_D_FILE, index=False)
    print(f"✓ Schedule D summary → {SCHEDULE_D_FILE}")

    print()
    print("=== Schedule D Summary ===")
    for _, r in summary_df.iterrows():
        print(
            f"  {r['term'].upper()}-TERM: "
            f"Proceeds ${r['total_proceeds']:,.2f}  "
            f"Basis ${r['total_cost_basis']:,.2f}  "
            f"Gain/Loss ${r['total_gain_or_loss']:,.2f}  "
            f"({r['num_transactions']} txns)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tax forms from reviewed data.")
    parser.add_argument("--year", type=int, default=2026, help="Tax year (default: 2026)")
    args = parser.parse_args()
    generate(args.year)


if __name__ == "__main__":
    main()
