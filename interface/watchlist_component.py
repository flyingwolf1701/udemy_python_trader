"""
Professional watchlist component for monitoring cryptocurrency prices.
Features a modern dark-themed interface with real-time price updates.
"""

import tkinter as tk
from tkinter import ttk
import typing

from models import Contract
from interface.styling import ThemeManager, Typography, Spacing


class Watchlist(ttk.Frame):
    """
    Modern watchlist component for displaying and tracking market prices.
    """
    def __init__(
        self,
        binance_contracts: typing.Dict[str, Contract],
        crypto_contracts: typing.Dict[str, Contract],
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        
        # Store available symbols
        self.binance_symbols = list(binance_contracts.keys())
        self.crypto_symbols = list(crypto_contracts.keys())
        
        # Get theme colors
        self.palette = ThemeManager.get_current_palette()
        
        # Initialize the UI
        self._create_widgets()
        
    def _create_widgets(self):
        """Create and arrange all UI widgets"""
        # Header frame with title
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X)
        
        watchlist_label = tk.Label(
            header_frame, 
            text="Market Watchlist", 
            background=self.palette.background_primary,
            foreground=self.palette.text_primary,
            font=Typography.HEADING,
            padx=12,
            pady=8
        )
        watchlist_label.pack(anchor="w")
        
        # Create a separator below the header
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill=tk.X)
        
        # Commands frame for inputs
        self._commands_frame = ttk.Frame(self)
        self._commands_frame.pack(fill=tk.X, padx=12, pady=12)
        
        # Configure the grid for the commands frame
        self._commands_frame.columnconfigure(0, weight=1)
        self._commands_frame.columnconfigure(1, weight=1)
        
        # Binance entry
        binance_frame = ttk.Frame(self._commands_frame)
        binance_frame.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        
        self._binance_label = tk.Label(
            binance_frame, 
            text="Binance Symbol",
            background=self.palette.background_primary,
            foreground=self.palette.text_secondary,
            font=Typography.NORMAL
        )
        self._binance_label.pack(anchor="w", pady=(0, 2))
        
        self._binance_entry = tk.Entry(
            binance_frame,
            background=self.palette.input_background,
            foreground=self.palette.input_text,
            insertbackground=self.palette.text_primary,
            font=Typography.NORMAL,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.palette.input_border,
            highlightcolor=self.palette.accent_primary,
            relief="flat"
        )
        self._binance_entry.bind("<Return>", self._add_binance_symbol)
        self._binance_entry.pack(fill=tk.X)
        
        # Crypto.com entry
        crypto_frame = ttk.Frame(self._commands_frame)
        crypto_frame.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        self._crypto_label = tk.Label(
            crypto_frame, 
            text="Crypto.com Symbol",
            background=self.palette.background_primary,
            foreground=self.palette.text_secondary,
            font=Typography.NORMAL
        )
        self._crypto_label.pack(anchor="w", pady=(0, 2))
        
        self._crypto_entry = tk.Entry(
            crypto_frame,
            background=self.palette.input_background,
            foreground=self.palette.input_text,
            insertbackground=self.palette.text_primary,
            font=Typography.NORMAL,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.palette.input_border,
            highlightcolor=self.palette.accent_primary,
            relief="flat"
        )
        self._crypto_entry.bind("<Return>", self._add_crypto_symbol)
        self._crypto_entry.pack(fill=tk.X)
        
        # Table header frame
        table_header_frame = ttk.Frame(self)
        table_header_frame.pack(fill=tk.X, padx=12, pady=(12, 0))
        
        # Configure table header columns
        table_header_frame.columnconfigure(0, weight=3)  # Symbol
        table_header_frame.columnconfigure(1, weight=2)  # Exchange
        table_header_frame.columnconfigure(2, weight=1)  # Bid
        table_header_frame.columnconfigure(3, weight=1)  # Ask
        table_header_frame.columnconfigure(4, weight=0)  # Remove
        
        # Table headers
        headers = ["Symbol", "Exchange", "Bid", "Ask", ""]
        for idx, header_text in enumerate(headers):
            header = tk.Label(
                table_header_frame,
                text=header_text,
                background=self.palette.background_primary,
                foreground=self.palette.text_secondary,
                font=Typography.BOLD,
                anchor="w" if idx < 2 else "e",
                padx=4
            )
            header.grid(row=0, column=idx, sticky="ew", pady=(0, 8))
        
        # Create a separator below table headers
        table_separator = ttk.Separator(self, orient="horizontal")
        table_separator.pack(fill=tk.X, padx=12)
        
        # Create a container for the watchlist table with scrolling
        table_container = ttk.Frame(self)
        table_container.pack(fill=tk.BOTH, expand=True, padx=12)
        
        # Create scrollable canvas
        self.canvas = tk.Canvas(
            table_container,
            background=self.palette.background_primary,
            borderwidth=0,
            highlightthickness=0
        )
        
        # Create scrollbar
        scrollbar = ttk.Scrollbar(
            table_container, 
            orient=tk.VERTICAL, 
            command=self.canvas.yview
        )
        
        # Configure canvas with scrollbar
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Place canvas and scrollbar
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create frame for table content
        self._table_frame = ttk.Frame(self.canvas)
        
        # Configure table columns
        self._table_frame.columnconfigure(0, weight=3)  # Symbol
        self._table_frame.columnconfigure(1, weight=2)  # Exchange
        self._table_frame.columnconfigure(2, weight=1)  # Bid
        self._table_frame.columnconfigure(3, weight=1)  # Ask
        self._table_frame.columnconfigure(4, weight=0)  # Remove
        
        # Create window inside canvas for the frame
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self._table_frame, 
            anchor="nw",
            width=self.canvas.winfo_width()
        )
        
        # Configure canvas to resize with window
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self._table_frame.bind('<Configure>', self._on_frame_configure)
        
        # Initialize data structures for table widgets
        self.body_widgets = dict()
        self._headers = ["symbol", "exchange", "bid", "ask", "remove"]
        
        # Initialize storage for table cells
        for h in self._headers:
            self.body_widgets[h] = dict()
            if h in ["bid", "ask"]:
                self.body_widgets[h + "_var"] = dict()
        
        self._body_index = 0
        
        # Empty state message when no symbols added
        self._empty_label = tk.Label(
            self._table_frame,
            text="Enter a symbol to add it to your watchlist",
            background=self.palette.background_primary,
            foreground=self.palette.text_secondary,
            font=Typography.NORMAL,
            pady=24
        )
        self._empty_label.grid(row=0, column=0, columnspan=5)
    
    def _on_canvas_configure(self, event):
        """Update canvas window width when canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_frame_configure(self, event):
        """Update the scroll region to encompass all content"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _remove_symbol(self, b_index: int):
        """Remove a symbol from the watchlist"""
        for h in self._headers:
            self.body_widgets[h][b_index].grid_forget()
            del self.body_widgets[h][b_index]
            
        # Check if watchlist is empty and show empty state if needed
        if not self.body_widgets["symbol"]:
            self._empty_label.grid(row=0, column=0, columnspan=5, pady=24)
        
        # Update the scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _add_binance_symbol(self, event):
        """Add a Binance symbol to the watchlist"""
        symbol = event.widget.get().strip().upper()
        
        if not symbol:
            return
            
        if symbol in self.binance_symbols:
            self._add_symbol(symbol, "Binance")
            event.widget.delete(0, tk.END)
        else:
            # Provide feedback that symbol is invalid
            current_bg = event.widget.cget("background")
            event.widget.config(background=self.palette.error)
            self.after(200, lambda: event.widget.config(background=current_bg))

    def _add_crypto_symbol(self, event):
        """Add a Crypto.com symbol to the watchlist"""
        symbol = event.widget.get().strip().upper()
        
        if not symbol:
            return
            
        if symbol in self.crypto_symbols:
            self._add_symbol(symbol, "Crypto")
            event.widget.delete(0, tk.END)
        else:
            # Provide feedback that symbol is invalid
            current_bg = event.widget.cget("background")
            event.widget.config(background=self.palette.error)
            self.after(200, lambda: event.widget.config(background=current_bg))

    def _add_symbol(self, symbol: str, exchange: str):
        """Add a symbol to the watchlist table"""
        # Hide empty state if this is the first symbol
        if self._body_index == 0:
            self._empty_label.grid_forget()
            
        # Get current row index
        b_index = self._body_index
        
        # Symbol cell
        self.body_widgets["symbol"][b_index] = tk.Label(
            self._table_frame, 
            text=symbol,
            background=self.palette.background_primary,
            foreground=self.palette.text_primary,
            font=Typography.NORMAL,
            anchor="w",
            padx=4,
            pady=8
        )
        self.body_widgets["symbol"][b_index].grid(row=b_index, column=0, sticky="ew")
        
        # Exchange cell
        self.body_widgets["exchange"][b_index] = tk.Label(
            self._table_frame,
            text=exchange,
            background=self.palette.background_primary,
            foreground=self.palette.text_secondary,
            font=Typography.NORMAL,
            anchor="w",
            padx=4,
            pady=8
        )
        self.body_widgets["exchange"][b_index].grid(row=b_index, column=1, sticky="ew")
        
        # Bid price cell with StringVar for dynamic updates
        self.body_widgets["bid_var"][b_index] = tk.StringVar()
        self.body_widgets["bid_var"][b_index].set("Loading...")
        self.body_widgets["bid"][b_index] = tk.Label(
            self._table_frame,
            textvariable=self.body_widgets["bid_var"][b_index],
            background=self.palette.background_primary,
            foreground=self.palette.chart_down,  # Using red for bid as convention in trading
            font=Typography.BOLD,
            anchor="e",
            padx=4,
            pady=8
        )
        self.body_widgets["bid"][b_index].grid(row=b_index, column=2, sticky="ew")
        
        # Ask price cell with StringVar for dynamic updates
        self.body_widgets["ask_var"][b_index] = tk.StringVar()
        self.body_widgets["ask_var"][b_index].set("Loading...")
        self.body_widgets["ask"][b_index] = tk.Label(
            self._table_frame,
            textvariable=self.body_widgets["ask_var"][b_index],
            background=self.palette.background_primary,
            foreground=self.palette.chart_up,  # Using green for ask as convention in trading
            font=Typography.BOLD,
            anchor="e",
            padx=4,
            pady=8
        )
        self.body_widgets["ask"][b_index].grid(row=b_index, column=3, sticky="ew")
        
        # Remove button - small 'x' button with minimal styling
        self.body_widgets["remove"][b_index] = tk.Button(
            self._table_frame,
            text="×",  # Unicode multiplication sign as a better-looking X
            command=lambda: self._remove_symbol(b_index),
            background=self.palette.background_primary,
            foreground=self.palette.text_secondary,
            borderwidth=0,
            font=Typography.BOLD,
            padx=2,
            pady=0,
            width=2,
            cursor="hand2",
            activebackground=self.palette.error,
            activeforeground=self.palette.text_primary
        )
        self.body_widgets["remove"][b_index].grid(row=b_index, column=4, sticky="e", padx=(0, 4))
        
        # Increment row index for next addition
        self._body_index += 1
        
        # Update the scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))