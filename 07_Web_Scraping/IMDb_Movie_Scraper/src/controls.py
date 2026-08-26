"""
IMDb Movie Scraper - Controls Module
Custom Tkinter widgets and controls.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional, List, Dict, Any
from .colors import COLORS


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
            pady=10,
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
            font=("Segoe UI", 10),
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
        """Get value, returning empty string if placeholder is shown."""
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
            "title": {"font": ("Segoe UI", 18, "bold"), "fg": COLORS["accent"]},
            "subtitle": {"font": ("Segoe UI", 12, "bold"), "fg": COLORS["fg"]},
            "secondary": {"font": ("Segoe UI", 9), "fg": COLORS["text_secondary"]},
            "success": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["success"]},
            "error": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["error"]},
            "warning": {"font": ("Segoe UI", 10, "bold"), "fg": COLORS["warning"]},
        }
        style_config = styles.get(style, styles["normal"])
        super().__init__(parent, text=text, bg=COLORS["bg"], **style_config, **kwargs)


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
            rowheight=35,
            font=("Segoe UI", 9),
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
        """Update progress bar to determinate mode."""
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

        tk.Radiobutton(
            formats_frame, text="CSV", variable=self.format_var, value="csv",
            bg=COLORS["bg"], fg=COLORS["fg"], selectcolor=COLORS["card_bg"],
            activebackground=COLORS["bg"], activeforeground=COLORS["accent"],
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=20, pady=5)

        tk.Radiobutton(
            formats_frame, text="JSON", variable=self.format_var, value="json",
            bg=COLORS["bg"], fg=COLORS["fg"], selectcolor=COLORS["card_bg"],
            activebackground=COLORS["bg"], activeforeground=COLORS["accent"],
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=20, pady=5)

        tk.Radiobutton(
            formats_frame, text="Both", variable=self.format_var, value="both",
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
            filetypes=[
                ("CSV files", "*.csv"),
                ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
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


class MovieDetailDialog(tk.Toplevel):
    """Dialog showing detailed movie information."""

    def __init__(self, parent, movie: Dict):
        super().__init__(parent)
        self.title(f"Movie Details: {movie.get('title', 'Unknown')}")
        self.geometry("700x600")
        self.configure(bg=COLORS["bg"])
        self.transient(parent)

        main_frame = ModernFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        canvas = tk.Canvas(main_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ModernFrame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._populate_details(scrollable_frame, movie)

        ModernButton(self, text="Close", command=self.destroy, style="secondary").pack(pady=10)

    def _populate_details(self, parent, movie: Dict):
        """Populate detail fields."""
        fields = [
            ("Rank", movie.get("rank")),
            ("Title", movie.get("title")),
            ("Year", movie.get("year")),
            ("Rating", f"{movie.get('rating', 'N/A')}/10" if movie.get('rating') else "N/A"),
            ("Votes", movie.get("votes")),
            ("Genres", ", ".join(movie.get("genres", [])) if movie.get("genres") else "N/A"),
            ("Duration", f"{movie.get('duration_minutes', 'N/A')} min" if movie.get('duration_minutes') else "N/A"),
            ("Director", movie.get("director", "N/A")),
            ("Writers", ", ".join(movie.get("writers", [])) if movie.get("writers") else "N/A"),
            ("Stars", ", ".join(movie.get("stars", [])) if movie.get("stars") else "N/A"),
            ("Certificate", movie.get("certificate", "N/A")),
            ("Release Date", movie.get("release_date", "N/A")),
            ("Countries", ", ".join(movie.get("countries", [])) if movie.get("countries") else "N/A"),
            ("Languages", ", ".join(movie.get("languages", [])) if movie.get("languages") else "N/A"),
            ("Budget", movie.get("budget", "N/A")),
            ("Gross Worldwide", movie.get("gross", "N/A")),
            ("IMDb URL", f"https://www.imdb.com{movie.get('url', '')}" if movie.get('url') else "N/A"),
        ]

        for i, (label, value) in enumerate(fields):
            row_frame = ModernFrame(parent)
            row_frame.pack(fill="x", pady=5)

            ModernLabel(row_frame, text=f"{label}:", style="subtitle", width=18, anchor="w").pack(side="left")
            
            value_text = str(value) if value is not None else "N/A"
            if label == "Description" and len(value_text) > 200:
                value_text = value_text[:200] + "..."
            
            value_label = ModernLabel(row_frame, text=value_text, style="normal", anchor="w", wraplength=450, justify="left")
            value_label.pack(side="left", fill="x", expand=True, padx=10)

        desc = movie.get("description")
        if desc:
            desc_frame = ModernFrame(parent)
            desc_frame.pack(fill="x", pady=10)
            ModernLabel(desc_frame, text="Description:", style="subtitle").pack(anchor="w")
            ModernLabel(desc_frame, text=desc, style="normal", wraplength=600, justify="left").pack(anchor="w", pady=5)