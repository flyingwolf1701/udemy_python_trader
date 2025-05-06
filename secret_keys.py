"""
Secrets configuration module for the CryptoTrader application.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Secrets:
    """Secrets settings for the CryptoTrader application."""
       
    # Binance API settings
    BINANCE_API_KEY = os.environ.get('BINANCE_API_KEY')
    BINANCE_API_SECRET = os.environ.get('BINANCE_API_SECRET')

    # Crypto Exchange API settings
    CRYPTO_API_KEY = os.environ.get('CRYPTO_API_KEY')
    CRYPTO_API_SECRET = os.environ.get('CRYPTO_API_SECRET')
