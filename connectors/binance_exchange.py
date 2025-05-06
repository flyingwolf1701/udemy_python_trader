import time
import hmac
import hashlib
import logging
import requests
from typing import Dict, Any, List, Union

from secret_keys import Secrets

logger = logging.getLogger(__name__)


class CryptoExchangeClient:
    """
    Client for Crypto.com Exchange v1 REST/JSON-RPC API.

    Public endpoints (GET):
      - /public/get-instruments
      - /public/get-book
      - /public/get-trades

    Private endpoints (POST JSON-RPC):
      - /private/user-balance
      - /private/create-order
      - /private/cancel-order
      - etc.

    Signature for private calls:
      sig = HMAC_SHA256(secret, method + id + api_key + paramString + nonce)
    where paramString is the deterministic concatenation of sorted param keys & values recursively.

    Docs: https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html
    """

    BASE_URL = "https://api.crypto.com/exchange/v1"

    def __init__(self, base_url: str = BASE_URL):
        self.api_key = Secrets.CRYPTO_API_KEY
        self.api_secret = Secrets.CRYPTO_API_SECRET.encode()
        self.base_url = base_url.rstrip("/")

    # ----------------------------
    # Public REST endpoints (GET)
    # ----------------------------

    def get_instruments(self) -> List[Dict[str, Any]]:
        """Fetch all available trading instruments."""
        url = f"{self.base_url}/public/get-instruments"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """Fetch order book for a given instrument."""
        url = f"{self.base_url}/public/get-book"
        params = {"instrument_name": instrument_name, "depth": depth}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("result", {}).get("data", [])
        if data:
            book = data[0]
            return {"bids": book.get("bids", []), "asks": book.get("asks", [])}
        return {"bids": [], "asks": []}

    def get_trades(self, instrument_name: str, count: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent trades for a given instrument."""
        url = f"{self.base_url}/public/get-trades"
        params = {"instrument_name": instrument_name, "count": count}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])

    # --------------------------------
    # Helper: signature + RPC POST
    # --------------------------------

    @staticmethod
    def _encode_params(obj: Union[Dict[str, Any], List[Any], Any], level: int = 0) -> str:
        """
        Recursively encode parameters into a deterministic string for signing.

        Args:
            obj: The parameter object (dict, list, or primitive).
            level: Recursion depth to avoid infinite loops.

        Returns:
            A deterministic string representation of the parameters.
        """
        if level > 10:
            # Safety check to prevent infinite recursion
            return str(obj)

        if isinstance(obj, dict):
            # Sort keys and recursively encode values
            return "".join(
                f"{k}{CryptoExchangeClient._encode_params(v, level + 1)}"
                for k, v in sorted(obj.items())
            )
        if isinstance(obj, list):
            # Recursively encode each element
            return "".join(CryptoExchangeClient._encode_params(v, level + 1) for v in obj)

        # Primitive type: convert to string
        return str(obj)

    def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make a JSON-RPC POST request to the Crypto.com API, signing if private.

        Args:
            method: The API method name (e.g., "private/create-order").
            params: The parameters dictionary.

        Returns:
            The 'result' field from the API response.

        Raises:
            requests.HTTPError: For HTTP errors.
            ValueError: For API response errors.
        """
        nonce = int(time.time() * 1000)
        payload: Dict[str, Any] = {
            "id": nonce,
            "method": method,
            "params": params or {},
            "nonce": nonce,
        }

        if method.startswith("private/"):
            payload["api_key"] = self.api_key
            param_str = self._encode_params(payload["params"])
            # Correct signature construction per docs:
            sig_base = f"{method}{payload['id']}{self.api_key}{param_str}{nonce}"
            signature = hmac.new(
                self.api_secret, sig_base.encode(), hashlib.sha256
            ).hexdigest()
            payload["sig"] = signature

        url = f"{self.base_url}/{method}"
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code", 0) != 0:
            error_msg = data.get("message", "Unknown error")
            raise ValueError(f"API error {method}: code={data.get('code')} message={error_msg}")

        return data.get("result", {})

    # --------------------------------
    # Private account / trading endpoints
    # --------------------------------

    def get_account_summary(self) -> List[Dict[str, Any]]:
        """
        Get wallet balances.

        Returns:
            List of balance dicts.
        """
        result = self._rpc("private/user-balance", {})
        return result.get("data", [])

    def create_order(
        self,
        instrument_name: str,
        side: str,
        type_: str,
        quantity: str,
        price: str | None = None,
    ) -> Dict[str, Any]:
        """
        Create a new order.

        Args:
            instrument_name: Trading pair symbol, e.g., "BTC_USDT".
            side: "BUY" or "SELL".
            type_: Order type, e.g., "LIMIT" or "MARKET".
            quantity: Order quantity as string.
            price: Price as string (required for LIMIT orders).

        Returns:
            Order details dict.
        """
        params: Dict[str, Any] = {
            "instrument_name": instrument_name,
            "side": side,
            "type": type_,
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price

        result = self._rpc("private/create-order", params)
        return result.get("data", {})

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an order by ID.

        Args:
            order_id: The order ID string.

        Returns:
            Cancellation result dict.
        """
        result = self._rpc("private/cancel-order", {"order_id": order_id})
        return result.get("data", {})

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a specific order.

        Args:
            order_id: The order ID string.

        Returns:
            Order details dict.
        """
        result = self._rpc("private/get-order-detail", {"order_id": order_id})
        return result.get("data", {})

    def get_open_orders(self, instrument_name: str) -> List[Dict[str, Any]]:
        """
        Get all open orders for a given instrument.

        Args:
            instrument_name: Trading pair symbol.

        Returns:
            List of open orders.
        """
        result = self._rpc("private/get-open-orders", {"instrument_name": instrument_name})
        return result.get("data", [])


# Example usage (uncomment to test):
# if __name__ == "__main__":
#     client = CryptoExchangeClient()
#     print(client.get_instruments()[:3])
