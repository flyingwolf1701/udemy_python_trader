from dataclasses import dataclass
from typing import Optional, Dict, Any


def tick_to_decimals(tick_size: float) -> int:
    """
    Determine the number of decimal places from a given tick size.
    """
    s = f"{tick_size:.8f}".rstrip("0")
    if "." in s:
        return len(s.split(".")[1])
    return 0


@dataclass
class Balance:
    """
    Account balance representation for different exchanges.
    """
    free: Optional[float] = None
    locked: Optional[float] = None
    initial_margin: Optional[float] = None
    maintenance_margin: Optional[float] = None
    margin_balance: Optional[float] = None
    wallet_balance: Optional[float] = None
    unrealized_pnl: Optional[float] = None

    @classmethod
    def from_info(cls, info: Dict[str, Any], exchange: str) -> "Balance":
        if exchange == "binance":
            # Binance.US spot account
            return cls(
                free=float(info.get("free", 0.0)),
                locked=float(info.get("locked", 0.0))
            )
        elif exchange == "crypto":
            # Crypto.com spot account
            free = float(info.get("available", info.get("free", 0.0)))
            locked = float(info.get("freeze", info.get("locked", 0.0)))
            return cls(free=free, locked=locked)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")


@dataclass
class Candle:
    """
    Historical price candle data.
    """
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_api(cls, candle_info: Any, timeframe: str, exchange: str) -> "Candle":
        if exchange == "binance":
            # Binance.US candle format
            ts = candle_info[0]
            return cls(
                timestamp=ts,
                open=float(candle_info[1]),
                high=float(candle_info[2]),
                low=float(candle_info[3]),
                close=float(candle_info[4]),
                volume=float(candle_info[5]),
            )
        elif exchange == "crypto":
            # Crypto.com Exchange candle format
            if isinstance(candle_info, dict):
                ts = int(candle_info.get("t", candle_info.get("timestamp")))
                return cls(
                    timestamp=ts,
                    open=float(candle_info.get("o", candle_info.get("open", 0))),
                    high=float(candle_info.get("h", candle_info.get("high", 0))),
                    low=float(candle_info.get("l", candle_info.get("low", 0))),
                    close=float(candle_info.get("c", candle_info.get("close", 0))),
                    volume=float(candle_info.get("v", candle_info.get("volume", 0))),
                )
            else:
                raise ValueError("Unsupported candle format for crypto exchange")
        elif exchange == "parse_trade":
            # For candles created from trade data
            ts = candle_info.get("ts")
            return cls(
                timestamp=ts,
                open=float(candle_info.get("open", 0)),
                high=float(candle_info.get("high", 0)),
                low=float(candle_info.get("low", 0)),
                close=float(candle_info.get("close", 0)),
                volume=float(candle_info.get("volume", 0)),
            )
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")


@dataclass
class Contract:
    """
    Market contract/instrument representation.
    """
    symbol: str
    base_asset: str
    quote_asset: str
    price_decimals: int
    quantity_decimals: int
    tick_size: float
    lot_size: float
    exchange: str

    @classmethod
    def from_info(cls, info: Dict[str, Any], exchange: str) -> "Contract":
        if exchange == "binance":
            # Binance.US contract format
            filters = info.get("filters", [])
            tick_size = 0.0
            lot_size = 0.0
            for f in filters:
                if f.get("filterType") == "PRICE_FILTER":
                    tick_size = float(f["tickSize"])
                elif f.get("filterType") == "LOT_SIZE":
                    lot_size = float(f["stepSize"])
            
            # If filters not found, use defaults from pricePrecision/quantityPrecision
            if tick_size == 0.0 and "pricePrecision" in info:
                price_precision = info["pricePrecision"]
                tick_size = 1 / pow(10, price_precision)
            
            if lot_size == 0.0 and "quantityPrecision" in info:
                qty_precision = info["quantityPrecision"]
                lot_size = 1 / pow(10, qty_precision)
                
            price_decimals = tick_to_decimals(tick_size)
            quantity_decimals = tick_to_decimals(lot_size)
            
            return cls(
                symbol=info["symbol"],
                base_asset=info["baseAsset"],
                quote_asset=info["quoteAsset"],
                price_decimals=price_decimals,
                quantity_decimals=quantity_decimals,
                tick_size=tick_size,
                lot_size=lot_size,
                exchange=exchange,
            )
        elif exchange == "crypto":
            # Crypto.com Exchange contract format
            symbol = info.get("instrument_name", info.get("symbol"))
            base_asset = info.get("base_coin", info.get("baseAsset"))
            quote_asset = info.get("quote_coin", info.get("quoteAsset"))
            tick_size = float(info.get("tick_size", info.get("price_tick_size", 0.00001)))
            lot_size = float(info.get("lot_size", info.get("qty_tick_size", 0.00001)))
            price_decimals = tick_to_decimals(tick_size)
            quantity_decimals = tick_to_decimals(lot_size)
            return cls(
                symbol=symbol,
                base_asset=base_asset,
                quote_asset=quote_asset,
                price_decimals=price_decimals,
                quantity_decimals=quantity_decimals,
                tick_size=tick_size,
                lot_size=lot_size,
                exchange=exchange,
            )
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")


@dataclass
class OrderStatus:
    """
    Status report for an order.
    """
    order_id: Any
    status: str
    avg_price: float
    executed_qty: Optional[float] = 0.0

    @classmethod
    def from_api(cls, info: Dict[str, Any], exchange: str) -> "OrderStatus":
        if exchange == "binance":
            return cls(
                order_id=info["orderId"],
                status=info["status"].lower(),
                avg_price=float(info.get("avgPrice", 0)),
                executed_qty=float(info.get("executedQty", 0)),
            )
        elif exchange == "crypto":
            # Crypto.com Exchange order format
            order_id = info.get("order_id", info.get("id", info.get("orderId")))
            status = info.get("status", "").lower()
            avg_price = float(info.get("avg_price", info.get("price", 0)))
            executed_qty = float(info.get("executed_qty", info.get("cumQty", 0)))
            return cls(
                order_id=order_id, 
                status=status, 
                avg_price=avg_price,
                executed_qty=executed_qty,
            )
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")


@dataclass
class Trade:
    """
    Represents a trade with entry and exit information.
    """
    time: int
    contract: Contract
    strategy: str
    side: str
    entry_price: Optional[float] = None
    status: str = "open"
    pnl: float = 0.0
    quantity: float = 0.0
    entry_id: Optional[str] = None
    
    def __eq__(self, other):
        if isinstance(other, Trade):
            return self.entry_id == other.entry_id
        return False
        
    def __hash__(self):
        return hash(self.entry_id)