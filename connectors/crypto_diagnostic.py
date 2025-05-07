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

# Import client and secrets
from connectors.crypto_exchange import CryptoExchangeClient
from secret_keys import Secrets

# Configure logger
logger = logging.getLogger("crypto_diagnostic")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Default instrument for fallback
TEST_INSTRUMENT = "BTC_USDT"

# Track test results
test_results = []  # list of (name, passed: bool, message)


class LogCaptureHandler(logging.Handler):
    """Handler to capture WARNING+ logs during a test."""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        if record.levelno >= logging.WARNING:
            self.records.append(record)


def run_test(name: str, func, ignore_warnings: bool = False):
    """Run a test, optionally ignoring warnings/errors captured."""
    logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}===== Test: {name} ====={Style.RESET_ALL}")
    handler = None
    root_logger = logging.getLogger()
    if not ignore_warnings:
        handler = LogCaptureHandler()
        root_logger.addHandler(handler)

    passed = True
    msg = ""
    result = None
    try:
        result = func()
        if isinstance(result, tuple) and len(result) == 2 and result[0] is False:
            passed = False
            msg = result[1]
    except Exception as e:
        passed = False
        msg = str(e)
        logger.debug(traceback.format_exc())
    finally:
        if handler:
            root_logger.removeHandler(handler)

    if handler and handler.records:
        passed = False
        log_msgs = "; ".join(f"{rec.levelname}: {rec.getMessage()}" for rec in handler.records)
        msg = f"{msg + '; ' if msg else ''}{log_msgs}"

    if passed:
        logger.info(f"✅ {name} passed.")
        test_results.append((name, True, ""))
        return result
    else:
        logger.error(f"❌ {name} failed: {msg}")
        test_results.append((name, False, msg))
        return None


def assert_non_empty(name, data):
    if not data:
        return False, f"{name} returned no data"
    return True, ""


def test_sequence(client, label):
    # Fetch instruments
    def fetch_and_check_instruments():
        inst = client.get_instruments()
        ok, m = assert_non_empty(f"Fetch instruments ({label})", inst)
        return (inst if ok else None) or (False, m)
    instruments = run_test(f"Fetch instruments ({label})", fetch_and_check_instruments)

    # Determine instrument symbol
    selected = TEST_INSTRUMENT
    if instruments and isinstance(instruments, list):
        first = instruments[0]
        selected = first.get("symbol") if isinstance(first, dict) and "symbol" in first else TEST_INSTRUMENT

    # Account summary
    def check_account_summary():
        summary = client.get_account_summary()
        ok, m = assert_non_empty(f"Account summary ({label})", summary)
        return (summary if ok else None) or (False, m)
    run_test(f"Account summary ({label})", check_account_summary)

    # Order book
    def check_order_book():
        ob = client.get_order_book(selected)
        ok, m = assert_non_empty(f"Order book for {selected} ({label})", ob.get("bids") or ob.get("asks"))
        return (ob if ok else None) or (False, m)
    run_test(f"Order book ({label})", check_order_book)

    # Recent trades
    def check_recent_trades():
        trades = client.get_trades(selected)
        ok, m = assert_non_empty(f"Recent trades for {selected} ({label})", trades)
        return (trades if ok else None) or (False, m)
    run_test(f"Recent trades ({label})", check_recent_trades)


def main():
    # Check environment variables
    missing = [var for var in ("CRYPTO_API_KEY", "CRYPTO_API_SECRET") if not getattr(Secrets, var)]
    if missing:
        logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
        test_results.append(("Environment variables", False, ", ".join(missing)))
    else:
        logger.info("✅ All Crypto API environment variables are set.")
        test_results.append(("Environment variables", True, ""))

    # Test live (prod) and sandbox (testnet)
    for mode, ignore in [("PROD", False), ("TESTNET", True)]:
        label = mode.lower()
        client = run_test(
            f"Initialize crypto client ({mode})",
            lambda: CryptoExchangeClient(testnet=(mode == "TESTNET")),
            ignore_warnings=ignore
        )
        if client:
            test_sequence(client, label)

    # Summary
    total = len(test_results)
    passed = [n for n, ok, _ in test_results if ok]
    failed = [(n, m) for n, ok, m in test_results if not ok]

    logger.info(f"\n{Fore.GREEN}{Style.BRIGHT}Diagnostics run: {total} tests. Passed: {len(passed)}. Failed: {len(failed)}{Style.RESET_ALL}")
    if failed:
        logger.error(f"{Fore.RED}Failures:{Style.RESET_ALL}")
        for name, m in failed:
            logger.error(f" - {name}: {m}")
        sys.exit(1)


if __name__ == "__main__":
    main()
