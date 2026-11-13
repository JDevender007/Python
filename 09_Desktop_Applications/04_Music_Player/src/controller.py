"""Music Player controller - connects view and model."""

from __future__ import annotations
import time
from pathlib import Path
from typing import Callable, Optional
from .model import Track, Playlist, PlayerState
from .ui.view import MusicView


def init_music_player(view: MusicView, root: tk.Tk) -> None:
    """Initialize the music player with view and model."""
    model = PlayerState()
    playlist = Playlist()
    
    # Wire up view
    view._model = model
    view._playlist = playlist
    
    # Set up initial state
    view._update_playback_buttons(paused=True)
    
    # Periodic update loop for time display
    _update_time_loop(root, view)


def _update_time_loop(root: tk.Tk, view: MusicView) -> None:
    """Periodically update the elapsed time display."""
    if PYGAME_AVAILABLE and pygame.mixer.music.get_busy():
        # Get current position
        try:
            pos = pygame.mixer.music.get_pos() / 1000  # ms to seconds
            track = view._get_current_track()
            if track and track.duration:
                view._update_time_display(pos, track.duration)
        except Exception:
            pass
    
    # Schedule next update (every 100ms)
    root.after(100, _update_time_loop, root, view)


def play_track(view: MusicView, track_path: str) -> None:
    """Play a track from the given path."""
    if PYGAME_AVAILABLE:
        try:
            pygame.mixer.music.load(track_path)
            pygame.mixer.music.play()
            # Update UI
            from pathlib import Path
            track = Path(track_path).name
            view._update_file_info(None)  # Would need Track object
            view._update_time_display(0, 0)
            view._update_playback_buttons(paused=False)
        except Exception as e:
            messagebox.showerror("Error", f"Could not play track: {e}")


def main() -> None:
    """Entry point for the Music Player application."""
    root = tk.Tk()
    root.title("Music Player - Python Portfolio")
    root.geometry("500x300")
    root.minsize(400, 250)
    
    # Create the view
    view = MusicView(root)
    view.pack(fill="both", expand=True)
    
    # Initialize the player
    init_music_player(view, root)
    
    root.mainloop()


if __name__ == "__main__":
    main()