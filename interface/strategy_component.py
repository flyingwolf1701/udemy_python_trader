"""
Enhanced strategy component for configuring and managing trading strategies.
Features a modern UI with intuitive controls for strategy parameters.
"""

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import typing

from interface.styling import (
    ThemeManager, Typography, Spacing, 
    LabelStyles, EntryStyles, ButtonStyles, FrameStyles
)

from connectors.binance_exchange import BinanceExchangeClient
from connectors.crypto_exchange import CryptoExchangeClient


class StrategyEditor(ttk.Frame):
    """
    Modern component for configuring and managing trading strategies.
    """
    def __init__(
        self,
        root,
        binance: BinanceExchangeClient,
        crypto: CryptoExchangeClient,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        
        self.root = root
        self._exchanges = {"Binance": binance, "Crypto": crypto}
        
        # Prepare available contracts and timeframes
        self._all_contracts = []
        self._all_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h"]
        
        for exchange, client in self._exchanges.items():
            for symbol, contract in client.contracts.items():
                if symbol is not None:
                    self._all_contracts.append(f"{symbol}_{exchange}")
        
        # Define available strategy types and their parameters
        self._extra_params = {
            "Technical": [
                {"name": "EMA Fast Length", "code_name": "ema_fast", "widget": tk.Entry, "data_type": int},
                {"name": "EMA Slow Length", "code_name": "ema_slow", "widget": tk.Entry, "data_type": int},
                {"name": "RSI Length", "code_name": "rsi_length", "widget": tk.Entry, "data_type": int},
                {"name": "RSI Overbought", "code_name": "rsi_overbought", "widget": tk.Entry, "data_type": float},
                {"name": "RSI Oversold", "code_name": "rsi_oversold", "widget": tk.Entry, "data_type": float},
            ],
            "Breakout": [
                {"name": "Min. Volume", "code_name": "min_volume", "widget": tk.Entry, "data_type": float},
                {"name": "Num. Candles", "code_name": "num_candles", "widget": tk.Entry, "data_type": int},
                {"name": "Percent Change", "code_name": "percent", "widget": tk.Entry, "data_type": float},
            ]
        }
        
        # Initialize widget containers
        self.body_widgets = dict()
        self._additional_parameters = dict()
        self._extra_input = dict()
        
        # Create UI
        self._create_widgets()
    
    def _create_widgets(self):
        """Create and arrange the UI components"""
        palette = ThemeManager.get_current_palette()
        
        # Header frame with title
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, Spacing.S))
        
        strategy_label = tk.Label(header_frame, text="Strategy Manager", **LabelStyles.header())
        strategy_label.pack(side=tk.LEFT)
        
        # Add strategy button
        button_style = ButtonStyles.primary()
        self._add_button = tk.Button(
            header_frame,
            text="+ Add Strategy",
            **button_style
        )
        self._add_button.config(command=self._add_strategy_row)
        self._add_button.pack(side=tk.RIGHT)
        
        # Create a separator below the header
        separator = ttk.Separator(self, orient="horizontal", style="Header.TSeparator")
        separator.pack(fill=tk.X, pady=(0, Spacing.S))
        
        # Create container for strategy table
        table_container = ttk.Frame(self)
        table_container.pack(fill=tk.BOTH, expand=True, padx=Spacing.S, pady=Spacing.S)
        
        # Create scrollable canvas for table
        canvas = tk.Canvas(
            table_container,
            background=palette.background_primary,
            borderwidth=0,
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, command=canvas.yview)
        
        # Create the scrollable frame for the table
        self._table_frame = ttk.Frame(canvas)
        self._table_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # Create window inside the canvas for the frame
        canvas.create_window((0, 0), window=self._table_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Define strategy table headers
        self._headers = [
            "Strategy",
            "Contract",
            "Timeframe",
            "Balance %",
            "TP %",
            "SL %",
            "Parameters",
            "Status",
            "Actions"
        ]
        
        # Create table headers
        for idx, h in enumerate(self._headers):
            header = tk.Label(
                self._table_frame,
                text=h,
                **LabelStyles.header()
            )
            header.grid(row=0, column=idx, padx=Spacing.XS, pady=(0, Spacing.S), sticky="w")
        
        # Add a separator below headers
        header_separator = ttk.Separator(self._table_frame, orient="horizontal")
        header_separator.grid(row=1, column=0, columnspan=len(self._headers), sticky="ew", pady=Spacing.XS)
        
        # Define the base parameters for strategy rows
        self._base_params = [
            {
                "code_name": "strategy_type",
                "widget": ttk.Combobox,
                "data_type": str,
                "values": list(self._extra_params.keys()),
                "width": 10,
            },
            {
                "code_name": "contract",
                "widget": ttk.Combobox,
                "data_type": str,
                "values": self._all_contracts if self._all_contracts else ["NONE_FOUND"],
                "width": 15,
            },
            {
                "code_name": "timeframe",
                "widget": ttk.Combobox,
                "data_type": str,
                "values": self._all_timeframes,
                "width": 7,
            },
            {
                "code_name": "balance_pct",
                "widget": tk.Entry,
                "data_type": float,
                "width": 7,
            },
            {
                "code_name": "take_profit",
                "widget": tk.Entry,
                "data_type": float,
                "width": 7,
            },
            {
                "code_name": "stop_loss",
                "widget": tk.Entry,
                "data_type": float,
                "width": 7,
            },
            {
                "code_name": "parameters",
                "widget": tk.Button,
                "data_type": None,
                "button_text": "Edit",
                "command": self._show_popup,
                "style_func": ButtonStyles.secondary,
            },
            {
                "code_name": "activation",
                "widget": tk.Button,
                "data_type": None,
                "button_text": "OFF",
                "command": self._switch_strategy,
                "style_func": ButtonStyles.danger,
            },
            {
                "code_name": "delete",
                "widget": tk.Button,
                "data_type": None,
                "button_text": "×",
                "command": self._delete_row,
                "style_func": ButtonStyles.danger,
            },
        ]
        
        # Initialize data structures for table rows
        for h in self._base_params:
            self.body_widgets[h["code_name"]] = dict()
            if h["code_name"] in ["strategy_type", "contract", "timeframe"]:
                self.body_widgets[h["code_name"] + "_var"] = dict()
        
        # Start the body index at 2 (after the header and separator)
        self._body_index = 2
        
        # Initialize empty state message
        self._empty_label = tk.Label(
            self._table_frame,
            text="Click '+ Add Strategy' to create a new trading strategy",
            **LabelStyles.standard()
        )
        self._empty_label.grid(row=2, column=0, columnspan=len(self._headers), pady=Spacing.L)
    
    def _add_strategy_row(self):
        """Add a new strategy row to the table"""
        # Hide empty state if visible
        self._empty_label.grid_forget()
        
        # Get current row index
        b_index = self._body_index
        
        # Get color palette
        palette = ThemeManager.get_current_palette()
        
        # Create row background (alternate colors for better readability)
        row_bg = palette.background_secondary if b_index % 2 == 0 else palette.background_primary
        
        # Create widgets for each column
        for col, base_param in enumerate(self._base_params):
            code_name = base_param["code_name"]
            
            if base_param["widget"] == ttk.Combobox:
                # Create combobox with StringVar
                self.body_widgets[code_name + "_var"][b_index] = tk.StringVar()
                self.body_widgets[code_name + "_var"][b_index].set(base_param["values"][0])
                
                self.body_widgets[code_name][b_index] = ttk.Combobox(
                    self._table_frame,
                    textvariable=self.body_widgets[code_name + "_var"][b_index],
                    values=base_param["values"],
                    width=base_param["width"],
                    state="readonly"
                )
                
                # Add trace to strategy_type to update parameters when changed
                if code_name == "strategy_type":
                    self.body_widgets[code_name + "_var"][b_index].trace_add(
                        "write",
                        lambda *args, idx=b_index: self._on_strategy_change(idx)
                    )
                
            elif base_param["widget"] == tk.Entry:
                # Create entry field
                self.body_widgets[code_name][b_index] = tk.Entry(
                    self._table_frame,
                    width=base_param["width"],
                    **EntryStyles.standard(),
                    justify=tk.CENTER
                )
                
            elif base_param["widget"] == tk.Button:
                # Create button with appropriate style
                style_func = base_param.get("style_func", ButtonStyles.primary)
                button_text = base_param.get("button_text", "")
                button_style = style_func()
                
                self.body_widgets[code_name][b_index] = tk.Button(
                    self._table_frame,
                    text=button_text,
                    **button_style,
                    command=lambda frozen_command=base_param["command"], idx=b_index: frozen_command(idx)
                )
            
            # Grid the widget
            self.body_widgets[code_name][b_index].grid(
                row=b_index, 
                column=col, 
                padx=Spacing.XS, 
                pady=Spacing.XS,
                sticky="w" if col < 6 else "e"
            )
        
        # Initialize additional parameters for this row
        self._additional_parameters[b_index] = dict()
        
        # Initialize parameter values based on the selected strategy
        self._on_strategy_change(b_index)
        
        # Increment row index for next addition
        self._body_index += 1
    
    def _on_strategy_change(self, b_index: int):
        """Update parameter structure when strategy type changes"""
        if b_index not in self.body_widgets["strategy_type_var"]:
            return
            
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()
        
        # Reset additional parameters dictionary for this row
        self._additional_parameters[b_index] = dict()
        
        # Initialize parameters for the selected strategy
        for param in self._extra_params.get(strat_selected, []):
            self._additional_parameters[b_index][param["code_name"]] = None
    
    def _delete_row(self, b_index: int):
        """Remove a strategy row from the table"""
        # Remove all widgets for this row
        for element in self._base_params:
            code_name = element["code_name"]
            if b_index in self.body_widgets[code_name]:
                self.body_widgets[code_name][b_index].grid_forget()
                del self.body_widgets[code_name][b_index]
                
                # Also delete any associated variable
                var_name = code_name + "_var"
                if var_name in self.body_widgets and b_index in self.body_widgets[var_name]:
                    del self.body_widgets[var_name][b_index]
        
        # Remove additional parameters for this row
        if b_index in self._additional_parameters:
            del self._additional_parameters[b_index]
        
        # Show empty state if no more rows
        if not any(self.body_widgets["strategy_type"]):
            self._empty_label.grid(row=2, column=0, columnspan=len(self._headers), pady=Spacing.L)
    
    def _show_popup(self, b_index: int):
        """Show a popup window for editing strategy parameters"""
        # Get strategy type
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()
        
        # Create popup window
        self._popup_window = tk.Toplevel(self)
        self._popup_window.title(f"{strat_selected} Strategy Parameters")
        self._popup_window.configure(**FrameStyles.primary())
        
        # Make it modal
        self._popup_window.transient(self)
        self._popup_window.grab_set()
        
        # Position it near the parameters button
        btn_x = self.body_widgets["parameters"][b_index].winfo_rootx()
        btn_y = self.body_widgets["parameters"][b_index].winfo_rooty()
        self._popup_window.geometry(f"+{btn_x + 20}+{btn_y + 20}")
        
        # Create content frame
        content_frame = ttk.Frame(self._popup_window)
        content_frame.pack(padx=Spacing.L, pady=Spacing.L, fill=tk.BOTH, expand=True)
        
        # Add header
        header_label = tk.Label(
            content_frame,
            text=f"{strat_selected} Strategy Parameters",
            **LabelStyles.header()
        )
        header_label.pack(anchor="w", pady=(0, Spacing.M))
        
        # Add parameter fields
        row_nb = 0
        
        # Clear extra inputs dictionary
        self._extra_input = dict()
        
        # Create fields for each parameter
        for param in self._extra_params[strat_selected]:
            code_name = param["code_name"]
            
            # Parameter label
            param_frame = ttk.Frame(content_frame)
            param_frame.pack(fill=tk.X, pady=Spacing.XS)
            
            param_label = tk.Label(
                param_frame,
                text=param["name"],
                **LabelStyles.standard()
            )
            param_label.pack(anchor="w", pady=(0, Spacing.XXS))
            
            # Parameter input field
            self._extra_input[code_name] = tk.Entry(
                param_frame,
                **EntryStyles.standard()
            )
            
            # Add current value if exists
            if self._additional_parameters[b_index][code_name] is not None:
                self._extra_input[code_name].insert(
                    tk.END, 
                    str(self._additional_parameters[b_index][code_name])
                )
                
            self._extra_input[code_name].pack(fill=tk.X)
            
            row_nb += 1
        
        # Button frame
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=(Spacing.M, 0))
        
        # Cancel button
        cancel_style = ButtonStyles.secondary()
        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            **cancel_style,
            command=self._popup_window.destroy
        )
        cancel_button.pack(side=tk.LEFT, padx=(0, Spacing.S))
        
        # Save button
        save_style = ButtonStyles.primary()
        save_button = tk.Button(
            button_frame,
            text="Save Parameters",
            **save_style,
            command=lambda: self._validate_parameters(b_index)
        )
        save_button.pack(side=tk.RIGHT)
    
    def _validate_parameters(self, b_index: int):
        """Validate and save parameters from the popup"""
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()
        
        # Process each parameter
        for param in self._extra_params[strat_selected]:
            code_name = param["code_name"]
            input_value = self._extra_input[code_name].get().strip()
            
            if not input_value:
                # Empty value
                self._additional_parameters[b_index][code_name] = None
            else:
                try:
                    # Convert to the appropriate data type
                    converted_value = param["data_type"](input_value)
                    self._additional_parameters[b_index][code_name] = converted_value
                except ValueError:
                    # Show error message for invalid input
                    messagebox.showerror(
                        "Invalid Input",
                        f"Invalid value for {param['name']}. Expected {param['data_type'].__name__}."
                    )
                    return
        
        # Close the popup
        self._popup_window.destroy()
    
    def _switch_strategy(self, b_index: int):
        """Toggle strategy activation state"""
        # Validate required fields
        required_params = ["balance_pct", "take_profit", "stop_loss"]
        missing_params = []
        
        for param in required_params:
            if not self.body_widgets[param][b_index].get():
                missing_params.append(param.replace('_', ' ').title())
        
        # Check strategy-specific parameters
        strat_selected = self.body_widgets["strategy_type_var"][b_index].get()
        
        for param in self._extra_params[strat_selected]:
            if self._additional_parameters[b_index][param["code_name"]] is None:
                missing_params.append(param["name"])
        
        # Show error if any parameters are missing
        if missing_params:
            error_message = "Missing required parameters:\n• " + "\n• ".join(missing_params)
            messagebox.showerror("Missing Parameters", error_message)
            return
        
        # Get strategy details
        symbol = self.body_widgets["contract_var"][b_index].get().split("_")[0]
        timeframe = self.body_widgets["timeframe_var"][b_index].get()
        exchange = self.body_widgets["contract_var"][b_index].get().split("_")[1]
        
        # Toggle activation state
        current_state = self.body_widgets["activation"][b_index].cget("text")
        
        if current_state == "OFF":
            # Activate the strategy
            for param in self._base_params:
                code_name = param["code_name"]
                
                # Disable all widgets except activation button
                if code_name != "activation" and "_var" not in code_name:
                    self.body_widgets[code_name][b_index].config(state=tk.DISABLED)
            
            # Update activation button style
            success_style = ButtonStyles.success()
            self.body_widgets["activation"][b_index].config(
                text="ON",
                **success_style
            )
            
            # Log the activation
            self.root.logging_frame.add_log(
                f"{strat_selected} strategy on {symbol}/{timeframe} started"
            )
        else:
            # Deactivate the strategy
            for param in self._base_params:
                code_name = param["code_name"]
                
                # Enable all widgets
                if code_name != "activation" and "_var" not in code_name:
                    self.body_widgets[code_name][b_index].config(state=tk.NORMAL)
            
            # Update activation button style
            danger_style = ButtonStyles.danger()
            self.body_widgets["activation"][b_index].config(
                text="OFF",
                **danger_style
            )
            
            # Log the deactivation
            self.root.logging_frame.add_log(
                f"{strat_selected} strategy on {symbol}/{timeframe} stopped"
            )