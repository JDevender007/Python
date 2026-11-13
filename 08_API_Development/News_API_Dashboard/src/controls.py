"""
News API Dashboard - Controls Module
Custom Tkinter widgets and controls.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional, List, Dict, Any
from .config import COLORS, COUNTRIES, CATEGORIES, SORT_OPTIONS
from .utils import format_number, format_relative_time, truncate_text, extract_domain, calculate_reading_time


class ModernButton(tk.Button):
    """Modern styled button."""

    def __init__(self, parent, text: str, command: Callable = None,
                 style: str = "primary", **kwargs):
        bg_color = COLORS["accent"] if style == "primary" else COLORS["button_bg"]
        fg_color = COLORS["bg"] if style == "primary" else COLORS["fg"]
        hover_color = COLORS["accent_hover"] if style == "primary" else COLORS["border"]

        super().__init__(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=fg_color,
            activebackground=hover_color,
            activeforeground=fg_color,
            font=("Segoe UI", 10, "bold" if style == "primary" else "normal"),
            relief="flat",
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            **kwargs
        )
        self.default_bg = bg_color
        self.hover_bg = hover_color
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, event):
        self.config(bg=self.hover_bg)

    def _on_leave(self, event):
        self.config(bg=self.default_bg)


class ModernEntry(tk.Entry):
    """Modern styled entry field."""

    def __init__(self, parent, placeholder: str = "", **kwargs):
        super().__init__(
            parent,
            bg=COLORS["input_bg"],
            fg=COLORS["input_fg"],
            insertbackground=COLORS["accent"],
            font=("Segoe UI", 11),
            relief="flat",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            **kwargs
        )
        self.placeholder = placeholder
        self.placeholder_color = COLORS["text_secondary"]
        self.default_fg = COLORS["input_fg"]
        self._has_placeholder = False

        if placeholder:
            self._show_placeholder()

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _show_placeholder(self):
        self.insert(0, self.placeholder)
        self.config(fg=self.placeholder_color)
        self._has_placeholder = True

    def _on_focus_in(self, event):
        if self._has_placeholder:
            self.delete(0, tk.END)
            self.config(fg=self.default_fg)
            self._has_placeholder = False

    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        if self._has_placeholder:
            return ""
        return self.get()


class ModernFrame(tk.Frame):
    """Modern styled frame."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)


class ModernLabel(tk.Label):
    """Modern styled label."""

    def __init__(self, parent, text: str, style: str = "normal", **kwargs):
        styles = {
            "normal": {"font": ("Segoe UI", 10), "fg": COLORS["fg"]},
            "title": {"font": ("Segoe UI", 22, "bold"), "fg": COLORS["accent"]},
            "subtitle": {"font": ("Segoe UI", 13, "bold"), "fg": COLORS["fg"]},
            "secondary": {"font": ("Segoe UI", 9), "fg": COLORS["text_secondary"]},
            "success": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["success"]},
            "error": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["error"]},
            "warning": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["warning"]},
            "large": {"font": ("Segoe UI", 18), "fg": COLORS["fg"]},
            "article_title": {"font": ("Segoe UI", 14, "bold"), "fg": COLORS["fg"], "wraplength": 600, "justify": "left"},
            "article_meta": {"font": ("Segoe UI", 9), "fg": COLORS["text_secondary"]},
            "article_desc": {"font": ("Segoe UI", 10), "fg": COLORS["fg"], "wraplength": 600, "justify": "left"},
        }
        style_config = styles.get(style, styles["normal"])
        super().__init__(parent, text=text, bg=COLORS["bg"], **style_config, **kwargs)


class ModernCombobox(ttk.Combobox):
    """Modern styled combobox."""

    def __init__(self, parent, values: List[str] = None, **kwargs):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.TCombobox",
            fieldbackground=COLORS["input_bg"],
            background=COLORS["card_bg"],
            foreground=COLORS["input_fg"],
            arrowcolor=COLORS["accent"],
            borderwidth=1,
            relief="flat",
        )

        super().__init__(
            parent,
            values=values or [],
            state="readonly",
            font=("Segoe UI", 10),
            style="Modern.TCombobox",
            **kwargs
        )


class ModernTreeview(ttk.Treeview):
    """Modern styled treeview/table."""

    def __init__(self, parent, columns: List[str], **kwargs):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.Treeview",
            background=COLORS["card_bg"],
            foreground=COLORS["fg"],
            fieldbackground=COLORS["card_bg"],
            borderwidth=0,
            rowheight=32,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=COLORS["table_header"],
            foreground=COLORS["accent"],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", COLORS["table_selected"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["scrollbar"],
            troughcolor=COLORS["card_bg"],
            borderwidth=0,
            arrowcolor=COLORS["fg"],
        )

        super().__init__(
            parent,
            columns=columns,
            show="headings",
            style="Modern.Treeview",
            **kwargs
        )

        for col in columns:
            self.heading(col, text=col.replace("_", " ").title())
            self.column(col, width=120, anchor="w", stretch=True)

        self.tag_configure("odd", background=COLORS["table_row_alt"])
        self.tag_configure("even", background=COLORS["card_bg"])


