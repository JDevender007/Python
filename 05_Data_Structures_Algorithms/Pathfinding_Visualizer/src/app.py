"""Application entry point for the Pathfinding Visualizer."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from types import TracebackType

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms import ALGORITHMS, SearchResult
from src.colors import COLORS
from src.config import CONFIG, AppConfig
from src.controls import ControlPanel
from src.grid import GridModel
from src.logger import get_logger
from src.utils import format_duration
from src.visualizer import AnimationPhase, GridVisualizer


class PathfindingApp(tk.Tk):
    """Main window coordinating controls, grid state, and visualization."""

    def __init__(self, config: AppConfig = CONFIG) -> None:
        super().__init__()
        self.config_data = config
        self.logger = get_logger(__name__)
        self._fullscreen = False
        self._active_result: SearchResult | None = None
        self._resize_after_id: str | None = None
        self._pending_columns = config.default_columns

        self.title(config.title)
        self.geometry(f"{config.initial_width}x{config.initial_height}")
        self.minsize(config.minimum_width, config.minimum_height)
        self.configure(background=COLORS.background)
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.report_callback_exception = self._handle_tk_exception

        rows = self._rows_for_columns(config.default_columns)
        self.grid_model = GridModel(rows=rows, columns=config.default_columns)
        self.grid_model.ensure_default_endpoints()

        self._build_layout()
        self._bind_shortcuts()
        self._update_grid_stat()
        self.after_idle(self.visualizer.redraw)
        self.logger.info(
            "Application initialized with a %sx%s grid.",
            config.default_columns,
            rows,
        )

    def _build_layout(self) -> None:
        shell = tk.Frame(self, background=COLORS.background)
        shell.pack(
            fill=tk.BOTH,
            expand=True,
            padx=self.config_data.window_padding,
            pady=self.config_data.window_padding,
        )

        self.controls = ControlPanel(
            shell,
            config=self.config_data,
            on_start=self.start_visualization,
            on_pause=self.pause_visualization,
            on_resume=self.resume_visualization,
            on_stop=self.stop_visualization,
            on_clear_path=self.clear_path,
            on_clear_grid=self.clear_grid,
            on_reset=self.reset_grid,
            on_maze=self.generate_maze,
            on_grid_size=self.request_grid_resize,
        )
        self.controls.pack(side=tk.LEFT, fill=tk.Y)

        workspace = tk.Frame(shell, background=COLORS.background)
        workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 0))

        heading = tk.Frame(workspace, background=COLORS.background)
        heading.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            heading,
            text="Interactive Grid",
            background=COLORS.background,
            foreground=COLORS.text,
            font=("TkDefaultFont", 16, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            heading,
            text="Space start  •  P pause  •  R resume  •  F11 fullscreen",
            background=COLORS.background,
            foreground=COLORS.muted_text,
            font=("TkDefaultFont", 9),
        ).pack(side=tk.RIGHT)

        self.visualizer = GridVisualizer(
            workspace,
            model=self.grid_model,
            on_grid_changed=self._on_grid_edited,
        )
        self.visualizer.pack(fill=tk.BOTH, expand=True)

    def _bind_shortcuts(self) -> None:
        self.bind_all(
            "<space>",
            lambda _event: self._shortcut(self.start_visualization),
        )
        for key in ("p", "P"):
            self.bind_all(
                f"<KeyPress-{key}>",
                lambda _event: self._shortcut(self.pause_visualization),
            )
        for key in ("r", "R"):
            self.bind_all(
                f"<KeyPress-{key}>",
                lambda _event: self._shortcut(self.resume_visualization),
            )
        for key in ("s", "S"):
            self.bind_all(
                f"<KeyPress-{key}>",
                lambda _event: self._shortcut(self.stop_visualization),
            )
        self.bind_all("<KeyPress-c>", lambda _event: self._shortcut(self.clear_grid))
        self.bind_all("<KeyPress-C>", lambda _event: self._shortcut(self.clear_grid))
        self.bind_all("<KeyPress-m>", lambda _event: self._shortcut(self.generate_maze))
        self.bind_all("<KeyPress-M>", lambda _event: self._shortcut(self.generate_maze))
        self.bind_all("<F11>", lambda _event: self._shortcut(self.toggle_fullscreen))
        self.bind_all("<Escape>", lambda _event: self._shortcut(self.close_application))

    @staticmethod
    def _shortcut(action: object) -> str:
        if callable(action):
            action()
        return "break"

    def start_visualization(self) -> None:
        """Run the selected algorithm and begin result animation."""
        if self.visualizer.is_animating:
            return
        start = self.grid_model.start_node
        end = self.grid_model.end_node
        if start is None or end is None:
            self.controls.update_statistics(
                status="Place both start and end nodes",
                fps=0.0,
            )
            return

        algorithm_name = self.controls.selected_algorithm
        algorithm = ALGORITHMS[algorithm_name]
        self.grid_model.clear_search()
        self.visualizer.redraw()

        try:
            result = algorithm(self.grid_model, start, end)
        except Exception as exc:
            self.logger.exception("Algorithm execution failed: %s", algorithm_name)
            self.controls.update_statistics(status="Error")
            messagebox.showerror(
                "Visualization Error",
                f"The selected algorithm could not be executed.\n\n{exc}",
                parent=self,
            )
            return

        self._active_result = result
        self.controls.update_statistics(
            algorithm=algorithm_name,
            visited=0,
            path_length=0,
            execution_time=format_duration(result.execution_time_ms),
            status="Searching",
            fps=0.0,
        )
        self.controls.set_animation_state("running")
        self.visualizer.start_animation(
            result=result,
            delay_supplier=lambda: self.controls.animation_delay_ms,
            on_progress=self._on_animation_progress,
            on_complete=self._on_animation_complete,
            on_fps=lambda fps: self.controls.update_statistics(fps=fps),
        )
        self.logger.info(
            "%s completed computation: visited=%s, path_nodes=%s, time=%.3f ms",
            algorithm_name,
            len(result.visited_order),
            len(result.path),
            result.execution_time_ms,
        )

    def pause_visualization(self) -> None:
        """Pause the active animation."""
        if self.visualizer.pause_animation():
            self.controls.set_animation_state("paused")
            self.controls.update_statistics(status="Paused")

    def resume_visualization(self) -> None:
        """Resume a paused animation."""
        if self.visualizer.resume_animation():
            self.controls.set_animation_state("running")
            self.controls.update_statistics(status="Searching")

    def stop_visualization(self) -> None:
        """Stop the active animation without clearing its current frame."""
        if self.visualizer.stop_animation():
            self.controls.set_animation_state("ready")
            self.controls.update_statistics(status="Stopped", fps=0.0)

    def clear_path(self) -> None:
        """Remove visited/path colors while preserving the current grid."""
        self.visualizer.stop_animation(notify=False)
        self.grid_model.clear_search()
        self.visualizer.redraw()
        self._active_result = None
        self.controls.set_animation_state("ready")
        self.controls.update_statistics(
            visited=0,
            path_length=0,
            execution_time="0.00 ms",
            status="Path cleared",
            fps=0.0,
        )

    def clear_grid(self) -> None:
        """Clear endpoints, walls, and search state."""
        self.visualizer.stop_animation(notify=False)
        self.grid_model.clear_all()
        self.visualizer.redraw()
        self._active_result = None
        self.controls.set_animation_state("ready")
        self.controls.update_statistics(
            visited=0,
            path_length=0,
            execution_time="0.00 ms",
            status="Grid cleared",
            fps=0.0,
        )

    def reset_grid(self) -> None:
        """Reset the grid and restore default endpoint positions."""
        self.clear_grid()
        self.grid_model.ensure_default_endpoints()
        self.visualizer.redraw()
        self.controls.update_statistics(status="Reset complete")

    def generate_maze(self) -> None:
        """Generate a random maze with a guaranteed valid route."""
        self.visualizer.stop_animation(notify=False)
        try:
            self.grid_model.generate_random_maze(self.config_data.maze_density)
        except ValueError as exc:
            self.logger.exception("Maze generation failed.")
            messagebox.showerror("Maze Error", str(exc), parent=self)
            return
        self.visualizer.redraw()
        self._active_result = None
        self.controls.set_animation_state("ready")
        self.controls.update_statistics(
            visited=0,
            path_length=0,
            execution_time="0.00 ms",
            status="Random maze generated",
            fps=0.0,
        )

    def request_grid_resize(self, columns: int) -> None:
        """Debounce slider changes before replacing the grid."""
        self._pending_columns = columns
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(100, self._apply_grid_resize)

    def _apply_grid_resize(self) -> None:
        self._resize_after_id = None
        columns = self._pending_columns
        rows = self._rows_for_columns(columns)
        self.visualizer.stop_animation(notify=False)
        self.visualizer.resize_grid(rows=rows, columns=columns)
        self.grid_model.ensure_default_endpoints()
        self.visualizer.redraw()
        self._active_result = None
        self.controls.set_animation_state("ready")
        self.controls.update_statistics(
            visited=0,
            path_length=0,
            execution_time="0.00 ms",
            status="Grid resized",
            fps=0.0,
        )
        self._update_grid_stat()
        self.logger.info("Grid resized to %sx%s.", columns, rows)

    def toggle_fullscreen(self) -> None:
        """Toggle native fullscreen mode."""
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)
        self.controls.update_statistics(
            status="Fullscreen" if self._fullscreen else "Windowed"
        )

    def close_application(self) -> None:
        """Stop scheduled work and close the application."""
        self.visualizer.stop_animation(notify=False)
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        self.logger.info("Application closed.")
        self.destroy()

    def _on_animation_progress(
        self,
        phase: AnimationPhase,
        visited_count: int,
        path_node_count: int,
    ) -> None:
        status = "Rendering shortest path" if phase == "path" else "Searching"
        self.controls.update_statistics(
            visited=visited_count,
            path_length=max(0, path_node_count - 1),
            status=status,
        )

    def _on_animation_complete(self, completed: bool) -> None:
        self.controls.set_animation_state("ready")
        if not completed:
            self.controls.update_statistics(status="Stopped", fps=0.0)
            return
        result = self._active_result
        if result is None:
            self.controls.update_statistics(status="Ready", fps=0.0)
            return
        self.controls.update_statistics(
            visited=len(result.visited_order),
            path_length=max(0, len(result.path) - 1),
            status="Path found" if result.found else "No path found",
        )

    def _on_grid_edited(self) -> None:
        self._active_result = None
        self.controls.update_statistics(
            visited=0,
            path_length=0,
            execution_time="0.00 ms",
            status="Grid edited",
            fps=0.0,
        )

    def _update_grid_stat(self) -> None:
        self.controls.update_statistics(
            grid_size=f"{self.grid_model.columns} × {self.grid_model.rows}"
        )

    def _rows_for_columns(self, columns: int) -> int:
        return max(10, round(columns * self.config_data.row_ratio))

    def _handle_tk_exception(
        self,
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        self.logger.error(
            "Unhandled Tkinter callback exception.",
            exc_info=(exception_type, exception, traceback),
        )
        messagebox.showerror(
            "Unexpected Error",
            "An unexpected error occurred. Details were written to the log file.",
            parent=self,
        )


def main() -> None:
    """Launch the desktop application."""
    app = PathfindingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
