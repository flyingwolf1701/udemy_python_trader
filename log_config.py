"""
Centralized logging configuration for the CryptoTrader application.

This module provides a consistent logging setup across the application with colored
output and configuration options that can be adjusted through environment variables.

from cryptotrader.config import get_logger
logger = get_logger(__name__)
"""

import os
import sys
import logging
from colorama import Fore, Style, init

# Initialize colorama (required for Windows compatibility)
init()

# Define color mapping for different log levels directly using colorama
LEVEL_COLORS = {
    logging.DEBUG: Fore.BLUE,
    logging.INFO: Fore.GREEN,
    logging.WARNING: Fore.YELLOW,
    logging.ERROR: Fore.RED,
    logging.CRITICAL: Style.BRIGHT + Fore.RED,
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log level names in terminal output."""
    
    def format(self, record):
        # Save original levelname
        orig_levelname = record.levelname
        # Add color to levelname based on log level
        if record.levelno in LEVEL_COLORS:
            record.levelname = f"{LEVEL_COLORS[record.levelno]}{record.levelname}{Style.RESET_ALL}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original levelname
        record.levelname = orig_levelname
        return result

# Configure root logger with colored formatting
log_level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_name, logging.INFO)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(log_level)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)

# Define the log format
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

# Use colored formatting if output is to a terminal
if sys.stdout.isatty():
    formatter = ColoredFormatter(log_format, datefmt=date_format)
else:
    formatter = logging.Formatter(log_format, datefmt=date_format)

console_handler.setFormatter(formatter)

# Only add handler if it hasn't been added already
if not root_logger.handlers:
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the application's settings.
    
    Args:
        name: The name for the logger, typically __name__
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)
