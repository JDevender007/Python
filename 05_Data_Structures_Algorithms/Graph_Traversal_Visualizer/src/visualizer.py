"""Main application view and traversal animation coordinator."""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
from collections.abc import Iterator
from enum import Enum
from tkinter import messagebox, ttk

from algorithms.bfs import breadth_first_steps
from algorithms.dfs import depth_first_steps
from algorithms.graph import Graph
from algorithms.traversal_utils import TraversalEvent, TraversalStep
from src.colors import Colors
from src.complexity import ComplexityPanel
from src.config import AppConfig
from src.controls import ControlCallbacks, ControlPanel
from src.graph_canvas import EditorMode, GraphCanvas
from src.logger import get_logger
from src.utils import format_duration, format_order

LOGGER = get_logger(__name__)


class AnimationState(Enum):
    """Traversal animation lifecycle states."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETE = "complete"


class StatisticsPanel(tk.Frame):
    """Live traversal and graph statistics."""

    def __init__(self, parent: tk.Misc, config: AppConfig) -> None:
        super().__init__(
            parent,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        self._config = config
        self._values: dict[str, tk.StringVar] = {
            "algorithm": tk.StringVar(value="BFS"),
            "visited": tk.StringVar(value="0"),
            "order": tk.StringVar(value="—"),
            "time": tk.StringVar(value="0 ms"),
            "nodes": tk.StringVar(value="0"),
            "edges": tk.StringVar(value="0"),
            "status": tk.StringVar(value="Ready"),
            "fps": tk.StringVar(value="0.0"),
            "start": tk.StringVar(value="—"),
        }
        self._build()

    def _build(self) -> None:
        padding = self._config.layout.panel_padding
        tk.Label(
            self,
            text="LIVE STATISTICS",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9, "bold"),
        ).pack(anchor="w", padx=padding, pady=(padding, 8))

        content = tk.Frame(self, bg=Colors.SURFACE)
        content.pack(fill="x", padx=padding, pady=(0, padding))
        rows = (
            ("Algorithm", "algorithm"),
            ("Start Node", "start"),
            ("Visited", "visited"),
            ("Traversal Order", "order"),
            ("Execution Time", "time"),
            ("Graph Size", "nodes"),
            ("Edges", "edges"),
            ("Status", "status"),
            ("FPS", "fps"),
        )
        for index, (caption, key) in enumerate(rows):
            tk.Label(
                content,
                text=caption,
                bg=Colors.SURFACE,
                fg=Colors.TEXT_MUTED,
                font=(self._config.fonts.family, 9),
            ).grid(row=index, column=0, sticky="nw", pady=4)
            value = tk.Label(
                content,
                textvariable=self._values[key],
                bg=Colors.SURFACE,
                fg=Colors.TEXT if key != "status" else Colors.SECONDARY,
                font=(
                    self._config.fonts.mono_family
                    if key in {"order", "time", "fps"}
                    else self._config.fonts.family,
                    9,
                    "bold",
                ),
                justify="right",
                anchor="e",
                wraplength=150,
            )
            value.grid(row=index, column=1, sticky="ne", pady=4, padx=(10, 0))
        content.grid_columnconfigure(1, weight=1)

    def set_value(self, key: str, value: str) -> None:
        """Set one displayed statistic."""
        self._values[key].set(value)


class GraphTraversalVisualizer(tk.Frame):
    """Complete graph traversal visualization application."""

    def __init__(self, root: tk.Tk, config: AppConfig | None = None) -> None:
        self.config_data = config or AppConfig()
        super().__init__(root, bg=Colors.BACKGROUND)
        self.root = root
        self.graph = Graph()

        self._state = AnimationState.IDLE
        self._step_iterator: Iterator[TraversalStep] | None = None
        self._current_step: TraversalStep | None = None
        self._step_elapsed = 0.0
        self._active_elapsed = 0.0
        self._visited: set[int] = set()
        self._order: list[int] = []
        self._traversed_edges: set[tuple[int, int]] = set()
        self._current_node: int | None = None
        self._current_edge: tuple[int, int] | None = None

        self._last_frame_time = time.perf_counter()
        self._fps_window_start = self._last_frame_time
        self._fps_frames = 0
        self._fps = 0.0
        self._fullscreen = False
        self._status_text = tk.StringVar(value="Ready")
        self._random = random.Random()
        self._reset_snapshot: dict[str, object] | None = None

        self.pack(fill="both", expand=True)
        self._configure_styles()
        self._build_layout()
        self._bind_shortcuts()
        self.generate_graph()
        self._schedule_frame()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            LOGGER.info("The 'clam' ttk theme is unavailable; using the default.")
        style.configure(
            "TCombobox",
            fieldbackground=Colors.SURFACE_ALT,
            background=Colors.SURFACE_ALT,
            foreground=Colors.TEXT,
            arrowcolor=Colors.TEXT,
            bordercolor=Colors.BORDER,
            lightcolor=Colors.BORDER,
            darkcolor=Colors.BORDER,
            padding=7,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Colors.SURFACE_ALT)],
            foreground=[("readonly", Colors.TEXT)],
            selectbackground=[("readonly", Colors.SURFACE_ALT)],
            selectforeground=[("readonly", Colors.TEXT)],
        )
        self.root.option_add("*TCombobox*Listbox.background", Colors.SURFACE_ALT)
        self.root.option_add("*TCombobox*Listbox.foreground", Colors.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", Colors.PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectForeground", Colors.WHITE)

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build_header()

        body = tk.Frame(self, bg=Colors.BACKGROUND)
        body.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=self.config_data.layout.padding,
            pady=(0, self.config_data.layout.padding),
        )
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        callbacks = ControlCallbacks(
            generate_graph=self.generate_graph,
            start_traversal=self.start_traversal,
            pause_traversal=self.pause_traversal,
            resume_traversal=self.resume_traversal,
            stop_traversal=self.stop_traversal,
            reset_visualization=self.reset_visualization,
            clear_graph=self.clear_graph,
            algorithm_changed=self._on_algorithm_changed,
            editor_mode_changed=self._on_editor_mode_changed,
        )
        controls_host = self._build_scrollable_controls(body, callbacks)
        controls_host.grid(row=0, column=0, sticky="nsw", padx=(0, 12))

        canvas_card = tk.Frame(
            body,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        canvas_card.grid(row=0, column=1, sticky="nsew")
        canvas_card.grid_rowconfigure(1, weight=1)
        canvas_card.grid_columnconfigure(0, weight=1)

        canvas_toolbar = tk.Frame(canvas_card, bg=Colors.SURFACE)
        canvas_toolbar.grid(row=0, column=0, sticky="ew", padx=14, pady=10)
        tk.Label(
            canvas_toolbar,
            text="GRAPH WORKSPACE",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self.config_data.fonts.family, 9, "bold"),
        ).pack(side="left")
        self._start_node_label = tk.Label(
            canvas_toolbar,
            text="Start: —",
            bg=Colors.SURFACE,
            fg=Colors.PRIMARY,
            font=(self.config_data.fonts.mono_family, 9, "bold"),
        )
        self._start_node_label.pack(side="right")

        self.graph_canvas = GraphCanvas(
            canvas_card,
            self.graph,
            self.config_data,
            on_graph_changed=self._on_graph_changed,
            on_status=self.set_status,
            on_start_node_changed=self._on_start_node_changed,
            weight_provider=lambda: self.controls.edge_weight,
        )
        self.graph_canvas.grid(row=1, column=0, sticky="nsew")

        right_panel = tk.Frame(
            body,
            bg=Colors.BACKGROUND,
            width=self.config_data.layout.right_panel_width,
        )
        right_panel.grid(row=0, column=2, sticky="nse", padx=(12, 0))
        right_panel.grid_propagate(False)

        self.statistics = StatisticsPanel(right_panel, self.config_data)
        self.statistics.pack(fill="x", pady=(0, 12))
        self.complexity = ComplexityPanel(right_panel, self.config_data)
        self.complexity.pack(fill="x", pady=(0, 12))
        self._build_legend(right_panel)
        self._build_status_bar()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=Colors.BACKGROUND)
        header.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self.config_data.layout.padding,
            pady=(14, 12),
        )
        left = tk.Frame(header, bg=Colors.BACKGROUND)
        left.pack(side="left")
        tk.Label(
            left,
            text="Graph Traversal Visualizer",
            bg=Colors.BACKGROUND,
            fg=Colors.TEXT,
            font=(
                self.config_data.fonts.family,
                self.config_data.fonts.title_size,
                "bold",
            ),
        ).pack(anchor="w")
        tk.Label(
            left,
            text="Build, edit, and animate breadth-first and depth-first search",
            bg=Colors.BACKGROUND,
            fg=Colors.TEXT_MUTED,
            font=(self.config_data.fonts.family, 10),
        ).pack(anchor="w", pady=(2, 0))

        badge = tk.Label(
            header,
            text="60 FPS  •  BFS  •  DFS",
            bg=Colors.SURFACE_ALT,
            fg=Colors.SECONDARY,
            padx=12,
            pady=7,
            font=(self.config_data.fonts.mono_family, 9, "bold"),
        )
        badge.pack(side="right")

    def _build_scrollable_controls(
        self,
        parent: tk.Misc,
        callbacks: ControlCallbacks,
    ) -> tk.Frame:
        host = tk.Frame(
            parent,
            bg=Colors.BACKGROUND,
            width=self.config_data.layout.left_panel_width,
        )
        host.grid_propagate(False)
        canvas = tk.Canvas(
            host,
            bg=Colors.BACKGROUND,
            highlightthickness=0,
            width=self.config_data.layout.left_panel_width - 14,
        )
        scrollbar = tk.Scrollbar(
            host,
            orient="vertical",
            command=canvas.yview,
            bg=Colors.SURFACE_ALT,
            troughcolor=Colors.BACKGROUND,
            activebackground=Colors.SURFACE_HOVER,
            relief="flat",
            bd=0,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.controls = ControlPanel(canvas, self.config_data, callbacks)
        window_id = canvas.create_window((0, 0), window=self.controls, anchor="nw")

        def update_scroll_region(_event: tk.Event[tk.Misc]) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_inner(event: tk.Event[tk.Misc]) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def mousewheel(event: tk.Event[tk.Misc]) -> str:
            delta = -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta * 3, "units")
            return "break"

        self.controls.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_inner)
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", mousewheel))
        canvas.bind(
            "<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>")
        )
        return host

    def _build_legend(self, parent: tk.Misc) -> None:
        frame = tk.Frame(
            parent,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        frame.pack(fill="x")
        tk.Label(
            frame,
            text="VISUAL KEY",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            font=(self.config_data.fonts.family, 9, "bold"),
        ).pack(anchor="w", padx=14, pady=(14, 8))
        items = (
            (Colors.NODE_START, "Start node"),
            (Colors.NODE_CURRENT, "Current node"),
            (Colors.NODE_VISITED, "Visited node"),
            (Colors.EDGE_CURRENT, "Current edge"),
            (Colors.EDGE_TRAVERSED, "Traversed path"),
        )
        for color, caption in items:
            row = tk.Frame(frame, bg=Colors.SURFACE)
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text="●", bg=Colors.SURFACE, fg=color).pack(side="left")
            tk.Label(
                row,
                text=caption,
                bg=Colors.SURFACE,
                fg=Colors.TEXT,
                font=(self.config_data.fonts.family, 9),
            ).pack(side="left", padx=(8, 0))
        tk.Frame(frame, bg=Colors.SURFACE, height=10).pack()

    def _build_status_bar(self) -> None:
        status = tk.Frame(
            self,
            bg=Colors.SURFACE,
            highlightbackground=Colors.BORDER,
            highlightthickness=1,
        )
        status.grid(row=2, column=0, sticky="ew")
        tk.Label(
            status,
            textvariable=self._status_text,
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            anchor="w",
            padx=14,
            pady=7,
            font=(self.config_data.fonts.family, 9),
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            status,
            text="F11 Fullscreen   •   Esc Exit",
            bg=Colors.SURFACE,
            fg=Colors.TEXT_MUTED,
            padx=14,
            font=(self.config_data.fonts.mono_family, 8),
        ).pack(side="right")

    def generate_graph(self) -> None:
        """Generate a connected random weighted graph."""
        self._stop_internal(clear_highlights=True)
        count = self.controls.node_count if hasattr(self, "controls") else 10
        self.graph.clear()

        for x, y in self._generate_positions(count):
            self.graph.add_node(x, y)

        for node_id in range(1, count):
            lower_bound = max(0, node_id - 4)
            parent = self._random.randrange(lower_bound, node_id)
            self.graph.add_edge(parent, node_id, self._random.randint(1, 9))

        maximum_edges = count * (count - 1) // 2
        desired_edges = min(maximum_edges, max(count - 1, round(count * 1.65)))
        attempts = 0
        while self.graph.edge_count < desired_edges and attempts < desired_edges * 20:
            source, target = self._random.sample(range(count), 2)
            if not self.graph.has_edge(source, target):
                self.graph.add_edge(source, target, self._random.randint(1, 9))
            attempts += 1

        self.graph.validate()
        self._reset_snapshot = self.graph.snapshot()
        self.graph_canvas.set_start_node(0)
        self.graph_canvas.clear_visual_state()
        self._reset_runtime_statistics()
        self._update_statistics()
        self.set_status(
            f"Generated a connected graph with {count} nodes and "
            f"{self.graph.edge_count} edges."
        )
        LOGGER.info(
            "Generated graph: nodes=%d edges=%d", count, self.graph.edge_count
        )

    def _generate_positions(self, count: int) -> list[tuple[float, float]]:
        positions: list[tuple[float, float]] = []
        if count <= 12:
            for index in range(count):
                angle = -math.pi / 2 + 2 * math.pi * index / count
                radius = 0.39
                positions.append(
                    (
                        0.5 + radius * math.cos(angle),
                        0.5 + radius * math.sin(angle),
                    )
                )
            return positions

        outer_count = math.ceil(count * 0.62)
        inner_count = count - outer_count
        for index in range(outer_count):
            angle = -math.pi / 2 + 2 * math.pi * index / outer_count
            positions.append(
                (0.5 + 0.43 * math.cos(angle), 0.5 + 0.43 * math.sin(angle))
            )
        for index in range(inner_count):
            angle = -math.pi / 2 + math.pi / inner_count + 2 * math.pi * index / inner_count
            positions.append(
                (0.5 + 0.23 * math.cos(angle), 0.5 + 0.23 * math.sin(angle))
            )
        return positions

    def start_traversal(self) -> None:
        """Start BFS or DFS from the selected start node."""
        if self.graph.node_count == 0:
            self.set_status("Generate or create a graph before starting traversal.")
            return

        try:
            self.graph.validate()
            start_node = self.graph_canvas.ensure_start_node()
            if start_node is None:
                raise ValueError("No start node is available.")
            algorithm = self.controls.algorithm
            self._reset_runtime_statistics()
            self.graph_canvas.clear_visual_state()
            if algorithm == "BFS":
                self._step_iterator = breadth_first_steps(self.graph, start_node)
            else:
                self._step_iterator = depth_first_steps(self.graph, start_node)
            self._state = AnimationState.RUNNING
            self.controls.set_animation_state(self._state.value)
            self.statistics.set_value("algorithm", algorithm)
            self.complexity.set_algorithm(algorithm)
            self._advance_step()
            self.set_status(f"Running {algorithm} from node {start_node}.")
            LOGGER.info("Started %s from node %d", algorithm, start_node)
        except ValueError as exc:
            LOGGER.warning("Traversal could not start: %s", exc)
            self.set_status(str(exc))
            messagebox.showwarning("Traversal unavailable", str(exc), parent=self.root)

    def pause_traversal(self) -> None:
        """Pause the current traversal."""
        if self._state is AnimationState.RUNNING:
            self._state = AnimationState.PAUSED
            self.controls.set_animation_state(self._state.value)
            self.set_status("Traversal paused.")

    def resume_traversal(self) -> None:
        """Resume a paused traversal."""
        if self._state is AnimationState.PAUSED:
            self._state = AnimationState.RUNNING
            self.controls.set_animation_state(self._state.value)
            self._last_frame_time = time.perf_counter()
            self.set_status("Traversal resumed.")

    def stop_traversal(self) -> None:
        """Stop traversal while preserving completed highlights."""
        if self._state in {AnimationState.RUNNING, AnimationState.PAUSED}:
            self._state = AnimationState.STOPPED
            self._step_iterator = None
            self._current_step = None
            self._current_edge = None
            self.controls.set_animation_state(self._state.value)
            self._push_visual_state(0.0)
            self.set_status("Traversal stopped.")
            self._update_statistics()

    def reset_visualization(self) -> None:
        """Restore the last generated graph and clear traversal state."""
        self._stop_internal(clear_highlights=True)
        if self._reset_snapshot is not None:
            self.graph.restore(self._reset_snapshot)
        self._reset_runtime_statistics()
        self.graph_canvas.ensure_start_node()
        self.graph_canvas.clear_visual_state()
        self._update_statistics()
        self.set_status("Graph restored to its last generated state.")

    def clear_graph(self) -> None:
        """Remove every node and edge from the workspace."""
        self._stop_internal(clear_highlights=True)
        self.graph.clear()
        self.graph_canvas.set_start_node(None)
        self.graph_canvas.clear_visual_state()
        self._reset_runtime_statistics()
        self._update_statistics()
        self.set_status("Graph cleared. Add nodes or generate a new graph.")
        LOGGER.info("Graph cleared")

    def _stop_internal(self, *, clear_highlights: bool) -> None:
        self._state = AnimationState.IDLE
        self._step_iterator = None
        self._current_step = None
        self._step_elapsed = 0.0
        self._current_node = None
        self._current_edge = None
        if clear_highlights:
            self._visited.clear()
            self._order.clear()
            self._traversed_edges.clear()
        if hasattr(self, "controls"):
            self.controls.set_animation_state(self._state.value)

    def _reset_runtime_statistics(self) -> None:
        self._active_elapsed = 0.0
        self._step_elapsed = 0.0
        self._visited.clear()
        self._order.clear()
        self._traversed_edges.clear()
        self._current_node = None
        self._current_edge = None
        self._current_step = None

    def _advance_step(self) -> None:
        if self._step_iterator is None:
            return
        try:
            self._current_step = next(self._step_iterator)
            self._step_elapsed = 0.0
            if self._current_step.message:
                self.set_status(self._current_step.message)
        except StopIteration:
            self._finish_traversal()

    def _duration_for_step(self, step: TraversalStep) -> float:
        speed = max(self.controls.animation_speed, 0.01)
        animation = self.config_data.animation
        if step.event is TraversalEvent.EDGE:
            return animation.edge_duration_seconds / speed
        if step.event is TraversalEvent.VISIT:
            return animation.visit_duration_seconds / speed
        if step.event is TraversalEvent.START:
            return animation.start_duration_seconds / speed
        return 0.12 / speed

    def _render_current_step(self, progress: float) -> None:
        step = self._current_step
        if step is None:
            self._push_visual_state(0.0)
            return

        preview_visited = set(self._visited)
        preview_order = list(self._order)
        self._current_edge = None
        self._current_node = step.current

        if step.event is TraversalEvent.EDGE:
            if step.source is not None and step.target is not None:
                self._current_edge = (step.source, step.target)
                self._current_node = step.source
        elif step.event is TraversalEvent.VISIT and step.current is not None:
            preview_visited.add(step.current)
            preview_order = list(step.visited_order)
        elif step.event is TraversalEvent.COMPLETE:
            preview_visited = set(step.visited_order)
            preview_order = list(step.visited_order)

        self.graph_canvas.set_visual_state(
            visited=preview_visited,
            current_node=self._current_node,
            current_edge=self._current_edge,
            traversed_edges=self._traversed_edges,
            traversal_order=preview_order,
            edge_progress=progress if step.event is TraversalEvent.EDGE else 0.0,
            pulse_progress=progress if step.event is TraversalEvent.VISIT else 0.0,
        )

    def _complete_current_step(self) -> None:
        step = self._current_step
        if step is None:
            return
        if step.event is TraversalEvent.EDGE:
            if step.source is not None and step.target is not None:
                self._traversed_edges.add(tuple(sorted((step.source, step.target))))
        elif step.event is TraversalEvent.VISIT:
            self._visited = set(step.visited_order)
            self._order = list(step.visited_order)
        elif step.event is TraversalEvent.COMPLETE:
            self._visited = set(step.visited_order)
            self._order = list(step.visited_order)
            self._finish_traversal()

    def _finish_traversal(self) -> None:
        if self._state is AnimationState.COMPLETE:
            return
        self._state = AnimationState.COMPLETE
        self._step_iterator = None
        self._current_step = None
        self._current_edge = None
        self.controls.set_animation_state(self._state.value)
        self.graph_canvas.set_visual_state(
            visited=self._visited,
            current_node=self._order[-1] if self._order else None,
            current_edge=None,
            traversed_edges=self._traversed_edges,
            traversal_order=self._order,
            edge_progress=1.0,
            pulse_progress=1.0,
        )
        self.set_status(
            f"{self.controls.algorithm} complete: visited {len(self._visited)} nodes."
        )
        self._update_statistics()
        LOGGER.info(
            "%s completed in %.4f seconds; visited=%s",
            self.controls.algorithm,
            self._active_elapsed,
            self._order,
        )

    def _push_visual_state(self, progress: float) -> None:
        self.graph_canvas.set_visual_state(
            visited=self._visited,
            current_node=self._current_node,
            current_edge=self._current_edge,
            traversed_edges=self._traversed_edges,
            traversal_order=self._order,
            edge_progress=progress,
            pulse_progress=progress,
        )

    def _schedule_frame(self) -> None:
        interval = max(1, round(1000 / self.config_data.animation.target_fps))
        self.after(interval, self._frame_tick)

    def _frame_tick(self) -> None:
        now = time.perf_counter()
        delta = min(now - self._last_frame_time, 0.1)
        self._last_frame_time = now
        self._fps_frames += 1

        if now - self._fps_window_start >= 0.5:
            elapsed = now - self._fps_window_start
            self._fps = self._fps_frames / elapsed if elapsed > 0 else 0.0
            self._fps_frames = 0
            self._fps_window_start = now

        if self._state is AnimationState.RUNNING and self._current_step is not None:
            self._active_elapsed += delta
            self._step_elapsed += delta
            duration = max(self._duration_for_step(self._current_step), 0.001)
            progress = min(1.0, self._step_elapsed / duration)
            self._render_current_step(progress)
            if progress >= 1.0:
                step_event = self._current_step.event
                self._complete_current_step()
                if step_event is not TraversalEvent.COMPLETE:
                    self._advance_step()

        self._update_statistics()
        self._schedule_frame()

    def _update_statistics(self) -> None:
        if not hasattr(self, "statistics"):
            return
        status_name = self._state.value.title()
        if self._state is AnimationState.IDLE:
            status_name = "Ready"
        self.statistics.set_value("algorithm", self.controls.algorithm)
        self.statistics.set_value("visited", str(len(self._visited)))
        self.statistics.set_value("order", format_order(self._order))
        self.statistics.set_value("time", format_duration(self._active_elapsed))
        self.statistics.set_value("nodes", str(self.graph.node_count))
        self.statistics.set_value("edges", str(self.graph.edge_count))
        self.statistics.set_value("status", status_name)
        self.statistics.set_value("fps", f"{self._fps:,.1f}")
        start_node = self.graph_canvas.start_node
        self.statistics.set_value(
            "start", "—" if start_node is None else str(start_node)
        )

    def _on_graph_changed(self) -> None:
        if self._state in {AnimationState.RUNNING, AnimationState.PAUSED}:
            self._stop_internal(clear_highlights=True)
            self.graph_canvas.clear_visual_state()
            self.set_status("Traversal stopped because the graph was edited.")
        self.graph.validate()
        self.graph_canvas.ensure_start_node()
        self._update_statistics()

    def _on_start_node_changed(self, node_id: int | None) -> None:
        text = "—" if node_id is None else str(node_id)
        if hasattr(self, "_start_node_label"):
            self._start_node_label.configure(text=f"Start: {text}")
        if hasattr(self, "statistics"):
            self.statistics.set_value("start", text)

    def _on_algorithm_changed(self, algorithm: str) -> None:
        self.complexity.set_algorithm(algorithm)
        self.statistics.set_value("algorithm", algorithm)
        self.set_status(f"Selected {algorithm} traversal.")

    def _on_editor_mode_changed(self, mode: EditorMode) -> None:
        self.graph_canvas.set_editor_mode(mode)
        self.set_status(f"Editor mode: {mode.name.replace('_', ' ').title()}.")

    def set_status(self, message: str) -> None:
        """Display a non-modal application status message."""
        self._status_text.set(message)

    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen window mode."""
        self._fullscreen = not self._fullscreen
        self.root.attributes("-fullscreen", self._fullscreen)
        self.set_status("Fullscreen enabled." if self._fullscreen else "Fullscreen disabled.")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _event: self._shortcut(self.start_traversal))
        self.root.bind("<Key-p>", lambda _event: self._shortcut(self.pause_traversal))
        self.root.bind("<Key-P>", lambda _event: self._shortcut(self.pause_traversal))
        self.root.bind("<Key-r>", lambda _event: self._shortcut(self.resume_traversal))
        self.root.bind("<Key-R>", lambda _event: self._shortcut(self.resume_traversal))
        self.root.bind("<Key-s>", lambda _event: self._shortcut(self.stop_traversal))
        self.root.bind("<Key-S>", lambda _event: self._shortcut(self.stop_traversal))
        self.root.bind("<Key-c>", lambda _event: self._shortcut(self.clear_graph))
        self.root.bind("<Key-C>", lambda _event: self._shortcut(self.clear_graph))
        self.root.bind("<Key-g>", lambda _event: self._shortcut(self.generate_graph))
        self.root.bind("<Key-G>", lambda _event: self._shortcut(self.generate_graph))
        self.root.bind("<F11>", lambda _event: self._shortcut(self.toggle_fullscreen))
        self.root.bind("<Escape>", lambda _event: self._shortcut(self.root.destroy))

    @staticmethod
    def _shortcut(command: object) -> str:
        if callable(command):
            command()
        return "break"
