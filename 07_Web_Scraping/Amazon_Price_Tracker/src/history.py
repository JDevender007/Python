from __future__ import annotations

import customtkinter as ctk

from src.colors import (
    BORDER,
    CARD,
    SECONDARY_TEXT,
    SUCCESS,
    TEXT,
)
from src.utils import format_price


class HistoryView(ctk.CTkFrame):

    def __init__(
        self,
        master,
        database,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.database = database

        self.selected_product = None

        self.build()

    def build(self):

        ctk.CTkLabel(
            self,
            text="Price History",
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
            self,
            text=("Review historical prices " "for tracked products."),
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                12,
            ),
        ).pack(
            anchor="w",
            pady=(4, 20),
        )

        self.product_list = ctk.CTkScrollableFrame(
            self,
            height=160,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )

        self.product_list.pack(
            fill="x",
            pady=(0, 15),
        )

        self.history_panel = ctk.CTkFrame(
            self,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )

        self.history_panel.pack(
            fill="both",
            expand=True,
        )

        self.refresh()

    def refresh(self):

        for child in self.product_list.winfo_children():

            child.destroy()

        products = self.database.get_products()

        if not products:

            ctk.CTkLabel(
                self.product_list,
                text="No tracked products.",
                text_color=SECONDARY_TEXT,
            ).pack(
                pady=20,
            )

            return

        for product in products:

            button = ctk.CTkButton(
                self.product_list,
                text=product["name"],
                anchor="w",
                height=38,
                fg_color="transparent",
                hover_color="#222735",
                text_color=TEXT,
                command=lambda item=product: (self.show_history(item)),
            )

            button.pack(
                fill="x",
                padx=8,
                pady=3,
            )

    def show_history(
        self,
        product,
    ):

        self.selected_product = product

        for child in self.history_panel.winfo_children():

            child.destroy()

        ctk.CTkLabel(
            self.history_panel,
            text=product["name"],
            text_color=TEXT,
            font=(
                "Segoe UI",
                16,
                "bold",
            ),
            wraplength=850,
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 5),
        )

        history = self.database.get_price_history(product["id"])

        if not history:

            ctk.CTkLabel(
                self.history_panel,
                text="No price history available.",
                text_color=SECONDARY_TEXT,
            ).pack(
                pady=40,
            )

            return

        for index, item in enumerate(
            reversed(history),
            start=1,
        ):

            row = ctk.CTkFrame(
                self.history_panel,
                fg_color="#202532",
                corner_radius=8,
            )

            row.pack(
                fill="x",
                padx=20,
                pady=3,
            )

            ctk.CTkLabel(
                row,
                text=item["checked_at"],
                text_color=SECONDARY_TEXT,
            ).pack(
                side="left",
                padx=15,
                pady=10,
            )

            ctk.CTkLabel(
                row,
                text=format_price(item["price"]),
                text_color=SUCCESS,
                font=(
                    "Segoe UI",
                    11,
                    "bold",
                ),
            ).pack(
                side="right",
                padx=15,
            )
