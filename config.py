"""
Configuration for Cryptotax.

API keys should be set via environment variables or a .env file.
Free-tier endpoints are used by default where possible.
"""

import os

# ── Blockchain API keys ──────────────────────────────────────────────────────
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY", "")
ARBISCAN_API_KEY = os.getenv("ARBISCAN_API_KEY", "")
OPTIMISM_API_KEY = os.getenv("OPTIMISM_API_KEY", "")
BASESCAN_API_KEY = os.getenv("BASESCAN_API_KEY", "")
BLOCKCYPHER_TOKEN = os.getenv("BLOCKCYPHER_TOKEN", "")
ALGORAND_API_KEY = os.getenv("ALGORAND_API_KEY", "")

# ── EVM chain explorers (Etherscan-compatible APIs) ──────────────────────────
EVM_CHAINS = {
    "ethereum": {
        "api_url": "https://api.etherscan.io/api",
        "api_key": ETHERSCAN_API_KEY,
        "native_symbol": "ETH",
        "coingecko_id": "ethereum",
    },
    "polygon": {
        "api_url": "https://api.polygonscan.com/api",
        "api_key": POLYGONSCAN_API_KEY,
        "native_symbol": "MATIC",
        "coingecko_id": "matic-network",
    },
    "arbitrum": {
        "api_url": "https://api.arbiscan.io/api",
        "api_key": ARBISCAN_API_KEY,
        "native_symbol": "ETH",
        "coingecko_id": "ethereum",
    },
    "optimism": {
        "api_url": "https://api-optimistic.etherscan.io/api",
        "api_key": OPTIMISM_API_KEY,
        "native_symbol": "ETH",
        "coingecko_id": "ethereum",
    },
    "base": {
        "api_url": "https://api.basescan.org/api",
        "api_key": BASESCAN_API_KEY,
        "native_symbol": "ETH",
        "coingecko_id": "ethereum",
    },
}

# ── Bitcoin ───────────────────────────────────────────────────────────────────
BLOCKCYPHER_API_URL = "https://api.blockcypher.com/v1/btc/main"

# ── Algorand ──────────────────────────────────────────────────────────────────
ALGORAND_INDEXER_URL = os.getenv(
    "ALGORAND_INDEXER_URL",
    "https://mainnet-idx.algonode.cloud",
)

# ── Price API (CoinGecko free tier) ──────────────────────────────────────────
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
FINAL_DIR = os.path.join(os.path.dirname(__file__), "final")
INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
