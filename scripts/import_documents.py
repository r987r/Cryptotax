#!/usr/bin/env python3
"""
Import documents (PDFs, CSVs) from the ``input/`` folder into ``data/``.

Usage
-----
  python scripts/import_documents.py              # process all files in input/
  python scripts/import_documents.py path/to/file # process a single file
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import INPUT_DIR


def _slug(path: str) -> str:
    """Create a filesystem-safe slug from a filename."""
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace(" ", "_").replace("/", "_")[:60]


def _process_file(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    slug = _slug(path)

    if ext == ".pdf":
        # Decide: Coinbase or generic tax-form
        name_lower = os.path.basename(path).lower()
        if "coinbase" in name_lower:
            from importers.coinbase_pdf import parse_coinbase_pdf, save_to_csv

            rows = parse_coinbase_pdf(path)
            out = save_to_csv(rows, f"coinbase_{slug}.csv")
        else:
            from importers.tax_form import parse_tax_form_pdf, save_to_csv

            rows = parse_tax_form_pdf(path)
            out = save_to_csv(rows, f"taxform_{slug}.csv")
        print(f"  PDF → {len(rows)} rows → {out}")

    elif ext == ".csv":
        from importers.custom_csv import import_custom_csv, save_to_csv

        rows = import_custom_csv(path)
        out = save_to_csv(rows, f"custom_{slug}.csv")
        print(f"  CSV → {len(rows)} rows → {out}")

    else:
        print(f"  ⚠ Skipping unsupported file type: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import documents into data/.")
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a single file to import.  If omitted, all files in input/ are processed.",
    )
    args = parser.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = sorted(
            glob.glob(os.path.join(INPUT_DIR, "*"))
        )
        # Filter out hidden files / .gitkeep
        files = [f for f in files if not os.path.basename(f).startswith(".")]

    if not files:
        print("No files found to import.")
        return

    for f in files:
        print(f"Processing: {f}")
        _process_file(f)

    print("Done.")


if __name__ == "__main__":
    main()
