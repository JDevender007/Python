from __future__ import annotations

import customtkinter as ctk

from tkinter import messagebox

from src.colors import (
    BACKGROUND,
    CARD,
    DANGER,
    PRIMARY,
    SECONDARY_TEXT,
    TEXT,
)

from src.config import (
    APP_NAME,
    APP_VERSION,
    FONT_FAMILY,
    MIN_HEIGHT,
    MIN_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)

from src.controls import Sidebar

from src.database import Database

from src.dashboard import Dashboard

from src.history import HistoryView

from src.parser import AmazonParser

from src.products import ProductForm

from src.scraper import AmazonScraper

from src.tracker import PriceTracker

from src.logger import logger


class AmazonPriceTrackerApp:

    def __init__(self):

        ctk.set_appearance_mode("dark")

        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()

        self.root.title(f"{APP_NAME} v{APP_VERSION}")

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.root.minsize(
            MIN_WIDTH,
            MIN_HEIGHT,
        )

        self.root.configure(fg_color=BACKGROUND)

        self.fullscreen = False

        self.database = Database()

        self.scraper = AmazonScraper()

        self.parser = AmazonParser()

        self.tracker = PriceTracker(self.database)

        self.current_page = None

        self.pages = {}

        self.create_layout()

        self.create_pages()

        self.show_dashboard()

        self.bind_shortcuts()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        logger.info("Application started")

    def create_layout(self):

        self.root.grid_columnconfigure(
            0,
            weight=0,
        )

        self.root.grid_columnconfigure(
            1,
            weight=1,
        )

        self.root.grid_rowconfigure(
            0,
            weight=1,
        )

        callbacks = {
            "dashboard": self.show_dashboard,
            "products": self.show_products,
            "add_product": self.show_add_product,
            "history": self.show_history,
            "settings": self.show_settings,
            "refresh": self.refresh_current_page,
        }

        self.sidebar = Sidebar(
            self.root,
            callbacks,
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="ns",
        )

        self.content = ctk.CTkFrame(
            self.root,
            fg_color=BACKGROUND,
            corner_radius=0,
        )

        self.content.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=25,
            pady=25,
        )

        self.content.grid_rowconfigure(
            0,
            weight=1,
        )

        self.content.grid_columnconfigure(
            0,
            weight=1,
        )

    def create_pages(self):

        self.pages["dashboard"] = Dashboard(
            self.content,
            self.database,
            self.tracker,
            self.show_product_details,
        )

        self.pages["products"] = ProductListPage(
            self.content,
            self.database,
            self.tracker,
            self.show_add_product,
            self.delete_product,
        )

        self.pages["add_product"] = ProductForm(
            self.content,
            self.scraper,
            self.parser,
            self.tracker,
            self.product_added,
        )

        self.pages["history"] = HistoryView(
            self.content,
            self.database,
        )

        self.pages["settings"] = SettingsPage(
            self.content,
            self,
        )

    def hide_pages(self):

        for page in self.pages.values():

            page.grid_remove()

    def show_page(
        self,
        name,
    ):

        self.hide_pages()

        page = self.pages[name]

        page.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.current_page = name

    def show_dashboard(self):

        self.pages["dashboard"].refresh()

        self.show_page("dashboard")

    def show_products(self):

        self.pages["products"].refresh()

        self.show_page("products")

    def show_add_product(self):

        self.show_page("add_product")

    def show_history(self):

        self.pages["history"].refresh()

        self.show_page("history")

    def show_settings(self):

        self.show_page("settings")

    def show_product_details(
        self,
        product,
    ):

        self.show_history()

        self.pages["history"].show_history(product)

    def product_added(self):

        self.pages["dashboard"].refresh()

        self.pages["products"].refresh()

    def delete_product(
        self,
        product_id,
    ):

        confirmation = messagebox.askyesno(
            "Delete Product",
            ("Are you sure you want to " "remove this product from tracking?"),
        )

        if not confirmation:

            return

        self.database.delete_product(product_id)

        self.pages["dashboard"].refresh()

        self.pages["products"].refresh()

    def refresh_current_page(self):

        if self.current_page == "dashboard":

            self.pages["dashboard"].refresh()

        elif self.current_page == "products":

            self.pages["products"].refresh()

        elif self.current_page == "history":

            self.pages["history"].refresh()

        self.set_status("Data refreshed")

    def set_status(
        self,
        message,
    ):

        logger.info(message)

    def toggle_fullscreen(self):

        self.fullscreen = not self.fullscreen

        self.root.attributes(
            "-fullscreen",
            self.fullscreen,
        )

    def exit_fullscreen(self):

        self.fullscreen = False

        self.root.attributes(
            "-fullscreen",
            False,
        )

    def bind_shortcuts(self):

        self.root.bind(
            "<F11>",
            lambda event: self.toggle_fullscreen(),
        )

        self.root.bind(
            "<Escape>",
            lambda event: self.exit_fullscreen(),
        )

        self.root.bind(
            "<Control-r>",
            lambda event: self.refresh_current_page(),
        )

        self.root.bind(
            "<Control-n>",
            lambda event: self.show_add_product(),
        )

        self.root.bind(
            "<Control-p>",
            lambda event: self.show_products(),
        )

    def on_close(self):

        try:

            self.scraper.close()

            self.database.close()

        except Exception as error:

            logger.error(
                "Error while closing application: %s",
                error,
            )

        self.root.destroy()

    def run(self):

        self.root.mainloop()


