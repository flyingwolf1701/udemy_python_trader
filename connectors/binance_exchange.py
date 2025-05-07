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
        self.contracts = self._load_contracts()
        self.balances = self._load_balances()
        self.prices = {}
        self.logs = []

        # Start websocket thread
        self._ws_id = 1
        self._ws = None
        t = threading.Thread(target=self._start_ws)
        t.daemon = True
        t.start()

        logger.info("✅ BinanceClient instantiated successfully")

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
        info = self._make_request("GET", "/api/v3/exchangeInfo", {})
        contracts: typing.Dict[str, Contract] = {}
        if info and "symbols" in info:
            for c in info["symbols"]:
                contract = Contract.from_info(c, "binance")
                contracts[contract.symbol] = contract
        return contracts

    def _load_balances(self) -> typing.Dict[str, Balance]:
        ts = int(time.time() * 1000)
        params = {"timestamp": ts}
        params["signature"] = self._generate_signature(params)
        data = self._make_request("GET", "/api/v3/account", params)
        balances: typing.Dict[str, Balance] = {}
        if data and "balances" in data:
            for b in data["balances"]:
                balance = Balance.from_info(b, "binance")
                # include only non-empty balances
                if balance.free is not None or balance.initial_margin is not None:
                    key = b.get("asset", "")
                    balances[key] = balance
        return balances

    def get_historical_candles(
        self, contract: Contract, interval: str
    ) -> typing.List[Candle]:
        params = {"symbol": contract.symbol, "interval": interval, "limit": 1000}
        raw = self._make_request("GET", "/api/v3/klines", params)
        return [Candle.from_api(c, interval, "binance") for c in raw] if raw else []

    def get_bid_ask(self, contract: Contract) -> typing.Dict[str, float]:
        params = {"symbol": contract.symbol}
        ob = self._make_request("GET", "/api/v3/ticker/bookTicker", params)
        if ob:
            bid = float(ob["bidPrice"])
            ask = float(ob["askPrice"])
            self.prices[contract.symbol] = {"bid": bid, "ask": ask}
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
        return OrderStatus.from_api(result, "binance") if result else None

    def cancel_order(self, contract: Contract, order_id: int) -> OrderStatus:
        params = {
            "symbol": contract.symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._generate_signature(params)
        result = self._make_request("DELETE", "/api/v3/order", params)
        return OrderStatus.from_api(result, "binance") if result else None

    def get_order_status(self, contract: Contract, order_id: int) -> OrderStatus:
        params = {
            "symbol": contract.symbol,
            "orderId": order_id,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._generate_signature(params)
        result = self._make_request("GET", "/api/v3/order", params)
        return OrderStatus.from_api(result, "binance") if result else None

    def _start_ws(self):
        # ensure using websocket-client‘s WebSocketApp
        self._ws = websocket.WebSocketApp(
            self._wss_url,
            on_open=self._on_open,
            on_close=self._on_close,
            on_error=self._on_error,
            on_message=self._on_message,
        )
        while True:
            try:
                self._ws.run_forever()
            except Exception as e:
                logger.error("WebSocket error: %s", e)
            time.sleep(2)

    def _on_open(self, ws):
        logger.info("WS connection opened")
        self.subscribe_channel(list(self.contracts.values()), "bookTicker")

    def _on_close(self, ws):
        logger.warning("WS connection closed")

    def _on_error(self, ws, error):
        logger.error("WS error: %s", error)

    def _on_message(self, ws, msg: str):
        data = json.loads(msg)
        if data.get("e") == "bookTicker":
            s = data["s"]
            self.prices.setdefault(s, {})
            self.prices[s]["bid"] = float(data["b"])
            self.prices[s]["ask"] = float(data["a"])

    def subscribe_channel(self, contracts: typing.List[Contract], channel: str):
        payload = {
            "method": "SUBSCRIBE",
            "params": [f"{c.symbol.lower()}@{channel}" for c in contracts],
            "id": self._ws_id,
        }
        try:
            self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error("Subscribe error: %s", e)
        self._ws_id += 1
