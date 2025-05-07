import sys
import traceback
from pathlib import Path
import logging
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent # Use resolve() for robustness
sys.path.insert(0, str(project_root))

try:
    from connectors.crypto_exchange import CryptoExchangeClient
except ImportError:
    logging.error("Failed to import CryptoExchangeClient. Ensure it's in the Python path and no circular imports.")
    sys.exit(1)


# Configure logger for the diagnostic script itself
# The client will use its own logger configured via basicConfig in its __main__ or here
logger = logging.getLogger("crypto_diagnostic") # Give it a specific name
logging.basicConfig(
    level=logging.DEBUG, # Ensure DEBUG level is set for all loggers
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    # force=True # Can be useful if other modules already configured logging
)


# Test instrument (adjust if needed, or will be picked from get_instruments)
TEST_INSTRUMENT = "BTC_USDT"
fetched_instrument_for_test = None


def print_test_header(name: str):
    logger.info(f"\n{Fore.CYAN}{Style.BRIGHT}===== Test: {name} ====={Style.RESET_ALL}")


def main():
    global fetched_instrument_for_test

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
    instruments = []
    try:
        instruments = client.get_instruments()
        if instruments and isinstance(instruments, list):
            logger.info(f"✅ Retrieved {len(instruments)} instruments. First few: {instruments[:3]}")
            if instruments:
                # Prefer a common instrument if available, otherwise pick the first one
                preferred_instruments = ["BTC_USDT", "ETH_USDT", "CRO_USDT"]
                for pi in preferred_instruments:
                    if any(inst['instrument_name'] == pi for inst in instruments):
                        fetched_instrument_for_test = pi
                        break
                if not fetched_instrument_for_test:
                    fetched_instrument_for_test = instruments[0]['instrument_name']
                logger.info(f"Selected '{fetched_instrument_for_test}' for subsequent tests.")
        elif isinstance(instruments, dict) and instruments.get("method") == "public/get-instruments":
             logger.warning(f"⚠️ Retrieved a dict, looks like raw response for get_instruments. Check parsing. Data: {instruments}")
        else:
            logger.warning(f"⚠️ No instruments retrieved or unexpected format: {instruments}")
    except Exception as e:
        logger.error(f"❌ Error fetching instruments: {e}")
        logger.error(f"   Response text from error if available: {getattr(e, 'response', None) and getattr(e.response, 'text', None)}")
        logger.debug(traceback.format_exc())


    # Test: account summary (Private Call - Most likely to show auth issues)
    print_test_header("Retrieving account summary (Private Call)")
    try:
        # The get_account_summary in the client already extracts the relevant list from "result"
        summary_data_list = client.get_account_summary() # This should be a list of balance dicts
        if isinstance(summary_data_list, list):
            logger.info(f"✅ Retrieved account summary with {len(summary_data_list)} balance entries.")
            for bal_entry in summary_data_list[:5]: # Print first 5 balances
                asset = bal_entry.get('currency', bal_entry.get('coin', bal_entry.get('asset', 'N/A'))) # common keys for asset name
                total_balance = bal_entry.get('balance', 'N/A')
                available_balance = bal_entry.get('available', bal_entry.get('free', 'N/A'))
                staked_balance = bal_entry.get('staked', 'N/A')
                logger.info(f"  ➡️ {asset}: Total={total_balance}, Available={available_balance}, Staked={staked_balance}")
            if not summary_data_list:
                logger.info("✅ Account summary retrieved, but no balance entries found (list is empty).")
        else:
            logger.warning(f"⚠️ Account summary not in expected list format. Received: {type(summary_data_list)}, Data: {summary_data_list}")

    except Exception as e:
        logger.error(f"❌ Error retrieving account summary: {e}")
        logger.error(f"   Response text from error if available: {getattr(e, 'response', None) and getattr(e.response, 'text', None)}")
        logger.debug(traceback.format_exc())


    # Determine which instrument to use for book and trades
    instrument_to_use = fetched_instrument_for_test if fetched_instrument_for_test else TEST_INSTRUMENT

    if not fetched_instrument_for_test:
         logger.warning(f"⚠️ No instruments fetched successfully, falling back to default '{TEST_INSTRUMENT}' for book/trades. This might fail if the instrument is invalid.")


    # Test: get_order_book
    print_test_header(f"Fetching order book for '{instrument_to_use}'")
    try:
        # client.get_order_book directly returns a dict like {"bids": [...], "asks": [...]}
        book = client.get_order_book(instrument_to_use)
        bids = book.get('bids', [])
        asks = book.get('asks', [])
        logger.info(f"✅ Order book for '{instrument_to_use}': {len(bids)} bids, {len(asks)} asks.")
        if bids: logger.info(f"   Top bid: {bids[0]}")
        if asks: logger.info(f"   Top ask: {asks[0]}")
        if not bids and not asks:
            logger.info(f"   Order book for '{instrument_to_use}' is empty.")
    except Exception as e:
        logger.error(f"❌ Error fetching order book for '{instrument_to_use}': {e}")
        logger.error(f"   Response text from error if available: {getattr(e, 'response', None) and getattr(e.response, 'text', None)}")
        logger.debug(traceback.format_exc())

    # Test: get_trades
    print_test_header(f"Fetching recent trades for '{instrument_to_use}'")
    try:
        # client.get_trades should return a list of trade dicts
        trades = client.get_trades(instrument_to_use) # Default count is handled by client
        if isinstance(trades, list):
            logger.info(f"✅ Retrieved {len(trades)} trades for '{instrument_to_use}'.")
            if trades: logger.info(f"   Most recent trade: {trades[0]}")
        else:
            logger.warning(f"⚠️ Trades data not in expected list format for '{instrument_to_use}'. Received: {type(trades)}, Data: {trades}")
    except Exception as e:
        logger.error(f"❌ Error fetching trades for '{instrument_to_use}': {e}")
        logger.error(f"   Response text from error if available: {getattr(e, 'response', None) and getattr(e.response, 'text', None)}")
        logger.debug(traceback.format_exc())

    logger.info(f"\n{Fore.GREEN}{Style.BRIGHT}Diagnostic completed.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()