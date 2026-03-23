#!/usr/bin/env python3
"""
Parse blockchain address transactions and save to data/.

Usage
-----
  python scripts/parse_address.py <chain> <address>

Examples
--------
  python scripts/parse_address.py ethereum 0xABC...
  python scripts/parse_address.py polygon  0xABC...
  python scripts/parse_address.py bitcoin  1A1zP1...
  python scripts/parse_address.py algorand ALGO...

Supported chains: ethereum, polygon, arbitrum, optimism, base, bitcoin, algorand
"""

from __future__ import annotations

import argparse
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EVM_CHAINS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse blockchain transactions for an address."
    )
    all_chains = list(EVM_CHAINS) + ["bitcoin", "algorand"]
    parser.add_argument(
        "chain",
        choices=all_chains,
        help="Blockchain to query.",
    )
    parser.add_argument("address", help="Wallet address to parse.")
    args = parser.parse_args()

    chain: str = args.chain
    address: str = args.address
    safe_addr = address[:8] + "..." + address[-4:] if len(address) > 14 else address
    filename = f"{chain}_{safe_addr}.csv"

    print(f"Fetching {chain} transactions for {address} ...")

    if chain in EVM_CHAINS:
        from parsers.ethereum import fetch_evm_transactions, save_to_csv

        rows = fetch_evm_transactions(address, chain=chain)
        path = save_to_csv(rows, filename)
    elif chain == "bitcoin":
        from parsers.bitcoin import fetch_bitcoin_transactions, save_to_csv

        rows = fetch_bitcoin_transactions(address)
        path = save_to_csv(rows, filename)
    elif chain == "algorand":
        from parsers.algorand import fetch_algorand_transactions, save_to_csv

        rows = fetch_algorand_transactions(address)
        path = save_to_csv(rows, filename)
    else:
        print(f"Chain '{chain}' is not yet supported.", file=sys.stderr)
        sys.exit(1)

    print(f"✓ {len(rows)} transactions saved → {path}")


if __name__ == "__main__":
    main()
