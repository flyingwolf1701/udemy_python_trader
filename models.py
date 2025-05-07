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
            # Spot account
            if "free" in info and "locked" in info:
                return cls(free=float(info["free"]), locked=float(info["locked"]))
            # Futures/margin account
            return cls(
                initial_margin=float(info["initialMargin"]),
                maintenance_margin=float(info["maintMargin"]),
                margin_balance=float(info["marginBalance"]),
                wallet_balance=float(info["walletBalance"]),
                unrealized_pnl=float(info["unrealizedProfit"]),
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
            # Crypto.com Exchange v1 candlestick format
            if isinstance(candle_info, dict):
                ts = int(candle_info.get("t", candle_info.get("timestamp")))
                return cls(
                    timestamp=ts,
                    open=float(candle_info["o"]),
                    high=float(candle_info["h"]),
                    low=float(candle_info["l"]),
                    close=float(candle_info["c"]),
                    volume=float(candle_info["v"]),
                )
            else:
                raise ValueError("Unsupported candle format for crypto exchange")
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

    @classmethod
    def from_info(cls, info: Dict[str, Any], exchange: str) -> "Contract":
        if exchange == "binance":
            filters = info.get("filters", [])
            tick_size = 0.0
            lot_size = 0.0
            for f in filters:
                if f.get("filterType") == "PRICE_FILTER":
                    tick_size = float(f["tickSize"])
                elif f.get("filterType") == "LOT_SIZE":
                    lot_size = float(f["stepSize"])
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
            )
        elif exchange == "crypto":
            # Crypto.com Exchange v1 instrument format
            symbol = info.get("instrument_name", info.get("symbol"))
            base_asset = info.get("base_coin", info.get("baseAsset"))
            quote_asset = info.get("quote_coin", info.get("quoteAsset"))
            tick_size = float(info.get("tick_size", info.get("price_tick_size", 0.0)))
            lot_size = float(info.get("lot_size", info.get("qty_tick_size", 0.0)))
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

    @classmethod
    def from_api(cls, info: Dict[str, Any], exchange: str) -> "OrderStatus":
        if exchange == "binance":
            return cls(
                order_id=info["orderId"],
                status=info["status"],
                avg_price=float(info.get("avgPrice", 0)),
            )
        elif exchange == "crypto":
            # Crypto.com Exchange v1 order format
            order_id = info.get("order_id", info.get("id", info.get("orderId")))
            status = info.get("status", "")
            avg_price = float(info.get("avg_price", info.get("price", 0)))
            return cls(order_id=order_id, status=status, avg_price=avg_price)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
