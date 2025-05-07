import time
import hmac
import hashlib
import logging
import requests
import traceback
from typing import Dict, Any, List, Union

from secret_keys import Secrets

logger = logging.getLogger(__name__)


class CryptoExchangeClient:
    """
    Crypto.com Exchange API v1 REST client with updated endpoints and signature.
    
    Key updates:
    - Properly implements the signature format according to official documentation
    - Updated endpoint paths to Exchange v1 API
    - Corrected response parsing for each endpoint
    """

    BASE_URL = "https://api.crypto.com/exchange/v1"
    MAX_RETRIES = 3
    # Maximum recursion level for params encoding
    MAX_LEVEL = 3

    def __init__(self, base_url: str = BASE_URL):
        # Always initialize instance attributes first
        self.base_url = base_url.rstrip("/")
        
        try:
            # Load API credentials into instance attributes
            self.api_key = Secrets.CRYPTO_API_KEY
            self.api_secret = Secrets.CRYPTO_API_SECRET
            
            if not self.api_key:
                logger.warning("API Key is None or empty - private endpoints will fail")
            if not self.api_secret:
                logger.warning("API Secret is None or empty - private endpoints will fail")
                
            logger.debug(f"Successfully initialized CryptoExchangeClient with base_url={self.base_url}")
            logger.debug(f"API Key: {self.api_key[:4] if self.api_key else 'None'}... (Length: {len(self.api_key) if self.api_key else 0})")
            
        except AttributeError as e:
            logger.critical(f"CRITICAL FAILURE: Could not retrieve API key/secret from the Secrets module. Error: {e}")
            logger.critical("Ensure CRYPTO_API_KEY and CRYPTO_API_SECRET are correctly defined in your secret_keys.py (or the .env file it reads from).")
            raise ValueError("Failed to load API credentials from Secrets module.") from e

    def _get_nonce(self) -> int:
        """Generate nonce using local time in milliseconds"""
        return int(time.time() * 1000)

    def _params_to_str(self, obj: Any, level: int) -> str:
        """
        Convert params to string for signature generation, exactly as specified in the docs.
        
        Args:
            obj: The parameter object to convert
            level: Current recursion level
            
        Returns:
            String representation of parameters for signature
        """
        if level >= self.MAX_LEVEL:
            return str(obj)
            
        if obj is None:
            return 'null'
            
        if isinstance(obj, dict):
            return_str = ""
            for key in sorted(obj.keys()):  # Sort keys alphabetically
                return_str += key
                if obj[key] is None:
                    return_str += 'null'
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
        Execute JSON-RPC call with retries and correct signature logic.
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
                    sig_base_str = method + str(payload["id"]) + self.api_key + param_str + str(payload["nonce"])
                    
                    logger.debug(f"Signature base string: '{sig_base_str}'")

                    # Generate HMAC-SHA256 signature
                    payload["sig"] = hmac.new(
                        bytes(str(self.api_secret), 'utf-8'),
                        msg=bytes(sig_base_str, 'utf-8'),
                        digestmod=hashlib.sha256
                    ).hexdigest()
                    
                    logger.debug(f"Generated Signature: {payload['sig']}")

                url = f"{self.base_url}/{method}"
                logger.debug(f"Request URL: POST {url}")
                logger.debug(f"Request Payload (JSON): {payload}")

                resp = requests.post(url, json=payload, timeout=10)

                logger.debug(f"Response Status Code: {resp.status_code}")
                logger.debug(f"Response Headers: {resp.headers}")
                response_text = resp.text
                logger.debug(f"Response Body (raw): {response_text}")

                # Try to parse JSON, handle potential errors if not JSON
                try:
                    data = resp.json()
                except requests.exceptions.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from response. Raw text: {response_text}")
                    if resp.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"Auth error (HTTP {resp.status_code}), retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    resp.raise_for_status()
                    raise

                # Check for API-level errors in the response body (Crypto.com standard: code=0 for success)
                if data.get("code", 0) != 0:
                    api_error_code = data.get('code')
                    api_error_message = data.get('message', 'No message provided.')
                    logger.error(f"API Error in response: Code {api_error_code}, Message: '{api_error_message}'")
                    # Specific handling for auth failure code like 40101
                    if api_error_code == 40101 and attempt < self.MAX_RETRIES - 1:
                         logger.warning(f"API Auth error code {api_error_code}, retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                         time.sleep(0.5 * (attempt + 1))
                         continue
                    raise ValueError(f"API Error {api_error_code}: {api_error_message}")

                return data.get("result", {})

            except requests.HTTPError as e:
                logger.error(f"HTTP Error: {e.response.status_code} {e.response.reason} for URL {e.request.url if e.request else url}")
                logger.error(f"Response body: {e.response.text if e.response else 'No response object'}")
                if e.response is not None and e.response.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                    logger.warning("Auth error (HTTP 401), retrying (%d/%d)...", attempt + 1, self.MAX_RETRIES)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
            except Exception as e:
                logger.error(f"RPC call for method '{method}' failed: {str(e)}")
                logger.debug(traceback.format_exc())
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("Retrying (%d/%d) after exception...", attempt + 1, self.MAX_RETRIES)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"Failed after {self.MAX_RETRIES} attempts for method {method}")

    # ----------------------------
    # Public Endpoints
    # ----------------------------

    def get_instruments(self) -> List[Dict[str, Any]]:
        """Fetch all available trading instruments"""
        url = f"{self.base_url}/public/get-instruments"
        logger.debug(f"Request URL: GET {url}")
        resp = requests.get(url, timeout=10)
        logger.debug(f"Response Status Code: {resp.status_code}")
        logger.debug(f"Response Body (raw): {resp.text}")
        resp.raise_for_status()
        # Important: Use the correct path to the instruments data
        return resp.json().get("result", {}).get("data", [])

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """Fetch order book for a given instrument"""
        url = f"{self.base_url}/public/get-book"
        params = {"instrument_name": instrument_name, "depth": str(depth)}
        logger.debug(f"Request URL: GET {url} with params {params}")
        resp = requests.get(url, params=params, timeout=10)
        logger.debug(f"Response Status Code: {resp.status_code}")
        logger.debug(f"Response Body (raw): {resp.text}")
        resp.raise_for_status()
        
        result_data = resp.json().get("result", {})
        book_data_list = result_data.get("data", [])

        if book_data_list and isinstance(book_data_list, list) and len(book_data_list) > 0:
            book_snapshot = book_data_list[0]
            return {
                "bids": book_snapshot.get("bids", []),
                "asks": book_snapshot.get("asks", [])
            }
        logger.warning(f"Order book data for {instrument_name} was empty or not in expected list format. Result data: {result_data}")
        return {"bids": [], "asks": []}

    def get_trades(self, instrument_name: str, count: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent trades for a given instrument"""
        url = f"{self.base_url}/public/get-trades"
        params = {"instrument_name": instrument_name, "count": count}
        logger.debug(f"Request URL: GET {url} with params {params}")
        resp = requests.get(url, params=params, timeout=10)
        logger.debug(f"Response Status Code: {resp.status_code}")
        logger.debug(f"Response Body (raw): {resp.text}")
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
        client_oid: Union[str, None] = None,
    ) -> Dict[str, Any]:
        """Create a new order"""
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
        """Cancel an order by ID. Instrument name is often required."""
        params = {"order_id": order_id, "instrument_name": instrument_name}
        return self._rpc("private/cancel-order", params)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Get order details"""
        params = {"order_id": order_id}
        return self._rpc("private/get-order-detail", params)

    def get_open_orders(self, instrument_name: Union[str, None] = None, page_size: int = 20, page: int = 0) -> List[Dict[str, Any]]:
        """Get open orders for an instrument (or all if instrument_name is None and API supports it)."""
        params: Dict[str, Any] = {"page_size": page_size, "page": page}
        if instrument_name:
            params["instrument_name"] = instrument_name
        result = self._rpc("private/get-open-orders", params)
        return result.get("order_list", result.get("data", []))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    client = CryptoExchangeClient()
    try:
        print("=== Testing Public Methods ===")
        instruments = client.get_instruments()
        print(f"Instruments (first 2): {instruments[:2]}")
        if instruments:
            test_instrument_from_list = instruments[0]['symbol']
            print(f"Order Book for {test_instrument_from_list}:", client.get_order_book(test_instrument_from_list))
            print(f"Trades for {test_instrument_from_list}:", client.get_trades(test_instrument_from_list)[:2])
        else:
            print("No instruments found to test order book and trades.")

        print("\n=== Testing Private Methods ===")
        balances = client.get_account_summary()
        print("Account Summary/Balances:", balances)

    except Exception as e:
        logger.error("Main test execution failed: %s", str(e))
        logger.debug(traceback.format_exc())