from __future__ import annotations

import customtkinter as ctk

from src.colors import (
    CARD,
    BORDER,
    DANGER,
    INFO,
    PRIMARY,
    SECONDARY_TEXT,
    SUCCESS,
    TEXT,
    WARNING,
)
from src.utils import format_price


class StatCard(ctk.CTkFrame):

    def __init__(
        self,
        master,
        title,
        value,
        subtitle,
        accent,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
            **kwargs,
        )

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            self,
            text=title.upper(),
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=(17, 4),
        )

        ctk.CTkLabel(
            self,
            text=value,
            text_color=TEXT,
            font=(
                "Segoe UI",
                25,
                "bold",
            ),
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=18,
            pady=2,
        )

        ctk.CTkLabel(
            self,
            text=subtitle,
            text_color=accent,
            font=(
                "Segoe UI",
                10,
            ),
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=18,
            pady=(2, 17),
        )


class Dashboard(ctk.CTkFrame):

    def __init__(
        self,
        master,
        database,
        tracker,
        on_product_selected,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.database = database
        self.tracker = tracker
        self.on_product_selected = on_product_selected

        self.build()

    def build(self):

        self.header = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.header.pack(
            fill="x",
            pady=(0, 20),
        )

        ctk.CTkLabel(
            self.header,
            text="Price Tracking Dashboard",
            text_color=TEXT,
            font=(
                "Segoe UI",
                26,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            self.header,
            text=("Monitor your tracked products " "and price movements."),
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                12,
            ),
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        self.stats = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.stats.pack(
            fill="x",
            pady=(0, 20),
        )

        for index in range(4):

            self.stats.grid_columnconfigure(
                index,
                weight=1,
            )

        self.create_stats()

        self.content = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.content.pack(
            fill="both",
            expand=True,
        )

        self.create_products_panel()

    def create_stats(self):

        products = self.database.get_products()

        total = len(products)

        alerts = 0

        lowest = 0.0

        for product in products:

            current = product["current_price"]

            target = product["target_price"]

            if target > 0 and current > 0 and current <= target:

                alerts += 1

            product_lowest = product["lowest_price"]

            if product_lowest > 0:

                if lowest == 0:

                    lowest = product_lowest

                else:

                    lowest = min(
                        lowest,
                        product_lowest,
                    )

        cards = [
            (
                "Tracked Products",
                str(total),
                "Products being monitored",
                PRIMARY,
            ),
            (
                "Lowest Price",
                format_price(lowest),
                "Lowest recorded price",
                SUCCESS,
            ),
            (
                "Target Alerts",
                str(alerts),
                "Products at target price",
                WARNING,
            ),
            (
                "Active Tracker",
                "Online",
                "Database monitoring active",
                INFO,
            ),
        ]

        for index, data in enumerate(cards):

            card = StatCard(
                self.stats,
                *data,
            )

            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=5,
            )

    def create_products_panel(self):

        panel = ctk.CTkFrame(
            self.content,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        header = ctk.CTkFrame(
            panel,
            fg_color="transparent",
        )

        header.pack(
            fill="x",
            padx=20,
            pady=(18, 10),
        )

        ctk.CTkLabel(
            header,
            text="Tracked Products",
            text_color=TEXT,
            font=(
                "Segoe UI",
                16,
                "bold",
            ),
        ).pack(
            side="left",
        )

        ctk.CTkButton(
            header,
            text="Refresh",
            width=90,
            height=32,
            corner_radius=8,
            fg_color=PRIMARY,
            hover_color="#818CF8",
            command=self.refresh,
        ).pack(
            side="right",
        )

        self.table = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
        )

        self.table.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(0, 12),
        )

        self.refresh()

    def refresh(self):

        for child in self.table.winfo_children():

            child.destroy()

        products = self.database.get_products()

        if not products:

            ctk.CTkLabel(
                self.table,
                text="No products are being tracked yet.",
                text_color=SECONDARY_TEXT,
                font=(
                    "Segoe UI",
                    13,
                ),
            ).pack(
                pady=60,
            )

            return

        for product in products:

            self.create_product_row(product)

    def create_product_row(
        self,
        product,
    ):

        row = ctk.CTkFrame(
            self.table,
            fg_color="#202532",
            corner_radius=10,
            height=65,
        )

        row.pack(
            fill="x",
            pady=4,
        )

        row.grid_columnconfigure(
            0,
            weight=3,
        )

        row.grid_columnconfigure(
            1,
            weight=1,
        )

        row.grid_columnconfigure(
            2,
            weight=1,
        )

        row.grid_columnconfigure(
            3,
            weight=1,
        )

        row.grid_columnconfigure(
            4,
            weight=1,
        )

        name = product["name"]

        if len(name) > 38:

            name = name[:35] + "..."

        ctk.CTkLabel(
            row,
            text=name,
            text_color=TEXT,
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=15,
        )

        ctk.CTkLabel(
            row,
            text=format_price(product["current_price"]),
            text_color=TEXT,
            font=(
                "Segoe UI",
                11,
            ),
        ).grid(
            row=0,
            column=1,
        )

        ctk.CTkLabel(
            row,
            text=format_price(product["target_price"]),
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                11,
            ),
        ).grid(
            row=0,
            column=2,
        )

        change = self.tracker.get_price_change(product["id"])

        change_color = (
            SUCCESS if change < 0 else DANGER if change > 0 else SECONDARY_TEXT
        )

        ctk.CTkLabel(
            row,
            text=f"{change:+.1f}%",
            text_color=change_color,
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
        ).grid(
            row=0,
            column=3,
        )

        target = product["target_price"]

        current = product["current_price"]

        if target > 0 and current > 0 and current <= target:

            status = "TARGET"

            status_color = SUCCESS

        else:

            status = "TRACKING"

            status_color = INFO

        ctk.CTkLabel(
            row,
            text=status,
            text_color=status_color,
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
        ).grid(
            row=0,
            column=4,
        )

        row.bind(
            "<Button-1>",
            lambda event, item=product: self.on_product_selected(item),
        )
