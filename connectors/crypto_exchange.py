import time
import hmac
import hashlib
import logging
import requests
import traceback
import threading
import json
import websocket
from typing import Dict, Any, List, Union, Optional

from secret_keys import Secrets
from models import Candle, Contract, Balance, OrderStatus


logger = logging.getLogger(__name__)


class CryptoExchangeClient:
    """
    Crypto.com Exchange API v1 REST client.

    Implements a clean interface to the Crypto.com Exchange v1 API with support
    for both public and private endpoints.
    """

    # REST API URLs
    PROD_REST_URL = "https://api.crypto.com/exchange/v1"  # Production REST
    TESTNET_REST_URL = "https://uat-api.3ona.co/exchange/v1"  # UAT sandbox REST
    
    # WebSocket URLs
    PROD_WS_USER = "wss://stream.crypto.com/exchange/v1/user"  # Production WS (user)
    PROD_WS_MARKET = "wss://stream.crypto.com/exchange/v1/market"  # Production WS (market)
    TESTNET_WS_USER = "wss://uat-stream.3ona.co/exchange/v1/user"  # UAT sandbox WS (user)
    TESTNET_WS_MARKET = "wss://uat-stream.3ona.co/exchange/v1/market"  # UAT sandbox WS (market)
    
    MAX_RETRIES = 3
    MAX_LEVEL = 3  # Maximum recursion level for params encoding

    def __init__(self, testnet: bool = False, public_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize the Crypto.com Exchange client.

        Args:
            testnet: Whether to use the UAT sandbox environment
            public_key: Optional API key to override from Secrets
            secret_key: Optional API secret to override from Secrets
        """
        # Set base URLs based on testnet flag
        self.base_url = self.TESTNET_REST_URL if testnet else self.PROD_REST_URL
        self.ws_market_url = self.TESTNET_WS_MARKET if testnet else self.PROD_WS_MARKET
        self.ws_user_url = self.TESTNET_WS_USER if testnet else self.PROD_WS_USER
        self.testnet = testnet

        try:
            # Load API credentials
            self.api_key = public_key or Secrets.CRYPTO_API_KEY
            self.api_secret = secret_key or Secrets.CRYPTO_API_SECRET

            if not self.api_key:
                logger.warning("API Key is None or empty - private endpoints will fail")
            if not self.api_secret:
                logger.warning(
                    "API Secret is None or empty - private endpoints will fail"
                )
        except AttributeError as e:
            logger.critical(
                f"Could not retrieve API key/secret from the Secrets module. Error: {e}"
            )
            logger.critical(
                "Ensure CRYPTO_API_KEY and CRYPTO_API_SECRET are correctly defined in your secret_keys.py or .env file."
            )
            raise ValueError(
                "Failed to load API credentials from Secrets module."
            ) from e
            
        # Initialize data containers
        self.logs = []  # Initialize logs list first
        self.prices = {}  # Initialize prices dictionary
        
        # Load data
        self.contracts = self._load_contracts()
        self.balances = self._load_balances()
        
        # Initialize WebSocket connection
        self._ws_id = 1
        self._ws = None
        
        # Start WebSocket thread
        t = threading.Thread(target=self._start_ws)
        t.daemon = True
        t.start()
        
        logger.info(f"CryptoExchangeClient initialized in {'TESTNET (Sandbox)' if testnet else 'PRODUCTION'} mode with API key: {'[PROVIDED]' if self.api_key else '[MISSING]'}")

    def _add_log(self, msg: str):
        logger.info(msg)
        self.logs.append({"log": msg, "displayed": False})

    def _get_nonce(self) -> int:
        """Generate nonce using local time in milliseconds"""
        return int(time.time() * 1000)

    def _params_to_str(self, obj: Any, level: int) -> str:
        """
        Convert params to string for signature generation according to API docs.

        Args:
            obj: The parameter object to convert
            level: Current recursion level

        Returns:
            String representation of parameters for signature
        """
        if level >= self.MAX_LEVEL:
            return str(obj)

        if obj is None:
            return "null"

        if isinstance(obj, dict):
            return_str = ""
            for key in sorted(obj.keys()):  # Sort keys alphabetically
                return_str += key
                if obj[key] is None:
                    return_str += "null"
                elif isinstance(obj[key], list):
                    for sub_obj in obj[key]:
                        return_str += self._params_to_str(sub_obj, level + 1)
                else:
                    return_str += str(obj[key])
            return return_str

        elif isinstance(obj, list):
            return_str = ""
            for sub_obj in obj:
                return_str += self._params_to_str(sub_obj, level + 1)
            return return_str

        else:
            return str(obj)

    def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JSON-RPC call with retries and signature logic.

        Args:
            method: API method name
            params: Request parameters

        Returns:
            API response result data

        Raises:
            ValueError: If API returns an error
            RuntimeError: If all retry attempts fail
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                nonce = self._get_nonce()
                payload: Dict[str, Any] = {
                    "id": nonce,
                    "method": method,
                    "params": params or {},
                    "nonce": nonce,
                }

                if method.startswith("private/"):
                    payload["api_key"] = self.api_key

                    # Generate parameter string according to official docs
                    param_str = ""
                    if "params" in payload and payload["params"]:
                        param_str = self._params_to_str(payload["params"], 0)

                    # Create signature base string: method + id + api_key + parameter_string + nonce
                    sig_base_str = (
                        method
                        + str(payload["id"])
                        + self.api_key
                        + param_str
                        + str(payload["nonce"])
                    )

                    # Generate HMAC-SHA256 signature
                    payload["sig"] = hmac.new(
                        bytes(str(self.api_secret), "utf-8"),
                        msg=bytes(sig_base_str, "utf-8"),
                        digestmod=hashlib.sha256,
                    ).hexdigest()

                url = f"{self.base_url}/{method}"
                logger.info(f"Sending {method} request to {url}")
                
                resp = requests.post(url, json=payload, timeout=10)

                # Try to parse JSON, handle potential errors
                try:
                    data = resp.json()
                except requests.exceptions.JSONDecodeError:
                    logger.error(
                        f"Failed to decode JSON from response. Raw text: {resp.text}"
                    )
                    if resp.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                        logger.warning(
                            f"Auth error (HTTP {resp.status_code}), retrying ({attempt + 1}/{self.MAX_RETRIES})..."
                        )
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    raise

                # Check for API-level errors
                if data.get("code", 0) != 0:
                    api_error_code = data.get("code")
                    api_error_message = data.get("message", "No message provided.")
                    logger.error(
                        f"API Error: Code {api_error_code}, Message: '{api_error_message}'"
                    )

                    # Retry on authentication failures
                    if api_error_code == 40101 and attempt < self.MAX_RETRIES - 1:
                        logger.warning(
                            f"API Auth error code {api_error_code}, retrying ({attempt + 1}/{self.MAX_RETRIES})..."
                        )
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    raise ValueError(f"API Error {api_error_code}: {api_error_message}")

                return data.get("result", {})

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error while making {method} request: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
            except requests.exceptions.Timeout as e:
                logger.error(f"Timeout while making {method} request: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
            except requests.HTTPError as e:
                logger.error(
                    f"HTTP Error: {e.response.status_code} {e.response.reason}"
                )
                if (
                    e.response is not None
                    and e.response.status_code == 401
                    and attempt < self.MAX_RETRIES - 1
                ):
                    logger.warning(
                        f"Auth error (HTTP 401), retrying ({attempt + 1}/{self.MAX_RETRIES})..."
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
            except Exception as e:
                logger.error(f"RPC call for method '{method}' failed: {str(e)}")
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"Retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

        raise RuntimeError(
            f"Failed after {self.MAX_RETRIES} attempts for method {method}"
        )
    
    # ----------------------------
    # WebSocket Methods
    # ----------------------------
    
    def _start_ws(self):
        """Start and maintain the WebSocket connection"""
        try:
            # In testnet, we might not have a valid WebSocket endpoint
            # or authentication might fail, so handle those cases gracefully
            self._ws = websocket.WebSocketApp(
                self.ws_market_url,
                on_open=self._on_open,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message,
            )
            
            logger.info(f"Starting Crypto.com WebSocket connection to {self.ws_market_url}...")
            
            while True:
                try:
                    self._ws.run_forever()
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to start WebSocket connection: {e}")
            # Still log that we're connected to avoid UI blocking
            self._add_log("WebSocket connection initialization skipped in testnet mode")

    def _on_open(self, ws):
        """Called when WebSocket connection opens"""
        env_type = "Sandbox" if self.testnet else "Production"
        logger.info(f"Crypto.com {env_type} WebSocket connection established successfully")
        self._add_log(f"{env_type} WebSocket connection established")
        
        # Subscribe to market data
        self.subscribe_market_data()

    def _on_close(self, ws, close_status_code=None, close_msg=None):
        """Called when WebSocket connection closes"""
        close_info = f" (Code: {close_status_code})" if close_status_code else ""
        logger.warning(f"Crypto.com WebSocket connection closed{close_info}")
        self._add_log(f"WebSocket connection closed{close_info}")

    def _on_error(self, ws, error):
        """Called when WebSocket connection encounters an error"""
        logger.error(f"Crypto.com WebSocket error: {error}")
        self._add_log(f"WebSocket error: {str(error)}")

    def _on_message(self, ws, message: str):
        """Process incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle different message types
            if "book" in data:
                self._process_book_update(data)
            elif "trade" in data:
                self._process_trade_update(data)
            elif "ticker" in data:
                self._process_ticker_update(data)
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse WebSocket message: {message}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _process_ticker_update(self, data):
        """Process ticker updates from WebSocket"""
        if "ticker" in data and "data" in data["ticker"]:
            for ticker in data["ticker"]["data"]:
                if "i" in ticker and "a" in ticker and "b" in ticker:
                    symbol = ticker["i"]  # instrument name
                    if symbol not in self.prices:
                        self.prices[symbol] = {}
                    
                    self.prices[symbol]["ask"] = float(ticker["a"])
                    self.prices[symbol]["bid"] = float(ticker["b"])
                    
                    # Log price updates for important pairs
                    if symbol in ["BTC_USDT", "ETH_USDT"]:
                        logger.debug(f"Updated {symbol} prices: Bid=${float(ticker['b'])}, Ask=${float(ticker['a'])}")
    
    def _process_book_update(self, data):
        """Process order book updates from WebSocket"""
        if "book" in data and "data" in data["book"]:
            for book in data["book"]["data"]:
                if "instrument_name" in book:
                    symbol = book["instrument_name"]
                    if "bids" in book and "asks" in book and len(book["bids"]) > 0 and len(book["asks"]) > 0:
                        if symbol not in self.prices:
                            self.prices[symbol] = {}
                        
                        self.prices[symbol]["bid"] = float(book["bids"][0][0])
                        self.prices[symbol]["ask"] = float(book["asks"][0][0])
    
    def _process_trade_update(self, data):
        """Process trade updates from WebSocket"""
        # Implementation for trade updates
        if "trade" in data and "data" in data["trade"]:
            for trade in data["trade"]["data"]:
                if "i" in trade:  # i = instrument_name
                    symbol = trade["i"]
                    logger.debug(f"New trade for {symbol}: {trade}")
    
    def subscribe_market_data(self):
        """Subscribe to market data for available instruments"""
        try:
            instruments = self.get_instruments()
            
            # Check if we got valid instruments
            if not instruments:
                logger.warning("No instruments found to subscribe to")
                self._add_log("Cannot subscribe to market data: No instruments available")
                return
                
            # Debug the structure of a single instrument to understand its format
            if instruments and len(instruments) > 0:
                sample = instruments[0]
                logger.info(f"Sample instrument format: {sample.keys()}")
                
            # Create subscription message
            tickers = []
            valid_count = 0
            invalid_count = 0
            
            for inst in instruments:
                try:
                    # Check various possible key names for instrument name
                    if isinstance(inst, dict):
                        instrument_name = None
                        
                        # Try different possible keys
                        if "instrument_name" in inst and inst["instrument_name"]:
                            instrument_name = inst["instrument_name"]
                        elif "symbol" in inst and inst["symbol"]:
                            instrument_name = inst["symbol"]
                        elif "instrument_id" in inst and inst["instrument_id"]:
                            instrument_name = inst["instrument_id"]
                            
                        if instrument_name:
                            tickers.append(f"ticker.{instrument_name}")
                            valid_count += 1
                        else:
                            invalid_count += 1
                            if invalid_count <= 3:  # Log only first few to avoid spam
                                logger.debug(f"Invalid instrument format: {inst}")
                except Exception as e:
                    logger.error(f"Error processing instrument for subscription: {e}")
                    continue
                    
            if not tickers:
                logger.warning("No valid ticker names found in instruments data")
                self._add_log("Cannot subscribe to market data: Invalid instrument format")
                
                # Create default instruments for sandbox mode
                if self.testnet:
                    logger.info("Using default ticker names for sandbox mode")
                    default_tickers = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
                    tickers = [f"ticker.{t}" for t in default_tickers]
                    self._add_log(f"Subscribing to {len(tickers)} default instruments in sandbox mode")
                else:
                    return
                    
            logger.info(f"Subscribing to {len(tickers)} instrument tickers (valid: {valid_count}, invalid: {invalid_count})")
            self._add_log(f"Subscribing to market data for {len(tickers)} instruments")
                
            # Batch subscribe in chunks to avoid message size limits
            chunk_size = 50
            chunks_sent = 0
            for i in range(0, len(tickers), chunk_size):
                chunk = tickers[i:i+chunk_size]
                sub_msg = {
                    "method": "subscribe",
                    "params": {
                        "channels": chunk
                    },
                    "id": self._ws_id
                }
                
                self._ws.send(json.dumps(sub_msg))
                self._ws_id += 1
                chunks_sent += 1
                time.sleep(0.5)  # Avoid flooding
                
            logger.info(f"Successfully sent {chunks_sent} subscription chunks for {len(tickers)} instruments")
            self._add_log(f"Market data subscription complete")
        except Exception as e:
            logger.error(f"Failed to subscribe to market data: {e}")
            self._add_log(f"Market data subscription failed: {str(e)}")
            
            # Try to subscribe to default tickers in sandbox mode
            if self.testnet:
                try:
                    logger.info("Attempting to subscribe to default tickers after error")
                    default_tickers = ["ticker.BTC_USDT", "ticker.ETH_USDT", "ticker.SOL_USDT"]
                    sub_msg = {
                        "method": "subscribe",
                        "params": {
                            "channels": default_tickers
                        },
                        "id": self._ws_id
                    }
                    
                    self._ws.send(json.dumps(sub_msg))
                    self._add_log("Subscribed to default market data")
                except Exception as fallback_e:
                    logger.error(f"Failed to subscribe to default tickers: {fallback_e}")

    # ----------------------------
    # Public Endpoints
    # ----------------------------

    def _load_contracts(self) -> Dict[str, Contract]:
        """Load contract information and create Contract objects"""
        contracts: Dict[str, Contract] = {}
        try:
            instruments = self.get_instruments()
            if not instruments:
                logger.warning("No instruments returned from API")
                if self.testnet:
                    self._add_log("Using synthetic test instruments for sandbox mode")
                else:
                    self._add_log("Warning: No trading instruments available from exchange")
                return contracts
                
            for instrument in instruments:
                symbol = instrument.get("instrument_name")
                # Skip instruments without a valid symbol
                if not symbol:
                    continue
                    
                try:
                    contract = Contract.from_info(instrument, "crypto")
                    contracts[symbol] = contract
                except Exception as inner_e:
                    logger.error(f"Failed to create contract for {symbol}: {inner_e}")
                    continue
                    
            logger.info(f"Successfully loaded {len(contracts)} trading contracts")
            if len(contracts) > 0:
                self._add_log(f"Loaded {len(contracts)} trading instruments")
            
        except Exception as e:
            logger.error(f"Failed to load contracts: {e}")
            self._add_log(f"Error loading trading instruments: {str(e)}")
            
            # In case we can't load contracts, add some default test pairs
            if self.testnet:
                self._add_fallback_contracts(contracts)
        
        return contracts
        
    def _add_fallback_contracts(self, contracts_dict: Dict[str, Contract]):
        """Add fallback test contracts when API fails"""
        logger.info("Adding default test contracts for testnet mode")
        self._add_log("Using synthetic test instruments due to API error")
        
        # Create some dummy contracts for testing
        test_pairs = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
        for pair in test_pairs:
            base, quote = pair.split("_")
            contracts_dict[pair] = Contract(
                symbol=pair,
                base_asset=base,
                quote_asset=quote,
                price_decimals=2,
                quantity_decimals=4,
                tick_size=0.01,
                lot_size=0.0001
            )
        
        return contracts_dict

    def _load_balances(self) -> Dict[str, Balance]:
        """Load account balances and create Balance objects"""
        balances: Dict[str, Balance] = {}
        try:
            # In testnet mode, we might not have authentication set up correctly
            # or the endpoint might return an error, so we'll handle that gracefully
            if self.testnet and (not self.api_key or not self.api_secret):
                logger.warning("Skipping balance loading in testnet mode without credentials")
                self._add_log("Sandbox mode active - using simulated balances")
                
                # Add some test balances for sandbox mode
                balances["USDT"] = Balance(free=10000.0, locked=0.0)
                balances["BTC"] = Balance(free=1.0, locked=0.0)
                balances["ETH"] = Balance(free=10.0, locked=0.0)
                
                return balances
                
            account_data = self.get_account_summary()
            for asset_data in account_data:
                if "currency" in asset_data:
                    currency = asset_data["currency"]
                    balance = Balance.from_info(asset_data, "crypto")
                    balances[currency] = balance
                    
            if len(balances) > 0:
                logger.info(f"Successfully loaded {len(balances)} account balances")
                self._add_log(f"Loaded {len(balances)} account balances")
            else:
                logger.warning("No non-zero balances found in account")
                self._add_log("No account balances found")
                
        except Exception as e:
            logger.error(f"Failed to load balances: {e}")
            self._add_log(f"Error loading account balances: {str(e)}")
            
            # Add some test balances in case of error in testnet mode
            if self.testnet:
                balances["USDT"] = Balance(free=10000.0, locked=0.0)
                balances["BTC"] = Balance(free=1.0, locked=0.0)
                balances["ETH"] = Balance(free=10.0, locked=0.0)
                self._add_log("Using simulated balances due to API error")
        
        return balances
        
    def get_instruments(self) -> List[Dict[str, Any]]:
        """
        Fetch all available trading instruments.

        Returns:
            List of instrument details
        """
        try:
            url = f"{self.base_url}/public/get-instruments"
            logger.info(f"Fetching instruments from {url}")
            
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            instruments = resp.json().get("result", {}).get("data", [])
            
            # If we got no instruments and we're in testnet mode, create some fallbacks
            if not instruments:
                if self.testnet:
                    logger.warning("No instruments returned from API, using fallback test instruments")
                    self._add_log("Using synthetic test instruments for sandbox mode")
                    # Create some basic test instruments
                    instruments = [
                        {"instrument_name": "BTC_USDT", "base_currency": "BTC", "quote_currency": "USDT", "price_decimals": 2, "quantity_decimals": 6},
                        {"instrument_name": "ETH_USDT", "base_currency": "ETH", "quote_currency": "USDT", "price_decimals": 2, "quantity_decimals": 5},
                        {"instrument_name": "SOL_USDT", "base_currency": "SOL", "quote_currency": "USDT", "price_decimals": 3, "quantity_decimals": 4},
                    ]
                else:
                    logger.error("Exchange returned empty instruments list")
                    self._add_log("Warning: No trading instruments available from exchange")
            else:
                logger.info(f"Successfully retrieved {len(instruments)} instruments")
            
            return instruments
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error while fetching instruments: {e}")
            self._add_log("Failed to connect to exchange API - check your internet connection")
            if self.testnet:
                return self._get_fallback_instruments()
            return []
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout while fetching instruments: {e}")
            self._add_log("Exchange API request timed out")
            if self.testnet:
                return self._get_fallback_instruments()
            return []
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            self._add_log(f"Error retrieving instrument list: {str(e)}")
            if self.testnet:
                return self._get_fallback_instruments()
            return []

    def _get_fallback_instruments(self) -> List[Dict[str, Any]]:
        """Return fallback test instruments when API fails in testnet mode"""
        self._add_log("Using synthetic test instruments due to API error")
        return [
            {"instrument_name": "BTC_USDT", "base_currency": "BTC", "quote_currency": "USDT", "price_decimals": 2, "quantity_decimals": 6},
            {"instrument_name": "ETH_USDT", "base_currency": "ETH", "quote_currency": "USDT", "price_decimals": 2, "quantity_decimals": 5},
            {"instrument_name": "SOL_USDT", "base_currency": "SOL", "quote_currency": "USDT", "price_decimals": 3, "quantity_decimals": 4},
        ]
        
    def get_contracts(self) -> Dict[str, Contract]:
        """Public alias for accessing contracts dictionary"""
        return self.contracts

    def get_balances(self) -> Dict[str, Balance]:
        """Public alias for accessing balances dictionary"""
        return self.balances

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """
        Fetch order book for a given instrument.

        Args:
            instrument_name: Trading pair symbol (e.g., "BTC_USDT")
            depth: Order book depth (number of price levels)

        Returns:
            Order book with bids and asks
        """
        logger.info(f"Fetching order book for {instrument_name} with depth {depth}")
        
        try:
            url = f"{self.base_url}/public/get-book"
            params = {"instrument_name": instrument_name, "depth": str(depth)}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
    
            result_data = resp.json().get("result", {})
            book_data_list = result_data.get("data", [])
    
            if (
                book_data_list
                and isinstance(book_data_list, list)
                and len(book_data_list) > 0
            ):
                book_snapshot = book_data_list[0]
                logger.info(f"Order book retrieved successfully for {instrument_name}")
                return {
                    "bids": book_snapshot.get("bids", []),
                    "asks": book_snapshot.get("asks", []),
                }
                
            logger.warning(f"Empty order book returned for {instrument_name}")
            return {"bids": [], "asks": []}
            
        except Exception as e:
            logger.error(f"Error fetching order book for {instrument_name}: {e}")
            self._add_log(f"Failed to fetch order book for {instrument_name}")
            return {"bids": [], "asks": []}

    def get_trades(
        self, instrument_name: str, count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent trades for a given instrument.

        Args:
            instrument_name: Trading pair symbol (e.g., "BTC_USDT")
            count: Number of trades to retrieve

        Returns:
            List of recent trades
        """
        logger.info(f"Fetching {count} recent trades for {instrument_name}")
        
        try:
            url = f"{self.base_url}/public/get-trades"
            params = {"instrument_name": instrument_name, "count": count}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            
            trades = resp.json().get("result", {}).get("data", [])
            logger.info(f"Retrieved {len(trades)} recent trades for {instrument_name}")
            return trades
            
        except Exception as e:
            logger.error(f"Error fetching trades for {instrument_name}: {e}")
            self._add_log(f"Failed to fetch recent trades for {instrument_name}")
            return []
    
    def get_historical_candles(
        self,
        instrument_name: str,
        interval: str,         # e.g. "1m", "5m", "1h", "1d"
        count: int = 25,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> List[Candle]:
        """
        Fetch historical OHLCV data from Crypto.com Exchange.

        :param instrument_name: e.g. "BTCUSD-PERP"
        :param interval: one of "1m","5m","15m","30m","1h","2h","4h","12h","1d","7d","14d","1M"
        :param count: number of candles to return (default 25)
        :param start_ts: optional inclusive start timestamp (ms)
        :param end_ts: optional exclusive end timestamp (ms)
        :returns: list of Candle(timestamp, open, high, low, close, volume)
        """
        logger.info(f"Fetching {count} {interval} candles for {instrument_name}")
        
        try:
            url = f"{self.base_url}/public/get-candlestick"
            params: Dict[str, Union[str, int]] = {
                "instrument_name": instrument_name,
                "timeframe": interval,
                "count": count,
            }
            if start_ts is not None:
                params["start_ts"] = start_ts
            if end_ts is not None:
                params["end_ts"] = end_ts
    
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            data = result.get("data", [])
    
            candles: List[Candle] = []
            for item in data:
                candles.append(
                    Candle(
                        timestamp=int(item["t"]),
                        open=float(item["o"]),
                        high=float(item["h"]),
                        low=float(item["l"]),
                        close=float(item["c"]),
                        volume=float(item["v"]),
                    )
                )
                
            logger.info(f"Retrieved {len(candles)} historical {interval} candles for {instrument_name}")
            return candles
            
        except Exception as e:
            logger.error(f"Error fetching historical candles for {instrument_name}: {e}")
            self._add_log(f"Failed to fetch historical data for {instrument_name}")
            return []
        
    def get_bid_ask(self, contract: Contract) -> Dict[str, float]:
        """
        Get current bid/ask prices for a contract.
        
        Args:
            contract: Contract object
            
        Returns:
            Dictionary with bid and ask prices
        """
        # Check if we already have the price in our cache
        if contract.symbol in self.prices:
            return self.prices[contract.symbol]
        
        logger.info(f"Fetching bid/ask for {contract.symbol}...")
            
        # Fetch from the API if not available
        try:
            book = self.get_order_book(contract.symbol, depth=1)
            
            bid = float(book["bids"][0][0]) if book["bids"] else None
            ask = float(book["asks"][0][0]) if book["asks"] else None
            
            self.prices[contract.symbol] = {"bid": bid, "ask": ask}
            
            if bid is not None and ask is not None:
                logger.info(f"Current {contract.symbol} market: Bid=${bid}, Ask=${ask}")
            else:
                logger.warning(f"Incomplete market data for {contract.symbol}")
                
            return self.prices[contract.symbol]
            
        except Exception as e:
            logger.error(f"Failed to fetch bid/ask for {contract.symbol}: {e}")
            self._add_log(f"Error fetching market prices for {contract.symbol}")
            
            # Return empty prices
            self.prices[contract.symbol] = {"bid": None, "ask": None}
            return self.prices[contract.symbol]

    # ----------------------------
    # Private Endpoints
    # ----------------------------

    def get_account_summary(self) -> List[Dict[str, Any]]:
        """
        Fetch wallet balances.

        Returns:
            List of account balances
        """
        logger.info("Fetching account balances from Crypto.com Exchange...")
        
        try:
            if not self.api_key or not self.api_secret:
                logger.error("Missing API credentials - cannot fetch account balances")
                self._add_log("Error: API credentials required for account balances")
                return []
                
            result = self._rpc("private/user-balance", {})
            balance_data = result.get("data", [])
            
            if balance_data:
                logger.info(f"Successfully retrieved {len(balance_data)} account balances")
            else:
                logger.warning("No balance data returned from API")
                
            return balance_data
            
        except Exception as e:
            logger.error(f"Failed to fetch account balances: {e}")
            self._add_log(f"Error fetching account balances: {str(e)}")
            return []

    def create_order(
        self,
        instrument_name: str,
        side: str,
        type_: str,
        quantity: str,
        price: Union[str, None] = None,
        client_oid: Union[str, None] = None,
    ) -> Dict[str, Any]:
        """
        Create a new order.

        Args:
            instrument_name: Trading pair symbol (e.g., "BTC_USDT")
            side: "BUY" or "SELL"
            type_: Order type (e.g., "LIMIT", "MARKET")
            quantity: Order quantity as string
            price: Price as string (required for LIMIT orders)
            client_oid: Optional client order ID

        Returns:
            Order details

        Raises:
            ValueError: If price is missing for LIMIT orders
        """
        logger.info(f"Creating {type_} {side} order for {quantity} {instrument_name}...")
        
        try:
            params = {
                "instrument_name": instrument_name,
                "side": side.upper(),
                "type": type_.upper(),
                "quantity": quantity,
            }
            if type_.upper() == "LIMIT" and price is not None:
                params["price"] = price
            elif type_.upper() == "LIMIT" and price is None:
                error_msg = "Price is required for LIMIT orders"
                logger.error(error_msg)
                self._add_log(f"Order error: {error_msg}")
                raise ValueError(error_msg)
    
            if client_oid:
                params["client_oid"] = client_oid
    
            result = self._rpc("private/create-order", params)
            
            if result:
                order_id = result.get("order_id", "Unknown")
                logger.info(f"Order created successfully with ID: {order_id}")
                self._add_log(f"Placed {side} order for {quantity} {instrument_name} at {price if price else 'MARKET'}")
            else:
                logger.error("Failed to create order - empty response")
                self._add_log(f"Failed to place {side} order for {instrument_name}")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            self._add_log(f"Order creation failed: {str(e)}")
            raise

    def cancel_order(self, order_id: str, instrument_name: str) -> Dict[str, Any]:
        """
        Cancel an order by ID.

        Args:
            order_id: The order ID to cancel
            instrument_name: Trading pair symbol

        Returns:
            Cancellation result
        """
        logger.info(f"Cancelling order {order_id} for {instrument_name}...")
        
        try:
            params = {"order_id": order_id, "instrument_name": instrument_name}
            result = self._rpc("private/cancel-order", params)
            
            if result:
                logger.info(f"Order {order_id} cancelled successfully")
                self._add_log(f"Cancelled order {order_id} for {instrument_name}")
            else:
                logger.error(f"Failed to cancel order {order_id} - empty response")
                self._add_log(f"Failed to cancel order {order_id}")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            self._add_log(f"Order cancellation failed: {str(e)}")
            raise

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a specific order.

        Args:
            order_id: The order ID string

        Returns:
            Order details
        """
        logger.info(f"Fetching details for order {order_id}...")
        
        try:
            params = {"order_id": order_id}
            result = self._rpc("private/get-order-detail", params)
            
            if result:
                order_status = result.get("status", "Unknown")
                order_type = result.get("type", "Unknown")
                logger.info(f"Order {order_id} status: {order_status}, type: {order_type}")
            else:
                logger.error(f"Failed to fetch order {order_id} details - empty response")
                self._add_log(f"Failed to get details for order {order_id}")
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch order details: {e}")
            self._add_log(f"Error retrieving order details: {str(e)}")
            raise

    def get_open_orders(
        self,
        instrument_name: Union[str, None] = None,
        page_size: int = 20,
        page: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all open orders for a given instrument.

        Args:
            instrument_name: Trading pair symbol (optional)
            page_size: Number of orders per page
            page: Page number (0-indexed)

        Returns:
            List of open orders
        """
        logger.info(f"Fetching open orders{f' for {instrument_name}' if instrument_name else ''}...")
        
        try:
            params: Dict[str, Any] = {"page_size": page_size, "page": page}
            if instrument_name:
                params["instrument_name"] = instrument_name
                
            result = self._rpc("private/get-open-orders", params)
            orders = result.get("order_list", result.get("data", []))
            
            if orders:
                logger.info(f"Retrieved {len(orders)} open orders")
                self._add_log(f"Found {len(orders)} open orders")
            else:
                logger.info("No open orders found")
                self._add_log("No open orders found")
                
            return orders
            
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            self._add_log(f"Error retrieving open orders: {str(e)}")
            return []