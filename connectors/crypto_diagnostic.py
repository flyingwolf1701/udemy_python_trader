"""
Crypto.com Exchange Client Diagnostic Script
--------------------------------------------
Tests the CryptoExchangeClient to verify connectivity and data retrieval.

Usage:
    From project root:
    python diagnostic/crypto_diagnostic.py
"""
import sys
import traceback
from pathlib import Path
import logging
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from connectors.crypto_exchange import CryptoExchangeClient
from secret_keys import Secrets

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Test instrument (adjust if needed)
TEST_INSTRUMENT = "BTC_USDT"


def print_test_header(name: str):
    logger.info(f"\n{Fore.CYAN}Test: {name}{Style.RESET_ALL}")


def main():

    # Instantiate client
    print_test_header("Initializing CryptoExchangeClient")
    try:
        client = CryptoExchangeClient()
        logger.info("✅ CryptoExchangeClient instantiated successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize client: {e}")
        logger.debug(traceback.format_exc())
        return

    # Test: get_instruments
    print_test_header("Fetching trading instruments")
    try:
        instruments = client.get_instruments()
        logger.info(f"✅ Retrieved {len(instruments)} instruments")
    except Exception as e:
        logger.error(f"❌ Error fetching instruments: {e}")
        logger.debug(traceback.format_exc())

    # Test: account summary
    print_test_header("Retrieving account summary")
    try:
        summary = client.get_account_summary()
        balances = summary.get("result", {}).get("data", {}).get("balances", [])
        logger.info(f"✅ Retrieved account summary with {len(balances)} balance entries")
        for bal in balances:
            asset = bal.get('instrument_name', bal.get('instrumentName', ''))
            free = bal.get('free', bal.get('available', ''))
            logger.info(f"  {asset}: available={free}")
    except Exception as e:
        logger.error(f"❌ Error retrieving account summary: {e}")
        logger.debug(traceback.format_exc())

    # Test: get_order_book
    print_test_header(f"Fetching order book for {TEST_INSTRUMENT}")
    try:
        book = client.get_order_book(TEST_INSTRUMENT)
        bids = book.get('result', {}).get('bids', [])
        asks = book.get('result', {}).get('asks', [])
        logger.info(f"✅ Order book: {len(bids)} bids, {len(asks)} asks")
    except Exception as e:
        logger.error(f"❌ Error fetching order book: {e}")
        logger.debug(traceback.format_exc())

    # Test: get_trades
    print_test_header(f"Fetching recent trades for {TEST_INSTRUMENT}")
    try:
        trades = client.get_trades(TEST_INSTRUMENT)
        logger.info(f"✅ Retrieved {len(trades)} trades")
    except Exception as e:
        logger.error(f"❌ Error fetching trades: {e}")
        logger.debug(traceback.format_exc())

    logger.info("\nDiagnostic completed.")


if __name__ == "__main__":
    main()
