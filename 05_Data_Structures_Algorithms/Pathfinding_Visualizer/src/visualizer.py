"""Interactive grid canvas and animation engine."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable
from typing import Literal

from algorithms import SearchResult
from src.colors import COLORS
from src.grid import GridModel
from src.logger import get_logger
from src.node import Node, NodeState

AnimationPhase = Literal["visited", "path"]
ProgressCallback = Callable[[AnimationPhase, int, int], None]
CompletionCallback = Callable[[bool], None]
FpsCallback = Callable[[float], None]


class GridVisualizer(tk.Frame):
    """Render and edit a grid while animating algorithm results."""

    def __init__(
        self,
        master: tk.Misc,
        model: GridModel,
        on_grid_changed: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            background=COLORS.panel,
            highlightbackground=COLORS.border,
            highlightthickness=1,
        )
        self.model = model
        self._on_grid_changed = on_grid_changed
        self._logger = get_logger(__name__)

        self.canvas = tk.Canvas(
            self,
            background=COLORS.canvas,
            borderwidth=0,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._cell_items: dict[Node, int] = {}
        self._cell_width = 1.0
        self._cell_height = 1.0
        self._interaction_locked = False
        self._drag_mode: str | None = None
        self._last_drag_node: Node | None = None

        self._animation_events: list[tuple[AnimationPhase, Node]] = []
        self._animation_index = 0
        self._visited_count = 0
        self._path_node_count = 0
        self._after_id: str | None = None
        self._paused = False
        self._stopped = True
        self._delay_supplier: Callable[[], int] | None = None
        self._progress_callback: ProgressCallback | None = None
        self._completion_callback: CompletionCallback | None = None
        self._fps_callback: FpsCallback | None = None
        self._fps_window_started = time.perf_counter()
        self._fps_frames = 0

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self.canvas.bind("<ButtonRelease-3>", self._on_button_release)
        self.canvas.bind("<Button-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)

    @property
    def is_animating(self) -> bool:
        """Return whether an animation is active or paused."""
        return not self._stopped

    @property
    def is_paused(self) -> bool:
        """Return whether the active animation is paused."""
        return self.is_animating and self._paused

    def set_interaction_locked(self, locked: bool) -> None:
        """Enable or disable grid editing."""
        self._interaction_locked = locked
        self.canvas.configure(cursor="arrow" if locked else "crosshair")

    def redraw(self) -> None:
        """Redraw every grid cell using the current canvas dimensions."""
        self.canvas.delete("all")
        self._cell_items.clear()

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self._cell_width = width / self.model.columns
        self._cell_height = height / self.model.rows

        for node in self.model:
            x1 = node.column * self._cell_width
            y1 = node.row * self._cell_height
            x2 = (node.column + 1) * self._cell_width
            y2 = (node.row + 1) * self._cell_height
            item_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=self._color_for(node.state),
                outline=COLORS.grid_line,
                width=1,
            )
            self._cell_items[node] = item_id

        self._draw_endpoint_labels()

    def refresh_node(self, node: Node) -> None:
        """Update a single cell without rebuilding the canvas."""
        item_id = self._cell_items.get(node)
        if item_id is None:
            self.redraw()
            return
        self.canvas.itemconfigure(item_id, fill=self._color_for(node.state))
        if node.is_start or node.is_end:
            self._draw_endpoint_labels()

    def clear_path(self) -> None:
        """Clear all search visualization state and redraw."""
        self.model.clear_search()
        self.redraw()

    def resize_grid(self, rows: int, columns: int) -> None:
        """Resize the underlying grid and rebuild the canvas."""
        self.stop_animation(notify=False)
        self.model.resize(rows, columns)
        self.redraw()

    def start_animation(
        self,
        result: SearchResult,
        delay_supplier: Callable[[], int],
        on_progress: ProgressCallback,
        on_complete: CompletionCallback,
        on_fps: FpsCallback,
    ) -> None:
        """Animate visited nodes followed by the discovered path."""
        self.stop_animation(notify=False)
        self._animation_events = [
            ("visited", node) for node in result.visited_order
        ]
        self._animation_events.extend(("path", node) for node in result.path)
        self._animation_index = 0
        self._visited_count = 0
        self._path_node_count = 0
        self._paused = False
        self._stopped = False
        self._delay_supplier = delay_supplier
        self._progress_callback = on_progress
        self._completion_callback = on_complete
        self._fps_callback = on_fps
        self._fps_window_started = time.perf_counter()
        self._fps_frames = 0
        self.set_interaction_locked(True)
        self._schedule_next(0)

    def pause_animation(self) -> bool:
        """Pause an active animation and return whether state changed."""
        if self._stopped or self._paused:
            return False
        self._paused = True
        return True

    def resume_animation(self) -> bool:
        """Resume a paused animation and return whether state changed."""
        if self._stopped or not self._paused:
            return False
        self._paused = False
        return True

    def stop_animation(self, notify: bool = True) -> bool:
        """Stop animation callbacks and unlock the interactive grid."""
        was_active = not self._stopped
        self._stopped = True
        self._paused = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                self._logger.debug("Scheduled callback was already unavailable.")
            self._after_id = None
        self.set_interaction_locked(False)
        if was_active and notify and self._completion_callback is not None:
            self._completion_callback(False)
        return was_active

    def _schedule_next(self, delay_ms: int | None = None) -> None:
        if self._stopped:
            return
        delay = delay_ms
        if delay is None:
            delay = self._delay_supplier() if self._delay_supplier else 16
        self._after_id = self.after(max(1, int(delay)), self._animation_tick)

    def _animation_tick(self) -> None:
        self._after_id = None
        if self._stopped:
            return
        if self._paused:
            self._schedule_next(16)
            return

        if self._animation_index >= len(self._animation_events):
            self._finish_animation()
            return

        phase, node = self._animation_events[self._animation_index]
        self._animation_index += 1

        if phase == "visited":
            self._visited_count += 1
            if not node.is_start and not node.is_end and not node.is_wall:
                node.is_visited = True
                self.refresh_node(node)
        else:
            self._path_node_count += 1
            if not node.is_start and not node.is_end and not node.is_wall:
                node.is_path = True
                node.is_visited = False
                self.refresh_node(node)

        if self._progress_callback is not None:
            self._progress_callback(
                phase,
                self._visited_count,
                self._path_node_count,
            )

        self._update_fps()
        self._schedule_next()

    def _finish_animation(self) -> None:
        self._stopped = True
        self._paused = False
        self.set_interaction_locked(False)
        self._report_fps(force=True)
        if self._completion_callback is not None:
            self._completion_callback(True)

    def _update_fps(self) -> None:
        self._fps_frames += 1
        elapsed = time.perf_counter() - self._fps_window_started
        if elapsed >= 0.5:
            self._report_fps(force=False)

    def _report_fps(self, force: bool) -> None:
        elapsed = time.perf_counter() - self._fps_window_started
        if elapsed <= 0.0:
            return
        if (force or self._fps_frames > 0) and self._fps_callback is not None:
            fps = min(60.0, self._fps_frames / elapsed)
            self._fps_callback(fps)
        self._fps_window_started = time.perf_counter()
        self._fps_frames = 0

    def _on_resize(self, _event: tk.Event[tk.Misc]) -> None:
        self.redraw()

    def _node_from_event(self, event: tk.Event[tk.Misc]) -> Node | None:
        if self._cell_width <= 0.0 or self._cell_height <= 0.0:
            return None
        column = int(event.x / self._cell_width)
        row = int(event.y / self._cell_height)
        return self.model.node_at(row, column)

    def _on_left_press(self, event: tk.Event[tk.Misc]) -> None:
        if self._interaction_locked:
            return
        node = self._node_from_event(event)
        if node is None:
            return

        self.model.clear_search()
        self.redraw()
        self._last_drag_node = None

        if node.is_start:
            self._drag_mode = "move_start"
        elif node.is_end:
            self._drag_mode = "move_end"
        elif node.is_wall:
            self._drag_mode = "erase"
        elif self.model.start_node is None:
            self._drag_mode = "place_start"
        elif self.model.end_node is None:
            self._drag_mode = "place_end"
        else:
            self._drag_mode = "draw_wall"

        self._apply_drag_action(node)

    def _on_left_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._interaction_locked or self._drag_mode is None:
            return
        node = self._node_from_event(event)
        if node is not None:
            self._apply_drag_action(node)

    def _on_right_press(self, event: tk.Event[tk.Misc]) -> None:
        if self._interaction_locked:
            return
        self.model.clear_search()
        self.redraw()
        self._drag_mode = "erase"
        self._last_drag_node = None
        node = self._node_from_event(event)
        if node is not None:
            self._apply_drag_action(node)

    def _on_right_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._interaction_locked:
            return
        node = self._node_from_event(event)
        if node is not None:
            self._apply_drag_action(node)

    def _on_button_release(self, _event: tk.Event[tk.Misc]) -> None:
        self._drag_mode = None
        self._last_drag_node = None

    def _apply_drag_action(self, node: Node) -> None:
        if node == self._last_drag_node:
            return
        self._last_drag_node = node

        if self._drag_mode == "place_start":
            self.model.set_start(node)
            self._drag_mode = None
        elif self._drag_mode == "place_end":
            self.model.set_end(node)
            self._drag_mode = None
        elif self._drag_mode == "move_start" and not node.is_end:
            self.model.set_start(node)
        elif self._drag_mode == "move_end" and not node.is_start:
            self.model.set_end(node)
        elif self._drag_mode == "draw_wall":
            self.model.set_wall(node, True)
        elif self._drag_mode == "erase":
            self.model.erase_node(node)

        self.redraw()
        self._on_grid_changed()

    def _draw_endpoint_labels(self) -> None:
        self.canvas.delete("endpoint_label")
        for node, label in (
            (self.model.start_node, "S"),
            (self.model.end_node, "E"),
        ):
            if node is None:
                continue
            x = (node.column + 0.5) * self._cell_width
            y = (node.row + 0.5) * self._cell_height
            font_size = max(8, int(min(self._cell_width, self._cell_height) * 0.42))
            self.canvas.create_text(
                x,
                y,
                text=label,
                fill="#FFFFFF",
                font=("TkDefaultFont", font_size, "bold"),
                tags="endpoint_label",
            )

    @staticmethod
    def _color_for(state: NodeState) -> str:
        return {
            NodeState.EMPTY: COLORS.empty,
            NodeState.WALL: COLORS.wall,
            NodeState.START: COLORS.start,
            NodeState.END: COLORS.end,
            NodeState.VISITED: COLORS.visited_glow,
            NodeState.PATH: COLORS.path,
        }[state]

    def destroy(self) -> None:
        """Cancel scheduled work before destroying the widget."""
        self.stop_animation(notify=False)
        super().destroy()
