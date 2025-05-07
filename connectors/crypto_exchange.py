import time
import hmac
import hashlib
import logging
import threading
import json
import requests
import websocket
from typing import Any, Dict, List, Optional, Union

from secret_keys import Secrets
from models import Candle, Contract, Balance, OrderStatus

logger = logging.getLogger(__name__)
# Enable debug logging for this module
logger.setLevel(logging.DEBUG)

class CryptoExchangeClient:
    """
    Simplified Crypto.com Exchange v1 API client with clear structure,
    using requests.Session, concise signature logic, and unified error handling.
    """
    PROD_REST_URL = "https://api.crypto.com/exchange/v1"
    TESTNET_REST_URL = "https://uat-api.3ona.co/exchange/v1"
    PROD_WS_MARKET = "wss://stream.crypto.com/exchange/v1/market"
    TESTNET_WS_MARKET = "wss://uat-stream.3ona.co/exchange/v1/market"
    PROD_WS_USER = "wss://stream.crypto.com/exchange/v1/user"
    TESTNET_WS_USER = "wss://uat-stream.3ona.co/exchange/v1/user"

    def __init__(
        self,
        testnet: bool = False,
    ):
        # Load credentials exclusively from environment
        self.api_key = Secrets.CRYPTO_API_KEY
        self.api_secret = Secrets.CRYPTO_API_SECRET
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "CRYPTO_API_KEY and CRYPTO_API_SECRET must be set in environment for private endpoints"
            )
        logger.info("API credentials loaded from environment; private endpoints enabled.")

        self.testnet = testnet
        self.base_url = self.TESTNET_REST_URL if testnet else self.PROD_REST_URL
        self.ws_market_url = self.TESTNET_WS_MARKET if testnet else self.PROD_WS_MARKET
        self.ws_user_url = self.TESTNET_WS_USER if testnet else self.PROD_WS_USER

        self.session = requests.Session()
        self.contracts: Dict[str, Contract] = {}
        self.balances: Dict[str, Balance] = {}
        self.prices: Dict[str, Dict[str, float]] = {}
        self.logs: List[Dict[str, Union[str, bool]]] = []

        self._initialize_data()
        threading.Thread(target=self._start_ws, daemon=True).start()
        logger.info(f"CryptoExchangeClient initialized ({'TESTNET' if testnet else 'PROD'}).")

    def _add_log(self, msg: str):
        logger.info(msg)
        self.logs.append({"log": msg, "displayed": False})

    def _get_nonce(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, method: str, params: Dict[str, Any], nonce: int) -> str:
        """
        Build and log the signature base string, then return the HMAC-SHA256 signature.
        """
        # Build parameter string: sorted keys, concatenate key+value
        param_str = ''.join(f"{k}{params[k]}" for k in sorted(params)) if params else ''
        # Base string for signature
        base = f"{method}{nonce}{self.api_key}{param_str}{nonce}"
        logger.debug(f"Signature base string: {base}")
        signature = hmac.new(
            self.api_secret.encode(), base.encode(), hashlib.sha256
        ).hexdigest()
        logger.debug(f"Computed signature: {signature}")
        return signature

    def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # JSON-RPC call with simple retry logic
        for i in range(3):
            nonce = self._get_nonce()
            sig = self._sign(method, params or {}, nonce)
            payload = {
                "id": nonce,
                "method": method,
                "api_key": self.api_key,
                "params": params or {},
                "nonce": nonce,
                "sig": sig,
            }
            logger.debug(f"RPC payload for {method}: {json.dumps(payload)}")
            try:
                resp = self.session.post(
                    f"{self.base_url}/{method}", json=payload, timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                logger.debug(f"RPC response for {method}: {json.dumps(data)}")
                if data.get("code", 0) != 0:
                    raise ValueError(f"API error {data['code']}: {data.get('message')}")
                return data.get("result", {})
            except Exception as e:
                logger.warning(f"RPC {method} attempt {i+1} failed: {e}")
                time.sleep(0.5 * (i + 1))
        logger.error(f"RPC {method} failed after retries")
        return {}

    def _initialize_data(self):
        self.contracts = self._load_contracts()
        self.balances = self._load_balances()

    # Public REST endpoints
    def get_instruments(self) -> List[Dict[str, Any]]:
        resp = self.session.get(
            f"{self.base_url}/public/get-instruments", timeout=10
        )
        resp.raise_for_status()
        instruments = resp.json().get("result", {}).get("data", [])
        logger.info(f"Fetched {len(instruments)} instruments.")
        return instruments

    def _load_contracts(self) -> Dict[str, Contract]:
        instruments = self.get_instruments()
        contracts: Dict[str, Contract] = {}
        for inst in instruments:
            try:
                c = Contract.from_info(inst, "crypto")
                contracts[c.symbol] = c
            except Exception as e:
                logger.warning(f"Skipping instrument {inst.get('instrument_name')}: {e}")
        self._add_log(f"Loaded {len(contracts)} trading contracts.")
        return contracts

    def get_order_book(
        self, instrument_name: str, depth: int = 10
    ) -> Dict[str, Any]:
        try:
            resp = self.session.get(
                f"{self.base_url}/public/get-book",
                params={"instrument_name": instrument_name, "depth": depth},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("result", {}).get("data", [])
            if data:
                snap = data[0]
                return {"bids": snap.get("bids", []), "asks": snap.get("asks", [])}
            return {"bids": [], "asks": []}
        except Exception as e:
            logger.error(f"get_order_book error: {e}")
            self._add_log(f"Failed to fetch order book for {instrument_name}")
            return {"bids": [], "asks": []}

    def get_trades(
        self, instrument_name: str, count: int = 100
    ) -> List[Dict[str, Any]]:
        try:
            resp = self.session.get(
                f"{self.base_url}/public/get-trades",
                params={"instrument_name": instrument_name, "count": count},
                timeout=10,
            )
            resp.raise_for_status()
            trades = resp.json().get("result", {}).get("data", [])
            logger.info(f"Fetched {len(trades)} trades for {instrument_name}.")
            return trades
        except Exception as e:
            logger.error(f"get_trades error: {e}")
            self._add_log(f"Failed to fetch trades for {instrument_name}")
            return []

    def get_historical_candles(
        self,
        instrument_name: str,
        interval: str,
        count: int = 25,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> List[Candle]:
        params: Dict[str, Any] = {"instrument_name": instrument_name, "timeframe": interval, "count": count}
        if start_ts:
            params["start_ts"] = start_ts
        if end_ts:
            params["end_ts"] = end_ts
        try:
            resp = self.session.get(
                f"{self.base_url}/public/get-candlestick", params=params, timeout=10
            )
            resp.raise_for_status()
            data = resp.json().get("result", {}).get("data", [])
            candles = [
                Candle(
                    timestamp=int(item["t"]),
                    open=float(item["o"]),
                    high=float(item["h"]),
                    low=float(item["l"]),
                    close=float(item["c"]),
                    volume=float(item["v"]),
                )
                for item in data
            ]
            logger.info(f"Fetched {len(candles)} candles for {instrument_name}.")
            return candles
        except Exception as e:
            logger.error(f"get_historical_candles error: {e}")
            self._add_log(f"Failed to fetch historical data for {instrument_name}")
            return []

    def get_account_summary(self) -> List[Dict[str, Any]]:
        """Private account balances via JSON-RPC."""
        result = self._rpc("private/user-balance", {})
        logger.debug(f"Raw account summary result: {result}")
        data = result.get("data", [])
        logger.info(f"Fetched {len(data)} account balances.")
        return data

    def _load_balances(self) -> Dict[str, Balance]:
        entries = self.get_account_summary()
        balances = {e["currency"]: Balance.from_info(e, "crypto") for e in entries}
        self._add_log(f"Loaded {len(balances)} account balances.")
        return balances

    def create_order(
        self,
        instrument_name: str,
        side: str,
        type_: str,
        quantity: Union[str, float],
        price: Optional[Union[str, float]] = None,
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "instrument_name": instrument_name,
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": str(quantity),
        }
        if type_.upper() == "LIMIT":
            if price is None:
                raise ValueError("Price required for LIMIT orders")
            params["price"] = str(price)
        if client_oid:
            params["client_oid"] = client_oid
        result = self._rpc("private/create-order", params)
        self._add_log(f"Created order for {instrument_name}: {result}")
        return result

    def cancel_order(
        self, order_id: str, instrument_name: str
    ) -> Dict[str, Any]:
        result = self._rpc("private/cancel-order", {
            "order_id": order_id,
            "instrument_name": instrument_name,
        })
        self._add_log(f"Cancelled order {order_id} for {instrument_name}")
        return result

    # WebSocket handling (market data only)
    def _start_ws(self):
        try:
            ws = websocket.WebSocketApp(
                self.ws_market_url,
                on_open=lambda ws: self._add_log("WS connected"),
                on_message=lambda ws, msg: None,
                on_error=lambda ws, err: logger.error(f"WS error: {err}"),
                on_close=lambda ws, code, msg: self._add_log(f"WS closed: {code}")
            )
            ws.run_forever()
        except Exception as e:
            logger.error(f"WebSocket failed: {e}")
