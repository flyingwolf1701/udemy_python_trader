import logging

from connectors.binance_exchange import BinanceExchangeClient
from connectors.crypto_exchange import CryptoExchangeClient

from interface.root_component import Root


logger = logging.getLogger()

logger.setLevel(logging.DEBUG)  # Overall minimum logging level

stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s :: %(message)s")
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)  # Terminal shows INFO and above

file_handler = logging.FileHandler("info.log")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)  # File captures DEBUG and above

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


if __name__ == "__main__":
    # Initialize Binance.US client
    binance = BinanceExchangeClient()
    logger.info("Binance.US client initialized")
    
    # Initialize Crypto.com client (no testnet)
    crypto = CryptoExchangeClient()
    logger.info("Crypto.com client initialized")

    # Start the application
    root = Root(binance, crypto)
    root.mainloop()