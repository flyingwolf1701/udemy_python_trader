import time
import hmac
import hashlib
import logging
import requests
from typing import Dict, Any, List, Union

from secret_keys import Secrets  # Your API key and secret here

logger = logging.getLogger(__name__)


class CryptoExchangeClient:
    """
    Crypto.com Exchange API v1 REST client with updated endpoints and signature.

    Key updates:
    - Removed deprecated 'public/get-time' call (no server time sync needed)
    - Updated endpoint paths to Exchange v1 API
    - Updated signature base string format
    """

    BASE_URL = "https://api.crypto.com/exchange/v1"
    MAX_RETRIES = 3

    def __init__(self, base_url: str = BASE_URL):
        self.api_key = Secrets.CRYPTO_API_KEY
        self.api_secret = Secrets.CRYPTO_API_SECRET.encode()
        self.base_url = base_url.rstrip("/")
        self.time_offset = 0  # No server time sync needed for Exchange v1

    def _get_nonce(self) -> int:
        """Generate nonce using local time in milliseconds"""
        return int(time.time() * 1000)

    @staticmethod
    def _encode_params(obj: Union[Dict[str, Any], List[Any], Any], level: int = 0) -> str:
        """Encode parameters with case-sensitive sorting"""
        if isinstance(obj, dict):
            return "".join(
                f"{k}{CryptoExchangeClient._encode_params(v, level+1)}"
                for k, v in sorted(obj.items(), key=lambda x: x[0])
            )
        if isinstance(obj, list):
            return "".join(CryptoExchangeClient._encode_params(v, level+1) for v in obj)
        return str(obj)


    def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JSON-RPC call with retries and updated signature logic.

        Signature base string format:
        "{method}{id}{nonce}{param_str}"
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
                    param_str = self._encode_params(payload["params"])
                    # Updated signature base string without api_key inside signature base
                    sig_base = f"{method}{payload['id']}{nonce}{param_str}" 
                    logger.debug("Signature Base: %s", sig_base)
                    logger.debug("Secret Key: %s...", self.api_secret[:4])
                    payload["sig"] = hmac.new(
                        self.api_secret, sig_base.encode(), hashlib.sha256
                    ).hexdigest()
                    logger.debug("Generated Signature: %s", payload["sig"][0:8] + "...")

                url = f"{self.base_url}/{method}"
                resp = requests.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code", 0) != 0:
                    raise ValueError(f"API Error {data.get('code')}: {data.get('message')}")

                return data.get("result", {})

            except requests.HTTPError as e:
                if e.response.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                    logger.warning("Auth error, retrying (%d/%d)...", attempt + 1, self.MAX_RETRIES)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.error("HTTP %d: %s", e.response.status_code, e.response.text)
                raise
            except Exception as e:
                logger.error("RPC call failed: %s", str(e))
                raise

        raise RuntimeError(f"Failed after {self.MAX_RETRIES} attempts")

    # ----------------------------
    # Public Endpoints
    # ----------------------------

    def get_instruments(self) -> List[Dict[str, Any]]:
        """Fetch all available trading instruments"""
        url = f"{self.base_url}/public/get-instruments"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """Fetch order book for a given instrument"""
        url = f"{self.base_url}/public/get-book"
        params = {"instrument_name": instrument_name, "depth": depth}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("result", {}).get("data", [])
        if data:
            entry = data[0]
            return {"bids": entry.get("bids", []), "asks": entry.get("asks", [])}
        return {"bids": [], "asks": []}

    def get_trades(self, instrument_name: str, count: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent trades for a given instrument"""
        url = f"{self.base_url}/public/get-trades"
        params = {"instrument_name": instrument_name, "count": count}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("data", [])

    # ----------------------------
    # Private Endpoints
    # ----------------------------

    def get_account_summary(self) -> List[Dict[str, Any]]:
        """Fetch wallet balances"""
        result = self._rpc("private/user-balance", {})
        return result.get("data", [])

    def create_order(
        self,
        instrument_name: str,
        side: str,
        type_: str,
        quantity: str,
        price: Union[str, None] = None,
    ) -> Dict[str, Any]:
        """Create a new order"""
        params = {
            "instrument_name": instrument_name,
            "side": side,
            "type": type_,
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price
        return self._rpc("private/create-order", params).get("data", {})

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order by ID"""
        return self._rpc("private/cancel-order", {"order_id": order_id}).get("data", {})

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details"""
        return self._rpc("private/get-order-detail", {"order_id": order_id}).get("data", {})

    def get_open_orders(self, instrument_name: str) -> List[Dict[str, Any]]:
        """Get open orders for an instrument"""
        return self._rpc("private/get-open-orders", {"instrument_name": instrument_name}).get("data", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    client = CryptoExchangeClient()
    try:
        print("=== Testing Public Methods ===")
        print("Instruments:", client.get_instruments()[:2])
        print("Order Book:", client.get_order_book("BTC_USDT"))
        print("\n=== Testing Private Methods ===")
        balances = client.get_account_summary()
        print("Account Balances:", balances)
    except Exception as e:
        logger.error("Test failed: %s", str(e))
