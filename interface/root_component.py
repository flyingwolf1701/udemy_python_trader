"""
Main application window for the Trading Bot with professional dark-themed UI.
"""

import tkinter as tk
from tkinter import ttk

import logging

from connectors.crypto_exchange import CryptoExchangeClient
from connectors.binance_exchange import BinanceExchangeClient

from interface.styling import ThemeManager, FrameStyles, Spacing
from interface.logging_component import Logging
from interface.watchlist_component import Watchlist
from interface.trades_component import TradesWatch
from interface.strategy_component import StrategyEditor


logger = logging.getLogger()


class Root(tk.Tk):
    """
    Main application window with a professional, dark-themed trading interface.
    """
    def __init__(self, binance: BinanceExchangeClient, crypto: CryptoExchangeClient):
        super().__init__()

        self.binance = binance
        self.crypto = crypto

        self.title("CryptoTrader Pro")
        self.configure(bg=ThemeManager.get_color("background_primary"))
        self.geometry("1280x800")  # Set initial window size
        self.minsize(1000, 700)    # Set minimum window size

        # Create a style for ttk widgets
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Use a modern base theme
        
        # Configure the style based on our theme
        self._configure_ttk_styles()

        # Create main layout frames
        self._create_layout()

        # Initialize UI components
        self._initialize_components()

        # Start the UI update cycle
        self._update_ui()

    def _configure_ttk_styles(self):
        """Configure ttk styles based on the current theme"""
        palette = ThemeManager.get_current_palette()
        
        # Configure ttk styles to match our theme
        self.style.configure("TFrame", 
                             background=palette.background_primary)
        
        self.style.configure("TButton", 
                             background=palette.accent_primary,
                             foreground=palette.text_primary,
                             borderwidth=0,
                             focusthickness=0,
                             focuscolor=palette.accent_primary)
        
        self.style.map("TButton",
                       background=[("active", palette.accent_secondary)],
                       foreground=[("active", palette.text_primary)])
        
        # Separator style
        self.style.configure("TSeparator", 
                             background=palette.border)
        
        # Header separator style - more visible
        self.style.configure("Header.TSeparator", 
                             background=palette.border)
        
        # Paned window style - no visible handle
        self.style.configure("TPanedwindow", 
                             background=palette.background_primary)
        
        # Scrollbar style - subtle and modern
        self.style.configure("TScrollbar", 
                             background=palette.background_tertiary,
                             troughcolor=palette.background_primary,
                             borderwidth=0,
                             arrowsize=13)
        
        # Combobox style - match input style
        self.style.configure("TCombobox",
                             background=palette.input_background,
                             foreground=palette.input_text,
                             fieldbackground=palette.input_background,
                             borderwidth=1)
        
        self.style.map("TCombobox",
                      fieldbackground=[("readonly", palette.input_background)],
                      selectbackground=[("readonly", palette.accent_primary)],
                      selectforeground=[("readonly", palette.text_primary)])

    def _create_layout(self):
        """Create the main application layout"""
        # Remove all padding to match the screenshot exactly
        self.main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL, style="TPanedwindow")
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Left panel - strategy and trades (main working area, wider)
        self._left_frame = ttk.Frame(self.main_paned)
        
        # Right panel - watchlist and logging (sidebar, narrower)
        self._right_frame = ttk.Frame(self.main_paned)
        
        # Add panels to the paned window with appropriate weights
        self.main_paned.add(self._left_frame, weight=7)  # Much wider
        self.main_paned.add(self._right_frame, weight=3)  # Narrower

    def _initialize_components(self):
        """Initialize and place all UI components"""
        bg_color = ThemeManager.get_color("background_primary")
        
        # Strategy Editor component (top left)
        self._strategy_frame = StrategyEditor(
            self, self.binance, self.crypto, self._left_frame
        )
        self._strategy_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 1))
        
        # Trades Monitor component (bottom left)
        self._trades_frame = TradesWatch(self._left_frame)
        self._trades_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(1, 0))
        
        # Watchlist component (top right)
        self._watchlist_frame = Watchlist(
            self.binance.contracts,
            self.crypto.contracts,
            self._right_frame
        )
        self._watchlist_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 1))
        
        # Logging component (bottom right)
        self.logging_frame = Logging(self._right_frame)
        self.logging_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(1, 0))

    def _update_ui(self):
        """Update UI components with latest data"""
        # Process logs
        self._update_logs()
        
        # Update watchlist prices
        self._update_watchlist()
        
        # Schedule next update
        self.after(1000, self._update_ui)

    def _update_logs(self):
        """Update logging component with new logs"""
        # Process Crypto exchange logs
        for log in self.crypto.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

        # Process Binance exchange logs
        for log in self.binance.logs:
            if not log["displayed"]:
                self.logging_frame.add_log(log["log"])
                log["displayed"] = True

    def _update_watchlist(self):
        """Update watchlist with latest price data"""
        try:
            for key, value in self._watchlist_frame.body_widgets["symbol"].items():
                symbol = self._watchlist_frame.body_widgets["symbol"][key].cget("text")
                exchange = self._watchlist_frame.body_widgets["exchange"][key].cget("text")

                if exchange == "Binance":
                    if symbol not in self.binance.contracts:
                        continue

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

                if prices["bid"] is not None:
                    price_str = "{0:.{prec}f}".format(prices["bid"], prec=precision)
                    self._watchlist_frame.body_widgets["bid_var"][key].set(price_str)
                if prices["ask"] is not None:
                    price_str = "{0:.{prec}f}".format(prices["ask"], prec=precision)
                    self._watchlist_frame.body_widgets["ask_var"][key].set(price_str)

        except RuntimeError as e:
            logger.error("Error while updating watchlist: %s", e)