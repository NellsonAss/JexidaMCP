"""Color definitions and theme management for Jexida CLI."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class Theme:
    """Color theme definition."""
    
    # Primary colors
    primary: str = "bright_cyan"
    secondary: str = "cyan"
    accent: str = "magenta"
    
    # Status colors
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    info: str = "blue"
    
    # UI element colors
    border: str = "dim cyan"
    header: str = "bold bright_cyan"
    muted: str = "dim"
    highlight: str = "bold"
    
    # Target-specific colors
    ssh_target: str = "cyan"
    local_target: str = "magenta"
    mcp_target: str = "blue"


class Colors:
    """Centralized color management for CLI output."""
    
    # Default theme
    _current_theme = Theme()
    
    @classmethod
    def get_theme(cls) -> Theme:
        """Get the current theme."""
        return cls._current_theme
    
    @classmethod
    def set_theme(cls, theme: Theme) -> None:
        """Set the current theme."""
        cls._current_theme = theme
    
    @classmethod
    def style(cls, text: str, style: str) -> str:
        """Apply a Rich style to text."""
        return f"[{style}]{text}[/{style}]"
    
    @classmethod
    def primary(cls, text: str) -> str:
        """Apply primary color."""
        return cls.style(text, cls._current_theme.primary)
    
    @classmethod
    def success(cls, text: str) -> str:
        """Apply success color."""
        return cls.style(text, cls._current_theme.success)
    
    @classmethod
    def warning(cls, text: str) -> str:
        """Apply warning color."""
        return cls.style(text, cls._current_theme.warning)
    
    @classmethod
    def error(cls, text: str) -> str:
        """Apply error color."""
        return cls.style(text, cls._current_theme.error)
    
    @classmethod
    def info(cls, text: str) -> str:
        """Apply info color."""
        return cls.style(text, cls._current_theme.info)
    
    @classmethod
    def muted(cls, text: str) -> str:
        """Apply muted style."""
        return cls.style(text, cls._current_theme.muted)
    
    @classmethod
    def highlight(cls, text: str) -> str:
        """Apply highlight style."""
        return cls.style(text, cls._current_theme.highlight)
    
    @classmethod
    def target_color(cls, target: str) -> str:
        """Get color for a specific target type."""
        theme = cls._current_theme
        target_map = {
            "ssh": theme.ssh_target,
            "remote": theme.ssh_target,
            "local": theme.local_target,
            "mcp": theme.mcp_target,
        }
        return target_map.get(target.lower(), theme.secondary)
    
    @classmethod
    def status_icon(cls, status: str) -> str:
        """Get a styled status icon."""
        icons = {
            "success": f"[{cls._current_theme.success}]✓[/{cls._current_theme.success}]",
            "error": f"[{cls._current_theme.error}]✗[/{cls._current_theme.error}]",
            "warning": f"[{cls._current_theme.warning}]⚠[/{cls._current_theme.warning}]",
            "info": f"[{cls._current_theme.info}]ℹ[/{cls._current_theme.info}]",
            "pending": f"[{cls._current_theme.muted}]○[/{cls._current_theme.muted}]",
            "active": f"[{cls._current_theme.success}]●[/{cls._current_theme.success}]",
        }
        return icons.get(status, "")

