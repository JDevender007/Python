"""
Weather API Client - Main Application Module
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import List, Optional
from .config import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, MIN_WIDTH, MIN_HEIGHT,
    COLORS, DEFAULT_UNITS, POPULAR_CITIES
)
from .tracker import WeatherTracker, create_tracker
from .exporter import WeatherExporter, create_exporter
from .controls import (
    ModernFrame, ModernLabel, ModernButton, ModernEntry, ModernCombobox,
    ModernTreeview, ProgressDialog, ExportDialog, WeatherCard, ForecastItemWidget
)
from .logger import logger


class WeatherApp:
    """Main application class for Weather API Client."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.tracker = create_tracker()
        self.exporter = create_exporter()
        self.setup_tracker_callbacks()
        self.setup_window()
        self.create_widgets()
        self.bind_shortcuts()

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
        self.create_search_bar()
        self.create_main_content()
        self.create_status_bar()

    def create_header(self):
        header = ModernFrame(self.root)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
        header.grid_columnconfigure(1, weight=1)

        ModernLabel(header, text="Weather API Client", style="title").grid(row=0, column=0, sticky="w")

        # Unit selector
        unit_frame = ModernFrame(header)
        unit_frame.grid(row=0, column=1, sticky="e")

        ModernLabel(unit_frame, text="Units:", style="secondary").pack(side="left", padx=5)
        self.units_var = tk.StringVar(value="metric")
        ModernCombobox(unit_frame, values=["metric (°C)", "imperial (°F)"],
                      textvariable=self.units_var, width=15).pack(side="left", padx=5)

        self.units_var.trace("w", self._on_units_change)

    def _on_units_change(self, *args):
        units = "metric" if "metric" in self.units_var.get() else "imperial"
        self.tracker.set_units(units)
        self.refresh_current_display()

    def create_search_bar(self):
        search_frame = ModernFrame(self.root)
        search_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        ModernLabel(search_frame, text="Search City:", style="secondary").pack(side="left", padx=5)

        self.city_entry = ModernEntry(search_frame, placeholder="Enter city name (e.g., London,UK)")
        self.city_entry.pack(side="left", fill="x", expand=True, padx=5, ipady=5)
        self.city_entry.bind("<Return>", lambda e: self.search_city())

        # Popular cities dropdown
        self.popular_var = tk.StringVar()
        popular_combo = ModernCombobox(search_frame, values=POPULAR_CITIES,
                                       textvariable=self.popular_var, width=20)
        popular_combo.pack(side="left", padx=5)
        popular_combo.bind("<<ComboboxSelected>>", self._on_popular_selected)

        ModernButton(search_frame, text="Search", command=self.search_city, style="primary").pack(side="left", padx=5)
        ModernButton(search_frame, text="Current Location", command=self.use_current_location, style="secondary").pack(side="left", padx=5)

    def _on_popular_selected(self, event):
        self.city_entry.delete(0, tk.END)
        self.city_entry.insert(0, self.popular_var.get())
        self.city_entry.config(fg=COLORS["input_fg"])
        self.search_city()

    def create_main_content(self):
        # Notebook for tabs
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Modern.TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
        )
        style.configure(
            "Modern.TNotebook.Tab",
            background=COLORS["card_bg"],
            foreground=COLORS["text_secondary"],
            padding=[20, 10],
            font=("Segoe UI", 10),
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["bg"])],
        )

        self.notebook = ttk.Notebook(self.root, style="Modern.TNotebook")
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.root.grid_rowconfigure(2, weight=1)

        self.create_current_tab()
        self.create_forecast_tab()
        self.create_search_tab()

    def create_current_tab(self):
        self.current_tab = ModernFrame(self.notebook)
        self.notebook.add(self.current_tab, text="  Current Weather  ")
        self.current_tab.grid_rowconfigure(1, weight=1)
        self.current_tab.grid_columnconfigure(0, weight=1)

        # Weather card
        self.weather_card = WeatherCard(self.current_tab)
        self.weather_card.grid(row=0, column=0, sticky="ew", padx=20, pady=20)

        # Details table
        detail_frame = ModernFrame(self.current_tab)
        detail_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        detail_frame.grid_rowconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)

        columns = ["Parameter", "Value"]
        self.detail_tree = ModernTreeview(detail_frame, columns=columns)
        self.detail_tree.grid(row=0, column=0, sticky="nsew")
        self.detail_tree.column("Parameter", width=200, anchor="w")
        self.detail_tree.column("Value", width=400, anchor="w")

        vsb = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.detail_tree.configure(yscrollcommand=vsb.set)

        # Action buttons
        btn_frame = ModernFrame(self.current_tab)
        btn_frame.grid(row=2, column=0, pady=10)
        ModernButton(btn_frame, text="Refresh", command=self.refresh_current, style="primary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Export", command=self.export_current, style="secondary").pack(side="left", padx=5)

    def create_forecast_tab(self):
        self.forecast_tab = ModernFrame(self.notebook)
        self.notebook.add(self.forecast_tab, text="  5-Day Forecast  ")
        self.forecast_tab.grid_rowconfigure(0, weight=1)
        self.forecast_tab.grid_columnconfigure(0, weight=1)

        # Canvas with scrollbar for forecast items
        canvas_frame = ModernFrame(self.forecast_tab)
        canvas_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.forecast_canvas = tk.Canvas(canvas_frame, bg=COLORS["bg"], highlightthickness=0)
        self.forecast_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.forecast_canvas.yview)
        self.forecast_inner = ModernFrame(self.forecast_canvas)

        self.forecast_inner.bind(
            "<Configure>",
            lambda e: self.forecast_canvas.configure(scrollregion=self.forecast_canvas.bbox("all"))
        )

        self.forecast_canvas.create_window((0, 0), window=self.forecast_inner, anchor="nw")
        self.forecast_canvas.configure(yscrollcommand=self.forecast_scrollbar.set)

        self.forecast_canvas.grid(row=0, column=0, sticky="nsew")
        self.forecast_scrollbar.grid(row=0, column=1, sticky="ns")

        # Bind mousewheel
        self.forecast_canvas.bind("<MouseWheel>", self._on_forecast_scroll)

        # Action buttons
        btn_frame = ModernFrame(self.forecast_tab)
        btn_frame.grid(row=1, column=0, pady=10)
        ModernButton(btn_frame, text="Refresh Forecast", command=self.refresh_forecast, style="primary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Export Forecast", command=self.export_forecast, style="secondary").pack(side="left", padx=5)

    def _on_forecast_scroll(self, event):
        self.forecast_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def create_search_tab(self):
        self.search_tab = ModernFrame(self.notebook)
        self.notebook.add(self.search_tab, text="  City Search  ")
        self.search_tab.grid_rowconfigure(1, weight=1)
        self.search_tab.grid_columnconfigure(0, weight=1)

        # Search results table
        table_frame = ModernFrame(self.search_tab)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ["Name", "Country", "State", "Latitude", "Longitude"]
        self.search_tree = ModernTreeview(table_frame, columns=columns)
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        self.search_tree.column("Name", width=200, anchor="w")
        self.search_tree.column("Country", width=80, anchor="center")
        self.search_tree.column("State", width=120, anchor="w")
        self.search_tree.column("Latitude", width=100, anchor="center")
        self.search_tree.column("Longitude", width=100, anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.search_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.search_tree.configure(yscrollcommand=vsb.set)

        self.search_tree.bind("<Double-1>", self.on_search_select)

        # Action buttons
        btn_frame = ModernFrame(self.search_tab)
        btn_frame.grid(row=1, column=0, pady=10)
        ModernButton(btn_frame, text="Get Weather", command=self.on_search_select, style="primary").pack(side="left", padx=5)
        ModernButton(btn_frame, text="Export Results", command=self.export_search, style="secondary").pack(side="left", padx=5)

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
        self.root.bind("<Control-s>", lambda e: self.search_city())
        self.root.bind("<Control-r>", lambda e: self.refresh_current())
        self.root.bind("<Control-e>", lambda e: self.export_current())
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

    def search_city(self):
        query = self.city_entry.get_value().strip()
        if not query:
            messagebox.showwarning("Empty Search", "Please enter a city name")
            return

        self.progress_var.set(0)

        def run_search():
            results = self.tracker.search_cities(query)
            self.root.after(0, lambda: self.display_search_results(results))

        threading.Thread(target=run_search, daemon=True).start()

    def use_current_location(self):
        # For demo, use a default location
        messagebox.showinfo("Location", "Current location detection requires browser/OS permissions.\nUsing London as default.")
        self.city_entry.delete(0, tk.END)
        self.city_entry.insert(0, "London,UK")
        self.city_entry.config(fg=COLORS["input_fg"])
        self.search_city()

    def display_search_results(self, results: List):
        self.search_tree.delete(*self.search_tree.get_children())

        for idx, result in enumerate(results):
            values = [
                result.name,
                result.country,
                result.state or "",
                f"{result.lat:.4f}",
                f"{result.lon:.4f}"
            ]
            tag = "odd" if idx % 2 else "even"
            self.search_tree.insert("", "end", values=values, tags=(tag,))

        self.status_label.config(text=f"Found {len(results)} cities")
        self.progress_var.set(100)

        # Switch to search tab
        self.notebook.select(self.search_tab)

    def on_search_select(self, event=None):
        selection = self.search_tree.selection()
        if not selection:
            return

        item = self.search_tree.item(selection[0])
        lat = float(item["values"][3])
        lon = float(item["values"][4])

        self.fetch_weather_by_coords(lat, lon)
        self.notebook.select(self.current_tab)

    def fetch_weather_by_coords(self, lat: float, lon: float):
        self.progress_var.set(0)

        def run_fetch():
            self.tracker.fetch_current_weather(lat=lat, lon=lon)
            self.tracker.fetch_forecast(lat=lat, lon=lon)
            self.root.after(0, self.refresh_all_displays)

        threading.Thread(target=run_fetch, daemon=True).start()

    def refresh_current(self):
        weather = self.tracker.get_current_weather()
        if weather:
            self.fetch_weather_by_coords(weather.coord.lat, weather.coord.lon)
        else:
            self.search_city()

    def refresh_forecast(self):
        weather = self.tracker.get_current_weather()
        if weather:
            def run_forecast():
                self.tracker.fetch_forecast(lat=weather.coord.lat, lon=weather.coord.lon)
                self.root.after(0, self.display_forecast)
            threading.Thread(target=run_forecast, daemon=True).start()
        else:
            self.search_city()

    def refresh_current_display(self):
        weather = self.tracker.get_current_weather()
        if weather:
            self.display_current_weather(weather)

    def refresh_all_displays(self):
        self.display_current_weather(self.tracker.get_current_weather())
        self.display_forecast()

    def display_current_weather(self, weather):
        if not weather:
            return

        self.weather_card.update_weather(weather, self.tracker.units)

        # Update details table
        self.detail_tree.delete(*self.detail_tree.get_children())

        details = [
            ("City", f"{weather.name}, {weather.sys.country}"),
            ("Coordinates", f"{weather.coord.lat:.4f}, {weather.coord.lon:.4f}"),
            ("Temperature", f"{weather.main.temp:.1f}°{'C' if self.tracker.units == 'metric' else 'F'}"),
            ("Feels Like", f"{weather.main.feels_like:.1f}°{'C' if self.tracker.units == 'metric' else 'F'}"),
            ("Min / Max", f"{weather.main.temp_min:.1f}° / {weather.main.temp_max:.1f}°"),
            ("Condition", weather.condition_description),
            ("Humidity", f"{weather.main.humidity}%"),
            ("Pressure", f"{weather.main.pressure} hPa"),
            ("Visibility", f"{weather.visibility / 1000:.1f} km"),
            ("Wind", f"{weather.wind.speed} m/s, {wind_deg_to_direction(weather.wind.deg)}"),
            ("Cloud Coverage", f"{weather.clouds.all}%"),
            ("Sunrise", datetime.fromtimestamp(weather.sys.sunrise).strftime("%H:%M")),
            ("Sunset", datetime.fromtimestamp(weather.sys.sunset).strftime("%H:%M")),
            ("Timezone", f"UTC{weather.timezone/3600:+.0f}"),
            ("Last Updated", datetime.fromtimestamp(weather.dt).strftime("%Y-%m-%d %H:%M:%S")),
        ]

        for i, (param, value) in enumerate(details):
            tag = "odd" if i % 2 else "even"
            self.detail_tree.insert("", "end", values=[param, value], tags=(tag,))

    def display_forecast(self):
        forecast = self.tracker.get_forecast()
        if not forecast:
            return

        # Clear existing
        for widget in self.forecast_inner.winfo_children():
            widget.destroy()

        # Group by date
        from collections import defaultdict
        daily_items = defaultdict(list)
        for item in forecast.list:
            dt = datetime.fromtimestamp(item.dt)
            date_key = dt.date()
            daily_items[date_key].append(item)

        # Create widgets for each day
        for date, items in list(daily_items.items())[:5]:
            day_frame = ModernFrame(self.forecast_inner)
            day_frame.pack(fill="x", padx=10, pady=10)

            # Day header
            header = ModernFrame(day_frame)
            header.pack(fill="x", pady=5)
            ModernLabel(header, text=date.strftime("%A, %B %d"), style="subtitle").pack(side="left")

            # Items container
            items_frame = ModernFrame(day_frame)
            items_frame.pack(fill="x")

            for item in items[:8]:  # Show 8 items per day (3-hour intervals)
                widget = ForecastItemWidget(items_frame, item, self.tracker.units)
                widget.pack(side="left", padx=5, pady=5, fill="y")

    def export_current(self):
        weather = self.tracker.get_current_weather()
        if not weather:
            messagebox.showwarning("No Data", "No current weather data to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_current_weather(weather, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_current_weather_json(weather, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Current weather exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_forecast(self):
        forecast = self.tracker.get_forecast()
        if not forecast:
            messagebox.showwarning("No Data", "No forecast data to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_forecast(forecast, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                self.exporter.export_forecast_json(forecast, filepath if fmt == "json" else None)
            messagebox.showinfo("Export Complete", "Forecast exported successfully!")

        ExportDialog(self.root, export_callback)

    def export_search(self):
        results = self.tracker.get_search_results()
        if not results:
            messagebox.showwarning("No Data", "No search results to export")
            return

        def export_callback(filepath: str, fmt: str):
            if fmt in ("csv", "both"):
                self.exporter.export_search_results(results, filepath if fmt == "csv" else None)
            if fmt in ("json", "both"):
                # JSON export for search results
                pass
            messagebox.showinfo("Export Complete", "Search results exported successfully!")

        ExportDialog(self.root, export_callback)

    def on_closing(self):
        if self.tracker.is_fetching:
            if messagebox.askyesno("Quit", "Fetching in progress. Quit anyway?"):
                self.tracker.stop()
                self.tracker.close()
                self.root.destroy()
        else:
            self.tracker.close()
            self.root.destroy()


from datetime import datetime
from .utils import wind_deg_to_direction


def main():
    root = tk.Tk()
    app = WeatherApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()