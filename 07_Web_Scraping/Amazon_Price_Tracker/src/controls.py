from __future__ import annotations

import customtkinter as ctk

from src.colors import (
    CARD,
    CARD_HOVER,
    PRIMARY,
    PRIMARY_HOVER,
    SECONDARY_TEXT,
    TEXT,
)


class ControlButton(ctk.CTkButton):

    def __init__(
        self,
        master,
        text,
        command,
        **kwargs,
    ):

        super().__init__(
            master,
            text=text,
            command=command,
            height=42,
            corner_radius=10,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            text_color=TEXT,
            font=(
                "Segoe UI",
                12,
                "bold",
            ),
            **kwargs,
        )


class SidebarButton(ctk.CTkButton):

    def __init__(
        self,
        master,
        text,
        command,
        **kwargs,
    ):

        super().__init__(
            master,
            text=text,
            command=command,
            height=44,
            corner_radius=10,
            fg_color="transparent",
            hover_color=CARD_HOVER,
            text_color=SECONDARY_TEXT,
            anchor="w",
            font=(
                "Segoe UI",
                12,
            ),
            **kwargs,
        )


class Sidebar(ctk.CTkFrame):

    def __init__(
        self,
        master,
        callbacks,
        **kwargs,
    ):

        super().__init__(
            master,
            width=240,
            corner_radius=0,
            fg_color=CARD,
            **kwargs,
        )

        self.callbacks = callbacks

        self.grid_propagate(False)

        self.build()

    def build(self):

        self.logo_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.logo_frame.pack(
            fill="x",
            padx=20,
            pady=(25, 30),
        )

        ctk.CTkLabel(
            self.logo_frame,
            text="◈",
            text_color=PRIMARY,
            font=(
                "Segoe UI",
                28,
                "bold",
            ),
        ).pack(
            side="left",
        )

        logo_text = ctk.CTkFrame(
            self.logo_frame,
            fg_color="transparent",
        )

        logo_text.pack(
            side="left",
            padx=10,
        )

        ctk.CTkLabel(
            logo_text,
            text="Price",
            text_color=TEXT,
            font=(
                "Segoe UI",
                17,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            logo_text,
            text="TRACKER",
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                8,
                "bold",
            ),
        ).pack(
            anchor="w",
        )

        self.create_section("WORKSPACE")

        self.create_button(
            "⌂   Dashboard",
            self.callbacks["dashboard"],
        )

        self.create_button(
            "▣   Products",
            self.callbacks["products"],
        )

        self.create_button(
            "＋   Add Product",
            self.callbacks["add_product"],
        )

        self.create_button(
            "⌁   Price History",
            self.callbacks["history"],
        )

        self.create_section("SYSTEM")

        self.create_button(
            "⚙   Settings",
            self.callbacks["settings"],
        )

        self.create_button(
            "↻   Refresh",
            self.callbacks["refresh"],
        )

        self.status_frame = ctk.CTkFrame(
            self,
            fg_color=CARD_HOVER,
            corner_radius=12,
        )

        self.status_frame.pack(
            side="bottom",
            fill="x",
            padx=15,
            pady=20,
        )

        ctk.CTkLabel(
            self.status_frame,
            text="●  Tracker Online",
            text_color="#22C55E",
            font=(
                "Segoe UI",
                11,
                "bold",
            ),
        ).pack(
            anchor="w",
            padx=15,
            pady=(12, 2),
        )

        ctk.CTkLabel(
            self.status_frame,
            text="Local database active",
            text_color=SECONDARY_TEXT,
            font=(
                "Segoe UI",
                9,
            ),
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 12),
        )

    def create_section(
        self,
        text,
    ):

        ctk.CTkLabel(
            self,
            text=text,
            text_color="#64748B",
            font=(
                "Segoe UI",
                9,
                "bold",
            ),
        ).pack(
            anchor="w",
            padx=20,
            pady=(5, 8),
        )

    def create_button(
        self,
        text,
        command,
    ):

        button = SidebarButton(
            self,
            text=text,
            command=command,
        )

        button.pack(
            fill="x",
            padx=12,
            pady=3,
        )
