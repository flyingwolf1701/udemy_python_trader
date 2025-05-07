import time
import hmac
import hashlib
import logging
import requests
import traceback # Added for full traceback logging
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
        self.api_secret = Secrets.CRYPTO_API_SECRET.encode('utf-8') # Ensure utf-8 encoding
        self.base_url = base_url.rstrip("/")
        self.time_offset = 0  # No server time sync needed for Exchange v1 (Verify this)

    def _get_nonce(self) -> int:
        """Generate nonce using local time in milliseconds"""
        return int(time.time() * 1000)

    @staticmethod
    def _encode_params(obj: Union[Dict[str, Any], List[Any], Any], level: int = 0) -> str:
        """Recursively encode parameters with deterministic sorting"""
        if level > 10: # Max recursion depth
            return str(obj) # Fallback for very deep objects
        if isinstance(obj, dict):
            if not obj: # Handle empty dictionary case
                return ""
            return "".join(
                f"{k}{CryptoExchangeClient._encode_params(v, level + 1)}"
                for k, v in sorted(obj.items()) # Sort keys for consistent ordering
            )
        if isinstance(obj, list):
            if not obj: # Handle empty list case
                return ""
            return "".join(CryptoExchangeClient._encode_params(v, level + 1) for v in obj) # Process elements in order

        # For non-dict/list types, convert to string.
        # Ensure boolean True/False are stringified consistently if API expects that (e.g. "true"/"false")
        # Crypto.com API usually takes actual JSON booleans, so str() is generally fine.
        return str(obj)


    def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JSON-RPC call with retries and updated signature logic.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                nonce = self._get_nonce()
                payload: Dict[str, Any] = {
                    "id": nonce,
                    "method": method,
                    "params": params or {}, # Ensure params is always a dict
                    "nonce": nonce,
                }

                if method.startswith("private/"):
                    payload["api_key"] = self.api_key
                    # Critical: Ensure payload["params"] are sorted alphabetically by key
                    # if the API requires it for the param_str. The _encode_params handles this.
                    param_str = self._encode_params(payload["params"])

                    # --------------- DETAILED LOGGING FOR SIGNATURE ---------------
                    logger.debug(f"--- Signature Generation Details (Attempt {attempt + 1}) ---")
                    logger.debug(f"Method: {method}")
                    logger.debug(f"Request ID (payload['id']): {payload['id']}")
                    logger.debug(f"Nonce (payload['nonce']): {payload['nonce']}")
                    logger.debug(f"API Key: {payload['api_key']}")
                    logger.debug(f"Raw Params (payload['params']): {payload['params']}")
                    logger.debug(f"Encoded Params (param_str): '{param_str}'")

                    # THIS IS THE MOST CRITICAL PART TO VERIFY WITH OFFICIAL DOCS:
                    # The signature base string format. Your current code: method + id + nonce + param_str
                    # A common format for Crypto.com (e.g., v2 Spot API) is:
                    # METHOD + ID + API_KEY + PARAMS_STRING + NONCE
                    # Example: sig_base_str = f"{method}{payload['id']}{payload['api_key']}{param_str}{payload['nonce']}"

                    sig_base_str = f"{method}{payload['id']}{payload['nonce']}{param_str}" # Your current base string
                    logger.debug(f"Current sig_base string (to be hashed): '{sig_base_str}'")
                    # Log an alternative if you suspect it, e.g.:
                    # alt_sig_base_str = f"{method}{payload['id']}{payload['api_key']}{param_str}{payload['nonce']}"
                    # logger.debug(f"Alternative sig_base (example for comparison): '{alt_sig_base_str}'")


                    payload["sig"] = hmac.new(
                        self.api_secret, sig_base_str.encode('utf-8'), hashlib.sha256
                    ).hexdigest()
                    logger.debug(f"Secret Key Used (first 4 chars): {self.api_secret[:4].decode(errors='ignore')}...")
                    logger.debug(f"Generated Signature (sig): {payload['sig']}")
                    logger.debug("--- End Signature Generation Details ---")
                    # --------------- END DETAILED LOGGING ---------------

                url = f"{self.base_url}/{method}"
                logger.debug(f"Request URL: POST {url}")
                logger.debug(f"Request Payload (JSON): {payload}") # This will be sent as JSON body

                resp = requests.post(url, json=payload, timeout=10) # Send as JSON

                logger.debug(f"Response Status Code: {resp.status_code}")
                logger.debug(f"Response Headers: {resp.headers}")
                # It's good practice to check content-type before assuming JSON
                response_text = resp.text
                logger.debug(f"Response Body (raw): {response_text}")

                # Try to parse JSON, handle potential errors if not JSON
                try:
                    data = resp.json()
                except requests.exceptions.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from response. Raw text: {response_text}")
                    # If auth error is indicated by status code, retry or raise
                    if resp.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                        logger.warning(f"Auth error (HTTP {resp.status_code}), retrying ({attempt + 1}/{self.MAX_RETRIES})...")
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    resp.raise_for_status() # Re-raise the original HTTPError if it was an HTTP error status
                    raise # Or raise a new error indicating JSON decode failure for non-HTTP error status

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

                return data.get("result", {}) # Assuming "result" field contains the useful data

            except requests.HTTPError as e:
                # This block catches 4xx/5xx errors raised by resp.raise_for_status()
                # or if manually re-raised after JSON decode failure with an HTTP error status
                logger.error(f"HTTP Error: {e.response.status_code} {e.response.reason} for URL {e.request.url if e.request else url}")
                logger.error(f"Response body: {e.response.text if e.response else 'No response object'}")
                if e.response is not None and e.response.status_code == 401 and attempt < self.MAX_RETRIES - 1:
                    logger.warning("Auth error (HTTP 401), retrying (%d/%d)...", attempt + 1, self.MAX_RETRIES)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise # Re-raise the HTTPError if it's not a 401 or if it's the last attempt
            except Exception as e:
                logger.error(f"RPC call for method '{method}' failed: {str(e)}")
                logger.debug(traceback.format_exc()) # Print full traceback for unexpected exceptions
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("Retrying (%d/%d) after exception...", attempt + 1, self.MAX_RETRIES)
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise # Re-raise the exception if it's the last attempt

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
        return resp.json().get("result", {}).get("instruments", []) # Adjusted based on typical crypto.com structure

    def get_order_book(self, instrument_name: str, depth: int = 10) -> Dict[str, Any]:
        """Fetch order book for a given instrument"""
        url = f"{self.base_url}/public/get-book"
        params = {"instrument_name": instrument_name, "depth": str(depth)} # Depth might need to be string
        logger.debug(f"Request URL: GET {url} with params {params}")
        resp = requests.get(url, params=params, timeout=10)
        logger.debug(f"Response Status Code: {resp.status_code}")
        logger.debug(f"Response Body (raw): {resp.text}")
        resp.raise_for_status()
        # Assuming structure: {"result": {"instrument_name": "...", "depth": ..., "data": [{"bids": [], "asks": [], "t": ...}]}}
        # Or sometimes it's {"result": {"data": [{"bids": [], "asks": [], "t": ...}], "instrument_name": "...", "depth": ...}}
        result_data = resp.json().get("result", {})
        book_data_list = result_data.get("data", []) # "data" is usually a list containing the book snapshot(s)

        if book_data_list and isinstance(book_data_list, list) and len(book_data_list) > 0:
            # Assuming the first element in the 'data' list is the order book we want
            book_snapshot = book_data_list[0]
            return {
                "bids": book_snapshot.get("bids", []),
                "asks": book_snapshot.get("asks", [])
            }
        logger.warning(f"Order book data for {instrument_name} was empty or not in expected list format. Result data: {result_data}")
        return {"bids": [], "asks": []}


    def get_trades(self, instrument_name: str, count: int = 100) -> List[Dict[str, Any]]:
        """Fetch recent trades for a given instrument"""
        # Note: Crypto.com v2 API calls this public/get-trades, params might vary
        # For v1, let's assume it's similar or check docs
        url = f"{self.base_url}/public/get-trades"
        params = {"instrument_name": instrument_name} # Count might not be supported or named differently.
        # If `count` is a parameter, it should be added: params["count"] = count
        logger.debug(f"Request URL: GET {url} with params {params}")
        resp = requests.get(url, params=params, timeout=10)
        logger.debug(f"Response Status Code: {resp.status_code}")
        logger.debug(f"Response Body (raw): {resp.text}")
        resp.raise_for_status()
        # Assuming structure: {"result": {"data": [...]}}
        return resp.json().get("result", {}).get("data", [])

    # ----------------------------
    # Private Endpoints
    # ----------------------------

    def get_account_summary(self) -> List[Dict[str, Any]]: # API docs suggest this might be private/get-account-summary
        """Fetch wallet balances.
        Crypto.com v1 API might be `private/get-account-summary` with no params,
        or `private/user-balance` as you have.
        The response for `private/get-account-summary` is usually `{"result": {"accounts": [...]}}`
        The response for `private/user-balance` (if it exists) might be different.
        """
        # Double check the method name and expected response structure from API docs.
        # Your code uses private/user-balance and expects result.data
        # Crypto.com V2 uses private/get-account-summary and result.accounts
        result = self._rpc("private/user-balance", {})
        # If the structure is {"result": {"balance": [...]}} or similar
        return result.get("data", []) # Keep as is if your API version expects 'data'
                                      # otherwise, it might be result.get("accounts", []) for example.

    def create_order(
        self,
        instrument_name: str,
        side: str, # "BUY" or "SELL"
        type_: str, # e.g. "LIMIT", "MARKET"
        quantity: str, # Use string for precision
        price: Union[str, None] = None, # Use string for precision, required for LIMIT
        client_oid: Union[str, None] = None, # Optional client order ID
    ) -> Dict[str, Any]:
        """Create a new order"""
        params = {
            "instrument_name": instrument_name,
            "side": side.upper(),
            "type": type_.upper(),
            "quantity": quantity, # Ensure this is string if API needs precise decimal
        }
        if type_.upper() == "LIMIT" and price is not None:
            params["price"] = price # Ensure this is string
        elif type_.upper() == "LIMIT" and price is None:
            raise ValueError("Price is required for LIMIT orders.")

        if client_oid:
            params["client_oid"] = client_oid

        # The method name might be private/create-order or private/exchange/create-order
        # Response usually contains "order_id"
        return self._rpc("private/create-order", params) # .get("data", {}) - RPC already gets result

    def cancel_order(self, order_id: str, instrument_name: str) -> Dict[str, Any]: # instrument_name often required
        """Cancel an order by ID. Instrument name is often required."""
        params = {"order_id": order_id, "instrument_name": instrument_name}
        # Method name could be private/cancel-order or private/exchange/cancel-order etc.
        return self._rpc("private/cancel-order", params)

    def get_order(self, order_id: str) -> Dict[str, Any]: # instrument_name might also be useful/required
        """Get order details"""
        params = {"order_id": order_id}
        # Method name like private/get-order-detail or private/exchange/get-order-details
        return self._rpc("private/get-order-detail", params) # .get("data", {})

    def get_open_orders(self, instrument_name: Union[str, None] = None, page_size: int = 20, page: int = 0) -> List[Dict[str, Any]]:
        """Get open orders for an instrument (or all if instrument_name is None and API supports it)."""
        params: Dict[str, Any] = {"page_size": page_size, "page": page}
        if instrument_name:
            params["instrument_name"] = instrument_name
        # Method name could be private/get-open-orders or private/exchange/get-open-orders
        # Response often result.order_list
        result = self._rpc("private/get-open-orders", params)
        return result.get("order_list", result.get("data", [])) # Adjust based on actual response


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
            test_instrument_from_list = instruments[0]['instrument_name']
            print(f"Order Book for {test_instrument_from_list}:", client.get_order_book(test_instrument_from_list))
            print(f"Trades for {test_instrument_from_list}:", client.get_trades(test_instrument_from_list)[:2])
        else:
            print("No instruments found to test order book and trades.")

        print("\n=== Testing Private Methods ===")
        # This will likely fail if signature is still an issue, but debug logs will be helpful
        balances = client.get_account_summary()
        print("Account Summary/Balances:", balances)

        # Example: Create and Cancel Order (CAUTION: THIS WILL PLACE A REAL ORDER IF AUTH WORKS)
        # You would need funds and a valid instrument.
        # Ensure API keys have trading permissions.
        # print("\n=== Testing Order Creation (Example - CAUTION) ===")
        # if instruments:
        #     sample_instrument = "CRO_USDT" # Choose a valid instrument you can trade
        #     if any(inst['instrument_name'] == sample_instrument for inst in instruments):
        #         try:
        #             # Example: create a very small LIMIT BUY order, far from market price to avoid execution
        #             # THIS IS A LIVE TEST - BE CAREFUL
        #             # new_order = client.create_order(
        #             #     instrument_name=sample_instrument,
        #             #     side="BUY",
        #             #     type_="LIMIT",
        #             #     quantity="1", # Smallest possible quantity
        #             #     price="0.0001" # Price far from market
        #             # )
        #             # print(f"Create Order Response: {new_order}")
        #             # order_id_to_check = new_order.get("order_id")
        #             # if order_id_to_check:
        #             #     print(f"Get Order Detail for {order_id_to_check}:", client.get_order(order_id_to_check))
        #             #     # print(f"Cancelling order {order_id_to_check}:", client.cancel_order(order_id_to_check, sample_instrument))
        #             pass # Comment out to prevent actual order
        #         except Exception as e_order:
        #             logger.error(f"Order creation/cancellation test failed: {e_order}")
        #     else:
        #         print(f"Skipping order test: {sample_instrument} not found in instruments.")


        # print("\n=== Testing Get Open Orders ===")
        # if instruments:
        #    open_orders = client.get_open_orders(instrument_name=instruments[0]['instrument_name'])
        #    print(f"Open Orders for {instruments[0]['instrument_name']}: {open_orders}")


    except Exception as e:
        logger.error("Main test execution failed: %s", str(e))
        logger.debug(traceback.format_exc())