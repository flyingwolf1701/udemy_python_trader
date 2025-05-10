"""
Professional trading application styling system with dark theme.
This module provides a comprehensive theming system designed specifically for a trading interface.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Tuple


class ThemeMode(Enum):
    """Available theme modes for the application."""
    DARK = "dark"
    LIGHT = "light"


@dataclass
class ColorPalette:
    """Color palette for the application."""
    # Primary background colors
    background_primary: str
    background_secondary: str
    background_tertiary: str
    
    # Text colors
    text_primary: str
    text_secondary: str
    text_accent: str
    
    # UI element colors
    accent_primary: str
    accent_secondary: str
    
    # Status colors
    success: str
    warning: str
    error: str
    info: str
    
    # Chart colors
    chart_up: str
    chart_down: str
    
    # Border colors
    border: str
    
    # Input fields
    input_background: str
    input_border: str
    input_text: str


# Dark theme color palette - Trading specific
DARK_THEME = ColorPalette(
    # Dark backgrounds
    background_primary="#121212",
    background_secondary="#1E1E1E",
    background_tertiary="#2D2D2D",
    
    # Text colors for dark theme
    text_primary="#FFFFFF",
    text_secondary="#B3B3B3",
    text_accent="#4DA6FF",
    
    # UI elements - Blue theme
    accent_primary="#2C7BE5",
    accent_secondary="#155ED4",
    
    # Status colors
    success="#10B981",  # Green
    warning="#F59E0B",  # Amber
    error="#EF4444",    # Red
    info="#3B82F6",     # Blue
    
    # Chart colors
    chart_up="#10B981",  # Green for price increase
    chart_down="#EF4444",  # Red for price decrease
    
    # Border
    border="#3A3A3A",
    
    # Input fields
    input_background="#2D2D2D",
    input_border="#3A3A3A",
    input_text="#FFFFFF"
)

# Light theme is available but not actively used in this trading app
LIGHT_THEME = ColorPalette(
    # Light backgrounds
    background_primary="#FFFFFF",
    background_secondary="#F3F4F6",
    background_tertiary="#E5E7EB",
    
    # Text colors for light theme
    text_primary="#111827",
    text_secondary="#6B7280",
    text_accent="#2563EB",
    
    # UI elements
    accent_primary="#2563EB",
    accent_secondary="#1D4ED8",
    
    # Status colors
    success="#059669",
    warning="#D97706",
    error="#DC2626",
    info="#2563EB",
    
    # Chart colors
    chart_up="#059669",
    chart_down="#DC2626",
    
    # Border
    border="#D1D5DB",
    
    # Input fields
    input_background="#F9FAFB",
    input_border="#D1D5DB",
    input_text="#111827"
)


class ThemeManager:
    """Manages the current theme and provides access to colors and styles."""
    
    _current_mode: ThemeMode = ThemeMode.DARK
    
    @classmethod
    def get_current_palette(cls) -> ColorPalette:
        """Returns the current color palette based on theme mode."""
        return DARK_THEME if cls._current_mode == ThemeMode.DARK else LIGHT_THEME
    
    @classmethod
    def switch_theme(cls, mode: ThemeMode) -> None:
        """Switches the current theme mode."""
        cls._current_mode = mode
    
    @classmethod
    def get_color(cls, color_name: str) -> str:
        """Get a color from the current palette by attribute name."""
        palette = cls.get_current_palette()
        return getattr(palette, color_name)


# Spacing system for consistent UI layout
class Spacing:
    """Provides consistent spacing values throughout the application."""
    XXS = "2"
    XS = "4"
    S = "8"
    M = "12"
    L = "16"
    XL = "24"
    XXL = "32"
    XXXL = "48"


# Font definitions for consistent typography
class Typography:
    """Provides consistent font styles throughout the application."""
    FAMILY = "Segoe UI"
    FAMILY_MONO = "Consolas"
    
    # Font sizes
    SIZE_XS = 9
    SIZE_S = 10
    SIZE_M = 11
    SIZE_L = 12
    SIZE_XL = 14
    SIZE_XXL = 16
    
    # Font configurations
    NORMAL = (FAMILY, SIZE_M, "normal")
    BOLD = (FAMILY, SIZE_M, "bold")
    HEADING = (FAMILY, SIZE_L, "bold")
    HEADING_LARGE = (FAMILY, SIZE_XL, "bold")
    MONOSPACE = (FAMILY_MONO, SIZE_M, "normal")


# Border styles
class Borders:
    """Provides consistent border styles throughout the application."""
    NONE = 0
    THIN = 1
    MEDIUM = 2
    
    @staticmethod
    def get_border(size: int = THIN, color: str = None) -> Dict:
        """Returns a border configuration dictionary."""
        if color is None:
            color = ThemeManager.get_color("border")
        return {"width": size, "color": color}


# Button styles
class ButtonStyles:
    """Provides consistent button styles throughout the application."""
    
    @staticmethod
    def primary() -> Dict:
        """Primary button style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.accent_primary,
            "foreground": palette.text_primary,
            "activebackground": palette.accent_secondary,
            "activeforeground": palette.text_primary,
            "font": Typography.BOLD,
            "borderwidth": 0,
            "padx": Spacing.M,
            "pady": Spacing.S,
            "cursor": "hand2"
        }
    
    @staticmethod
    def secondary() -> Dict:
        """Secondary button style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_tertiary,
            "foreground": palette.text_primary,
            "activebackground": palette.background_secondary,
            "activeforeground": palette.text_primary,
            "font": Typography.NORMAL,
            "borderwidth": 0,
            "padx": Spacing.M,
            "pady": Spacing.S,
            "cursor": "hand2"
        }
    
    @staticmethod
    def danger() -> Dict:
        """Danger/delete button style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.error,
            "foreground": palette.text_primary,
            "activebackground": "#C81E1E",  # Darker red
            "activeforeground": palette.text_primary,
            "font": Typography.BOLD,
            "borderwidth": 0,
            "padx": Spacing.M,
            "pady": Spacing.S,
            "cursor": "hand2"
        }
    
    @staticmethod
    def success() -> Dict:
        """Success button style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.success,
            "foreground": palette.text_primary,
            "activebackground": "#047857",  # Darker green
            "activeforeground": palette.text_primary,
            "font": Typography.BOLD,
            "borderwidth": 0,
            "padx": Spacing.M,
            "pady": Spacing.S,
            "cursor": "hand2"
        }


# Entry styles
class EntryStyles:
    """Provides consistent entry field styles."""
    
    @staticmethod
    def standard() -> Dict:
        """Standard entry field style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.input_background,
            "foreground": palette.input_text,
            "insertbackground": palette.text_primary,  # Cursor color
            "font": Typography.NORMAL,
            "borderwidth": 1,
            "highlightthickness": 1,
            "highlightbackground": palette.input_border,
            "highlightcolor": palette.accent_primary,
            "relief": "flat"
        }