class ProgressDialog(tk.Toplevel):
    """Progress dialog for long-running operations."""

    def __init__(self, parent, title: str = "Processing", message: str = "Please wait..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x150")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.cancelled = False

        ModernLabel(self, text=message, style="normal").pack(pady=20)

        self.progress = ttk.Progressbar(
            self, mode="indeterminate", style="Modern.Horizontal.TProgressbar"
        )
        self.progress.pack(fill="x", padx=20, pady=10)
        self.progress.start(10)

        btn_frame = ModernFrame(self)
        btn_frame.pack(pady=10)
        ModernButton(btn_frame, text="Cancel", command=self._cancel, style="secondary").pack()

        self.center_window()

    def _cancel(self):
        self.cancelled = True
        self._update_status("Cancelling...")

    def _update_status(self, message: str):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(text=message)
                break

    def update_progress(self, current: int, total: int, message: str = ""):
        self.progress.stop()
        self.progress.config(mode="determinate", maximum=total, value=current)
        if message:
            self._update_status(message)

    def center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")


class ExportDialog(tk.Toplevel):
    """Dialog for export options."""

    def __init__(self, parent, callback: Callable[[str, str], None]):
        super().__init__(parent)
        self.title("Export Data")
        self.geometry("400x250")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.transient(parent)
        self.grab_set()
        self.callback = callback

        ModernLabel(self, text="Export Options", style="title").pack(pady=20)

        self.format_var = tk.StringVar(value="csv")

        formats_frame = ModernFrame(self)
        formats_frame.pack(pady=10)

        for text, value in [("CSV", "csv"), ("JSON", "json"), ("Both", "both")]:
            tk.Radiobutton(
                formats_frame, text=text, variable=self.format_var, value=value,
                bg=COLORS["bg"], fg=COLORS["fg"], selectcolor=COLORS["card_bg"],
                activebackground=COLORS["bg"], activeforeground=COLORS["accent"],
                font=("Segoe UI", 10)
            ).pack(anchor="w", padx=20, pady=5)

        btn_frame = ModernFrame(self)
        btn_frame.pack(pady=20)

        ModernButton(btn_frame, text="Export", command=self._export, style="primary").pack(side="left", padx=10)
        ModernButton(btn_frame, text="Cancel", command=self.destroy, style="secondary").pack(side="left", padx=10)

        self.center_window()

    def _export(self):
        fmt = self.format_var.get()
        filepath = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}" if fmt != "both" else ".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Export File"
        )
        if filepath:
            self.callback(filepath, fmt)
        self.destroy()

    def center_window(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")


class ArticleCard(tk.Frame):
    """Article display card."""

    def __init__(self, parent, article, on_click: Callable = None, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.article = article
        self.on_click = on_click
        self.create_widgets()

    def create_widgets(self):
        main_frame = ModernFrame(self)
        main_frame.pack(fill="x", padx=15, pady=12)

        # Image placeholder + content
        content_frame = ModernFrame(main_frame)
        content_frame.pack(fill="x", expand=True)

        # Title
        self.title_label = ModernLabel(content_frame, text=self.article.title, style="article_title")
        self.title_label.pack(anchor="w", pady=(0, 8))

        # Meta info
        meta_frame = ModernFrame(content_frame)
        meta_frame.pack(fill="x", pady=(0, 8))

        source_text = self.article.source_display
        if self.article.author:
            source_text += f" • {self.article.author}"
        if self.article.category:
            source_text += f" • {self.article.category.title()}"
        if self.article.country:
            source_text += f" • {self.article.country.upper()}"

        ModernLabel(meta_frame, text=source_text, style="article_meta").pack(side="left")

        ModernLabel(meta_frame, text=self.article.relative_time, style="article_meta").pack(side="right")

        # Description
        if self.article.description:
            desc = truncate_text(self.article.description, 300)
            ModernLabel(content_frame, text=desc, style="article_desc").pack(anchor="w", pady=(0, 8))

        # Footer
        footer_frame = ModernFrame(content_frame)
        footer_frame.pack(fill="x")

        ModernLabel(footer_frame, text=f"📖 {self.article.reading_time}", style="article_meta").pack(side="left")

        domain = extract_domain(self.article.url)
        if domain:
            ModernLabel(footer_frame, text=f"🔗 {domain}", style="article_meta").pack(side="right")

        # Click handler
        if self.on_click:
            for widget in [self, main_frame, content_frame, self.title_label]:
                widget.bind("<Button-1>", lambda e: self.on_click())
                widget.config(cursor="hand2")


class SourceCard(tk.Frame):
    """Source display card."""

    def __init__(self, parent, source, **kwargs):
        super().__init__(parent, bg=COLORS["card_bg"], **kwargs)
        self.source = source
        self.create_widgets()

    def create_widgets(self):
        main_frame = ModernFrame(self)
        main_frame.pack(fill="x", padx=15, pady=10)

        # Name and category
        header = ModernFrame(main_frame)
        header.pack(fill="x")

        ModernLabel(header, text=self.source.name, style="subtitle").pack(side="left")

        if self.source.category:
            cat_label = ModernLabel(header, text=self.source.category.title(), style="secondary")
            cat_label.pack(side="right")

        # Description
        if self.source.description:
            desc = truncate_text(self.source.description, 200)
            ModernLabel(main_frame, text=desc, style="article_desc").pack(anchor="w", pady=(5, 0))

        # Meta
        meta_frame = ModernFrame(main_frame)
        meta_frame.pack(fill="x", pady=(8, 0))

        if self.source.country:
            ModernLabel(meta_frame, text=f"🌍 {self.source.country.upper()}", style="article_meta").pack(side="left", padx=(0, 15))
        if self.source.language:
            ModernLabel(meta_frame, text=f"🌐 {self.source.language}", style="article_meta").pack(side="left", padx=(0, 15))
        if self.source.url:
            domain = extract_domain(self.source.url)
            ModernLabel(meta_frame, text=f"🔗 {domain}", style="article_meta").pack(side="right")