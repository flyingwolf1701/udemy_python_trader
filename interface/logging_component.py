"""
Professional logging component with dark theme.
Displays application logs with timestamps and color-coded message types.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime


class Logging(ttk.Frame):
    """
    Modern logging component that displays timestamped application messages.
    """
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        self._create_widgets()
        
    def _create_widgets(self):
        """Create and configure the logging widgets"""
        # Get theme colors from parent
        bg_color = self.master.winfo_toplevel().config().get('background', ['#121212'])[4]
        fg_color = "#FFFFFF"  # White text
        fg_secondary = "#B3B3B3"  # Light gray text
        accent_color = "#4DA6FF"  # Accent blue
        
        # Header frame
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X)
        
        # Log header with title
        log_label = tk.Label(
            header_frame, 
            text="Activity Log",
            background=bg_color,
            foreground=fg_color,
            font=("Segoe UI", 12, "bold"),
            padx=12,
            pady=8
        )
        log_label.pack(anchor="w")
        
        # Create a separator below the header
        separator = ttk.Separator(self, orient="horizontal")
        separator.pack(fill=tk.X)
        
        # Log display frame
        log_frame = ttk.Frame(self)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        
        # Configure the log text widget with professional styling
        self.logging_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            background=bg_color,
            foreground=fg_secondary,
            font=("Consolas", 10, "normal"),
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="arrow",
            insertbackground=fg_color
        )
        self.logging_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create a scrollbar
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.logging_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.logging_text.config(yscrollcommand=scrollbar.set)
        
        # Tag configurations for styled log entries
        self.logging_text.tag_configure("timestamp", foreground=accent_color)
        self.logging_text.tag_configure("info", foreground="#3B82F6")      # Info Blue
        self.logging_text.tag_configure("warning", foreground="#F59E0B")   # Warning Amber
        self.logging_text.tag_configure("error", foreground="#EF4444")     # Error Red
        self.logging_text.tag_configure("success", foreground="#10B981")   # Success Green

    def add_log(self, message: str):
        """
        Add a new log message to the log display.
        
        Args:
            message: The log message to display
        """
        # Parse message to determine log level
        log_level = "info"  # default level
        
        if any(keyword in message.lower() for keyword in ["error", "failed", "failure"]):
            log_level = "error"
        elif any(keyword in message.lower() for keyword in ["warn", "warning", "attention"]):
            log_level = "warning"
        elif any(keyword in message.lower() for keyword in ["success", "completed", "loaded"]):
            log_level = "success"
            
        # Enable editing
        self.logging_text.configure(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.logging_text.insert("1.0", f"{timestamp} ", "timestamp")
        
        # Add the log message with appropriate tag
        self.logging_text.insert("1.0 lineend", f"{message}\n", log_level)
        
        # Disable editing
        self.logging_text.configure(state=tk.DISABLED)
        
        # Auto-scroll to the top
        self.logging_text.see("1.0")
        
    def clear_logs(self):
        """Clear all logs from the display"""
        self.logging_text.configure(state=tk.NORMAL)
        self.logging_text.delete("1.0", tk.END)
        self.logging_text.configure(state=tk.DISABLED)