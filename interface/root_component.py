import tkinter as tk
import logging

from connectors.crypto_exchange import CryptoExchangeClient
from connectors.binance_exchange import BinanceExchangeClient

from interface.styling import *
from interface.logging_component import Logging
from interface.watchlist_component import Watchlist
from interface.trades_component import TradesWatch
from interface.strategy_component import StrategyEditor


logger = logging.getLogger()


class Root(tk.Tk):
    def __init__(self, binance: BinanceExchangeClient, crypto: CryptoExchangeClient):
        super().__init__()

        self.binance = binance
        self.crypto = crypto

        self.title("Trading Bot")

        self.configure(bg=BG_COLOR)

        self._left_frame = tk.Frame(self, bg=BG_COLOR)
        self._left_frame.pack(side=tk.LEFT)

        self._right_frame = tk.Frame(self, bg=BG_COLOR)
        self._right_frame.pack(side=tk.LEFT)

        self._watchlist_frame = Watchlist(
            self.binance.contracts,
            self.crypto.contracts,
            self._left_frame,
            bg=BG_COLOR,
        )
        self._watchlist_frame.pack(side=tk.TOP)

        self.logging_frame = Logging(self._left_frame, bg=BG_COLOR)
        self.logging_frame.pack(side=tk.TOP)

        self._strategy_frame = StrategyEditor(
            self, self.binance, self.crypto, self._right_frame, bg=BG_COLOR
        )
        self._strategy_frame.pack(side=tk.TOP)

        self._trades_frame = TradesWatch(self._right_frame, bg=BG_COLOR)
        self._trades_frame.pack(side=tk.TOP)

        self._update_ui()

    def _update_ui(self):
        # Logs

        for log in self.crypto.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

        for log in self.binance.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

        # Watchlist prices

        try:
            for key, value in self._watchlist_frame.body_widgets["symbol"].items():
                symbol = self._watchlist_frame.body_widgets["symbol"][key].cget("text")
                exchange = self._watchlist_frame.body_widgets["exchange"][key].cget(
                    "text"
                )

                if exchange == "Binance":
                    if symbol not in self.binance.contracts:
                        continue

                    if symbol not in self.binance.prices:
                        self.binance.get_bid_ask(self.binance.contracts[symbol])
                        continue

                    precision = self.binance.contracts[symbol].price_decimals

                    prices = self.binance.prices[symbol]

                elif exchange == "crypto":
                    if symbol not in self.crypto.contracts:
                        continue

                    if symbol not in self.crypto.prices:
                        continue

                    precision = self.crypto.contracts[symbol].price_decimals

                    prices = self.crypto.prices[symbol]

                else:
                    continue

                if prices["bid"] is not None:
                    price_str = "{0:.{prec}f}".format(prices["bid"], prec=precision)
                    self._watchlist_frame.body_widgets["bid_var"][key].set(price_str)
                if prices["ask"] is not None:
                    price_str = "{0:.{prec}f}".format(prices["ask"], prec=precision)
                    self._watchlist_frame.body_widgets["ask_var"][key].set(price_str)

        except RuntimeError as e:
            logger.error("Error while looping through watchlist dictionary: %s", e)

        self.after(1500, self._update_ui)
