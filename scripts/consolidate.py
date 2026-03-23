#!/usr/bin/env python3
"""
Consolidate all CSV files in ``data/`` into a single ``final/rpt.csv``.

The script:
1. Reads every CSV in ``data/``.
2. Merges them into one DataFrame, sorted by date.
3. Attempts to link related transactions (e.g. a send on one chain matched
   with a receive on another within a short time window).
4. Flags rows it could not link with a ``link_note`` column.
5. Writes the result to ``final/rpt.csv``.

Usage
-----
  python scripts/consolidate.py
"""

from __future__ import annotations

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from config import DATA_DIR, FINAL_DIR

# Time window (seconds) for linking send↔receive across chains/sources
LINK_WINDOW = 3600  # 1 hour


def _load_all_csvs() -> pd.DataFrame:
    """Load and concatenate every CSV in the data directory."""
    pattern = os.path.join(DATA_DIR, "*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No CSV files found in data/.  Run parse_address or import_documents first.")
        sys.exit(0)

    frames: list[pd.DataFrame] = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["_src_file"] = os.path.basename(f)
            frames.append(df)
        except Exception as exc:
            print(f"  ⚠ Could not read {f}: {exc}")
    if not frames:
        print("No valid data found.")
        sys.exit(0)

    return pd.concat(frames, ignore_index=True)


def _try_link(df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort linking of send↔receive pairs across sources."""
    df = df.copy()
    df["link_id"] = ""
    df["link_note"] = ""

    sends = df[df["type"].isin(["send", "token_send"])].copy()
    receives = df[df["type"].isin(["receive", "token_receive"])].copy()

    link_counter = 0
    used_recv_idx: set[int] = set()

    for s_idx, s_row in sends.iterrows():
        if not s_row["date"] or pd.isna(s_row["date"]):
            continue
        candidates = receives[
            (receives["asset"] == s_row["asset"])
            & (abs(receives["date"] - s_row["date"]) <= LINK_WINDOW)
            & (~receives.index.isin(used_recv_idx))
        ]
        if candidates.empty:
            df.at[s_idx, "link_note"] = "no matching receive found"
            continue

        # Pick the closest in time
        best_idx = (abs(candidates["date"] - s_row["date"])).idxmin()
        link_counter += 1
        lid = f"link_{link_counter}"
        df.at[s_idx, "link_id"] = lid
        df.at[best_idx, "link_id"] = lid
        used_recv_idx.add(best_idx)

    # Flag unlinked receives
    for r_idx in receives.index:
        if r_idx not in used_recv_idx and df.at[r_idx, "link_id"] == "":
            df.at[r_idx, "link_note"] = "no matching send found"

    return df


def consolidate() -> str:
    """Run the full consolidation pipeline and return the output path."""
    print("Loading CSV files from data/ ...")
    df = _load_all_csvs()
    print(f"  {len(df)} total rows across {df['_src_file'].nunique()} file(s).")

    # Ensure date is numeric for sorting/linking
    df["date"] = pd.to_numeric(df["date"], errors="coerce").fillna(0).astype(int)
    df.sort_values("date", inplace=True)

    print("Attempting to link related transactions ...")
    df = _try_link(df)
    linked = (df["link_id"] != "").sum()
    unlinked = (df["link_note"] != "").sum()
    print(f"  Linked pairs: {linked // 2}  |  Unlinked notes: {unlinked}")

    # Drop helper column
    df.drop(columns=["_src_file"], inplace=True)

    os.makedirs(FINAL_DIR, exist_ok=True)
    out_path = os.path.join(FINAL_DIR, "rpt.csv")
    df.to_csv(out_path, index=False)
    print(f"✓ Consolidated report written → {out_path}  ({len(df)} rows)")
    return out_path


def main() -> None:
    consolidate()


if __name__ == "__main__":
    main()
