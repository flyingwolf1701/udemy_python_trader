from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

# Constants for BitMEX data adjustments
BITMEX_MULTIPLIER = 0.00000001
BITMEX_TF_MINUTES = {"1m": 1, "5m": 5, "1h": 60, "1d": 1440}


def tick_to_decimals(tick_size: float) -> int:
    """
    Determine the number of decimal places from a given tick size.
    """
    s = f"{tick_size:.8f}".rstrip('0')
    if '.' in s:
        return len(s.split('.')[1])
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
    def from_info(cls, info: Dict[str, Any], exchange: str) -> 'Balance':
        if exchange == "binance":
            # Spot account
            if 'free' in info and 'locked' in info:
                return cls(
                    free=float(info['free']),
                    locked=float(info['locked'])
                )
            # Futures/margin account
            return cls(
                initial_margin=float(info['initialMargin']),
                maintenance_margin=float(info['maintMargin']),
                margin_balance=float(info['marginBalance']),
                wallet_balance=float(info['walletBalance']),
                unrealized_pnl=float(info['unrealizedProfit'])
            )
        elif exchange == "bitmex":
            # Scale BitMEX margins to asset units
            return cls(
                initial_margin=info['initMargin'] * BITMEX_MULTIPLIER,
                maintenance_margin=info['maintMargin'] * BITMEX_MULTIPLIER,
                margin_balance=info['marginBalance'] * BITMEX_MULTIPLIER,
                wallet_balance=info['walletBalance'] * BITMEX_MULTIPLIER,
                unrealized_pnl=info['unrealisedPnl'] * BITMEX_MULTIPLIER
            )
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
    def from_api(cls, candle_info: Any, timeframe: str, exchange: str) -> 'Candle':
        if exchange == "binance":
            ts = candle_info[0]
            return cls(
                timestamp=ts,
                open=float(candle_info[1]),
                high=float(candle_info[2]),
                low=float(candle_info[3]),
                close=float(candle_info[4]),
                volume=float(candle_info[5])
            )
        elif exchange == "bitmex":
            ts_str = candle_info['timestamp']
            # Convert ISO8601 UTC string to datetime
            iso = ts_str.rstrip('Z') + '+00:00'
            dt = datetime.fromisoformat(iso)
            # Adjust back one period for proper open time
            delta = timedelta(minutes=BITMEX_TF_MINUTES[timeframe])
            ts = int((dt - delta).timestamp() * 1000)
            return cls(
                timestamp=ts,
                open=candle_info['open'],
                high=candle_info['high'],
                low=candle_info['low'],
                close=candle_info['close'],
                volume=candle_info['volume']
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

    @classmethod
    def from_info(cls, info: Dict[str, Any], exchange: str) -> 'Contract':
        if exchange == "binance":
            # Extract filters for tick and lot sizes
            filters = info.get('filters', [])
            tick_size = 0.0
            lot_size = 0.0
            for f in filters:
                if f.get('filterType') == 'PRICE_FILTER':
                    tick_size = float(f['tickSize'])
                elif f.get('filterType') == 'LOT_SIZE':
                    lot_size = float(f['stepSize'])
            price_decimals = tick_to_decimals(tick_size)
            quantity_decimals = tick_to_decimals(lot_size)
            return cls(
                symbol=info['symbol'],
                base_asset=info['baseAsset'],
                quote_asset=info['quoteAsset'],
                price_decimals=price_decimals,
                quantity_decimals=quantity_decimals,
                tick_size=tick_size,
                lot_size=lot_size
            )
        elif exchange == "bitmex":
            return cls(
                symbol=info['symbol'],
                base_asset=info['rootSymbol'],
                quote_asset=info['quoteCurrency'],
                price_decimals=tick_to_decimals(info['tickSize']),
                quantity_decimals=tick_to_decimals(info['lotSize']),
                tick_size=info['tickSize'],
                lot_size=info['lotSize']
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
    def from_api(cls, info: Dict[str, Any], exchange: str) -> 'OrderStatus':
        if exchange == "binance":
            return cls(
                order_id=info['orderId'],
                status=info['status'],
                avg_price=float(info.get('avgPrice', 0))
            )
        elif exchange == "bitmex":
            return cls(
                order_id=info['orderID'],
                status=info['ordStatus'],
                avg_price=info.get('avgPx', 0)
            )
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
