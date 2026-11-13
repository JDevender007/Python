"""Text editor view - the graphical user interface."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional


class EditorView(ttk.Frame):
    """The text editor's graphical user interface."""

    def __init__(self, master: tk.Tk, **kwargs: any) -> None:
        super().__init__(master, **kwargs)
        self.master = master
        self._create_widgets()
        self._setup_layout()
        self._setup_bindings()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Menu bar
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)

        # File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="New", accelerator="Ctrl+N", command=self._on_new)
        self.file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self._on_open)
        self.file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self._on_save)
        self.file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self._on_save_as)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Close", accelerator="Ctrl+W", command=self._on_close)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_exit)
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        # Edit menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self._on_undo)
        self.edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self._on_redo)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._on_cut)
        self.edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._on_copy)
        self.edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self._on_paste)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self._on_select_all)
        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Find...", accelerator="Ctrl+F", command=self._on_find)
        self.edit_menu.add_command(label="Replace...", accelerator="Ctrl+H", command=self._on_replace)
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)

        # Search menu
        self.search_menu = tk.Menu(self.menubar, tearoff=0)
        self.search_menu.add_command(label="Find Next", accelerator="F3", command=self._on_find_next)
        self.search_menu.add_command(label="Previous", accelerator="Shift+F3", command=self._on_find_previous)
        self.menubar.add_cascade(label="Search", menu=self.search_menu)

        # View menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.word_wrap_var = tk.BooleanVar()
        self.view_menu.add_checkbutton(
            label="Word Wrap", variable=self.word_wrap_var,
            command=self._on_toggle_word_wrap
        )
        self.font_size_var = tk.IntVar(value=12)
        self.view_menu.add_separator()
        self.view_menu.add_label_variable("Font Size:", self.font_size_var)
        self.view_menu.add_separator()
        self.view_menu.add_command(label="Theme", command=self._on_theme)
        self.menubar.add_cascade(label="View", menu=self.view_menu)

        # Help menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label="About", command=self._on_about)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)

        # Main text area with scrollbar
        self.scroll_frame = ttk.Frame(self)
        self.scrollbar = ttk.Scrollbar(self.scroll_frame)
        self.text_area = tk.Text(
            self.scroll_frame,
            yscrollcommand=self.scrollbar.set,
            undo=True,
            font=("Segoe UI", 12),
            wrap="word" if self.word_wrap else "none",
        )
        self.scrollbar.config(command=self.text_area.yview)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.line_var = tk.StringVar(value="Line: 1")
        self.col_var = tk.StringVar(value="Col: 1")
        self.word_count_var = tk.StringVar(value="Words: 0")
        self.char_count_var = tk.StringVar(value="Chars: 0")

        self.status_bar = ttk.Frame(self)
        self.line_label = ttk.Label(self.status_bar, textvariable=self.line_var, anchor="w")
        self.col_label = ttk.Label(self.status_bar, textvariable=self.col_var, anchor="e")
        self.word_label = ttk.Label(self.status_bar, textvariable=self.word_count_var, anchor="w")
        self.char_label = ttk.Label(self.status_bar, textvariable=self.char_count_var, anchor="e")

        # Toolbar (optional - can be hidden)
        self.toolbar = ttk.Frame(self)
        ttk.Button(self.toolbar, text="Bold").pack(side="left", padx=2)
        ttk.Button(self.toolbar, text="Italic").pack(side="left", padx=2)

    def _setup_layout(self) -> None:
        """Set up the layout manager."""
        # Configure grid weights
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.scroll_frame.rowconfigure(0, weight=1)
        self.scroll_frame.columnconfigure(0, weight=1)

        # Pack widgets
        self.menubar.pack(side="top", fill="x")
        self.toolbar.pack(side="top", fill="x") if hasattr(self, 'toolbar') and self.toolbar.winfo_exists() else None
        
        self.scroll_frame.pack(fill="both", expand=True, side="top")
        self.text_area.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.status_bar.pack(side="bottom", fill="x")
        self.line_label.pack(side="left")
        self.col_label.pack(side="right")
        self.word_label.pack(side="left", padx=10)
        self.char_label.pack(side="right", padx=10)

        # Pack scroll frame
        self.scroll_frame.pack(fill="both", expand=True)

    def _setup_bindings(self) -> None:
        """Set up keyboard and text event bindings."""
        # Keyboard shortcuts
        self.master.bind("<Control-n>", lambda e: self._on_new())
        self.master.bind("<Control-o>", lambda e: self._on_open())
        self.master.bind("<Control-s>", lambda e: self._on_save())
        self.master.bind("<Control-a>", lambda e: self._on_select_all())
        self.master.bind("<Control-z>", lambda e: self._on_undo())
        self.master.bind("<Control-y>", lambda e: self._on_redo())
        self.master.bind("<Control-f>", lambda e: self._on_find())
        self.master.bind("<Control-h>", lambda e: self._on_replace())
        self.master.bind("<F3>", lambda e: self._on_find_next())
        self.master.bind("<Shift-F3>", lambda e: self._on_find_previous())

        # Text area events
        self.text_area.bind("<<Undo>>", lambda e: self._on_undo_state())
        self.text_area.bind("<<Redo>>", lambda e: self._on_redo_state())
        self.text_area.bind("<<Change>>", lambda e: self._on_text_change())

        # Mouse wheel scrolling
        self.text_area.bind("<MouseWheel>", self._on_mousewheel)
        self.text_area.bind("<Button-4>", self._on_mousewheel_up)
        self.text_area.bind("<Button-5>", self._on_mousewheel_down)

    # --- Event handlers ---

    def _on_new(self) -> None:
        """Handle New command."""
        pass  # Delegated to controller

    def _on_open(self) -> None:
        """Handle Open command."""
        pass  # Delegated to controller

    def _on_save(self) -> None:
        """Handle Save command."""
        pass  # Delegated to controller

    def _on_save_as(self) -> None:
        """Handle Save As command."""
        pass  # Delegated to controller

    def _on_close(self) -> None:
        """Handle Close command."""
        pass  # Delegated to controller

    def _on_exit(self) -> None:
        """Handle Exit command."""
        self.master.destroy()

    def _on_undo(self) -> None:
        """Handle Undo command."""
        pass  # Delegated to controller

    def _on_redo(self) -> None:
        """Handle Redo command."""
        pass  # Delegated to controller

    def _on_cut(self) -> None:
        """Handle Cut command."""
        pass  # Delegated to controller

    def _on_copy(self) -> None:
        """Handle Copy command."""
        pass  # Delegated to controller

    def _on_paste(self) -> None:
        """Handle Paste command."""
        pass  # Delegated to controller

    def _on_select_all(self) -> None:
        """Handle Select All command."""
        self.text_area.tag_add("sel", "1.0", "end")

    def _on_find(self) -> None:
        """Handle Find command."""
        pass  # Delegated to controller

    def _on_replace(self) -> None:
        """Handle Replace command."""
        pass  # Delegated to controller

    def _on_find_next(self) -> None:
        """Handle Find Next."""
        pass

    def _on_find_previous(self) -> None:
        """Handle Find Previous."""
        pass

    def _on_toggle_word_wrap(self) -> None:
        """Toggle word wrap."""
        wrap = self.word_wrap_var.get()
        self.text_area.config(wrap="word" if wrap else "none")

    def _on_theme(self) -> None:
        """Change theme."""
        pass

    def _on_about(self) -> None:
        """Show about dialog."""
        messagebox.showinfo(
            "About Text Editor",
            "A lightweight text editor built with Tkinter.\n"
            "Part of Python Placement Portfolio Project 02"
        )

    # --- Text area interaction helpers ---

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel scrolling."""
        self.text_area.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_up(self, event: tk.Event) -> None:
        """Handle mouse wheel up (Linux)."""
        self.text_area.yview_scroll(-1, "units")

    def _on_mousewheel_down(self, event: tk.Event) -> None:
        """Handle mouse wheel down (Linux)."""
        self.text_area.yview_scroll(1, "units")

    def _on_text_change(self) -> None:
        """Handle text changes - update status and undo/redo."""
        # Update status bar
        self._update_status_bar()
        # Mark document as modified
        if hasattr(self, '_controller') and self._controller:
            self._controller.on_text_changed()

    def _update_status_bar(self) -> None:
        """Update the status bar with cursor position and stats."""
        try:
            # Get cursor position
            idx = self.text_area.index("insert")
            line_num, col_num = idx.split(".")
            self.line_var.set(f"Line: {int(line_num)}")
            self.col_var.set(f"Col: {int(float(col_num))}")

            # Get selection and calculate stats
            try:
                sel_start = self.text_area.index("sel.first")
                sel_end = self.text_area.index("sel.last")
                selected_text = self.text_area.get(sel_start, sel_end)
                num_words = len(selected_text.split()) if selected_text.strip() else 0
                self.word_count_var.set(f"Words: {num_words}")
            except tk.TclError:
                # No selection
                num_words = len(self.text_area.get("1.0", "end-1c").split())
                self.word_count_var.set(f"Words: {num_words}")

            # Total stats
            total_text = self.text_area.get("1.0", "end-1c")
            total_chars = len(total_text)
            total_lines = len(total_text.splitlines())
            self.char_count_var.set(f"Chars: {total_chars}")
        except Exception:
            pass

    def set_controller(self, controller: object) -> None:
        """Set the controller reference."""
        self._controller = controller
        # Initialize status bar
        self._update_status_bar()

    def get_text(self) -> str:
        """Get all text from the text area."""
        return self.text_area.get("1.0", "end-1c")

    def set_text(self, text: str) -> None:
        """Set the text in the text area."""
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)


# --- Public API functions for controller ---

def init_view(view: EditorView, controller: object) -> None:
    """Initialize the view with a controller reference."""
    view.set_controller(controller)