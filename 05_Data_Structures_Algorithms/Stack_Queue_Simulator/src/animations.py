"""Frame-scheduled animation utilities for Tkinter widgets."""

from __future__ import annotations

import time
import tkinter as tk
from collections.abc import Callable

from .logger import get_logger
from .utils import clamp, ease_in_out_cubic


ProgressCallback = Callable[[float], None]
CompletionCallback = Callable[[], None]


class AnimationManager:
    """Run one smooth, cancellable animation at a configured frame rate."""

    def __init__(self, widget: tk.Misc, fps: int = 60) -> None:
        if fps <= 0:
            raise ValueError("FPS must be greater than zero.")
        self._widget = widget
        self._frame_interval_ms = max(1, round(1000 / fps))
        self._after_id: str | None = None
        self._generation = 0
        self._logger = get_logger("animations")

    @property
    def is_running(self) -> bool:
        """Return whether an animation currently has a scheduled frame."""

        return self._after_id is not None

    def cancel(self) -> None:
        """Cancel the current animation without invoking completion."""

        self._generation += 1
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            finally:
                self._after_id = None

    def animate(
        self,
        duration_ms: int,
        on_progress: ProgressCallback,
        on_complete: CompletionCallback | None = None,
    ) -> None:
        """Animate from progress 0.0 to 1.0 using cubic easing."""

        self.cancel()
        self._generation += 1
        generation = self._generation
        duration_seconds = max(0, duration_ms) / 1000
        started_at = time.perf_counter()

        if duration_seconds == 0:
            on_progress(1.0)
            if on_complete is not None:
                on_complete()
            return

        def frame() -> None:
            if generation != self._generation:
                return

            try:
                elapsed = time.perf_counter() - started_at
                raw_progress = clamp(elapsed / duration_seconds, 0.0, 1.0)
                eased_progress = ease_in_out_cubic(raw_progress)
                on_progress(eased_progress)

                if raw_progress >= 1.0:
                    self._after_id = None
                    if on_complete is not None:
                        on_complete()
                    return

                self._after_id = self._widget.after(
                    self._frame_interval_ms,
                    frame,
                )
            except (tk.TclError, RuntimeError):
                self._after_id = None
                self._logger.debug("Animation stopped because the widget closed.")
            except Exception:
                self._after_id = None
                self._logger.exception("Animation frame failed.")
                raise

        frame()
