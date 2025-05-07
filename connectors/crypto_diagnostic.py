import sys
import traceback
from pathlib import Path
import logging
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from connectors.crypto_exchange import CryptoExchangeClient
except ImportError:
    logging.error("Failed to import CryptoExchangeClient. Ensure it's in the Python path and no circular imports.")
    sys.exit(1)

# Configure logger
logger = logging.getLogger("crypto_diagnostic")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Default instrument for fallback
TEST_INSTRUMENT = "BTC_USDT"

# Counters for diagnostics
diagnostics = {"passed": 0, "failed": 0}


def run_test(name: str, func):
    logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}===== Test: {name} ====={Style.RESET_ALL}")
    try:
        result = func()
        logger.info(f"✅ {name} passed.")
        diagnostics["passed"] += 1
        return result
    except Exception as e:
        logger.error(f"❌ {name} failed: {e}")
        logger.debug(traceback.format_exc())
        diagnostics["failed"] += 1
        return None


def main():
    # Initialize client
    client = run_test("Initialize crypto client", lambda: CryptoExchangeClient())

    # Fetch instruments
    instruments = run_test("Fetch instruments", client.get_instruments if client else lambda: [])
    selected = TEST_INSTRUMENT
    if instruments:
        selected = instruments[0]["symbol"] if isinstance(instruments[0], dict) and "symbol" in instruments[0] else instruments[0]

    # Account summary (private)
    run_test("Account summary", lambda: client.get_account_summary())

    # Order book
    run_test(
        f"Order book for {selected}",
        lambda: client.get_order_book(selected)
    )

    # Recent trades
    run_test(
        f"Recent trades for {selected}",
        lambda: client.get_trades(selected)
    )

    # Summary
    logger.info(f"\n{Fore.GREEN}{Style.BRIGHT}Diagnostics completed. Passed={diagnostics['passed']} Failed={diagnostics['failed']}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
