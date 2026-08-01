"""Canvas-based array visualization with smooth 60 FPS color animation."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Sequence

from .config import (
    BAR_GAP_RATIO,
    BAR_MAX_WIDTH,
    BAR_MIN_WIDTH,
    CANVAS_PADDING_BOTTOM,
    CANVAS_PADDING_TOP,
    CANVAS_PADDING_X,
    FONT_MONO_SMALL,
    FRAME_INTERVAL_MS,
    GRID_LINE_COUNT,
    PALETTE,
)
from .utils import ensure_color_count, interpolate_color


class ArrayVisualizer(tk.Canvas):
    """Render integer arrays as responsive vertical bars."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(
            parent,
            background=PALETTE.background,
            highlightthickness=0,
            bd=0,
        )
        self._array: list[int] = []
        self._colors: list[str] = []
        self._animation_id: str | None = None
        self._animation_token = 0
        self._last_frame_time = time.perf_counter()
        self._fps_samples: list[float] = []
        self._fps = 0.0
        self.bind("<Configure>", self._on_resize)

    @property
    def fps(self) -> float:
        """Return the recent average rendering frame rate."""

        return self._fps

    def set_data(
        self,
        array: Sequence[int],
        colors: Sequence[str] | None = None,
    ) -> None:
        """Replace the displayed array and redraw immediately."""

        self.cancel_animation()
        self._array = list(array)
        requested = colors or [PALETTE.default_bar] * len(self._array)
        self._colors = ensure_color_count(
            requested,
            len(self._array),
            PALETTE.default_bar,
        )
        self._draw()

    def animate_to(
        self,
        array: Sequence[int],
        colors: Sequence[str],
        duration_ms: int,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Animate color changes at approximately 60 frames per second."""

        self.cancel_animation()
        self._animation_token += 1
        token = self._animation_token

        new_array = list(array)
        target_colors = ensure_color_count(
            colors,
            len(new_array),
            PALETTE.default_bar,
        )

        if self._array != new_array:
            self._array = new_array
            self._colors = [PALETTE.default_bar] * len(new_array)

        start_colors = ensure_color_count(
            self._colors,
            len(new_array),
            PALETTE.default_bar,
        )
        started = time.perf_counter()
        duration_seconds = max(duration_ms, 1) / 1000.0

        def render_frame() -> None:
            if token != self._animation_token:
                return

            elapsed = time.perf_counter() - started
            progress = min(1.0, elapsed / duration_seconds)
            eased = 1.0 - (1.0 - progress) ** 3
            self._colors = [
                interpolate_color(start, end, eased)
                for start, end in zip(start_colors, target_colors, strict=True)
            ]
            self._draw()
            self._record_frame()

            if progress >= 1.0:
                self._colors = target_colors.copy()
                self._draw()
                self._animation_id = None
                if on_complete is not None:
                    on_complete()
                return

            self._animation_id = self.after(FRAME_INTERVAL_MS, render_frame)

        render_frame()

    def cancel_animation(self) -> None:
        """Cancel an active color transition safely."""

        self._animation_token += 1
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def _on_resize(self, _event: tk.Event[tk.Misc]) -> None:
        self._draw()

    def _record_frame(self) -> None:
        now = time.perf_counter()
        delta = now - self._last_frame_time
        self._last_frame_time = now
        if delta <= 0:
            return
        self._fps_samples.append(1.0 / delta)
        self._fps_samples = self._fps_samples[-30:]
        self._fps = sum(self._fps_samples) / len(self._fps_samples)

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        self._draw_grid(width, height)

        if not self._array:
            self.create_text(
                width / 2,
                height / 2,
                text="Generate an array to begin",
                fill=PALETTE.muted_text,
                font=FONT_MONO_SMALL,
            )
            return

        drawable_width = max(1, width - 2 * CANVAS_PADDING_X)
        drawable_height = max(
            1,
            height - CANVAS_PADDING_TOP - CANVAS_PADDING_BOTTOM,
        )
        count = len(self._array)
        slot_width = drawable_width / count
        bar_width = max(
            BAR_MIN_WIDTH,
            min(BAR_MAX_WIDTH, slot_width * (1.0 - BAR_GAP_RATIO)),
        )
        maximum_value = max(max(abs(value) for value in self._array), 1)
        minimum_value = min(self._array)
        baseline = height - CANVAS_PADDING_BOTTOM

        for index, value in enumerate(self._array):
            normalized_value = abs(value) / maximum_value
            bar_height = max(4, drawable_height * normalized_value)
            center_x = CANVAS_PADDING_X + slot_width * (index + 0.5)
            x1 = center_x - bar_width / 2
            x2 = center_x + bar_width / 2
            y1 = baseline - bar_height
            color = self._colors[index]

            self.create_rectangle(
                x1,
                y1,
                x2,
                baseline,
                fill=color,
                outline="",
            )

            if count <= 45 or index % max(1, count // 24) == 0:
                self.create_text(
                    center_x,
                    baseline + 16,
                    text=str(value),
                    fill=PALETTE.text,
                    font=FONT_MONO_SMALL,
                )

        range_text = f"min {minimum_value}   •   max {max(self._array)}"
        self.create_text(
            CANVAS_PADDING_X,
            16,
            anchor="w",
            text=range_text,
            fill=PALETTE.muted_text,
            font=FONT_MONO_SMALL,
        )

    def _draw_grid(self, width: int, height: int) -> None:
        usable_height = height - CANVAS_PADDING_TOP - CANVAS_PADDING_BOTTOM
        if usable_height <= 0:
            return
        for index in range(GRID_LINE_COUNT + 1):
            y = CANVAS_PADDING_TOP + usable_height * index / GRID_LINE_COUNT
            self.create_line(
                CANVAS_PADDING_X,
                y,
                width - CANVAS_PADDING_X,
                y,
                fill=PALETTE.grid,
                width=1,
                dash=(2, 5),
            )
