import logging
import requests
import time
import typing

from urllib.parse import urlencode
import hmac
import hashlib
import websocket  # requires `pip install websocket-client`
import json
import threading

from models import Contract, Balance, Candle, OrderStatus  # uses dataclass factories
from secret_keys import Secrets

logger = logging.getLogger()


class BinanceExchangeClient:
    """
    Client for interacting with Binance.US Spot REST and WebSocket APIs.
    Uses API key and secret from Secrets configuration.
    """

    def __init__(self, public_key=None, secret_key=None):
        """
        Initialize Binance Exchange client.
        
        Args:
            public_key: Optional API key to override from Secrets
            secret_key: Optional API secret to override from Secrets
        """
        self._public_key = public_key or Secrets.BINANCE_API_KEY
        self._secret_key = secret_key or Secrets.BINANCE_API_SECRET

        # Spot REST API base URL for Binance.US
        self._base_url = "https://api.binance.us"
        # Spot WebSocket base endpoint for market streams
        self._wss_url = "wss://stream.binance.us:9443/ws"

        self._headers = {"X-MBX-APIKEY": self._public_key}

        # Initialize data
        self.logs = []  # Initialize logs list
        self.prices = {}  # Initialize prices dictionary
        
        # Load data
        self.contracts = self._load_contracts()
        self.balances = self._load_balances()

        # Start websocket thread
        self._ws_id = 1
        self._ws = None
        t = threading.Thread(target=self._start_ws)
        t.daemon = True
        t.start()

        logger.info(f"BinanceClient initialized successfully with API key: {'[PROVIDED]' if self._public_key else '[MISSING]'}")

    def get_contracts(self) -> typing.Dict[str, Contract]:
        """Public alias for fetching contracts"""
        return self._load_contracts()

    def get_balances(self) -> typing.Dict[str, Balance]:
        """Public alias for fetching balances"""
        return self._load_balances()

    def _add_log(self, msg: str):
        logger.info(msg)
        self.logs.append({"log": msg, "displayed": False})

    def _generate_signature(self, params: typing.Dict) -> str:
        return hmac.new(
            self._secret_key.encode(), urlencode(params).encode(), hashlib.sha256
        ).hexdigest()

    def _make_request(self, method: str, endpoint: str, params: typing.Dict):
        url = self._base_url + endpoint
        try:
            if method == "GET":
                resp = requests.get(url, params=params, headers=self._headers)
            elif method == "POST":
                resp = requests.post(url, params=params, headers=self._headers)
            elif method == "DELETE":
                resp = requests.delete(url, params=params, headers=self._headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except Exception as e:
            logger.error("Connection error %s %s: %s", method, endpoint, e)
            return None

        if resp.status_code == 200:
            return resp.json()
        logger.error(
            "API error %s %s: %s (code %s)",
            method,
            endpoint,
            resp.text,
            resp.status_code,
        )
        return None

    def _load_contracts(self) -> typing.Dict[str, Contract]:
        """Load all available trading contracts from Binance.US API"""
        logger.info("Fetching available trading pairs from Binance.US...")
        
        info = self._make_request("GET", "/api/v3/exchangeInfo", {})
        contracts: typing.Dict[str, Contract] = {}
        
        if info is None:
            logger.error("Failed to retrieve exchange information from Binance.US")
            self._add_log("Error: Could not fetch trading pairs from Binance.US")
            return contracts
            
        if "symbols" not in info:
            logger.error("Unexpected response format: 'symbols' not found in exchange info")
            self._add_log("Error: Invalid response format from Binance.US API")
            return contracts
            
        valid_pairs = 0
        for c in info["symbols"]:
            try:
                contract = Contract.from_info(c, "binance")
                contracts[contract.symbol] = contract
                valid_pairs += 1
            except Exception as e:
                logger.warning(f"Failed to process symbol {c.get('symbol', 'UNKNOWN')}: {e}")
                
        logger.info(f"Successfully loaded {valid_pairs} trading pairs from Binance.US")
        self._add_log(f"Loaded {valid_pairs} Binance.US trading pairs")
        
        return contracts

    def _load_balances(self) -> typing.Dict[str, Balance]:
        """Load account balances from Binance.US API"""
        if not self._public_key or not self._secret_key:
            logger.warning("Missing API credentials - cannot fetch account balances")
            self._add_log("Warning: API credentials required for account balances")
            return {}
            
        logger.info("Fetching account balances from Binance.US...")
        
        ts = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = self._generate_signature(params)
        data = self._make_request("GET", "/api/v3/account", params)
        
        balances: typing.Dict[str, Balance] = {}
        
        if data is None:
            logger.error("Failed to retrieve account data from Binance.US")
            self._add_log("Error: Could not fetch account balances from Binance.US")
            return balances
            
        if "balances" not in data:
            logger.error("Unexpected response format: 'balances' not found in account data")
            self._add_log("Error: Invalid response format from Binance.US API")
            return balances
            
        non_zero_assets = 0
        for b in data["balances"]:
            try:
                balance = Balance.from_info(b, "binance")
                # include only non-empty balances
                if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0:
                    key = b.get("asset", "")
                    balances[key] = balance
                    non_zero_assets += 1
            except Exception as e:
                logger.warning(f"Failed to process balance for {b.get('asset', 'UNKNOWN')}: {e}")
                
        logger.info(f"Successfully loaded {non_zero_assets} non-zero balances from Binance.US")
        if non_zero_assets > 0:
            self._add_log(f"Loaded {non_zero_assets} non-zero balances from Binance.US")
        
        return balances

    def get_historical_candles(
        self, contract: Contract, interval: str
    ) -> typing.List[Candle]:
        """
        Fetch historical OHLCV candle data.
        
        Args:
            contract: Contract object
            interval: Time interval (e.g. "1m", "5m", "1h", "1d")
            
        Returns:
            List of Candle objects
        """
        logger.info(f"Fetching {interval} candles for {contract.symbol}...")
        
        params = {"symbol": contract.symbol, "interval": interval, "limit": 1000}
        raw = self._make_request("GET", "/api/v3/klines", params)
        
        if raw is None:
            logger.error(f"Failed to retrieve historical data for {contract.symbol}")
            self._add_log(f"Error: Could not fetch historical data for {contract.symbol}")
            return []
            
        candles = [Candle.from_api(c, interval, "binance") for c in raw] 
        
        logger.info(f"Retrieved {len(candles)} historical {interval} candles for {contract.symbol}")
        return candles

    def get_bid_ask(self, contract: Contract) -> typing.Dict[str, float]:
        """
        Get current bid/ask prices for a contract.
        
        Args:
            contract: Contract object
            
        Returns:
            Dictionary with bid and ask prices
        """
        logger.info(f"Fetching bid/ask for {contract.symbol}...")
        
        params = {"symbol": contract.symbol}
        ob = self._make_request("GET", "/api/v3/ticker/bookTicker", params)
        
        if ob is None:
            logger.error(f"Failed to retrieve bid/ask data for {contract.symbol}")
            self._add_log(f"Error: Could not fetch market prices for {contract.symbol}")
            return {"bid": None, "ask": None}
            
        bid = float(ob.get("bidPrice", 0))
        ask = float(ob.get("askPrice", 0))
        
        # Store for later use
        self.prices[contract.symbol] = {"bid": bid, "ask": ask}
        
        logger.info(f"Current {contract.symbol} market: Bid=${bid}, Ask=${ask}")
        return self.prices[contract.symbol]

    def place_order(
        self,
        contract: Contract,
        side: str,
        quantity: float,
        order_type: str,
        price: float = None,
        tif: str = None,
    ) -> OrderStatus:
        """
        Place a new order on Binance.US
        
        Args:
            contract: Contract object
            side: "BUY" or "SELL"
            quantity: Order quantity
            order_type: "LIMIT" or "MARKET"
            price: Limit price (required for LIMIT orders)
            tif: Time-in-force (e.g., "GTC", "IOC", "FOK")
            
        Returns:
            OrderStatus object
        """
        logger.info(f"Placing {order_type} {side} order for {quantity} {contract.symbol}...")
        
        params = {"symbol": contract.symbol, "side": side, "type": order_type}
        params["quantity"] = round(
            round(quantity / contract.lot_size) * contract.lot_size,
            contract.quantity_decimals,
        )
        
        if price is not None:
            params["price"] = round(
                round(price / contract.tick_size) * contract.tick_size,
                contract.price_decimals,
            )
            
        if tif:
            params["timeInForce"] = tif
            
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._generate_signature(params)
        
        result = self._make_request("POST", "/api/v3/order", params)
        
        if result is None:
            logger.error(f"Failed to place {order_type} {side} order for {contract.symbol}")
            self._add_log(f"Error: Order placement failed for {contract.symbol}")
            return None
            
        order_status = OrderStatus.from_api(result, "binance")
        
        logger.info(f"Order placed successfully: ID {order_status.order_id}")
        self._add_log(f"Placed {side} order for {quantity} {contract.symbol} at {price if price else 'MARKET'}")
        
        return order_status

    def cancel_order(self, contract: Contract, order_id: int) -> OrderStatus:
        """
        Cancel an existing order
        
        Args:
            contract: Contract object
            order_id: Order ID to cancel
            
        Returns:
            OrderStatus object
        """
        logger.info(f"Cancelling order {order_id} for {contract.symbol}...")
        
        params = {
            "symbol": contract.symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._generate_signature(params)
        
        result = self._make_request("DELETE", "/api/v3/order", params)
        
        if result is None:
            logger.error(f"Failed to cancel order {order_id}")
            self._add_log(f"Error: Failed to cancel order {order_id}")
            return None
            
        order_status = OrderStatus.from_api(result, "binance")
        
        logger.info(f"Order {order_id} cancelled successfully")
        self._add_log(f"Cancelled order {order_id} for {contract.symbol}")
        
        return order_status

    def get_order_status(self, contract: Contract, order_id: int) -> OrderStatus:
        """
        Check the status of an order
        
        Args:
            contract: Contract object
            order_id: Order ID to check
            
        Returns:
            OrderStatus object
        """
        logger.info(f"Checking status of order {order_id}...")
        
        params = {
            "symbol": contract.symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._generate_signature(params)
        
        result = self._make_request("GET", "/api/v3/order", params)
        
        if result is None:
            logger.error(f"Failed to retrieve status for order {order_id}")
            self._add_log(f"Error: Could not get status for order {order_id}")
            return None
            
        order_status = OrderStatus.from_api(result, "binance")
        
        logger.info(f"Order {order_id} status: {order_status.status}")
        return order_status

    def _start_ws(self):
        """Start and maintain WebSocket connection"""
        try:
            # ensure using websocket-client's WebSocketApp
            self._ws = websocket.WebSocketApp(
                self._wss_url,
                on_open=self._on_open,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message,
            )
            
            logger.info("Starting Binance.US WebSocket connection...")
            
            while True:
                try:
                    self._ws.run_forever()
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                time.sleep(2)
        except Exception as e:
            logger.error(f"Failed to start WebSocket connection: {e}")

    def _on_open(self, ws):
        """Called when WebSocket connection opens"""
        logger.info("Binance.US WebSocket connection established successfully")
        self._add_log("Binance.US market data stream connected")
        self.subscribe_channel(list(self.contracts.values()), "bookTicker")

    def _on_close(self, ws, close_status_code=None, close_msg=None):
        """Called when WebSocket connection closes"""
        close_info = f" (Code: {close_status_code})" if close_status_code else ""
        logger.warning(f"Binance.US WebSocket connection closed{close_info}")
        self._add_log(f"Binance.US market data stream disconnected{close_info}")

    def _on_error(self, ws, error):
        """Called when WebSocket connection encounters an error"""
        logger.error(f"Binance.US WebSocket error: {error}")
        self._add_log(f"Binance.US WebSocket error: {str(error)}")

    def _on_message(self, ws, msg: str):
        """Process incoming WebSocket messages"""
        try:
            data = json.loads(msg)
            
            if data.get("e") == "bookTicker":
                s = data["s"]
                self.prices.setdefault(s, {})
                self.prices[s]["bid"] = float(data["b"])
                self.prices[s]["ask"] = float(data["a"])
        except json.JSONDecodeError:
            logger.error(f"Failed to parse WebSocket message: {msg}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    def subscribe_channel(self, contracts: typing.List[Contract], channel: str):
        """
        Subscribe to a WebSocket channel for multiple contracts
        
        Args:
            contracts: List of Contract objects
            channel: Channel name (e.g., "bookTicker", "trade", "kline_1m")
        """
        logger.info(f"Subscribing to {channel} for {len(contracts)} contracts...")
        
        payload = {
            "method": "SUBSCRIBE",
            "params": [f"{c.symbol.lower()}@{channel}" for c in contracts],
            "id": self._ws_id,
        }
        
        try:
            self._ws.send(json.dumps(payload))
            logger.info(f"Subscription request sent for {len(contracts)} contracts")
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            self._add_log(f"Failed to subscribe to market data: {str(e)}")
            
        self._ws_id += 1