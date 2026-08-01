"""Canvas-based visualizer for stack and queue operations."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .animations import AnimationManager
from .colors import ColorPalette
from .config import AppConfig
from .logger import get_logger
from .utils import lerp, shorten_text


@dataclass(frozen=True, slots=True)
class ElementPose:
    """Geometry and display state for one visualized element."""

    value: object
    x: float
    y: float
    width: float
    height: float
    emphasis: bool = False
    ghost: bool = False


class DataStructureVisualizer(tk.Canvas):
    """Render and animate stack or queue elements on a Tkinter canvas."""

    def __init__(
        self,
        master: tk.Misc,
        config: AppConfig,
        colors: ColorPalette,
        fps_callback: Callable[[float], None] | None = None,
    ) -> None:
        super().__init__(
            master,
            background=colors.canvas,
            borderwidth=0,
            highlightthickness=0,
        )
        self._config = config
        self._colors = colors
        self._fps_callback = fps_callback
        self._animation = AnimationManager(self, fps=config.fps)
        self._logger = get_logger("visualizer")

        self._structure = "Stack"
        self._values: list[object] = []
        self._highlights: set[int] = set()
        self._status_text = "Ready"
        self._status_kind = "info"
        self._status_after_id: str | None = None
        self._resize_after_id: str | None = None

        self._pulse_count = 0
        self._pulse_started_at = time.perf_counter()
        self._pulse_after_id: str | None = None

        self.bind("<Configure>", self._on_resize)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after_idle(self._draw_scene)
        self._schedule_fps_pulse()

    def display(
        self,
        values: Sequence[object],
        structure: str,
        highlights: set[int] | None = None,
    ) -> None:
        """Display a stable snapshot of the selected data structure."""

        self._animation.cancel()
        self._structure = structure.title()
        self._values = list(values)
        self._highlights = set() if highlights is None else set(highlights)
        self._draw_scene()

    def animate_change(
        self,
        old_values: Sequence[object],
        new_values: Sequence[object],
        structure: str,
        operation: str,
        duration_ms: int,
        final_highlights: set[int] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Animate a transition between two data-structure snapshots."""

        normalized_structure = structure.title()
        old_list = list(old_values)
        new_list = list(new_values)
        self._structure = normalized_structure
        self._values = new_list
        self._highlights = set() if final_highlights is None else set(final_highlights)

        start_poses, end_poses = self._build_transition_poses(
            old_list,
            new_list,
            normalized_structure,
            operation.lower(),
        )

        if len(start_poses) != len(end_poses):
            self._logger.error("Animation pose count mismatch; drawing final state.")
            self._draw_scene()
            if on_complete is not None:
                on_complete()
            return

        def draw_progress(progress: float) -> None:
            poses: list[ElementPose] = []
            for start, end in zip(start_poses, end_poses, strict=True):
                poses.append(
                    ElementPose(
                        value=end.value,
                        x=lerp(start.x, end.x, progress),
                        y=lerp(start.y, end.y, progress),
                        width=lerp(start.width, end.width, progress),
                        height=lerp(start.height, end.height, progress),
                        emphasis=start.emphasis or end.emphasis,
                        ghost=start.ghost or end.ghost,
                    )
                )
            self._draw_scene(poses=poses)

        def complete() -> None:
            self._draw_scene()
            if on_complete is not None:
                on_complete()

        self._animation.animate(duration_ms, draw_progress, complete)

    def show_status(
        self,
        message: str,
        kind: str = "info",
        duration_ms: int = 2200,
    ) -> None:
        """Show a temporary status banner over the canvas."""

        self._status_text = message
        self._status_kind = kind
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except tk.TclError:
                pass

        self._draw_scene()

        def restore_ready() -> None:
            self._status_after_id = None
            self._status_text = "Ready for the next operation"
            self._status_kind = "info"
            self._draw_scene()

        self._status_after_id = self.after(duration_ms, restore_ready)

    def _build_transition_poses(
        self,
        old_values: list[object],
        new_values: list[object],
        structure: str,
        operation: str,
    ) -> tuple[list[ElementPose], list[ElementPose]]:
        old_slots = self._slot_positions(structure)
        new_slots = self._slot_positions(structure)
        starts: list[ElementPose] = []
        ends: list[ElementPose] = []

        if operation in {"push", "enqueue"} and len(new_values) == len(old_values) + 1:
            for index, value in enumerate(old_values):
                start = self._pose_from_slot(value, old_slots[index])
                end = self._pose_from_slot(value, new_slots[index])
                starts.append(start)
                ends.append(end)

            target = new_slots[len(new_values) - 1]
            target_pose = self._pose_from_slot(
                new_values[-1],
                target,
                emphasis=True,
                ghost=True,
            )
            if structure == "Stack":
                start_pose = ElementPose(
                    value=new_values[-1],
                    x=target_pose.x,
                    y=-target_pose.height - 36,
                    width=target_pose.width,
                    height=target_pose.height,
                    emphasis=True,
                    ghost=True,
                )
            else:
                start_pose = ElementPose(
                    value=new_values[-1],
                    x=max(self.winfo_width(), 900) + 80,
                    y=target_pose.y,
                    width=target_pose.width,
                    height=target_pose.height,
                    emphasis=True,
                    ghost=True,
                )
            starts.append(start_pose)
            ends.append(target_pose)
            return starts, ends

        if operation == "pop" and len(old_values) == len(new_values) + 1:
            for index, value in enumerate(new_values):
                starts.append(self._pose_from_slot(value, old_slots[index]))
                ends.append(self._pose_from_slot(value, new_slots[index]))

            source = self._pose_from_slot(
                old_values[-1],
                old_slots[len(old_values) - 1],
                emphasis=True,
                ghost=True,
            )
            destination = ElementPose(
                value=source.value,
                x=source.x,
                y=-source.height - 36,
                width=source.width,
                height=source.height,
                emphasis=True,
                ghost=True,
            )
            starts.append(source)
            ends.append(destination)
            return starts, ends

        if operation == "dequeue" and len(old_values) == len(new_values) + 1:
            for new_index, value in enumerate(new_values):
                old_index = new_index + 1
                starts.append(self._pose_from_slot(value, old_slots[old_index]))
                ends.append(self._pose_from_slot(value, new_slots[new_index]))

            source = self._pose_from_slot(
                old_values[0],
                old_slots[0],
                emphasis=True,
                ghost=True,
            )
            destination = ElementPose(
                value=source.value,
                x=-source.width - 80,
                y=source.y,
                width=source.width,
                height=source.height,
                emphasis=True,
                ghost=True,
            )
            starts.append(source)
            ends.append(destination)
            return starts, ends

        if operation in {"clear", "reset"} and old_values:
            for index, value in enumerate(old_values):
                source = self._pose_from_slot(value, old_slots[index], ghost=True)
                direction = -1 if index % 2 == 0 else 1
                destination = ElementPose(
                    value=value,
                    x=source.x + direction * max(self.winfo_width(), 800) * 0.45,
                    y=-source.height - (index * 14),
                    width=max(8.0, source.width * 0.3),
                    height=max(8.0, source.height * 0.3),
                    ghost=True,
                )
                starts.append(source)
                ends.append(destination)
            return starts, ends

        if operation in {"fill", "random_fill"}:
            for index, value in enumerate(new_values):
                target = self._pose_from_slot(value, new_slots[index], emphasis=True)
                if structure == "Stack":
                    source = ElementPose(
                        value=value,
                        x=target.x,
                        y=-target.height - 24 - index * 8,
                        width=target.width * 0.65,
                        height=target.height * 0.65,
                        emphasis=True,
                        ghost=True,
                    )
                else:
                    source = ElementPose(
                        value=value,
                        x=max(self.winfo_width(), 900) + 50 + index * 20,
                        y=target.y,
                        width=target.width * 0.65,
                        height=target.height * 0.65,
                        emphasis=True,
                        ghost=True,
                    )
                starts.append(source)
                ends.append(target)
            return starts, ends

        for index, value in enumerate(new_values):
            target = self._pose_from_slot(value, new_slots[index])
            starts.append(target)
            ends.append(target)
        return starts, ends

    def _draw_scene(self, poses: Sequence[ElementPose] | None = None) -> None:
        if not self.winfo_exists():
            return

        stable_scene = poses is None
        self.delete("scene")
        width = max(self.winfo_width(), 640)
        height = max(self.winfo_height(), 500)

        self.create_text(
            self._config.canvas_padding,
            32,
            text=f"{self._structure.upper()} VISUALIZATION",
            fill=self._colors.text_secondary,
            font=(
                self._config.font_family,
                self._config.small_font_size,
                "bold",
            ),
            anchor="w",
            tags="scene",
        )
        self.create_text(
            self._config.canvas_padding,
            61,
            text="LIFO: top-first removal"
            if self._structure == "Stack"
            else "FIFO: front-first removal",
            fill=self._colors.text_primary,
            font=(
                self._config.font_family,
                self._config.heading_font_size,
                "bold",
            ),
            anchor="w",
            tags="scene",
        )

        self._draw_capacity_slots()

        if poses is None:
            slots = self._slot_positions(self._structure)
            poses = [
                self._pose_from_slot(
                    value,
                    slots[index],
                    emphasis=index in self._highlights,
                )
                for index, value in enumerate(self._values)
            ]

        for pose in poses:
            self._draw_element(pose)

        if stable_scene:
            self._draw_markers()

        self._draw_empty_state(width, height)
        self._draw_status_banner(width)

    def _draw_capacity_slots(self) -> None:
        slots = self._slot_positions(self._structure)
        for index, (x, y, element_width, element_height) in enumerate(slots):
            self._rounded_rectangle(
                x,
                y,
                x + element_width,
                y + element_height,
                radius=min(10, element_height / 4),
                fill=self._colors.canvas,
                outline=self._colors.border,
                width=1,
                dash=(4, 4),
                tags="scene",
            )
            self.create_text(
                x + 8,
                y + 7,
                text=str(index + 1),
                fill=self._colors.text_muted,
                font=(
                    self._config.monospace_font_family,
                    max(7, self._config.small_font_size - 1),
                ),
                anchor="nw",
                tags="scene",
            )

    def _draw_element(self, pose: ElementPose) -> None:
        if pose.width <= 2 or pose.height <= 2:
            return

        if pose.emphasis:
            fill = self._colors.highlight
            outline = self._colors.highlight
            text_fill = self._colors.background
        elif pose.ghost:
            fill = self._colors.ghost_fill
            outline = self._colors.secondary
            text_fill = self._colors.text_primary
        elif self._structure == "Stack":
            fill = self._colors.stack_fill
            outline = self._colors.stack_outline
            text_fill = self._colors.text_primary
        else:
            fill = self._colors.queue_fill
            outline = self._colors.queue_outline
            text_fill = self._colors.text_primary

        self._rounded_rectangle(
            pose.x,
            pose.y,
            pose.x + pose.width,
            pose.y + pose.height,
            radius=min(self._config.element_corner_radius, pose.height / 3),
            fill=fill,
            outline=outline,
            width=2 if pose.emphasis else 1,
            tags="scene",
        )
        self.create_text(
            pose.x + pose.width / 2,
            pose.y + pose.height / 2,
            text=shorten_text(pose.value),
            fill=text_fill,
            font=(
                self._config.monospace_font_family,
                self._config.body_font_size,
                "bold",
            ),
            tags="scene",
        )

    def _draw_markers(self) -> None:
        if not self._values:
            return

        slots = self._slot_positions(self._structure)
        if self._structure == "Stack":
            x, y, element_width, element_height = slots[len(self._values) - 1]
            marker_x = x + element_width + 18
            marker_y = y + element_height / 2
            self.create_line(
                marker_x + 62,
                marker_y,
                marker_x,
                marker_y,
                arrow=tk.LAST,
                fill=self._colors.highlight,
                width=2,
                tags="scene",
            )
            self.create_text(
                marker_x + 68,
                marker_y,
                text="TOP",
                fill=self._colors.highlight,
                font=(
                    self._config.font_family,
                    self._config.small_font_size,
                    "bold",
                ),
                anchor="w",
                tags="scene",
            )
        else:
            front_x, front_y, front_w, front_h = slots[0]
            rear_x, rear_y, rear_w, rear_h = slots[len(self._values) - 1]
            label_y = front_y + front_h + 22
            self.create_text(
                front_x + front_w / 2,
                label_y,
                text="FRONT",
                fill=self._colors.highlight,
                font=(
                    self._config.font_family,
                    self._config.small_font_size,
                    "bold",
                ),
                tags="scene",
            )
            self.create_text(
                rear_x + rear_w / 2,
                label_y,
                text="REAR",
                fill=self._colors.accent,
                font=(
                    self._config.font_family,
                    self._config.small_font_size,
                    "bold",
                ),
                tags="scene",
            )

    def _draw_empty_state(self, width: int, height: int) -> None:
        if self._values:
            return
        self.create_text(
            width / 2,
            height / 2,
            text=f"{self._structure} is empty",
            fill=self._colors.text_secondary,
            font=(
                self._config.font_family,
                self._config.heading_font_size,
                "bold",
            ),
            tags="scene",
        )
        self.create_text(
            width / 2,
            height / 2 + 28,
            text="Use the controls or keyboard shortcuts to add elements.",
            fill=self._colors.text_muted,
            font=(self._config.font_family, self._config.small_font_size),
            tags="scene",
        )

    def _draw_status_banner(self, width: int) -> None:
        color_map = {
            "success": self._colors.success,
            "warning": self._colors.warning,
            "danger": self._colors.danger,
            "info": self._colors.info,
        }
        banner_color = color_map.get(self._status_kind, self._colors.info)
        banner_width = min(460, max(260, width - 110))
        x1 = width / 2 - banner_width / 2
        x2 = width / 2 + banner_width / 2
        y1 = max(self.winfo_height(), 500) - 48
        y2 = y1 + 30
        self._rounded_rectangle(
            x1,
            y1,
            x2,
            y2,
            radius=14,
            fill=self._colors.panel_alt,
            outline=banner_color,
            width=1,
            tags="scene",
        )
        self.create_oval(
            x1 + 12,
            y1 + 10,
            x1 + 22,
            y1 + 20,
            fill=banner_color,
            outline=banner_color,
            tags="scene",
        )
        self.create_text(
            x1 + 31,
            (y1 + y2) / 2,
            text=shorten_text(self._status_text, maximum_length=56),
            fill=self._colors.text_primary,
            font=(self._config.font_family, self._config.small_font_size),
            anchor="w",
            tags="scene",
        )

    def _slot_positions(
        self,
        structure: str,
    ) -> list[tuple[float, float, float, float]]:
        width = max(self.winfo_width(), 640)
        height = max(self.winfo_height(), 500)
        capacity = self._config.capacity
        padding = self._config.canvas_padding
        gap = self._config.element_gap

        if structure == "Stack":
            available_height = max(260, height - 165)
            element_height = min(
                self._config.element_height,
                max(25, (available_height - gap * (capacity - 1)) / capacity),
            )
            element_width = min(
                self._config.element_width,
                max(88, width * 0.22),
            )
            x = width / 2 - element_width / 2
            bottom = height - 72
            return [
                (
                    x,
                    bottom - (index + 1) * element_height - index * gap,
                    element_width,
                    element_height,
                )
                for index in range(capacity)
            ]

        available_width = max(360, width - padding * 2)
        element_width = min(
            self._config.element_width,
            max(42, (available_width - gap * (capacity - 1)) / capacity),
        )
        element_height = min(self._config.element_height, max(38, height * 0.08))
        total_width = capacity * element_width + (capacity - 1) * gap
        start_x = width / 2 - total_width / 2
        y = height / 2 - element_height / 2
        return [
            (
                start_x + index * (element_width + gap),
                y,
                element_width,
                element_height,
            )
            for index in range(capacity)
        ]

    @staticmethod
    def _pose_from_slot(
        value: object,
        slot: tuple[float, float, float, float],
        emphasis: bool = False,
        ghost: bool = False,
    ) -> ElementPose:
        x, y, width, height = slot
        return ElementPose(
            value=value,
            x=x,
            y=y,
            width=width,
            height=height,
            emphasis=emphasis,
            ghost=ghost,
        )

    def _rounded_rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs: object,
    ) -> int:
        radius = max(0, min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2))
        points = (
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        )
        return self.create_polygon(points, smooth=True, splinesteps=20, **kwargs)

    def _on_resize(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is not None:
            try:
                self.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass
        self._resize_after_id = self.after(60, self._finish_resize)

    def _finish_resize(self) -> None:
        self._resize_after_id = None
        if not self._animation.is_running:
            self._draw_scene()

    def _schedule_fps_pulse(self) -> None:
        self._pulse_after_id = self.after(
            self._config.frame_interval_ms,
            self._fps_pulse,
        )

    def _fps_pulse(self) -> None:
        self._pulse_count += 1
        now = time.perf_counter()
        elapsed = now - self._pulse_started_at
        if elapsed >= 1.0:
            measured_fps = self._pulse_count / elapsed
            if self._fps_callback is not None:
                self._fps_callback(measured_fps)
            self._pulse_count = 0
            self._pulse_started_at = now
        self._schedule_fps_pulse()

    def _on_destroy(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        self._animation.cancel()
        for after_id in (
            self._status_after_id,
            self._resize_after_id,
            self._pulse_after_id,
        ):
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
