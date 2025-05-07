import time
import hmac
import hashlib
import logging
import requests
import traceback
from typing import Dict, Any, List, Union

from secret_keys import Secrets
from models import Candle


logger = logging.getLogger(__name__)


class CryptoExchangeClient:
    """
    Crypto.com Exchange API v1 REST client.

    Implements a clean interface to the Crypto.com Exchange v1 API with support
    for both public and private endpoints.
    """

    BASE_URL = "https://api.crypto.com/exchange/v1"
    MAX_RETRIES = 3
    MAX_LEVEL = 3  # Maximum recursion level for params encoding

    def __init__(self, base_url: str = BASE_URL):
        """
        Initialize the Crypto.com Exchange client.

        Args:
            base_url: Base API URL (defaults to BASE_URL)
        """
        self.base_url = base_url.rstrip("/")

        try:
            # Load API credentials
            self.api_key = Secrets.CRYPTO_API_KEY
            self.api_secret = Secrets.CRYPTO_API_SECRET

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
    # Public Endpoints
    # ----------------------------

    def get_instruments(self) -> List[Dict[str, Any]]:
        """
        Fetch all available trading instruments.

        Returns:
            List of instrument details
        """
        url = f"{self.base_url}/public/get-instruments"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """
        Fetch order book for a given instrument.

        Args:
            instrument_name: Trading pair symbol (e.g., "BTC_USDT")
            depth: Order book depth (number of price levels)

        Returns:
            Order book with bids and asks
        """
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
            return {
                "bids": book_snapshot.get("bids", []),
                "asks": book_snapshot.get("asks", []),
            }
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
        url = f"{self.base_url}/public/get-trades"
        params = {"instrument_name": instrument_name, "count": count}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])
    
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
        return candles

    # ----------------------------
    # Private Endpoints
    # ----------------------------

    def get_account_summary(self) -> List[Dict[str, Any]]:
        """
        Fetch wallet balances.

        Returns:
            List of account balances
        """
        result = self._rpc("private/user-balance", {})
        return result.get("data", [])

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
        params = {
            "instrument_name": instrument_name,
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": quantity,
        }
        if type_.upper() == "LIMIT" and price is not None:
            params["price"] = price
        elif type_.upper() == "LIMIT" and price is None:
            raise ValueError("Price is required for LIMIT orders.")

        if client_oid:
            params["client_oid"] = client_oid

        return self._rpc("private/create-order", params)

    def cancel_order(self, order_id: str, instrument_name: str) -> Dict[str, Any]:
        """
        Cancel an order by ID.

        Args:
            order_id: The order ID to cancel
            instrument_name: Trading pair symbol

        Returns:
            Cancellation result
        """
        params = {"order_id": order_id, "instrument_name": instrument_name}
        return self._rpc("private/cancel-order", params)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a specific order.

        Args:
            order_id: The order ID string

        Returns:
            Order details
        """
        params = {"order_id": order_id}
        return self._rpc("private/get-order-detail", params)

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
        params: Dict[str, Any] = {"page_size": page_size, "page": page}
        if instrument_name:
            params["instrument_name"] = instrument_name
        result = self._rpc("private/get-open-orders", params)
        return result.get("order_list", result.get("data", []))