class ProductListPage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        database,
        tracker,
        add_product_callback,
        delete_callback,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.database = database

        self.tracker = tracker

        self.add_product_callback = add_product_callback

        self.delete_callback = delete_callback

        self.build()

    def build(self):

        header = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        header.pack(
            fill="x",
            pady=(0, 20),
        )

        title_frame = ctk.CTkFrame(
            header,
            fg_color="transparent",
        )

        title_frame.pack(
            side="left",
        )

        ctk.CTkLabel(
            title_frame,
            text="Tracked Products",
            text_color=TEXT,
            font=(
                FONT_FAMILY,
                26,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            title_frame,
            text=("Manage products currently " "being monitored."),
            text_color=SECONDARY_TEXT,
            font=(
                FONT_FAMILY,
                12,
            ),
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        ctk.CTkButton(
            header,
            text="+  Add Product",
            width=130,
            height=40,
            corner_radius=9,
            fg_color=PRIMARY,
            hover_color="#818CF8",
            command=self.add_product_callback,
        ).pack(
            side="right",
        )

        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=CARD,
            corner_radius=14,
        )

        self.list_frame.pack(
            fill="both",
            expand=True,
        )

        self.refresh()

    def refresh(self):

        for child in self.list_frame.winfo_children():

            child.destroy()

        products = self.database.get_products()

        if not products:

            ctk.CTkLabel(
                self.list_frame,
                text="No products are being tracked.",
                text_color=SECONDARY_TEXT,
                font=(
                    FONT_FAMILY,
                    13,
                ),
            ).pack(
                pady=80,
            )

            return

        for product in products:

            self.create_product_card(product)

    def create_product_card(
        self,
        product,
    ):

        card = ctk.CTkFrame(
            self.list_frame,
            fg_color="#202532",
            corner_radius=12,
        )

        card.pack(
            fill="x",
            padx=8,
            pady=6,
        )

        card.grid_columnconfigure(
            0,
            weight=1,
        )

        title = product["name"]

        if len(title) > 55:

            title = title[:52] + "..."

        ctk.CTkLabel(
            card,
            text=title,
            text_color=TEXT,
            font=(
                FONT_FAMILY,
                13,
                "bold",
            ),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(15, 3),
        )

        ctk.CTkLabel(
            card,
            text=product["url"],
            text_color=SECONDARY_TEXT,
            font=(
                FONT_FAMILY,
                10,
            ),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=18,
            pady=(0, 12),
        )

        info = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        info.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=18,
            pady=(0, 15),
        )

        self.create_info(
            info,
            "CURRENT",
            product["current_price"],
        )

        self.create_info(
            info,
            "TARGET",
            product["target_price"],
        )

        self.create_info(
            info,
            "LOWEST",
            product["lowest_price"],
        )

        delete_button = ctk.CTkButton(
            info,
            text="Delete",
            width=75,
            height=30,
            corner_radius=7,
            fg_color=DANGER,
            hover_color="#F87171",
            command=lambda pid=product["id"]: (self.delete_callback(pid)),
        )

        delete_button.pack(
            side="right",
            padx=(10, 0),
        )

    def create_info(
        self,
        parent,
        label,
        value,
    ):

        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        frame.pack(
            side="left",
            padx=(0, 35),
        )

        ctk.CTkLabel(
            frame,
            text=label,
            text_color=SECONDARY_TEXT,
            font=(
                FONT_FAMILY,
                9,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            frame,
            text=f"₹{value:,.2f}",
            text_color=TEXT,
            font=(
                FONT_FAMILY,
                11,
                "bold",
            ),
        ).pack(
            anchor="w",
            pady=(2, 0),
        )


class SettingsPage(ctk.CTkFrame):

    def __init__(
        self,
        master,
        app,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.app = app

        self.build()

    def build(self):

        ctk.CTkLabel(
            self,
            text="Settings",
            text_color=TEXT,
            font=(
                FONT_FAMILY,
                26,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            self,
            text=("Application information " "and preferences."),
            text_color=SECONDARY_TEXT,
            font=(
                FONT_FAMILY,
                12,
            ),
        ).pack(
            anchor="w",
            pady=(4, 20),
        )

        card = ctk.CTkFrame(
            self,
            fg_color=CARD,
            corner_radius=14,
        )

        card.pack(
            fill="x",
        )

        self.info(
            card,
            "Application",
            APP_NAME,
        )

        self.info(
            card,
            "Version",
            APP_VERSION,
        )

        self.info(
            card,
            "Interface",
            "Dark Mode",
        )

        self.info(
            card,
            "Storage",
            "SQLite Database",
        )

        self.info(
            card,
            "Framework",
            "CustomTkinter",
        )

    def info(
        self,
        parent,
        title,
        value,
    ):

        row = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        row.pack(
            fill="x",
            padx=25,
            pady=12,
        )

        ctk.CTkLabel(
            row,
            text=title,
            text_color=SECONDARY_TEXT,
            font=(
                FONT_FAMILY,
                11,
            ),
        ).pack(
            side="left",
        )

        ctk.CTkLabel(
            row,
            text=value,
            text_color=TEXT,
            font=(
                FONT_FAMILY,
                11,
                "bold",
            ),
        ).pack(
            side="right",
        )


def main():

    app = AmazonPriceTrackerApp()

    app.run()


if __name__ == "__main__":

    main()
