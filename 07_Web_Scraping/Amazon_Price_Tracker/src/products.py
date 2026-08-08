from __future__ import annotations

import customtkinter as ctk

from src.colors import (
    BORDER,
    CARD,
    DANGER,
    INPUT,
    PRIMARY,
    PRIMARY_HOVER,
    SECONDARY_TEXT,
    SUCCESS,
    TEXT,
)
from src.utils import (
    format_price,
    is_valid_url,
)


class ProductForm(ctk.CTkFrame):

    def __init__(
        self,
        master,
        scraper,
        parser,
        tracker,
        on_complete,
        **kwargs,
    ):

        super().__init__(
            master,
            fg_color="transparent",
            **kwargs,
        )

        self.scraper = scraper
        self.parser = parser
        self.tracker = tracker
        self.on_complete = on_complete

        self.url_var = ctk.StringVar()

        self.target_var = ctk.StringVar()

        self.status_var = ctk.StringVar(value="Ready to add a product.")

        self.build()

    def build(self):

        ctk.CTkLabel(
            self,
            text="Add Product",
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
            text=("Enter a product URL and target price " "to start tracking."),
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                12,
            ),
        ).pack(
            anchor="w",
            pady=(4, 20),
        )

        card = ctk.CTkFrame(
            self,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )

        card.pack(
            fill="x",
            padx=2,
        )

        inner = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        inner.pack(
            fill="x",
            padx=25,
            pady=25,
        )

        self.create_field(
            inner,
            "Product URL",
            self.url_var,
            0,
        )

        self.create_field(
            inner,
            "Target Price",
            self.target_var,
            2,
        )

        ctk.CTkButton(
            inner,
            text="Fetch Product",
            height=44,
            corner_radius=10,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            font=(
                "Segoe UI",
                12,
                "bold",
            ),
            command=self.fetch_product,
        ).grid(
            row=4,
            column=0,
            sticky="w",
            pady=(20, 10),
        )

        self.preview = ctk.CTkFrame(
            self,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )

        self.preview.pack(
            fill="x",
            pady=20,
        )

        self.preview_label = ctk.CTkLabel(
            self.preview,
            text="Product preview will appear here.",
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                12,
            ),
            justify="left",
            anchor="w",
        )

        self.preview_label.pack(
            fill="x",
            padx=25,
            pady=25,
        )

        self.status_label = ctk.CTkLabel(
            self,
            textvariable=self.status_var,
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                11,
            ),
        )

        self.status_label.pack(
            anchor="w",
        )

    def create_field(
        self,
        parent,
        label,
        variable,
        row,
    ):

        ctk.CTkLabel(
            parent,
            text=label,
            text_color=TEXT,
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
        ).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(5, 7),
        )

        ctk.CTkEntry(
            parent,
            textvariable=variable,
            height=42,
            corner_radius=9,
            fg_color=INPUT,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text=(
                "https://www.amazon.in/..." if row == 0 else "Example: 49999"
            ),
        ).grid(
            row=row + 1,
            column=0,
            sticky="ew",
        )

        parent.grid_columnconfigure(
            0,
            weight=1,
        )

    def fetch_product(self):

        url = self.url_var.get().strip()

        target_text = self.target_var.get().strip()

        if not is_valid_url(url):

            self.set_status(
                "Enter a valid product URL.",
                DANGER,
            )

            return

        try:

            target_price = float(target_text)

        except ValueError:

            self.set_status(
                "Enter a valid target price.",
                DANGER,
            )

            return

        if target_price < 0:

            self.set_status(
                "Target price cannot be negative.",
                DANGER,
            )

            return

        self.set_status(
            "Fetching product information...",
            SECONDARY_TEXT,
        )

        self.update_idletasks()

        try:

            html = self.scraper.fetch(url)

            product = self.parser.parse(html)

            if not product["name"]:

                raise ValueError("Product name was not found.")

            if product["price"] <= 0:

                self.set_status(
                    ("Product was found, " "but the price could not be extracted."),
                    DANGER,
                )

                return

            product_id = self.tracker.add_product(
                product["name"],
                url,
                product["price"],
                target_price,
                product["availability"],
            )

            self.preview_label.configure(
                text=(
                    f"Product: {product['name']}\n\n"
                    f"Current Price: "
                    f"{format_price(product['price'])}\n"
                    f"Target Price: "
                    f"{format_price(target_price)}\n"
                    f"Availability: "
                    f"{product['availability']}\n\n"
                    f"Tracking ID: {product_id}"
                ),
                text_color=TEXT,
            )

            self.set_status(
                "Product added successfully.",
                SUCCESS,
            )

            self.on_complete()

        except Exception as error:

            self.set_status(
                str(error),
                DANGER,
            )

    def set_status(
        self,
        message,
        color,
    ):

        self.status_var.set(message)

        self.status_label.configure(text_color=color)
