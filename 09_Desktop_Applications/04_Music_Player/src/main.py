"""Music Player - A desktop music player built with Tkinter and pygame."""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Import music player components
from src.model import PlayerState, Playlist, Track
from src.ui.view import MusicView
from src.controller import init_music_player, play_track


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