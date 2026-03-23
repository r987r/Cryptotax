# Cryptotax

Open-source crypto tax toolkit.  Parse on-chain transactions, import exchange
documents, consolidate everything, and generate IRS tax forms — all from the
command line.

## Quick Start

```bash
pip install -r requirements.txt
```

Set API keys (optional — free-tier endpoints work without keys for low volume):

```bash
export ETHERSCAN_API_KEY="..."
export POLYGONSCAN_API_KEY="..."
export ARBISCAN_API_KEY="..."
export BLOCKCYPHER_TOKEN="..."
```

## Workflow

### 1. Parse blockchain addresses → `data/`

```bash
# Ethereum & EVM chains (polygon, arbitrum, optimism, base)
python scripts/parse_address.py ethereum  0xYourAddress
python scripts/parse_address.py polygon   0xYourAddress
python scripts/parse_address.py arbitrum  0xYourAddress

# Bitcoin
python scripts/parse_address.py bitcoin   1YourBitcoinAddress

# Algorand
python scripts/parse_address.py algorand  YourAlgorandAddress
```

Each command fetches the full transaction history, classifies each transaction
(send, receive, swap, stake, etc.), looks up historical USD prices, and saves a
CSV to `data/`.

### 2. Import documents → `data/`

Place PDFs (Coinbase statements, 1099 forms) and custom CSVs in `input/`, then:

```bash
python scripts/import_documents.py          # process everything in input/
python scripts/import_documents.py file.csv  # or a single file
```

Supported formats:
- **Coinbase PDF** statements (auto-detected by filename containing "coinbase")
- **Tax-form PDFs** (1099-B, 1099-MISC, etc.)
- **Custom CSVs** — column names are auto-mapped from common aliases

### 3. Consolidate → `final/rpt.csv`

```bash
python scripts/consolidate.py
```

Merges every CSV in `data/` into one sorted report.  The script attempts to
link related transactions (e.g. a send on Ethereum matched with a receive on
Polygon within a 1-hour window).  Rows it cannot link are flagged with a
`link_note`.

### 4. Copilot review → `final/copilot_rpt.csv`

```bash
python scripts/copilot_review.py
```

Adds a `review_flags` column highlighting:
- Missing USD values
- Large transactions (>$100k)
- Duplicate tx hashes
- Date gaps >90 days
- Unlinked sends/receives

Review and correct any flagged rows, then save.

### 5. Generate tax forms (2026)

```bash
python scripts/generate_tax_forms.py --year 2026
```

Produces:
- `final/form_8949.csv` — one row per disposal, matching IRS Form 8949
- `final/schedule_d_summary.csv` — short-term vs long-term totals

Cost basis is calculated using **FIFO** (First-In, First-Out) across all
acquisitions.

## Project Structure

```
├── config.py                  # API keys, chain configs, paths
├── parsers/
│   ├── ethereum.py            # ETH + EVM chains (Polygon, Arbitrum, …)
│   ├── bitcoin.py             # Bitcoin via BlockCypher
│   ├── algorand.py            # Algorand via Indexer
│   └── price.py               # CoinGecko USD price lookups
├── importers/
│   ├── coinbase_pdf.py        # Coinbase PDF statement parser
│   ├── tax_form.py            # Generic tax-form PDF parser
│   └── custom_csv.py          # Custom CSV importer
├── scripts/
│   ├── parse_address.py       # CLI: parse a blockchain address
│   ├── import_documents.py    # CLI: import PDFs & CSVs
│   ├── consolidate.py         # CLI: merge → final/rpt.csv
│   ├── copilot_review.py      # CLI: review → final/copilot_rpt.csv
│   └── generate_tax_forms.py  # CLI: produce Form 8949 & Schedule D
├── data/                      # Parsed CSVs (per-source)
├── final/                     # Consolidated & tax reports
├── input/                     # Drop PDFs & CSVs here
└── tests/
    ├── test_parsers.py
    ├── test_importers.py
    └── test_consolidate.py
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```
