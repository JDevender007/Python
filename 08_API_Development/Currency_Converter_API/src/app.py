"""
Currency Converter API - Main Application Module
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import List, Optional
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    COLORS, POPULAR_CURRENCIES
)
from .tracker import CurrencyTracker, create_tracker
from .exporter import CurrencyExporter, create_exporter
from .controls import (
    ModernFrame, ModernLabel, ModernButton, ModernEntry, ModernCombobox,
    ModernTreeview, ProgressDialog, ExportDialog, ConversionCard, HistoryItemWidget
)
from .utils import load_history, format_currency, get_currency_symbol, format_number, format_rate
from .logger import logger


class CurrencyConverterApp:
    """Main application class for Currency Converter."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.tracker = create_tracker()
        self.exporter = create_exporter()
        self.setup_tracker_callbacks()
        self.setup_window()
        self.create_widgets()
        self.bind_shortcuts()
        self.load_initial_data()

    def setup_tracker_callbacks(self):
        self.tracker.set_progress_callback(self.on_progress)
        self.tracker.set_status_callback(self.on_status)

    def setup_window(self):
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.root.configure(bg=COLORS["bg"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        self.create_header()
        self.create_converter_section()
        self.create_history_section()
        self.create_status_bar()

    def create_header(self):
        header = ModernFrame(self.root)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        header.grid_columnconfigure(1, weight=1)

        ModernLabel(header, text="Currency Converter", style="title").grid(row=0, column=0, sticky="w")

        # Rate info
        self.rate_info_label = ModernLabel(header, text="Rates: Loading...", style="secondary")
        self.rate_info_label.grid(row=0, column=1, sticky="e")

    def create_converter_section(self):
        converter_frame = ModernFrame(self.root)
        converter_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 10))
        converter_frame.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # Conversion card
        self.conversion_card = ConversionCard(converter_frame)
        self.conversion_card.pack(fill="x", pady=10)
        self.conversion_card.set_swap_command(self.swap_currencies)

        # Input section
        input_frame = ModernFrame(converter_frame)
        input_frame.pack(fill="x", pady=10)

        # From currency selector
        from_frame = ModernFrame(input_frame)
        from_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ModernLabel(from_frame, text="From Currency", style="secondary").pack(anchor="w")
        self.from_currency_var = tk.StringVar(value="USD")
        self.from_currency_combo = ModernCombobox(
            from_frame,
            values=POPULAR_CURRENCIES,
            textvariable=self.from_currency_var,
            width=10
        )
        self.from_currency_combo.pack(fill="x", pady=5)
        self.from_currency_combo.bind("<<ComboboxSelected>>", lambda e: self.on_currency_change())

        # Amount entry
        amount_frame = ModernFrame(input_frame)
        amount_frame.pack(side="left", fill="x", expand=True, padx=10)

        ModernLabel(amount_frame, text="Amount", style="secondary").pack(anchor="w")
        self.amount_entry = ModernEntry(amount_frame, placeholder="Enter amount")
        self.amount_entry.pack(fill="x", pady=5, ipady=8)
        self.amount_entry.bind("<KeyRelease>", lambda e: self.on_amount_change())
        self.amount_entry.bind("<Return>", lambda e: self.convert())

        # To currency selector
        to_frame = ModernFrame(input_frame)
        to_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))

        ModernLabel(to_frame, text="To Currency", style="secondary").pack(anchor="w")
        self.to_currency_var = tk.StringVar(value="EUR")
        self.to_currency_combo = ModernCombobox(
            to_frame,
            values=POPULAR_CURRENCIES,
            textvariable=self.to_currency_var,
            width=10
        )
        self.to_currency_combo.pack(fill="x", pady=5)
        self.to_currency_combo.bind("<<ComboboxSelected>>", lambda e: self.on_currency_change())

        # Convert button
        btn_frame = ModernFrame(converter_frame)
        btn_frame.pack(fill="x", pady=10)

        ModernButton(btn_frame, text="Convert", command=self.convert, style="primary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Refresh Rates", command=self.refresh_rates, style="secondary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Export", command=self.export_conversion, style="secondary").pack(side="left", padx=5)

        # Rate display
        self.current_rate_label = ModernLabel(converter_frame, text="", style="rate")
        self.current_rate_label.pack(pady=5)

    def create_history_section(self):
        history_frame = ModernFrame(self.root)
        history_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        history_frame.grid_rowconfigure(1, weight=1)
        history_frame.grid_columnconfigure(0, weight=1)

        # History header
        header_frame = ModernFrame(history_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ModernLabel(header_frame, text="Conversion History", style="subtitle").pack(side="left")

        btn_frame = ModernFrame(header_frame)
        btn_frame.pack(side="right")
        ModernButton(btn_frame, text="Export History", command=self.export_history, style="secondary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Clear History", command=self.clear_history, style="secondary").pack(side="left", padx=5)

        # History list
        list_frame = ModernFrame(history_frame)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.history_canvas = tk.Canvas(list_frame, bg=COLORS["bg"], highlightthickness=0)
        self.history_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_canvas.yview)
        self.history_inner = ModernFrame(self.history_canvas)

        self.history_inner.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        )

        self.history_canvas.create_window((0, 0), window=self.history_inner, anchor="nw")
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)

        self.history_canvas.grid(row=0, column=0, sticky="nsew")
        self.history_scrollbar.grid(row=0, column=1, sticky="ns")

        self.history_canvas.bind("<MouseWheel>", self._on_history_scroll)

    def _on_history_scroll(self, event):
        self.history_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_status_bar(self):
        status_frame = ModernFrame(self.root)
        status_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)

        self.status_label = ModernLabel(status_frame, text="Ready", style="secondary")
        self.status_label.pack(side="left")

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame, variable=self.progress_var, mode="determinate", length=200
        )
        self.progress_bar.pack(side="right", padx=20)

    def bind_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.amount_entry.focus())
        self.root.bind("<Control-r>", lambda e: self.refresh_rates())
        self.root.bind("<Control-e>", lambda e: self.export_conversion())
        self.root.bind("<Control-h>", lambda e: self.export_history())
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)
        self.fullscreen = False

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self, event=None):
        if self.fullscreen:
            self.fullscreen = False
            self.root.attributes("-fullscreen", False)

    def on_progress(self, current: int, total: int, message: str):
        self.root.after(0, lambda: self._update_progress_ui(current, total, message))

    def _update_progress_ui(self, current: int, total: int, message: str):
        self.progress_var.set((current / total * 100) if total > 0 else 0)
        self.status_label.config(text=message)

    def on_status(self, message: str):
        self.root.after(0, lambda: self.status_label.config(text=message))

    def load_initial_data(self):
        self.tracker.load_history()
        self.refresh_rates()
        self.display_history()

    def refresh_rates(self):
        def run_refresh():
            self.tracker.fetch_rates(force=True)
            self.root.after(0, self.update_rate_info)

        threading.Thread(target=run_refresh, daemon=True).start()

    def update_rate_info(self):
        rates = self.tracker.current_rates
        if rates:
            self.rate_info_label.config(text=f"Rates: {len(rates.rates)} currencies | Base: {rates.base} | Source: {rates.source}")
            self.current_rate_label.config(text=f"1 {rates.base} = {format_rate(rates.get_rate(self.to_currency_var.get()) or 0)} {self.to_currency_var.get()}")
        else:
            self.rate_info_label.config(text="Rates: Not loaded")

    def on_currency_change(self):
        from_curr = self.from_currency_var.get()
        to_curr = self.to_currency_var.get()
        rate = self.tracker.get_rate(from_curr, to_curr)
        if rate:
            self.current_rate_label.config(text=f"1 {from_curr} = {format_rate(rate)} {to_curr}")
        self.convert()

    def on_amount_change(self):
        # Auto-convert on amount change (with small delay)
        self.root.after(500, self.convert)

    def convert(self):
        amount_str = self.amount_entry.get_value().strip()
        if not amount_str:
            return

        try:
            amount = float(amount_str.replace(",", ""))
        except ValueError:
            return

        from_curr = self.from_currency_var.get()
        to_curr = self.to_currency_var.get()

        if from_curr == to_curr:
            self.conversion_card.update_conversion(from_curr, to_curr, amount, amount, 1.0)
            self.current_rate_label.config(text=f"1 {from_curr} = 1.0000 {to_curr}")
            return

        self.progress_var.set(0)

        def run_convert():
            result = self.tracker.convert(amount, from_curr, to_curr)
            self.root.after(0, lambda: self.display_conversion_result(result))

        threading.Thread(target=run_convert, daemon=True).start()

    def display_conversion_result(self, result: Optional):
        if result:
            self.conversion_card.update_conversion(
                result.from_currency, result.to_currency,
                result.amount, result.result, result.rate
            )
            self.current_rate_label.config(text=f"1 {result.from_currency} = {format_rate(result.rate)} {result.to_currency}")
            self.display_history()
        else:
            self.status_label.config(text="Conversion failed")

    def swap_currencies(self):
        from_curr = self.from_currency_var.get()
        to_curr = self.to_currency_var.get()
        self.from_currency_var.set(to_curr)
        self.to_currency_var.set(from_curr)
        self.on_currency_change()

    def display_history(self):
        # Clear existing
        for widget in self.history_inner.winfo_children():
            widget.destroy()

        history = self.tracker.get_conversion_history()
        for entry in reversed(history[-20:]):  # Show last 20
            widget = HistoryItemWidget(self.history_inner, entry)
            widget.pack(fill="x", padx=10, pady=5)

    def export_conversion(self):
        # Export last conversion
        history = self.tracker.get_conversion_history()
        if not history:
            messagebox.showwarning("No Data", "No conversion to export")
            return

        last = history[-1]

        def export_callback(filepath: str, fmt: str):
            # Create a mock conversion object for export
            class MockConversion:
                pass
            conv = MockConversion()
            conv.from_currency = last["from_currency"]
            conv.to_currency = last["to_currency"]
            conv.amount = last["amount"]
            conv.result = last["result"]
            conv.rate = last["rate"]
            conv.timestamp = int(datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00")).timestamp())
            conv.source = "manual"

            if fmt in ("csv", "both"):
                self.exporter.export_conversion(conv, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_conversion_json(conv, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Conversion exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_history(self):
        history = self.tracker.get_conversion_history()
        if not history:
            messagebox.showwarning("No Data", "No history to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_history(history, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_history_json(history, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "History exported successfully!")

        ExportDialog(self.root, export_callback)

    def clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all conversion history?"):
            self.tracker.clear_history()
            self.display_history()
            self.status_label.config(text="History cleared")

    def on_closing(self):
        if self.tracker.is_fetching:
            if messagebox.askyesno("Quit", "Operation in progress. Quit anyway?"):
                self.tracker.stop()
                self.tracker.close()
                self.root.destroy()
        else:
            self.tracker.close()
            self.root.destroy()


from datetime import datetime
import threading


def main():
    root = tk.Tk()
    app = CurrencyConverterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()