# Label styles
class LabelStyles:
    """Provides consistent label styles."""
    
    @staticmethod
    def header() -> Dict:
        """Header label style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_primary,
            "foreground": palette.text_primary,
            "font": Typography.HEADING,
            "padx": Spacing.XS,
            "pady": Spacing.XS
        }
    
    @staticmethod
    def standard() -> Dict:
        """Standard label style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_primary,
            "foreground": palette.text_secondary,
            "font": Typography.NORMAL,
            "padx": Spacing.XS,
            "pady": Spacing.XS
        }
    
    @staticmethod
    def value() -> Dict:
        """Value label style (for displaying data)."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_primary,
            "foreground": palette.text_accent,
            "font": Typography.NORMAL,
            "padx": Spacing.XS,
            "pady": Spacing.XS
        }
    
    @staticmethod
    def table_header() -> Dict:
        """Style for table headers."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_primary,
            "foreground": palette.text_secondary,
            "font": Typography.BOLD,
            "padx": Spacing.S,
            "pady": Spacing.S
        }


# Frame styles
class FrameStyles:
    """Provides consistent frame styles throughout the application."""
    
    @staticmethod
    def primary() -> Dict:
        """Primary frame style."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_primary,
            "padx": Spacing.M,
            "pady": Spacing.M,
            "borderwidth": 0
        }
    
    @staticmethod
    def secondary() -> Dict:
        """Secondary frame style (for grouping elements)."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_secondary,
            "padx": Spacing.M,
            "pady": Spacing.M,
            "borderwidth": 1,
            "relief": "solid",
            "highlightbackground": palette.border,
            "highlightthickness": 1
        }
    
    @staticmethod
    def card() -> Dict:
        """Card style for containing content."""
        palette = ThemeManager.get_current_palette()
        return {
            "background": palette.background_secondary,
            "padx": Spacing.M,
            "pady": Spacing.M,
            "borderwidth": 0,
            "relief": "flat"
        }


# For backwards compatibility with existing code
# These will be deprecated in future versions
BG_COLOR = ThemeManager.get_color("background_primary")
BG_COLOR_2 = ThemeManager.get_color("background_secondary")
FG_COLOR = ThemeManager.get_color("text_primary")
FG_COLOR_2 = ThemeManager.get_color("text_accent")
GLOBAL_FONT = Typography.NORMAL
BOLD_FONT = Typography.BOLD

# BG_COLOR = "gray12"
# BG_COLOR_2 = "#1c2c5c"
# FG_COLOR = "white"
# FG_COLOR_2 = "SteelBlue1"
# GLOBAL_FONT = ("Calibri", 11, "normal")
# BOLD_FONT = ("Calibri", 11, "bold")