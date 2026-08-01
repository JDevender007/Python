"""Interactive Tkinter canvas for graph editing and animation."""

from __future__ import annotations

import math
import tkinter as tk
from collections.abc import Callable, Collection, Sequence
from enum import Enum

from algorithms.graph import Edge, Graph
from src.colors import Colors
from src.config import AppConfig
from src.logger import get_logger
from src.utils import clamp, ease_in_out_cubic, point_segment_distance

LOGGER = get_logger(__name__)


class EditorMode(Enum):
    """Available mouse interaction modes."""

    MOVE_NODE = "move_node"
    ADD_NODE = "add_node"
    ADD_EDGE = "add_edge"
    DELETE_NODE = "delete_node"
    DELETE_EDGE = "delete_edge"
    SET_START = "set_start"


class GraphCanvas(tk.Canvas):
    """Render and edit an undirected weighted graph."""

    def __init__(
        self,
        parent: tk.Misc,
        graph: Graph,
        config: AppConfig,
        *,
        on_graph_changed: Callable[[], None],
        on_status: Callable[[str], None],
        on_start_node_changed: Callable[[int | None], None],
        weight_provider: Callable[[], float],
    ) -> None:
        super().__init__(
            parent,
            bg=Colors.BACKGROUND,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
        )
        self.graph = graph
        self._config = config
        self._on_graph_changed = on_graph_changed
        self._on_status = on_status
        self._on_start_node_changed = on_start_node_changed
        self._weight_provider = weight_provider

        self._mode = EditorMode.MOVE_NODE
        self._start_node: int | None = None
        self._dragged_node: int | None = None
        self._hovered_node: int | None = None
        self._pending_edge_start: int | None = None
        self._pointer = (0.0, 0.0)

        self._visited: set[int] = set()
        self._current_node: int | None = None
        self._current_edge: tuple[int, int] | None = None
        self._traversed_edges: set[tuple[int, int]] = set()
        self._traversal_order: tuple[int, ...] = ()
        self._edge_progress = 0.0
        self._pulse_progress = 0.0

        self._context_node: int | None = None
        self._context_menu = self._create_context_menu()
        self._bind_events()

    @property
    def start_node(self) -> int | None:
        """Return the selected traversal start node."""
        return self._start_node

    def set_editor_mode(self, mode: EditorMode) -> None:
        """Switch mouse interaction mode."""
        self._mode = mode
        self._dragged_node = None
        self._pending_edge_start = None
        cursor = "fleur" if mode is EditorMode.MOVE_NODE else "crosshair"
        self.configure(cursor=cursor)
        self.redraw()

    def set_start_node(self, node_id: int | None) -> None:
        """Set or clear the traversal start node."""
        if node_id is not None and node_id not in self.graph:
            raise ValueError(f"Node {node_id} does not exist.")
        self._start_node = node_id
        self._on_start_node_changed(node_id)
        self.redraw()

    def ensure_start_node(self) -> int | None:
        """Select the lowest node identifier when no valid start exists."""
        if self._start_node in self.graph:
            return self._start_node
        nodes = self.graph.nodes
        self.set_start_node(nodes[0].node_id if nodes else None)
        return self._start_node

    def clear_visual_state(self) -> None:
        """Clear traversal highlights without changing the graph."""
        self._visited.clear()
        self._current_node = None
        self._current_edge = None
        self._traversed_edges.clear()
        self._traversal_order = ()
        self._edge_progress = 0.0
        self._pulse_progress = 0.0
        self.redraw()

    def set_visual_state(
        self,
        *,
        visited: Collection[int],
        current_node: int | None,
        current_edge: tuple[int, int] | None,
        traversed_edges: Collection[tuple[int, int]],
        traversal_order: Sequence[int],
        edge_progress: float,
        pulse_progress: float,
    ) -> None:
        """Update animation highlights and redraw the graph."""
        self._visited = set(visited)
        self._current_node = current_node
        self._current_edge = current_edge
        self._traversed_edges = {
            tuple(sorted(edge)) for edge in traversed_edges
        }
        self._traversal_order = tuple(traversal_order)
        self._edge_progress = clamp(edge_progress, 0.0, 1.0)
        self._pulse_progress = clamp(pulse_progress, 0.0, 1.0)
        self.redraw()

    def redraw(self) -> None:
        """Redraw all graph and animation elements."""
        self.delete("all")
        self._draw_grid()
        if self.graph.node_count == 0:
            self._draw_empty_state()
            return

        for edge in self.graph.edges:
            self._draw_edge(edge)
        self._draw_current_edge()
        self._draw_pending_edge()

        order_indexes = {
            node_id: index + 1
            for index, node_id in enumerate(self._traversal_order)
        }
        for node in self.graph.nodes:
            self._draw_node(node.node_id, order_indexes.get(node.node_id))

        self._draw_canvas_legend()

    def _bind_events(self) -> None:
        self.bind("<Configure>", lambda _event: self.redraw())
        self.bind("<ButtonPress-1>", self._on_left_press)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Button-3>", self._on_right_click)

    def _on_left_press(self, event: tk.Event[tk.Misc]) -> None:
        node_id = self._node_at(event.x, event.y)
        self._pointer = (event.x, event.y)

        try:
            if self._mode is EditorMode.ADD_NODE:
                self._add_node(event.x, event.y, node_id)
            elif self._mode is EditorMode.MOVE_NODE:
                self._dragged_node = node_id
            elif self._mode is EditorMode.ADD_EDGE:
                self._handle_add_edge(node_id)
            elif self._mode is EditorMode.DELETE_NODE:
                self._delete_node(node_id)
            elif self._mode is EditorMode.DELETE_EDGE:
                self._delete_edge(event.x, event.y)
            elif self._mode is EditorMode.SET_START and node_id is not None:
                self.set_start_node(node_id)
                self._on_status(f"Start node set to {node_id}.")
        except (ValueError, tk.TclError) as exc:
            LOGGER.warning("Canvas edit failed: %s", exc)
            self._on_status(str(exc))
        self.redraw()

    def _on_left_drag(self, event: tk.Event[tk.Misc]) -> None:
        self._pointer = (event.x, event.y)
        if self._mode is EditorMode.MOVE_NODE and self._dragged_node is not None:
            x, y = self._to_normalized(event.x, event.y)
            self.graph.move_node(self._dragged_node, x, y)
            self._on_graph_changed()
        self.redraw()

    def _on_left_release(self, _event: tk.Event[tk.Misc]) -> None:
        if self._dragged_node is not None:
            self._on_status(f"Moved node {self._dragged_node}.")
        self._dragged_node = None

    def _on_motion(self, event: tk.Event[tk.Misc]) -> None:
        self._pointer = (event.x, event.y)
        hovered = self._node_at(event.x, event.y)
        if hovered != self._hovered_node or self._pending_edge_start is not None:
            self._hovered_node = hovered
            self.redraw()

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        self._hovered_node = None
        self.redraw()

    def _on_double_click(self, event: tk.Event[tk.Misc]) -> None:
        node_id = self._node_at(event.x, event.y)
        if node_id is not None:
            self.set_start_node(node_id)
            self._on_status(f"Start node set to {node_id}.")

    def _on_right_click(self, event: tk.Event[tk.Misc]) -> None:
        self._context_node = self._node_at(event.x, event.y)
        if self._context_node is None:
            return
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def _create_context_menu(self) -> tk.Menu:
        menu = tk.Menu(
            self,
            tearoff=False,
            bg=Colors.SURFACE_ALT,
            fg=Colors.TEXT,
            activebackground=Colors.PRIMARY,
            activeforeground=Colors.WHITE,
            bd=0,
        )
        menu.add_command(label="Set as start node", command=self._context_set_start)
        menu.add_command(label="Delete node", command=self._context_delete_node)
        return menu

    def _context_set_start(self) -> None:
        if self._context_node is not None and self._context_node in self.graph:
            self.set_start_node(self._context_node)
            self._on_status(f"Start node set to {self._context_node}.")

    def _context_delete_node(self) -> None:
        self._delete_node(self._context_node)
        self.redraw()

    def _add_node(self, x: float, y: float, occupied_node: int | None) -> None:
        if occupied_node is not None:
            self._on_status("That position is already occupied by a node.")
            return
        nearest = self._nearest_node_distance(x, y)
        min_spacing = self._config.canvas.node_radius * 2.5
        if nearest is not None and nearest < min_spacing:
            self._on_status("Place the new node farther from existing nodes.")
            return
        normalized_x, normalized_y = self._to_normalized(x, y)
        node_id = self.graph.add_node(normalized_x, normalized_y)
        if self._start_node is None:
            self.set_start_node(node_id)
        self._on_graph_changed()
        self._on_status(f"Added node {node_id}.")

    def _delete_node(self, node_id: int | None) -> None:
        if node_id is None:
            self._on_status("Select a node to delete.")
            return
        self.graph.remove_node(node_id)
        if self._start_node == node_id:
            self._start_node = None
            self.ensure_start_node()
        self._visited.discard(node_id)
        self._traversal_order = tuple(
            item for item in self._traversal_order if item != node_id
        )
        self._on_graph_changed()
        self._on_status(f"Deleted node {node_id}.")

    def _handle_add_edge(self, node_id: int | None) -> None:
        if node_id is None:
            self._pending_edge_start = None
            self._on_status("Select a node to begin an edge.")
            return
        if self._pending_edge_start is None:
            self._pending_edge_start = node_id
            self._on_status(f"Select a destination for node {node_id}.")
            return
        source = self._pending_edge_start
        self._pending_edge_start = None
        if source == node_id:
            self._on_status("Self-loops are not supported.")
            return
        weight = self._weight_provider()
        updated = self.graph.has_edge(source, node_id)
        self.graph.add_edge(source, node_id, weight)
        self._on_graph_changed()
        action = "Updated" if updated else "Added"
        self._on_status(
            f"{action} edge {source}–{node_id} with weight {weight:g}."
        )

    def _delete_edge(self, x: float, y: float) -> None:
        edge = self._edge_at(x, y)
        if edge is None:
            self._on_status("Select an edge to delete.")
            return
        self.graph.remove_edge(edge.source, edge.target)
        self._traversed_edges.discard(edge.key)
        self._on_graph_changed()
        self._on_status(f"Deleted edge {edge.source}–{edge.target}.")

    def _draw_grid(self) -> None:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        spacing = 36
        for x in range(0, width, spacing):
            self.create_line(x, 0, x, height, fill="#111A2B", width=1)
        for y in range(0, height, spacing):
            self.create_line(0, y, width, y, fill="#111A2B", width=1)

    def _draw_empty_state(self) -> None:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        self.create_text(
            width / 2,
            height / 2 - 18,
            text="No graph yet",
            fill=Colors.TEXT,
            font=(self._config.fonts.family, 18, "bold"),
        )
        self.create_text(
            width / 2,
            height / 2 + 18,
            text="Generate a graph or switch to Add Node mode.",
            fill=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 10),
        )

    def _draw_edge(self, edge: Edge) -> None:
        source_x, source_y = self._node_position(edge.source)
        target_x, target_y = self._node_position(edge.target)
        traversed = edge.key in self._traversed_edges
        color = Colors.EDGE_TRAVERSED if traversed else Colors.EDGE
        width = 3 if traversed else self._config.canvas.edge_width
        self.create_line(
            source_x,
            source_y,
            target_x,
            target_y,
            fill=color,
            width=width,
            capstyle=tk.ROUND,
        )

        midpoint_x = (source_x + target_x) / 2
        midpoint_y = (source_y + target_y) / 2
        label = (
            str(int(edge.weight))
            if float(edge.weight).is_integer()
            else f"{edge.weight:.1f}"
        )
        text_id = self.create_text(
            midpoint_x,
            midpoint_y,
            text=label,
            fill=Colors.TEXT,
            font=(self._config.fonts.mono_family, 8, "bold"),
        )
        bounds = self.bbox(text_id)
        if bounds is not None:
            rectangle = self.create_rectangle(
                bounds[0] - 4,
                bounds[1] - 2,
                bounds[2] + 4,
                bounds[3] + 2,
                fill=Colors.SURFACE_ALT,
                outline=Colors.BORDER,
                width=1,
            )
            self.tag_lower(rectangle, text_id)

    def _draw_current_edge(self) -> None:
        if self._current_edge is None:
            return
        source, target = self._current_edge
        if source not in self.graph or target not in self.graph:
            return
        source_x, source_y = self._node_position(source)
        target_x, target_y = self._node_position(target)
        progress = ease_in_out_cubic(self._edge_progress)
        animated_x = source_x + (target_x - source_x) * progress
        animated_y = source_y + (target_y - source_y) * progress
        self.create_line(
            source_x,
            source_y,
            animated_x,
            animated_y,
            fill=Colors.EDGE_CURRENT,
            width=self._config.canvas.highlighted_edge_width,
            capstyle=tk.ROUND,
        )
        self.create_oval(
            animated_x - 4,
            animated_y - 4,
            animated_x + 4,
            animated_y + 4,
            fill=Colors.WHITE,
            outline=Colors.EDGE_CURRENT,
            width=2,
        )

    def _draw_pending_edge(self) -> None:
        if self._pending_edge_start is None:
            return
        start_x, start_y = self._node_position(self._pending_edge_start)
        self.create_line(
            start_x,
            start_y,
            self._pointer[0],
            self._pointer[1],
            fill=Colors.PRIMARY,
            width=2,
            dash=(5, 4),
        )

    def _draw_node(self, node_id: int, order_index: int | None) -> None:
        x, y = self._node_position(node_id)
        radius = self._config.canvas.node_radius
        if node_id == self._current_node:
            pulse = math.sin(self._pulse_progress * math.pi)
            radius += int(5 * max(0.0, pulse))

        self.create_oval(
            x - radius + 3,
            y - radius + 5,
            x + radius + 3,
            y + radius + 5,
            fill=Colors.SHADOW,
            outline="",
        )

        fill = Colors.NODE
        outline = Colors.NODE_OUTLINE
        outline_width = self._config.canvas.node_outline_width
        if node_id in self._visited:
            fill = Colors.NODE_VISITED
            outline = Colors.SECONDARY
        if node_id == self._hovered_node:
            fill = Colors.NODE_HOVER if node_id not in self._visited else fill
            outline = Colors.WHITE
        if node_id == self._current_node:
            fill = Colors.NODE_CURRENT
            outline = Colors.WHITE
            outline_width = 3

        if node_id == self._start_node:
            self.create_oval(
                x - radius - 7,
                y - radius - 7,
                x + radius + 7,
                y + radius + 7,
                outline=Colors.NODE_START,
                width=2,
                dash=(5, 3),
            )

        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=outline_width,
        )
        self.create_text(
            x,
            y,
            text=str(node_id),
            fill=Colors.WHITE,
            font=(self._config.fonts.family, 11, "bold"),
        )

        if order_index is not None:
            badge_x = x + radius - 2
            badge_y = y - radius + 2
            self.create_oval(
                badge_x - 10,
                badge_y - 10,
                badge_x + 10,
                badge_y + 10,
                fill=Colors.SURFACE_ALT,
                outline=Colors.WHITE,
                width=1,
            )
            self.create_text(
                badge_x,
                badge_y,
                text=str(order_index),
                fill=Colors.WHITE,
                font=(self._config.fonts.mono_family, 7, "bold"),
            )

    def _draw_canvas_legend(self) -> None:
        width = max(self.winfo_width(), 1)
        self.create_text(
            width - 14,
            16,
            anchor="ne",
            text=f"Mode: {self._mode.name.replace('_', ' ').title()}",
            fill=Colors.TEXT_MUTED,
            font=(self._config.fonts.family, 9, "bold"),
        )

    def _node_at(self, x: float, y: float) -> int | None:
        radius = self._config.canvas.node_radius + self._config.canvas.hit_padding
        closest: tuple[float, int] | None = None
        for node in self.graph.nodes:
            node_x, node_y = self._node_position(node.node_id)
            current_distance = math.hypot(x - node_x, y - node_y)
            if current_distance <= radius and (
                closest is None or current_distance < closest[0]
            ):
                closest = (current_distance, node.node_id)
        return None if closest is None else closest[1]

    def _edge_at(self, x: float, y: float) -> Edge | None:
        threshold = 10.0
        closest: tuple[float, Edge] | None = None
        for edge in self.graph.edges:
            source_x, source_y = self._node_position(edge.source)
            target_x, target_y = self._node_position(edge.target)
            current_distance = point_segment_distance(
                x, y, source_x, source_y, target_x, target_y
            )
            if current_distance <= threshold and (
                closest is None or current_distance < closest[0]
            ):
                closest = (current_distance, edge)
        return None if closest is None else closest[1]

    def _nearest_node_distance(self, x: float, y: float) -> float | None:
        distances = []
        for node in self.graph.nodes:
            node_x, node_y = self._node_position(node.node_id)
            distances.append(math.hypot(x - node_x, y - node_y))
        return min(distances) if distances else None

    def _node_position(self, node_id: int) -> tuple[float, float]:
        node = self.graph.get_node(node_id)
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        padding = self._config.canvas.canvas_padding
        drawable_width = max(1, width - padding * 2)
        drawable_height = max(1, height - padding * 2)
        return (
            padding + node.x * drawable_width,
            padding + node.y * drawable_height,
        )

    def _to_normalized(self, x: float, y: float) -> tuple[float, float]:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        padding = self._config.canvas.canvas_padding
        drawable_width = max(1, width - padding * 2)
        drawable_height = max(1, height - padding * 2)
        return (
            clamp((x - padding) / drawable_width, 0.0, 1.0),
            clamp((y - padding) / drawable_height, 0.0, 1.0),
        )
