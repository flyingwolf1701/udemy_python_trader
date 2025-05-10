import logging
from typing import *
import time
from threading import Timer
import pandas as pd

from models import *

if TYPE_CHECKING:  # Import for typing only
    from connectors.crypto_exchange import CryptoExchangeClient
    from connectors.binance_exchange import BinanceExchangeClient

logger = logging.getLogger()

# Timeframe equivalents in seconds (for candle processing)
TF_EQUIV = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}


class Strategy:
    def __init__(self, client: Union["BinanceExchangeClient", "CryptoExchangeClient"], 
                 contract: Contract, exchange: str, timeframe: str, 
                 balance_pct: float, take_profit: float, stop_loss: float, strat_name: str):

        self.client = client
        self.contract = contract
        self.exchange = exchange
        self.tf = timeframe
        self.tf_equiv = TF_EQUIV[timeframe] * 1000  # Convert to milliseconds
        self.balance_pct = balance_pct
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.strat_name = strat_name

        self.ongoing_position = False

        self.candles: List[Candle] = []
        self.trades: List[Trade] = []
        self.logs = []

    def _add_log(self, msg: str):
        logger.info("%s", msg)
        self.logs.append({"log": msg, "displayed": False})

    def parse_trades(self, price: float, size: float, timestamp: int) -> str:
        """
        Parse new trades coming in from the websocket and update the Candle list based on the timestamp.
        :param price: The trade price
        :param size: The trade size
        :param timestamp: Unix timestamp in milliseconds
        :return: Status indicator - "same_candle" or "new_candle"
        """
        timestamp_diff = int(time.time() * 1000) - timestamp
        if timestamp_diff >= 2000:
            logger.warning("%s %s: %s milliseconds of difference between the current time and the trade time",
                           self.exchange, self.contract.symbol, timestamp_diff)

        last_candle = self.candles[-1]

        # Same Candle
        if timestamp < last_candle.timestamp + self.tf_equiv:
            last_candle.close = price
            last_candle.volume += size

            if price > last_candle.high:
                last_candle.high = price
            elif price < last_candle.low:
                last_candle.low = price

            # Check Take profit / Stop loss
            for trade in self.trades:
                if trade.status == "open" and trade.entry_price is not None:
                    self._check_tp_sl(trade)

            return "same_candle"

        # Missing Candle(s)
        elif timestamp >= last_candle.timestamp + 2 * self.tf_equiv:
            missing_candles = int((timestamp - last_candle.timestamp) / self.tf_equiv) - 1

            logger.info("%s missing %s candles for %s %s (%s %s)", self.exchange, missing_candles, 
                        self.contract.symbol, self.tf, timestamp, last_candle.timestamp)

            for missing in range(missing_candles):
                new_ts = last_candle.timestamp + self.tf_equiv
                candle_info = {'ts': new_ts, 'open': last_candle.close, 'high': last_candle.close,
                               'low': last_candle.close, 'close': last_candle.close, 'volume': 0}
                new_candle = Candle.from_api(candle_info, self.tf, "crypto")  # Using crypto format for consistency
                self.candles.append(new_candle)
                last_candle = new_candle

            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {'ts': new_ts, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': size}
            new_candle = Candle.from_api(candle_info, self.tf, "crypto")
            self.candles.append(new_candle)

            return "new_candle"

        # New Candle
        elif timestamp >= last_candle.timestamp + self.tf_equiv:
            new_ts = last_candle.timestamp + self.tf_equiv
            candle_info = {'ts': new_ts, 'open': price, 'high': price, 'low': price, 'close': price, 'volume': size}
            new_candle = Candle.from_api(candle_info, self.tf, "crypto")
            self.candles.append(new_candle)

            logger.info("%s New candle for %s %s", self.exchange, self.contract.symbol, self.tf)

            return "new_candle"

    def _check_order_status(self, order_id):
        """
        Called regularly after an order has been placed, until it is filled.
        :param order_id: The order id to check.
        :return: None
        """
        order_status = self.client.get_order_status(self.contract, order_id)

        if order_status is not None:
            logger.info("%s order status: %s", self.exchange, order_status.status)

            if order_status.status == "filled":
                for trade in self.trades:
                    if trade.entry_id == order_id:
                        trade.entry_price = order_status.avg_price
                        trade.quantity = float(order_status.executed_qty) if hasattr(order_status, 'executed_qty') else 0
                        break
                return

        t = Timer(2.0, lambda: self._check_order_status(order_id))
        t.start()

    def _open_position(self, signal_result: int):
        """
        Open Long or Short position based on the signal result.
        :param signal_result: 1 (Long) or -1 (Short)
        :return: None
        """
        # Determine if spot market (Binance.US is spot only)
        is_spot = hasattr(self.client, 'base_url') and 'binance.us' in getattr(self.client, 'base_url', '')
        
        # Short is not allowed on Spot platforms
        if is_spot and signal_result == -1:
            self._add_log(f"Short positions not available on {self.exchange} spot market")
            return

        # Get trade size based on balance percentage
        trade_size = self._get_trade_size()
        if trade_size is None or trade_size == 0:
            return

        order_side = "buy" if signal_result == 1 else "sell"
        position_side = "long" if signal_result == 1 else "short"

        self._add_log(f"{position_side.capitalize()} signal on {self.contract.symbol} {self.tf}")

        order_status = self.client.place_order(
            self.contract, 
            "MARKET", 
            trade_size, 
            order_side
        )

        if order_status is not None:
            self._add_log(f"{order_side.capitalize()} order placed on {self.exchange} | Status: {order_status.status}")

            self.ongoing_position = True

            avg_fill_price = None

            if order_status.status == "filled":
                avg_fill_price = order_status.avg_price
            else:
                t = Timer(2.0, lambda: self._check_order_status(order_status.order_id))
                t.start()

            # Create a new trade object
            new_trade = Trade(
                time=int(time.time() * 1000),
                contract=self.contract, 
                strategy=self.strat_name,
                side=position_side,
                entry_price=avg_fill_price,
                status="open", 
                pnl=0, 
                quantity=float(order_status.executed_qty) if hasattr(order_status, 'executed_qty') else 0,
                entry_id=order_status.order_id
            )
            self.trades.append(new_trade)

    def _get_trade_size(self) -> Optional[float]:
        """
        Calculate the trade size based on account balance and risk percentage
        :return: Trade size or None if calculation fails
        """
        try:
            current_price = self.candles[-1].close
            
            # Get balance info
            balances = self.client.balances
            
            # For Binance, use USDT balance
            if "binance" in self.exchange.lower():
                if 'USDT' in balances:
                    balance = balances['USDT'].free
                else:
                    self._add_log("No USDT balance available")
                    return None
            # For Crypto.com, use the quote asset of the contract
            else:
                quote_asset = self.contract.quote_asset
                if quote_asset in balances:
                    balance = balances[quote_asset].free
                else:
                    self._add_log(f"No {quote_asset} balance available")
                    return None
            
            if balance is None:
                self._add_log(f"Could not fetch balance")
                return None
                
            trade_size = (balance * self.balance_pct / 100) / current_price
            
            # Adjust trade size to contract lot size
            trade_size = round(round(trade_size / self.contract.lot_size) * self.contract.lot_size, 8)
            
            return trade_size
            
        except Exception as e:
            logger.error(f"Error calculating trade size: {e}")
            self._add_log(f"Error calculating trade size: {e}")
            return None

    def _check_tp_sl(self, trade: Trade):
        """
        Based on the average entry price, calculates whether the defined stop loss or take profit has been reached.
        :param trade: The trade to check
        :return: None
        """
        tp_triggered = False
        sl_triggered = False

        price = self.candles[-1].close

        if trade.side == "long":
            if self.stop_loss is not None:
                if price <= trade.entry_price * (1 - self.stop_loss / 100):
                    sl_triggered = True
            if self.take_profit is not None:
                if price >= trade.entry_price * (1 + self.take_profit / 100):
                    tp_triggered = True

        elif trade.side == "short":
            if self.stop_loss is not None:
                if price >= trade.entry_price * (1 + self.stop_loss / 100):
                    sl_triggered = True
            if self.take_profit is not None:
                if price <= trade.entry_price * (1 - self.take_profit / 100):
                    tp_triggered = True

        if tp_triggered or sl_triggered:
            self._add_log(f"{'Stop loss' if sl_triggered else 'Take profit'} for {self.contract.symbol} {self.tf} "
                          f"| Current Price = {price} (Entry price was {trade.entry_price})")

            order_side = "SELL" if trade.side == "long" else "BUY"

            # For spot markets, ensure we don't sell more than available
            is_spot = hasattr(self.client, 'base_url') and 'binance.us' in getattr(self.client, 'base_url', '')
            
            if is_spot and order_side == "SELL":
                # Check current balances
                current_balances = self.client.balances
                if current_balances is not None and self.contract.base_asset in current_balances:
                    available = current_balances[self.contract.base_asset].free
                    trade.quantity = min(available, trade.quantity)

            order_status = self.client.place_order(self.contract, "MARKET", trade.quantity, order_side)

            if order_status is not None:
                self._add_log(f"Exit order on {self.contract.symbol} {self.tf} placed successfully")
                trade.status = "closed"
                self.ongoing_position = False


class TechnicalStrategy(Strategy):
    def __init__(self, client, contract: Contract, exchange: str, timeframe: str, balance_pct: float, 
                 take_profit: float, stop_loss: float, other_params: Dict):
        super().__init__(client, contract, exchange, timeframe, balance_pct, take_profit, stop_loss, "Technical")

        self._ema_fast = other_params['ema_fast']
        self._ema_slow = other_params['ema_slow']
        self._ema_signal = other_params['ema_signal']
        self._rsi_length = other_params['rsi_length']

    def _rsi(self) -> float:
        """
        Compute the Relative Strength Index.
        :return: The RSI value of the previous candlestick
        """
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)

        # Calculate the different between the value of one row and the value of the row before
        delta = closes.diff().dropna()

        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0  # Keep only the negative change, others are set to 0

        avg_gain = up.ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()
        avg_loss = down.abs().ewm(com=(self._rsi_length - 1), min_periods=self._rsi_length).mean()

        rs = avg_gain / avg_loss  # Relative Strength

        rsi = 100 - 100 / (1 + rs)
        rsi = rsi.round(2)

        return rsi.iloc[-2]

    def _macd(self) -> Tuple[float, float]:
        """
        Compute the MACD and its Signal line.
        :return: The MACD and the MACD Signal value of the previous candlestick
        """
        close_list = [candle.close for candle in self.candles]
        closes = pd.Series(close_list)

        ema_fast = closes.ewm(span=self._ema_fast).mean()
        ema_slow = closes.ewm(span=self._ema_slow).mean()

        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=self._ema_signal).mean()

        return macd_line.iloc[-2], macd_signal.iloc[-2]

    def _check_signal(self):
        """
        Compute technical indicators and compare their value to some predefined levels to know whether to go Long,
        Short, or do nothing.
        :return: 1 for a Long signal, -1 for a Short signal, 0 for no signal
        """
        macd_line, macd_signal = self._macd()
        rsi = self._rsi()

        if rsi < 30 and macd_line > macd_signal:
            return 1
        elif rsi > 70 and macd_line < macd_signal:
            return -1
        else:
            return 0

    def check_trade(self, tick_type: str):
        """
        To be triggered from the websocket _on_message() methods. Triggered only once per candlestick to avoid
        constantly calculating the indicators. A trade can occur only if there is no open position at the moment.
        :param tick_type: same_candle or new_candle
        :return: None
        """
        if tick_type == "new_candle" and not self.ongoing_position:
            signal_result = self._check_signal()

            if signal_result in [1, -1]:
                self._open_position(signal_result)


class BreakoutStrategy(Strategy):
    def __init__(self, client, contract: Contract, exchange: str, timeframe: str, balance_pct: float,
                 take_profit: float, stop_loss: float, other_params: Dict):
        super().__init__(client, contract, exchange, timeframe, balance_pct, take_profit, stop_loss, "Breakout")

        self._min_volume = other_params['min_volume']

    def _check_signal(self) -> int:
        """
        Use candlesticks OHLC data to define Long or Short patterns.
        :return: 1 for a Long signal, -1 for a Short signal, 0 for no signal
        """
        if self.candles[-1].close > self.candles[-2].high and self.candles[-1].volume > self._min_volume:
            return 1
        elif self.candles[-1].close < self.candles[-2].low and self.candles[-1].volume > self._min_volume:
            return -1
        else:
            return 0

    def check_trade(self, tick_type: str):
        """
        To be triggered from the websocket _on_message() methods
        :param tick_type: same_candle or new_candle
        :return: None
        """
        if not self.ongoing_position:
            signal_result = self._check_signal()

            if signal_result in [1, -1]:
                self._open_position(signal_result)