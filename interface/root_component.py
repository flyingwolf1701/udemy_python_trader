import tkinter as tk
from tkinter.messagebox import askquestion
import logging
import json

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
        self.protocol("WM_DELETE_WINDOW", self._ask_before_close)

        self.configure(bg=BG_COLOR)

        # Create the menu, sub menu and menu commands
        self.main_menu = tk.Menu(self)
        self.configure(menu=self.main_menu)

        self.workspace_menu = tk.Menu(self.main_menu, tearoff=False)
        self.main_menu.add_cascade(label="Workspace", menu=self.workspace_menu)
        self.workspace_menu.add_command(label="Save workspace", command=self._save_workspace)

        # Separates the root component in two blocks
        self._left_frame = tk.Frame(self, bg=BG_COLOR)
        self._left_frame.pack(side=tk.LEFT)

        self._right_frame = tk.Frame(self, bg=BG_COLOR)
        self._right_frame.pack(side=tk.LEFT)

        # Creates and places components
        self._watchlist_frame = Watchlist(
            self.binance.contracts,
            self.crypto.contracts,
            self._left_frame,
            bg=BG_COLOR,
        )
        self._watchlist_frame.pack(side=tk.TOP, padx=10)

        self.logging_frame = Logging(self._left_frame, bg=BG_COLOR)
        self.logging_frame.pack(side=tk.TOP, pady=15)

        self._strategy_frame = StrategyEditor(
            self, self.binance, self.crypto, self._right_frame, bg=BG_COLOR
        )
        self._strategy_frame.pack(side=tk.TOP, pady=15)

        self._trades_frame = TradesWatch(self._right_frame, bg=BG_COLOR)
        self._trades_frame.pack(side=tk.TOP, pady=15)

        self._update_ui()

    def _ask_before_close(self):
        """
        Triggered when the user clicks on the Close button of the interface.
        This lets you have control over what's happening just before closing the interface.
        """
        result = askquestion("Confirmation", "Do you really want to exit the application?")
        if result == "yes":
            # Clean up WebSocket connections if available
            if hasattr(self.binance, '_ws') and self.binance._ws:
                self.binance._ws.close()
            if hasattr(self.crypto, '_ws') and self.crypto._ws:
                self.crypto._ws.close()
                
            self.destroy()

    def _update_ui(self):
        """
        Updates the UI components every 1500ms. Thread-safe method to update Tkinter elements.
        """
        # Logs
        for log in self.crypto.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

        for log in self.binance.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

        # Strategies and Trades (if implemented)
        for client in [self.binance, self.crypto]:
            try:
                if hasattr(client, 'strategies'):
                    for b_index, strat in client.strategies.items():
                        for log in strat.logs:
                            if not log['displayed']:
                                self.logging_frame.add_log(log['log'])
                                log['displayed'] = True
                        
                        # Update trades information
                        for trade in strat.trades:
                            if trade.time not in self._trades_frame.body_widgets['symbol']:
                                self._trades_frame.add_trade(trade)
                            
                            if "binance" in trade.contract.exchange:
                                precision = trade.contract.price_decimals
                            else:
                                precision = 8  # The Crypto PNL precision (adjust if needed)
                            
                            if hasattr(self._trades_frame.body_widgets, 'pnl_var') and trade.time in self._trades_frame.body_widgets['pnl_var']:
                                pnl_str = "{0:.{prec}f}".format(trade.pnl, prec=precision)
                                self._trades_frame.body_widgets['pnl_var'][trade.time].set(pnl_str)
                                
                            if hasattr(self._trades_frame.body_widgets, 'status_var') and trade.time in self._trades_frame.body_widgets['status_var']:
                                self._trades_frame.body_widgets['status_var'][trade.time].set(trade.status.capitalize())
                                
                            if hasattr(self._trades_frame.body_widgets, 'quantity_var') and trade.time in self._trades_frame.body_widgets['quantity_var']:
                                self._trades_frame.body_widgets['quantity_var'][trade.time].set(trade.quantity)
            except RuntimeError as e:
                logger.error("Error while looping through strategies dictionary: %s", e)
            except AttributeError as e:
                logger.error("Attribute error during strategy update: %s", e)

        # Watchlist prices
        try:
            for key, value in self._watchlist_frame.body_widgets['symbol'].items():
                symbol = self._watchlist_frame.body_widgets['symbol'][key].cget("text")
                exchange = self._watchlist_frame.body_widgets['exchange'][key].cget("text")

                if exchange == "Binance":
                    if symbol not in self.binance.contracts:
                        continue

                    # Subscribe to symbol if needed and WebSocket is available
                    if hasattr(self.binance, 'subscribe_channel'):
                        ws_connected = getattr(self.binance, 'ws_connected', False)
                        ws_subscriptions = getattr(self.binance, 'ws_subscriptions', {})
                        
                        if ws_connected and ws_subscriptions and symbol not in ws_subscriptions.get("bookTicker", []):
                            self.binance.subscribe_channel([self.binance.contracts[symbol]], "bookTicker")

                    if symbol not in self.binance.prices:
                        self.binance.get_bid_ask(self.binance.contracts[symbol])
                        continue

                    precision = self.binance.contracts[symbol].price_decimals
                    prices = self.binance.prices[symbol]

                elif exchange == "Crypto":
                    if symbol not in self.crypto.contracts:
                        continue

                    if symbol not in self.crypto.prices:
                        continue

                    precision = self.crypto.contracts[symbol].price_decimals
                    prices = self.crypto.prices[symbol]
                else:
                    continue

                if prices.get('bid') is not None:
                    price_str = "{0:.{prec}f}".format(prices['bid'], prec=precision)
                    self._watchlist_frame.body_widgets['bid_var'][key].set(price_str)
                    
                if prices.get('ask') is not None:
                    price_str = "{0:.{prec}f}".format(prices['ask'], prec=precision)
                    self._watchlist_frame.body_widgets['ask_var'][key].set(price_str)

        except RuntimeError as e:
            logger.error("Error while looping through watchlist dictionary: %s", e)
        except KeyError as e:
            logger.error(f"Key error in watchlist update: {e}")

        self.after(1500, self._update_ui)

    def _save_workspace(self):
        """
        Saves the current workspace configuration.
        """
        # Watchlist
        try:
            watchlist_symbols = []
            for key, value in self._watchlist_frame.body_widgets['symbol'].items():
                symbol = value.cget("text")
                exchange = self._watchlist_frame.body_widgets['exchange'][key].cget("text")
                watchlist_symbols.append((symbol, exchange,))

            if hasattr(self._watchlist_frame, 'db'):
                self._watchlist_frame.db.save("watchlist", watchlist_symbols)
        except Exception as e:
            logger.error(f"Error saving watchlist: {e}")

        # Strategies
        try:
            if hasattr(self._strategy_frame, 'body_widgets') and hasattr(self._strategy_frame, 'extra_params'):
                strategies = []
                strat_widgets = self._strategy_frame.body_widgets
                
                for b_index in strat_widgets.get('contract', {}):
                    strategy_type = strat_widgets['strategy_type_var'][b_index].get()
                    contract = strat_widgets['contract_var'][b_index].get()
                    timeframe = strat_widgets['timeframe_var'][b_index].get()
                    balance_pct = strat_widgets['balance_pct'][b_index].get()
                    take_profit = strat_widgets['take_profit'][b_index].get()
                    stop_loss = strat_widgets['stop_loss'][b_index].get()
                    
                    # Extra parameters
                    extra_params = dict()
                    if strategy_type in self._strategy_frame.extra_params:
                        for param in self._strategy_frame.extra_params[strategy_type]:
                            code_name = param['code_name']
                            if hasattr(self._strategy_frame, 'additional_parameters') and b_index in self._strategy_frame.additional_parameters:
                                extra_params[code_name] = self._strategy_frame.additional_parameters[b_index].get(code_name)
                    
                    strategies.append((
                        strategy_type, contract, timeframe, balance_pct, 
                        take_profit, stop_loss, json.dumps(extra_params),
                    ))
                
                if hasattr(self._strategy_frame, 'db'):
                    self._strategy_frame.db.save("strategies", strategies)
        except Exception as e:
            logger.error(f"Error saving strategies: {e}")

        self.logging_frame.add_log("Workspace saved")