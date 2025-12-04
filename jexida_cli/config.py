"""Configuration management for Jexida CLI."""

import fnmatch
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from tomlkit import parse, dumps


# Default context settings
DEFAULT_CONTEXT_MAX_DEPTH = 4
DEFAULT_CONTEXT_MAX_FILE_SIZE = 100 * 1024  # 100KB
DEFAULT_CONTEXT_EXCLUDE_PATTERNS = [
    "__pycache__", ".git", ".svn", ".hg", "node_modules",
    ".venv", "venv", ".env", "env", ".idea", ".vscode", ".jexida",
    "dist", "build", ".eggs", "*.egg-info", ".tox",
    ".pytest_cache", ".mypy_cache", ".coverage", "htmlcov",
    ".DS_Store", "Thumbs.db",
]


class Config:
    """Manages Jexida configuration from TOML file."""

    def __init__(self):
        """Initialize config with defaults."""
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.toml"
        self.data: Dict[str, Any] = {}

    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        if os.name == "nt":  # Windows
            config_dir = Path(os.environ.get("APPDATA", Path.home())) / ".jexida"
        else:  # Unix-like
            config_dir = Path.home() / ".jexida"
        return config_dir

    def load(self) -> None:
        """Load configuration from file, using defaults if file doesn't exist."""
        # Default configuration
        self.data = {
            "connection": {
                "host": "192.168.1.224",
                "user": "jexida",
            },
            "model": {
                "name": "phi3",
            },
            "mcp": {
                "port": 8080,
                "timeout": 60.0,
            },
            "routines": {},
            "whitelist": {},
            "context": {
                "max_depth": DEFAULT_CONTEXT_MAX_DEPTH,
                "max_file_size": DEFAULT_CONTEXT_MAX_FILE_SIZE,
                "exclude_patterns": DEFAULT_CONTEXT_EXCLUDE_PATTERNS.copy(),
                "auto_save_session": True,
                "auto_load_session": True,
            },
        }

        # Load from file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    file_data = parse(f.read())
                # Merge with defaults
                if "connection" in file_data:
                    self.data["connection"].update(dict(file_data["connection"]))
                if "model" in file_data:
                    self.data["model"].update(dict(file_data["model"]))
                if "mcp" in file_data:
                    self.data["mcp"].update(dict(file_data["mcp"]))
                if "routines" in file_data:
                    # Convert nested tomlkit tables to dicts
                    routines_dict = {}
                    for key, value in file_data["routines"].items():
                        if hasattr(value, "value"):  # tomlkit Table
                            routines_dict[key] = dict(value)
                        else:
                            routines_dict[key] = value
                    self.data["routines"] = routines_dict
                if "whitelist" in file_data:
                    # Load whitelist patterns
                    whitelist_dict = {}
                    for key, value in file_data["whitelist"].items():
                        whitelist_dict[key] = str(value) if value else "always"
                    self.data["whitelist"] = whitelist_dict
                if "context" in file_data:
                    # Merge context settings
                    context_data = dict(file_data["context"])
                    self.data["context"].update(context_data)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")
                print("Using default configuration.")

    def save(self) -> None:
        """Save current configuration to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            # Convert dict to tomlkit document and write
            from tomlkit import document, table, inline_table
            doc = document()
            for key, value in self.data.items():
                if key == "routines" and isinstance(value, dict):
                    # Routines need special handling for inline tables
                    tbl = table()
                    for k, v in value.items():
                        if isinstance(v, dict):
                            it = inline_table()
                            for ik, iv in v.items():
                                it[ik] = iv
                            tbl[k] = it
                        else:
                            tbl[k] = v
                    doc[key] = tbl
                elif isinstance(value, dict):
                    tbl = table()
                    for k, v in value.items():
                        tbl[k] = v
                    doc[key] = tbl
                else:
                    doc[key] = value
            f.write(dumps(doc))

    @property
    def host(self) -> str:
        """Get the SSH host."""
        return self.data["connection"]["host"]

    @property
    def user(self) -> str:
        """Get the SSH user."""
        return self.data["connection"]["user"]

    @property
    def mcp_port(self) -> int:
        """Get the MCP server port."""
        return self.data.get("mcp", {}).get("port", 8080)

    @property
    def mcp_timeout(self) -> float:
        """Get the MCP server request timeout."""
        return self.data.get("mcp", {}).get("timeout", 60.0)

    @property
    def model(self) -> str:
        """Get the Ollama model name."""
        return self.data["model"]["name"]

    @property
    def routines(self) -> Dict[str, Dict[str, str]]:
        """Get the routines dictionary."""
        return self.data.get("routines", {})

    @property
    def whitelist(self) -> Dict[str, str]:
        """Get the whitelist dictionary (pattern -> 'always')."""
        return self.data.get("whitelist", {})

    def get_routine(self, name: str) -> Optional[Dict[str, str]]:
        """Get a specific routine by name."""
        return self.routines.get(name)

    def set_model(self, model_name: str) -> None:
        """
        Set the model name and save to config file.

        Args:
            model_name: The new model name
        """
        self.data["model"]["name"] = model_name
        self.save()

    def is_whitelisted(self, command: str) -> bool:
        """
        Check if a command matches any whitelist pattern.

        Supports three pattern types:
        - Exact match: "ls" matches only "ls"
        - Glob/wildcard: "cat *" matches "cat foo.txt", "cat bar"
        - Regex (prefix with ~): "~docker.*" matches "docker ps", "docker run"

        Args:
            command: The command to check

        Returns:
            True if the command matches any whitelist pattern
        """
        for pattern in self.whitelist.keys():
            # Regex pattern (prefix with ~)
            if pattern.startswith("~"):
                regex_pattern = pattern[1:]
                try:
                    if re.match(regex_pattern, command):
                        return True
                except re.error:
                    continue
            # Glob/wildcard pattern (contains * or ?)
            elif "*" in pattern or "?" in pattern:
                if fnmatch.fnmatch(command, pattern):
                    return True
            # Exact match
            else:
                if command == pattern:
                    return True
        return False

    def add_to_whitelist(self, pattern: str) -> None:
        """
        Add a pattern to the whitelist and save config.

        Args:
            pattern: The pattern to add (exact, glob, or regex with ~ prefix)
        """
        self.data["whitelist"][pattern] = "always"
        self.save()

    def remove_from_whitelist(self, pattern: str) -> bool:
        """
        Remove a pattern from the whitelist and save config.

        Args:
            pattern: The pattern to remove

        Returns:
            True if pattern was found and removed, False otherwise
        """
        if pattern in self.data["whitelist"]:
            del self.data["whitelist"][pattern]
            self.save()
            return True
        return False

    def get_whitelist_patterns(self) -> List[str]:
        """
        Get all whitelist patterns.

        Returns:
            List of whitelist patterns
        """
        return list(self.whitelist.keys())

    # Context configuration properties

    @property
    def context_max_depth(self) -> int:
        """Get the maximum directory scan depth."""
        return self.data.get("context", {}).get("max_depth", DEFAULT_CONTEXT_MAX_DEPTH)

    @property
    def context_max_file_size(self) -> int:
        """Get the maximum file size for reading content."""
        return self.data.get("context", {}).get("max_file_size", DEFAULT_CONTEXT_MAX_FILE_SIZE)

    @property
    def context_exclude_patterns(self) -> List[str]:
        """Get the patterns to exclude from directory scanning."""
        return self.data.get("context", {}).get("exclude_patterns", DEFAULT_CONTEXT_EXCLUDE_PATTERNS)

    @property
    def context_auto_save_session(self) -> bool:
        """Get whether to auto-save sessions."""
        return self.data.get("context", {}).get("auto_save_session", True)

    @property
    def context_auto_load_session(self) -> bool:
        """Get whether to auto-load sessions."""
        return self.data.get("context", {}).get("auto_load_session", True)

