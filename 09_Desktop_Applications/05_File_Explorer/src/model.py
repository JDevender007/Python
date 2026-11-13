"""File Explorer model - manages filesystem operations and directory structure."""

from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any


class DirectoryNode:
    """Represents a directory node in the file tree."""
    
    def __init__(self, path: Path, parent: Optional["DirectoryNode"] = None) -> None:
        self.path = path.resolve()
        self.parent = parent
        self.name = self.path.name
        self.is_file = self.path.is_file()
        self.is_root = self.path.root == self.path
        
        # Calculate children
        self.children: List["DirectoryNode"] = []
        self._size: Optional[int] = None
        self._modified: Optional[str] = None
        
        if not self.is_file:
            self._load_children()
    
    def _load_children(self) -> None:
        """Load child nodes (files and directories)."""
        try:
            for item in self.path.iterdir():
                if item.name.startswith("."):
                    continue  # Skip hidden files by default
                is_file = item.is_file()
                child = DirectoryNode(item, parent=self)
                self.children.append(child)
        except (PermissionError, OSError):
            pass  # Cannot read directory
        
        # Sort: directories first, then files, both alphabetically
        self.children.sort(key=lambda c: (c.is_file, c.name.lower()))
    
    @property
    def size(self) -> Optional[str]:
        """Get directory size as human-readable string."""
        if self._size is not None:
            return self._size
        if self.is_file:
            try:
                size = self.path.stat().st_size
                return self._format_size(size)
            except OSError:
                return "0 B"
        return None
    
    @staticmethod
    def _format_size(size: int) -> str:
        """Format bytes to human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    @property
    def modified(self) -> Optional[str]:
        """Get last modified time."""
        if self._modified is not None:
            return self._modified
        try:
            mtime = self.path.stat().st_mtime
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime)
            self._modified = dt.strftime("%Y-%m-%d %H:%M")
            return self._modified
        except OSError:
            return None
        return None
    
    def get_path(self) -> str:
        """Get the full path string."""
        return str(self.path)
    
    def get_relative_path(self, base: Optional[Path] = None) -> str:
        """Get path relative to base."""
        base = base or self.path.root
        try:
            return str(self.path.relative_to(base))
        except ValueError:
            return self.path.name
    
    def can_execute(self) -> bool:
        """Check if this is an executable file."""
        if self.is_file:
            return self.path.suffix.lower() in [".exe", ".bat", ".cmd", ".sh"]
        return False
    
    def can_open(self) -> bool:
        """Check if this can be opened with default application."""
        if self.is_file:
            return True  # Most files can be opened
        return self.path.is_dir()
    
    def __repr__(self) -> str:
        return f"DirectoryNode(path={self.path}, is_file={self.is_file})"


class FileSystemModel:
    """Manages the filesystem model for the file explorer."""
    
    def __init__(self, root_path: Optional[Path] = None) -> None:
        self.root: Optional[DirectoryNode] = None
        self.current: Optional[DirectoryNode] = None
        self.history: List[DirectoryNode] = []
        self.favorites: List[Path] = []
        self._show_hidden: bool = False
        
        # Set root to current user's home or provided path
        if root_path is None:
            root_path = Path.home()
        elif not root_path.exists():
            root_path = Path.home()
        
        self.root = DirectoryNode(root_path)
        self.current = self.root
    
    def refresh(self) -> None:
        """Refresh the current directory."""
        if self.current and not self.current.is_file:
            self.current._load_children()
    
    def go_to(self, path: Path) -> Optional[DirectoryNode]:
        """Navigate to a given path."""
        target = path.resolve()
        
        # Check if path exists
        if not target.exists():
            return None
        
        # If it's a file, create a file node
        if target.is_file():
            node = DirectoryNode(target)
            # Save to history only for directory navigation
            self.history.append(self.current) if self.current else None
            self.current = node
            return self.current
        
        # It's a directory - find or create node
        node = self._find_node(target)
        if node and not node.is_file:
            # Save to history
            self.history.append(self.current) if self.current else None
            self.current = node
            return self.current
        
        return None
    
    def _find_node(self, target: Path) -> Optional[DirectoryNode]:
        """Find a directory node by path."""
        def search(node: DirectoryNode, target: Path) -> Optional[DirectoryNode]:
            if node.path == target:
                return node
            for child in node.children:
                if child.is_dir():
                    result = search(child, target)
                    if result:
                        return result
            return None
        
        if self.root:
            return search(self.root, target)
        return None
    
    def go_up(self) -> Optional[DirectoryNode]:
        """Navigate to parent directory."""
        if self.current and self.current.parent:
            self.history.append(self.current)
            self.current = self.current.parent
            return self.current
        return None
    
    def go_home(self) -> DirectoryNode:
        """Navigate to home directory."""
        self.history.append(self.current)
        self.current = DirectoryNode(Path.home())
        return self.current
    
    def go_root(self) -> DirectoryNode:
        """Navigate to root directory."""
        self.history.append(self.current)
        self.current = DirectoryNode(Path.root)
        return self.current
    
    def get_selected(self) -> Optional[DirectoryNode]:
        """Get the currently selected node."""
        return self.current
    
    def toggle_hidden(self) -> None:
        """Toggle showing/hiding hidden files."""
        self._show_hidden = not self._show_hidden
        if self.current and not self.current.is_file:
            self.current._load_children()
    
    def get_drive_roots(self) -> List[DirectoryNode]:
        """Get list of drive roots (Windows)."""
        roots = []
        if os.name == "nt":  # Windows
            for drive in ["A:", "C:"] + [f"{d}:" for d in "DEFGHIJKLMNOPQRSTUVWXYZ" if 
                        os.path.exists(f"{d}:")]:
                roots.append(DirectoryNode(Path(dr)))
        else:  # Unix/Linux/Mac
            roots.append(DirectoryNode(Path("/")))
        return roots
    
    def get_current_path(self) -> str:
        """Get the current path string."""
        if self.current:
            return self.current.get_path()
        return str(Path.home())
    
    def get_breadcrumbs(self) -> List[str]:
        """Get breadcrumb trail."""
        breadcrumbs = []
        node = self.current
        while node and node.parent:
            breadcrumbs.append(node.name)
            node = node.parent
        breadcrumbs.reverse()
        breadcrumbs.append(self.current.path.root.name if self.current else "")
        return breadcrumbs