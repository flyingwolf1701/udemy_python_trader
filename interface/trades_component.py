"""
Professional trades monitor component with dark theme.
Displays active and completed trades with status updates.
"""

import tkinter as tk
from tkinter import ttk
import typing

from interface.styling import ThemeManager, Typography, Spacing


class TradesWatch(ttk.Frame):
    """
    Modern component for monitoring active and historical trades.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize data structures
        self.body_widgets = dict()
        self._headers = ["time", "symbol", "exchange", "strategy", "side", "quantity", "status", "pnl"]
        
        # Create the UI
        self._create_widgets()
        
    def _create_widgets(self):
        """Create and arrange all UI widgets"""
        palette = ThemeManager.get_current_palette()
        
        # Header frame with title
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X)
        
        # Trade Monitor header
        trades_label = tk.Label(
            header_frame, 
            text="Trade Monitor",
            background=palette.background_primary,
            foreground=palette.text_primary,
            font=Typography.HEADING,
            padx=Spacing.L,
            pady=Spacing.S
        )
        trades_label.pack(anchor="w")
        
        # Create a separator below the header
        separator = ttk.Separator(self, orient="horizontal", style="TSeparator")
        separator.pack(fill=tk.X)
        
        # Table header frame
        table_header_frame = ttk.Frame(self)
        table_header_frame.pack(fill=tk.X, padx=Spacing.L, pady=(Spacing.S, 0))
        
        # Setup columns with appropriate weights
        column_weights = [1, 2, 1, 2, 1, 1, 1, 1]  # Relative weights for each column
        for i, weight in enumerate(column_weights):
            table_header_frame.columnconfigure(i, weight=weight)
        
        # Define header labels with better text
        headers = ["Time", "Symbol", "Exchange", "Strategy", "Side", "Quantity", "Status", "Pnl"]
        for idx, h in enumerate(headers):
            header = tk.Label(
                table_header_frame,
                text=h,
                background=palette.background_primary,
                foreground=palette.text_secondary,
                font=Typography.BOLD,
                anchor="w",
                padx=Spacing.XS,
                pady=Spacing.S
            )
            header.grid(row=0, column=idx, sticky="ew")
        
        # Add a separator below headers
        table_separator = ttk.Separator(self, orient="horizontal", style="TSeparator")
        table_separator.pack(fill=tk.X, padx=Spacing.L)
        
        # Create a frame for the table content
        self._table_frame = ttk.Frame(self)
        self._table_frame.pack(fill=tk.BOTH, expand=True, padx=Spacing.L, pady=0)
        
        # Setup same column weights for the table content
        for i, weight in enumerate(column_weights):
            self._table_frame.columnconfigure(i, weight=weight)
        
        # Initialize storage for table cells
        for h in self._headers:
            self.body_widgets[h] = dict()
            if h in ["status", "pnl"]:
                self.body_widgets[h + "_var"] = dict()
        
        # Start body index at 0
        self._body_index = 0
        
        # Empty state message
        self._empty_label = tk.Label(
            self._table_frame,
            text="No trades to display",
            background=palette.background_primary,
            foreground=palette.text_secondary,
            font=Typography.NORMAL,
            pady=Spacing.XL
        )
        self._empty_label.grid(row=0, column=0, columnspan=len(self._headers))
    
    def add_trade(self, data: typing.Dict):
        """
        Add a new trade to the trade monitor.
        
        Args:
            data: Dictionary containing trade data with keys matching the headers
        """
        # Hide empty state label if visible
        self._empty_label.grid_forget()
        
        # Get current row index and trade index
        b_index = self._body_index
        t_index = data['time']
        
        # Get colors based on current theme
        palette = ThemeManager.get_current_palette()
        
        # Determine text color for the side (buy/sell)
        side_color = palette.chart_up if data['side'].upper() == "BUY" else palette.chart_down
        
        # Common label style for this row
        row_bg = palette.background_primary
        
        # Time
        self.body_widgets['time'][t_index] = tk.Label(
            self._table_frame,
            text=data['time'],
            background=row_bg,
            foreground=palette.text_secondary,
            font=Typography.NORMAL,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['time'][t_index].grid(row=b_index, column=0, sticky="ew")
        
        # Symbol
        self.body_widgets['symbol'][t_index] = tk.Label(
            self._table_frame,
            text=data['symbol'],
            background=row_bg,
            foreground=palette.text_primary,
            font=Typography.BOLD,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['symbol'][t_index].grid(row=b_index, column=1, sticky="ew")
        
        # Exchange
        self.body_widgets['exchange'][t_index] = tk.Label(
            self._table_frame,
            text=data['exchange'],
            background=row_bg,
            foreground=palette.text_secondary,
            font=Typography.NORMAL,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['exchange'][t_index].grid(row=b_index, column=2, sticky="ew")
        
        # Strategy
        self.body_widgets['strategy'][t_index] = tk.Label(
            self._table_frame,
            text=data['strategy'],
            background=row_bg,
            foreground=palette.text_primary,
            font=Typography.NORMAL,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['strategy'][t_index].grid(row=b_index, column=3, sticky="ew")
        
        # Side (with color coding for buy/sell)
        self.body_widgets['side'][t_index] = tk.Label(
            self._table_frame,
            text=data['side'].upper(),
            background=row_bg,
            foreground=side_color,
            font=Typography.BOLD,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['side'][t_index].grid(row=b_index, column=4, sticky="ew")
        
        # Quantity
        self.body_widgets['quantity'][t_index] = tk.Label(
            self._table_frame,
            text=data['quantity'],
            background=row_bg,
            foreground=palette.text_primary,
            font=Typography.NORMAL,
            anchor="e",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['quantity'][t_index].grid(row=b_index, column=5, sticky="ew")
        
        # Status (with StringVar for dynamic updates)
        self.body_widgets['status_var'][t_index] = tk.StringVar()
        self.body_widgets['status_var'][t_index].set("PENDING")
        self.body_widgets['status'][t_index] = tk.Label(
            self._table_frame,
            textvariable=self.body_widgets['status_var'][t_index],
            background=row_bg,
            foreground=palette.warning,  # Default to warning color for pending status
            font=Typography.BOLD,
            anchor="w",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['status'][t_index].grid(row=b_index, column=6, sticky="ew")
        
        # Set up a trace on the status variable to update the color when it changes
        self.body_widgets['status_var'][t_index].trace_add(
            "write", 
            lambda *args, idx=t_index: self._update_status_color(idx)
        )
        
        # PNL (with StringVar for dynamic updates)
        self.body_widgets['pnl_var'][t_index] = tk.StringVar()
        self.body_widgets['pnl_var'][t_index].set("--")
        self.body_widgets['pnl'][t_index] = tk.Label(
            self._table_frame,
            textvariable=self.body_widgets['pnl_var'][t_index],
            background=row_bg,
            foreground=palette.text_primary,  # Default color, will update when PNL is set
            font=Typography.BOLD,
            anchor="e",
            padx=Spacing.XS,
            pady=Spacing.S
        )
        self.body_widgets['pnl'][t_index].grid(row=b_index, column=7, sticky="ew")
        
        # Set up a trace on the PNL variable to update the color when it changes
        self.body_widgets['pnl_var'][t_index].trace_add(
            "write", 
            lambda *args, idx=t_index: self._update_pnl_color(idx)
        )
        
        # Increment row index for next addition
        self._body_index += 1
    
    def _update_status_color(self, index):
        """Update the color of the status label based on its value"""
        palette = ThemeManager.get_current_palette()
        status = self.body_widgets['status_var'][index].get()
        
        if status == "COMPLETED":
            self.body_widgets['status'][index].config(foreground=palette.success)
        elif status == "CANCELED":
            self.body_widgets['status'][index].config(foreground=palette.error)
        elif status == "PENDING":
            self.body_widgets['status'][index].config(foreground=palette.warning)
        else:
            self.body_widgets['status'][index].config(foreground=palette.text_primary)
    
    def _update_pnl_color(self, index):
        """Update the color of the PNL label based on its value"""
        palette = ThemeManager.get_current_palette()
        pnl_text = self.body_widgets['pnl_var'][index].get()
        
        if pnl_text == "--":
            self.body_widgets['pnl'][index].config(foreground=palette.text_primary)
            return
            
        try:
            # Remove any currency symbols and parse as float
            pnl_value = float(pnl_text.replace('$', '').replace(',', ''))
            
            if pnl_value > 0:
                self.body_widgets['pnl'][index].config(foreground=palette.chart_up)
            elif pnl_value < 0:
                self.body_widgets['pnl'][index].config(foreground=palette.chart_down)
            else:
                self.body_widgets['pnl'][index].config(foreground=palette.text_primary)
        except ValueError:
            # If parsing fails, use default color
            self.body_widgets['pnl'][index].config(foreground=palette.text_primary)
    
    def update_trade(self, time_index: str, status: str = None, pnl: str = None):
        """
        Update the status and/or PNL of an existing trade.
        
        Args:
            time_index: The time index of the trade to update
            status: New status value (optional)
            pnl: New PNL value (optional)
        """
        if time_index not in self.body_widgets['time']:
            return
            
        if status is not None:
            self.body_widgets['status_var'][time_index].set(status)
            
        if pnl is not None:
            self.body_widgets['pnl_var'][time_index].set(pnl)