import logging

from connectors.binance_exchange import BinanceExchangeClient
from connectors.crypto_exchange import CryptoExchangeClient

from interface.root_component import Root


logger = logging.getLogger()

logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s :: %(message)s")
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("info.log")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)


if __name__ == "__main__":
    binance = BinanceExchangeClient()
    
    # Create Crypto.com client without testnet
    crypto = CryptoExchangeClient()

    root = Root(binance, crypto)
    root.mainloop()