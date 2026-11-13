"""File Explorer view - the graphical user interface."""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional
from pathlib import Path

from .model import DirectoryNode, FileSystemModel


class ExplorerView(ttk.Frame):
    """The file explorer's graphical user interface."""
    
    def __init__(self, master: tk.Tk, **kwargs: any) -> None:
        super().__init__(master, **kwargs)
        self.master = master
        self.model: Optional[FileSystemModel] = None
        self._setup_ui()
        self._setup_bindings()
    
    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Toolbar
        self.toolbar = ttk.Frame(self)
        
        ttk.Button(self.toolbar, text="Up", command=self._on_up).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Home", command=self._on_home).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Root", command=self._on_root).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Refresh", command=self._on_refresh).pack(side="left", padx=2)
        
        ttk.Label(self.toolbar, text="Path:").pack(side="left", padx=(10, 2))
        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(self.toolbar, textvariable=self.path_var, width=40)
        self.path_entry.pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Go", command=self._on_go).pack(side="left", padx=2)
        
        ttk.Button(self.toolbar, text="New Folder", command=self._on_new_folder).pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Search", command=self._on_search).pack(side="left", padx=2)
        
        # Main area - split between tree and file list
        self.pane = ttk.PanedWindow(self, orient="horizontal")
        
        # Left - Directory tree
        self.tree_frame = ttk.LabelFrame(self.pane, text="Directory Tree")
        self.tree = ttk.Treeview(self.tree_frame, selectmode="browse")
        self.tree_scroll_y = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree_scroll_x = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set, xscrollcommand=self.tree_scroll_x.set)
        
        # Right - File list
        self.list_frame = ttk.LabelFrame(self.pane, text="Files")
        self.file_list = ttk.Treeview(self.list_frame, selectmode="extended")
        self.file_scroll_y = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.file_list.yview)
        self.file_scroll_x = ttk.Scrollbar(self.list_frame, orient="horizontal", command=self.file_list.xview)
        self.file_list.configure(yscrollcommand=self.file_scroll.set, xscrollcommand=self.file_scroll_x.set)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunge", anchor="w")
        
        # Configure pane weights
        self.pane.add(self.tree_frame, weight=1)
        self.pane.add(self.list_frame, weight=2)
        
        # Toolbar will be packed/gridded first
        # The pane will be packed after
        
    def _setup_layout(self) -> None:
        """Set up the layout manager."""
        # Toolbar
        self.toolbar.pack(side="top", fill="x", padx=5, pady=2)
        
        # Paned window with tree and file list
        self.pane.pack(fill="both", expand=True, padx=5, pady=2)
        
        # Status bar
        self.status_bar.pack(side="bottom", fill="x", padx=5, pady=2)
        
        # Initialize tree structure
        self._init_tree()
    
    def _init_tree(self) -> None:
        """Initialize the directory tree with root."""
        if self.model and self.model.root:
            self._populate_tree(self.tree, self.model.root)
            # Select root
            self.tree.selection_set(self.tree.get_children()[0] if self.tree.get_children() else "")
    
    def _setup_bindings(self) -> None:
        """Set up keyboard and event bindings."""
        # Tree double-click to navigate
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.file_list.bind("<Double-1>", self._on_file_double_click)
        
        # Keyboard shortcuts
        self.master.bind("<Up>", lambda e: self._on_up())
        self.master.bind("<Home>", lambda e: self._on_home())
        self.master.bind("<BackSpace>", lambda e: self._on_up())
        self.master.bind("<F2>", lambda e: self._on_rename())
        self.master.bind("<Return>", lambda e: self._on_double_click())
        
        # Tree keyboard navigation
        self.tree.bind("<Key>", self._on_tree_key)
        self.file_list.bind("<Key>", self._on_list_key)
    
    # --- Event handlers ---
    
    def _on_tree_double_click(self, event: tk.Event) -> None:
        """Handle double-click on tree item."""
        item = self.tree.focus()
        if item:
            self._navigate_to_item(item)
    
    def _on_file_double_click(self, event: tk.Event) -> None:
        """Handle double-click on file list item."""
        item = self.file_list.focus()
        if item:
            self._navigate_to_item(item)
    
    def _on_up(self) -> None:
        """Navigate up one directory."""
        if self.model:
            self.model.go_up()
            self._refresh_current()
    
    def _on_home(self) -> None:
        """Navigate to home directory."""
        if self.model:
            self.model.go_home()
            self._refresh_current()
    
    def _on_root(self) -> None:
        """Navigate to root directory."""
        if self.model:
            self.model.go_root()
            self._refresh_current()
    
    def _on_refresh(self) -> None:
        """Refresh current directory."""
        if self.model:
            self.model.refresh()
            self._refresh_current()
    
    def _on_go(self) -> None:
        """Go to path entered in field."""
        path_str = self.path_var.get().strip()
        if not path_str:
            return
        try:
            path = Path(path_str)
            if self.model:
                node = self.model.go_to(path)
                if node:
                    self._refresh_node(node)
        except Exception:
            messagebox.showerror("Error", "Invalid path")
    
    def _on_new_folder(self) -> None:
        """Create new folder."""
        if self.model and self.current:
            folder_name = tk.askstring("New Folder", "Enter folder name:")
            if folder_name:
                try:
                    new_path = Path(self.current.path) / folder_name
                    new_path.mkdir(exist_ok=True)
                    self.model.refresh()
                    self._refresh_current()
                except (PermissionError, OSError) as e:
                    messagebox.showerror("Error", f"Could not create folder: {e}")
    
    def _on_search(self) -> None:
        """Search for files."""
        # Basic search implementation
        term = tk.askstring("Search", "Search term:")
        if term:
            messagebox.showinfo("Search", f"Search for '{term}' - basic implementation")
    
    def _on_rename(self) -> None:
        """Rename selected item."""
        # Get selected item
        tree_item = self.tree.focus()
        list_item = self.file_list.focus()
        
        if tree_item:
            self._rename_item(tree_item, self.tree)
        elif list_item:
            self._rename_item(list_item, self.file_list)
        else:
            messagebox.showinfo("Rename", "Select an item to rename")
    
    def _rename_item(self, item_id, tree_widget) -> None:
        """Rename a tree item."""
        current_name = tree_widget.item(item_id, "text")
        new_name = tk.askstring("Rename", "Enter new name:", initialvalue=current_name)
        if new_name and new_name != current_name:
            try:
                # Get the path associated with this item
                # This is simplified - real implementation would store path in item tags
                item_path = Path(new_name)
                # Just rename the display name for now
                tree_widget.item(item_id, text=new_name)
                messagebox.showinfo("Rename", f"Renamed to: {new_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not rename: {e}")
    
    def _on_search(self) -> None:
        """Search for files."""
        term = tk.askstring("Search", "Search term:")
        if term:
            messagebox.showinfo("Search", f"Search for '{term}' - basic implementation")
    
    def _navigate_to_item(self, item_id) -> None:
        """Navigate to the selected tree or list item."""
        # Get the path associated with the item
        # In a full implementation, we'd store the path in the item's tags
        item_text = self.tree.item(item_id, "text") if self.tree.focus() == item_id else self.file_list.item(item_id, "text")
        
        # Simplified: navigate to a folder named after the item
        if self.model and self.current:
            new_path = Path(self.current.path) / item_text
            if new_path.exists() and new_path.is_dir():
                self.model.go_to(new_path)
                self._refresh_current()
    
    def _on_list_key(self, event: tk.Event) -> None:
        """Handle keyboard events in file list."""
        key = event.keysym
        if key == "Return":
            self._on_double_click()
        elif key in ("Up", "Down"):
            # Navigate selection
            pass
    
    def _on_tree_key(self, event: tk.Event) -> None:
        """Handle keyboard events in tree."""
        key = event.keysym
        if key == "Return":
            self._navigate_to_item(self.tree.focus())
        elif key == "Up":
            # Select previous item
            children = self.tree.get_children()
            if children:
                current_idx = self.tree.current()
                new_idx = (current_idx - 1) % len(children) if current_idx >= 0 else len(children) - 1
                self.tree.selection_set(children[new_idx])
        elif key == "Down":
            # Select next item
            children = self.tree.get_children()
            if children:
                current_idx = self.tree.current()
                new_idx = (current_idx + 1) % len(children) if current_idx >= 0 else 0
                self.tree.selection_set(children[new_idx])
    
    # --- Public API ---
    
    def set_model(self, model: FileSystemModel) -> None:
        """Set the file system model."""
        self.model = model
        self._init_tree()
        self._refresh_current()
    
    def _populate_tree(self, tree: tk.Treeview, node: DirectoryNode, parent: str = "") -> None:
        """Recursively populate the tree view."""
        # Insert this node
        node_id = tree.insert(parent, "end", text=node.name, open=True)
        
        # Add children
        for child in node.children:
            self._populate_tree(tree, child, node_id)
    
    def _refresh_current(self) -> None:
        """Refresh the current directory display."""
        if not self.model or not self.current:
            return
        
        # Update path entry
        self.path_var.set(self.current.get_path())
        
        # Refresh tree
        self._populate_tree(self.tree, self.current)
        
        # Refresh file list
        self._refresh_file_list()
        
        # Update status
        self._update_status()
    
    def _refresh_file_list(self) -> None:
        """Refresh the file list display."""
        # Clear current items
        self.file_list.delete(*self.file_list.get_children())
        
        if not self.current or self.current.is_file:
            return
        
        # Add files and directories
        for child in self.current.children:
            if child.is_file:
                # Try to get icon/index
                icon = "📄"  # Placeholder
                # Get size
                size_str = child.size or "?"
                display_text = f"{child.name} ({size_str})"
            else:
                icon = "📁"  # Placeholder for directory
                display_text = child.name
            
            self.file_list.insert("", "end", values=(icon, display_text))
    
    def _update_status(self) -> None:
        """Update the status bar."""
        if self.model and self.current:
            total = len(self.current.children) if self.current.children else 0
            self.status_var.set(
                f"Path: {self.current.path} | {total} items"
            )
        else:
            self.status_var.set("Ready")