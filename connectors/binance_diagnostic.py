"""
Binance Client Diagnostic Script
--------------------------------
Tests the BinanceClient to verify connectivity and data retrieval.

Usage:
    Run from project root:
    python diagnostic/binance_diagnostic.py
"""

import sys
import traceback
from pathlib import Path
from colorama import init, Fore, Style
import logging

# Initialize colorama
init(autoreset=True)

# Add project root to Python path
project_root = Path(__file__).parent.parent  # adjust if needed
sys.path.insert(0, str(project_root))

from connectors.binance_exchange import BinanceClient

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Test symbol (ensure this exists in Binance.US markets)
TEST_SYMBOL = "BTCUSDT"


def print_test_header(name: str):
    logger.info(f"\n{Fore.CYAN}Test: {name}{Style.RESET_ALL}")


def main():
    logger.info(f"Added {project_root} to PYTHONPATH")
    logger.info("Initializing BinanceClient...")

    try:
        client = BinanceClient()
        logger.info("✅ BinanceClient instantiated successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize BinanceClient: {e}")
        logger.debug(traceback.format_exc())
        return

    # Test: get_contracts
    print_test_header("Fetching available contracts")
    try:
        contracts = client.get_contracts()
        logger.info(f"✅ Retrieved {len(contracts)} contracts")
    except Exception as e:
        logger.error(f"❌ Error fetching contracts: {e}")
        logger.debug(traceback.format_exc())

    # Test: get_balances
    print_test_header("Retrieving account balances")
    try:
        balances = client.get_balances()
        logger.info(f"✅ Retrieved {len(balances)} balances")
        for asset, bal in balances.items():
            logger.info(f"  {asset}: free={bal.free}, locked={bal.locked}")
    except Exception as e:
        logger.error(f"❌ Error retrieving balances: {e}")
        logger.debug(traceback.format_exc())

    # Test: get_bid_ask
    print_test_header(f"Getting bid/ask for {TEST_SYMBOL}")
    try:
        contract = contracts.get(TEST_SYMBOL)
        if not contract:
            logger.error(f"❌ Symbol {TEST_SYMBOL} not found in contracts")
        else:
            bidask = client.get_bid_ask(contract)
            if bidask:
                logger.info(f"✅ Bid: {bidask['bid']}, Ask: {bidask['ask']}")
            else:
                logger.error("❌ No bid/ask data returned")
    except Exception as e:
        logger.error(f"❌ Error getting bid/ask: {e}")
        logger.debug(traceback.format_exc())

    # Test: get_historical_candles
    print_test_header(f"Fetching historical candles for {TEST_SYMBOL} (1h interval)")
    try:
        candle_list = client.get_historical_candles(contract, "1h")
        logger.info(f"✅ Retrieved {len(candle_list)} candles")
    except Exception as e:
        logger.error(f"❌ Error fetching candles: {e}")
        logger.debug(traceback.format_exc())

    logger.info("\nDiagnostic completed.")


if __name__ == "__main__":
    main()
