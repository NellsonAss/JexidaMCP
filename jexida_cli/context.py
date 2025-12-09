"""Context management and session persistence for Jexida CLI."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set


# Default exclusion patterns for directory scanning
DEFAULT_EXCLUDE_PATTERNS: Set[str] = {
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "env",
    ".idea",
    ".vscode",
    ".jexida",
    "dist",
    "build",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
    "htmlcov",
    ".DS_Store",
    "Thumbs.db",
}

# File extensions considered as text files
TEXT_FILE_EXTENSIONS: Set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".txt", ".rst",
    ".html", ".css", ".scss", ".sass", ".less",
    ".sql", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".xml", ".csv", ".env", ".gitignore", ".dockerignore",
    ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".scala", ".r", ".lua", ".vim",
    "Dockerfile", "Makefile", "Vagrantfile", "Gemfile", "Rakefile",
}

# Maximum file size for reading content (100KB)
MAX_FILE_SIZE_BYTES = 100 * 1024


class ContextManager:
    """Manages directory context and session persistence."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        max_depth: int = 4,
        exclude_patterns: Optional[Set[str]] = None,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
    ):
        """
        Initialize the context manager.

        Args:
            working_dir: Working directory (defaults to current directory)
            max_depth: Maximum depth for directory scanning
            exclude_patterns: Patterns to exclude from scanning
            max_file_size: Maximum file size for content reading in bytes
        """
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self.max_depth = max_depth
        self.exclude_patterns = exclude_patterns or DEFAULT_EXCLUDE_PATTERNS
        self.max_file_size = max_file_size
        
        # Hidden context folder
        self.context_dir = self.working_dir / ".jexida"
        self.session_file = self.context_dir / "session.json"
        
        # Cached structure
        self._structure_cache: Optional[str] = None
        self._file_list_cache: Optional[List[str]] = None

    def _should_exclude(self, name: str) -> bool:
        """
        Check if a file/directory should be excluded.

        Args:
            name: File or directory name

        Returns:
            True if should be excluded
        """
        # Check exact match
        if name in self.exclude_patterns:
            return True
        
        # Check glob patterns (simple * matching)
        for pattern in self.exclude_patterns:
            if "*" in pattern:
                # Simple glob: *.egg-info matches foo.egg-info
                if pattern.startswith("*"):
                    if name.endswith(pattern[1:]):
                        return True
                elif pattern.endswith("*"):
                    if name.startswith(pattern[:-1]):
                        return True
        
        return False

    def _is_text_file(self, path: Path) -> bool:
        """
        Check if a file is likely a text file.

        Args:
            path: Path to file

        Returns:
            True if file appears to be text
        """
        name = path.name.lower()
        suffix = path.suffix.lower()
        
        # Check extension
        if suffix in TEXT_FILE_EXTENSIONS:
            return True
        
        # Check filename (for files like Dockerfile, Makefile)
        if name in TEXT_FILE_EXTENSIONS:
            return True
        
        # Files without extension might be text (scripts, configs)
        if not suffix and path.is_file():
            return True
        
        return False

    def scan_structure(self, force_refresh: bool = False) -> str:
        """
        Scan and return the directory structure as a tree string.

        Args:
            force_refresh: Force rescan even if cached

        Returns:
            Directory tree as formatted string
        """
        if self._structure_cache and not force_refresh:
            return self._structure_cache
        
        lines = [str(self.working_dir) + "/"]
        self._file_list_cache = []
        
        self._scan_dir(self.working_dir, "", 0, lines)
        
        self._structure_cache = "\n".join(lines)
        return self._structure_cache

    def _scan_dir(
        self, 
        directory: Path, 
        prefix: str, 
        depth: int, 
        lines: List[str]
    ) -> None:
        """
        Recursively scan a directory and build tree representation.

        Args:
            directory: Directory to scan
            prefix: Current line prefix for tree drawing
            depth: Current depth level
            lines: List to append lines to
        """
        if depth >= self.max_depth:
            return
        
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return
        
        # Filter out excluded entries
        entries = [e for e in entries if not self._should_exclude(e.name)]
        
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            
            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                self._scan_dir(entry, child_prefix, depth + 1, lines)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")
                # Cache relative path for file list
                try:
                    rel_path = entry.relative_to(self.working_dir)
                    self._file_list_cache.append(str(rel_path))
                except ValueError:
                    pass

    def get_file_list(self, force_refresh: bool = False) -> List[str]:
        """
        Get list of all files (relative paths).

        Args:
            force_refresh: Force rescan even if cached

        Returns:
            List of relative file paths
        """
        if self._file_list_cache is None or force_refresh:
            self.scan_structure(force_refresh)
        return self._file_list_cache or []

    def read_file_content(self, relative_path: str) -> Optional[str]:
        """
        Read content of a file if it's a text file and within size limits.

        Args:
            relative_path: Path relative to working directory

        Returns:
            File content or None if cannot be read
        """
        is_valid, file_path, message = self._validate_path(relative_path)
        if not is_valid:
            return message

        if not file_path.exists() or not file_path.is_file():
            return None

        # Check if text file
        if not self._is_text_file(file_path):
            return f"[File is not a text file: {relative_path}]"

        # Check size
        if file_path.stat().st_size > self.max_file_size:
            return f"[File too large: {file_path.stat().st_size} bytes, max: {self.max_file_size} bytes]"

        # Read content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Binary file or non-UTF-8
            return f"[File is not UTF-8 text: {relative_path}]"
        except Exception as e:
            return f"[Error reading file: {e}]"

    def _validate_path(self, relative_path: str) -> (bool, Optional[Path], Optional[str]):
        """
        Validate that a relative path is safe and within the working directory.

        Args:
            relative_path: Path relative to working directory

        Returns:
            Tuple of (is_valid, absolute_path, error_message)
        """
        try:
            file_path = self.working_dir / relative_path
            
            # Security check: ensure path is within working directory
            resolved_path = file_path.resolve()
            if not str(resolved_path).startswith(str(self.working_dir)):
                return False, None, "[Error: Path is outside the working directory]"

            # Prevent interacting with the .jexida directory itself
            if ".jexida" in resolved_path.parts:
                return False, None, "[Error: Access to .jexida directory is not allowed]"

            return True, resolved_path, None
        except Exception as e:
            return False, None, f"[Error: Invalid path - {e}]"

    def write_file_content(self, relative_path: str, content: str) -> (bool, str):
        """
        Write content to a file.

        Args:
            relative_path: Path relative to working directory
            content: Content to write

        Returns:
            Tuple of (success, message)
        """
        is_valid, file_path, message = self._validate_path(relative_path)
        if not is_valid:
            return False, message

        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Invalidate caches
            self._structure_cache = None
            self._file_list_cache = None
            
            return True, f"Successfully wrote to {relative_path}"
        except Exception as e:
            return False, f"[Error writing file: {e}]"

    def search_files(
        self, 
        search_pattern: str, 
        search_string: str, 
        max_results: int = 50
    ) -> List[str]:
        """
        Search for a string in files matching a glob pattern.

        Args:
            search_pattern: Glob pattern for files to search
            search_string: String to search for
            max_results: Maximum number of results to return

        Returns:
            A list of formatted result strings
        """
        results = []
        try:
            # Use rglob for recursive globbing from the working directory
            for file_path in self.working_dir.rglob(search_pattern):
                if len(results) >= max_results:
                    break
                
                if (
                    file_path.is_file()
                    and not self._should_exclude(file_path.name)
                    and self._is_text_file(file_path)
                    and ".jexida" not in file_path.parts
                ):
                    try:
                        relative_path = file_path.relative_to(self.working_dir)
                        with open(file_path, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f, 1):
                                if search_string in line:
                                    results.append(f"{relative_path}:{i}:{line.strip()}")
                                    if len(results) >= max_results:
                                        break
                    except Exception:
                        # Ignore files that can't be read
                        continue
            
            return results
        except Exception as e:
            return [f"[Error during search: {e}]"]

    def ensure_context_dir(self) -> bool:
        """
        Ensure the .jexida context directory exists.

        Returns:
            True if directory exists or was created
        """
        try:
            self.context_dir.mkdir(parents=True, exist_ok=True)
            
            # On Windows, try to set hidden attribute
            if os.name == "nt":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(
                        str(self.context_dir), 0x02  # FILE_ATTRIBUTE_HIDDEN
                    )
                except Exception:
                    pass
            
            return True
        except Exception:
            return False

    def save_session(self, conversation_history: List[Dict[str, str]]) -> bool:
        """
        Save conversation history to session file.

        Args:
            conversation_history: List of conversation messages

        Returns:
            True if saved successfully
        """
        if not self.ensure_context_dir():
            return False
        
        try:
            session_data = {
                "directory": str(self.working_dir),
                "last_updated": datetime.now().isoformat(),
                "conversation_history": conversation_history,
            }
            
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception:
            return False

    def load_session(self) -> Optional[List[Dict[str, str]]]:
        """
        Load conversation history from session file.

        Returns:
            Conversation history list or None if not found/invalid
        """
        if not self.session_file.exists():
            return None
        
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            # Verify it's for the same directory
            if session_data.get("directory") != str(self.working_dir):
                return None
            
            return session_data.get("conversation_history", [])
        except Exception:
            return None

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get session metadata without loading full history.

        Returns:
            Session info dict or None
        """
        if not self.session_file.exists():
            return None
        
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            
            return {
                "directory": session_data.get("directory"),
                "last_updated": session_data.get("last_updated"),
                "message_count": len(session_data.get("conversation_history", [])),
            }
        except Exception:
            return None

    def clear_session(self) -> bool:
        """
        Clear/delete the session file.

        Returns:
            True if cleared successfully
        """
        try:
            if self.session_file.exists():
                self.session_file.unlink()
            return True
        except Exception:
            return False

    def get_context_summary(self) -> str:
        """
        Get a summary of the current context.

        Returns:
            Context summary string
        """
        file_list = self.get_file_list()
        file_count = len(file_list)
        
        # Count by extension
        ext_counts: Dict[str, int] = {}
        for f in file_list:
            ext = Path(f).suffix.lower() or "(no ext)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        # Top extensions
        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:5]
        ext_summary = ", ".join(f"{ext}: {count}" for ext, count in top_exts)
        
        summary = [
            f"Directory: {self.working_dir}",
            f"Files: {file_count}",
            f"Types: {ext_summary}",
        ]
        
        # Session info
        session_info = self.get_session_info()
        if session_info:
            summary.append(f"Session: {session_info['message_count']} messages")
            summary.append(f"Last updated: {session_info['last_updated']}")
        else:
            summary.append("Session: (none)")
        
        return "\n".join(summary)

