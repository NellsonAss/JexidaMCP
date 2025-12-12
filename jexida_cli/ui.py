"""Backwards-compatible import for UI components.

The UI has been refactored into jexida_cli.ui/ package.
This module provides backwards compatibility.
"""

from .ui.renderer import Renderer
from .ui.frame import Frame
from .ui.colors import Colors, Theme

# Alias Renderer as UI for backwards compatibility
UI = Renderer

__all__ = [
    "UI",
    "Renderer",
    "Frame",
    "Colors",
    "Theme",
]
