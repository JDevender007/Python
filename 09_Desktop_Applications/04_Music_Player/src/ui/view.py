"""Music Player view - the graphical user interface."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional
from pathlib import Path

try:
    import pygame
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class MusicView(ttk.Frame):
    """The music player's graphical user interface."""
    
    def __init__(self, master: tk.Tk, **kwargs: any) -> None:
        super().__init__(master, **kwargs)
        self.master = master
        self.pygame_available = PYGAME_AVAILABLE
        self._create_widgets()
        self._setup_layout()
        self._setup_bindings()
    
    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        # Menu bar
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)
        
        # File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="Open File", accelerator="Ctrl+O", command=self._on_open_file)
        self.file_menu.add_command(label="Open Folder", accelerator="Ctrl+F", command=self._on_open_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_exit)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        
        # Playback menu
        self.playback_menu = tk.Menu(self.menubar, tearoff=0)
        self.playback_menu.add_command(label="Play", accelerator="Ctrl+P", command=self._on_play)
        self.playback_menu.add_command(label="Pause", accelerator="Ctrl+Shift+P", command=self._on_pause)
        self.playback_menu.add_command(label="Stop", accelerator="Ctrl+S", command=self._on_stop)
        self.playback_menu.add_separator()
        self.playback_menu.add_command(label="Next", accelerator="Ctrl+N", command=self._on_next)
        self.playback_menu.add_command(label="Previous", accelerator="Ctrl+B", command=self._on_previous)
        self.playback_menu.add_separator()
        self.playback_menu.add_command(label="Shuffle", command=self._on_shuffle)
        self.playback_menu.add_command(label="Repeat", command=self._on_repeat)
        self.menubar.add_cascade(label="Playback", menu=self.playback_menu)
        
        # Volume menu
        self.volume_menu = tk.Menu(self.menubar, tearoff=0)
        self.volume_var = tk.DoubleVar(value=0.5)
        self.volume_menu.add_scale(
            variable=self.volume_var,
            from_=0.0, to=1.0, resolution=0.1,
            label="Volume", command=self._on_volume_change
        )
        self.menubar.add_cascade(label="Volume", menu=self.volume_menu)
        
        # Playlist area
        self.playlist_frame = ttk.LabelFrame(self, text="Playlist")
        self.playlist_listbox = tk.Listbox(self.playlist_frame, selectmode="single", height=8)
        self.playlist_scrollbar = ttk.Scrollbar(self.playlist_frame, orient="vertical", 
                                                  command=self.playlist_listbox.yview)
        self.playlist_listbox.config(yscrollcommand=self.playlist_scrollbar.set)
        
        # Control frame
        self.control_frame = ttk.Frame(self)
        
        # Buttons
        self.btn_play = ttk.Button(self.control_frame, text="Play", command=self._on_play)
        self.btn_pause = ttk.Button(self.control_frame, text="Pause", command=self._on_pause, state="disabled")
        self.btn_stop = ttk.Button(self.control_frame, text="Stop", command=self._on_stop)
        self.btn_next = ttk.Button(self.control_frame, text="Next", command=self._on_next)
        self.btn_prev = ttk.Button(self.control_frame, text="Previous", command=self._on_previous)
        
        # Status display
        self.status_label = ttk.Label(self, text="No file loaded", anchor="w")
        self.time_label = ttk.Label(self, text="0:00 / 0:00", anchor="w")
        
        # File info
        self.file_info_label = ttk.Label(self, text="", anchor="w")
    
    def _setup_layout(self) -> None:
        """Set up the layout manager."""
        # Configure grid weights
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        
        # Pack menu bar
        self.menubar.pack(side="top", fill="x")
        
        # Playlist frame
        self.playlist_frame.pack(side="top", fill="x", padx=5, pady=2)
        self.playlist_listbox.pack(side="left", fill="x", expand=True)
        self.playlist_scrollbar.pack(side="right", fill="y")
        
        # Control frame
        self.control_frame.pack(side="top", fill="x", padx=5, pady=2)
        
        # Buttons in control frame
        self.btn_prev.pack(side="left", padx=2)
        self.btn_prev.config(state="disabled" if not self.pygame_available else "normal")
        self.btn_play.pack(side="left", padx=2)
        self.btn_pause.pack(side="left", padx=2)
        self.btn_stop.pack(side="left", padx=2)
        self.btn_next.pack(side="left", padx=2)
        
        # Status area
        self.status_label.pack(side="left", fill="x", expand=True, padx=5)
        self.time_label.pack(side="right", padx=5)
        self.file_info_label.pack(side="bottom", fill="x", padx=5, pady=2)
    
    def _setup_bindings(self) -> None:
        """Set up keyboard and mouse bindings."""
        # Keyboard shortcuts
        self.master.bind("<Control-o>", lambda e: self._on_open_file())
        self.master.bind("<Control-f>", lambda e: self._on_open_folder())
        self.master.bind("<Alt-F4>", lambda e: self._on_exit())
        self.master.bind("<Control-p>", lambda e: self._on_play())
        self.master.bind("<Key-n>", lambda e: self._on_next())
        self.master.bind("<Key-b>", lambda e: self._on_previous())
    
    # --- Event handlers ---
    
    def _on_open_file(self) -> None:
        """Open single audio file."""
        filepath = filedialog.askopenfilename(
            filetypes=self._get_audio_filetypes()
        )
        if filepath:
            self._add_to_playlist(Path(filepath))
    
    def _on_open_folder(self) -> None:
        """Open music folder."""
        folder = filedialog.askdirectory()
        if folder:
            self._load_folder(Path(folder))
    
    def _on_exit(self) -> None:
        """Exit application."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        self.master.destroy()
    
    def _on_play(self) -> None:
        """Play/pause toggle."""
        if PYGAME_AVAILABLE:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                self._update_playback_buttons(paused=True)
            else:
                # Get current track
                track = self._get_current_track()
                if track and self._try_load_track(track):
                    pygame.mixer.music.play()
                    self._update_playback_buttons(paused=False)
        else:
            messagebox.showinfo("Info", "Pygame mixer not available for playback")
    
    def _on_pause(self) -> None:
        """Pause playback."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.pause()
            self._update_playback_buttons(paused=True)
    
    def _on_stop(self) -> None:
        """Stop playback."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
            self._update_playback_buttons(paused=False)
    
    def _on_next(self) -> None:
        """Play next track."""
        # In a real app, get from playlist controller
        messagebox.showinfo("Info", "Next track - playlist control coming soon")
    
    def _on_previous(self) -> None:
        """Play previous track."""
        messagebox.showinfo("Info", "Previous track - playlist control coming soon")
    
    def _on_shuffle(self) -> None:
        """Toggle shuffle."""
        messagebox.showinfo("Info", "Shuffle - feature coming soon")
    
    def _on_repeat(self) -> None:
        """Toggle repeat."""
        messagebox.showinfo("Info", "Repeat - feature coming soon")
    
    def _on_volume_change(self, value: float) -> None:
        """Handle volume change."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.set_volume(value)
    
    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Handle canvas resize."""
        pass
    
    # --- Public API ---
    
    def set_playlist(self, tracks: list) -> None:
        """Set the playlist."""
        self.playlist_listbox.delete(0, tk.END)
        for track in tracks:
            display_text = f"{track.title}"
            if track.artist:
                display_text += f" - {track.artist}"
            self.playlist_listbox.insert(tk.END, display_text)
    
    def select_track(self, index: int) -> None:
        """Select a track in the playlist."""
        if 0 <= index < self.playlist_listbox.size():
            self.playlist_listbox.selection_clear(0, tk.END)
            self.playlist_listbox.selection_set(index)
            self.playlist_listbox.activate(index)
    
    def get_selected_track_index(self) -> Optional[int]:
        """Get the selected track index."""
        try:
            return self.playlist_listbox.curselection()[0]
        except IndexError:
            return None
    
    def _get_audio_filetypes(self) -> list:
        """Get audio file type filters."""
        if PYGAME_AVAILABLE:
            return [
                ("Audio files", "*.mp3;*.wav;*.ogg;*.flac;*.m4a"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("All files", "*.*"),
            ]
        return [("All files", "*.*")]
    
    def _add_to_playlist(self, filepath: Path) -> None:
        """Add a file to the playlist and play it."""
        track = self._model.add(filepath)
        if track:
            self.playlist_listbox.insert(tk.END, f"{track.title}")
            self._select_last_track()
            if PYGAME_AVAILABLE:
                self._try_load_and_play(track)
    
    def _load_folder(self, folder: Path) -> None:
        """Load all audio files from a folder."""
        extensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a']
        files = sorted(folder.glob("*.*"))
        audio_files = [f for f in files if f.suffix.lower() in extensions]
        
        for filepath in audio_files:
            self._add_to_playlist(filepath)
        
        if audio_files:
            self._select_last_track()
            if PYGAME_AVAILABLE:
                first_track = self._model.tracks[0] if self._model.tracks else None
                if first_track:
                    self._try_load_and_play(first_track)
    
    def _try_load_and_play(self, track: Track) -> None:
        """Try to load and play a track."""
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.load(str(track.filepath))
                pygame.mixer.music.play()
                self._update_playback_buttons(paused=False)
                self._update_file_info(track)
                self._update_time_display(0, track.duration or 0)
            except Exception as e:
                messagebox.showerror("Error", f"Could not play file: {e}")
    
    def _select_last_track(self) -> None:
        """Select the last item in the playlist."""
        idx = self.playlist_listbox.size() - 1
        if idx >= 0:
            self.playlist_listbox.selection_set(idx)
            self.playlist_listbox.activate(idx)
    
    def _get_current_track(self) -> Optional[Track]:
        """Get the currently selected track."""
        idx = self.get_selected_track_index()
        if idx is not None and idx < len(self._model.tracks):
            return self._model.tracks[idx]
        return None
    
    def _update_playback_buttons(self, paused: bool) -> None:
        """Update play/pause button states."""
        if hasattr(self, 'btn_play') and hasattr(self, 'btn_pause'):
            self.btn_play.config(state="normal")
            self.btn_pause.config(state="normal")
            if paused:
                self.btn_play.config(state="disabled")
            else:
                self.btn_pause.config(state="disabled")
    
    def _update_file_info(self, track: Track) -> None:
        """Update the file info label."""
        info = f"Now playing: {track.title}"
        if track.artist:
            info += f" - {track.artist}"
        if track.album:
            info += f" ({track.album})"
        self.file_info_label.config(text=info)
    
    def _update_time_display(self, elapsed: float, total: float) -> None:
        """Update the time display."""
        def format_time(t: float) -> str:
            minutes = int(t // 60)
            seconds = int(t % 60)
            return f"{minutes}:{seconds:02d}"
        
        self.time_label.config(text=f"{format_time(elapsed)} / {format_time(total)}")
    
    def set_model(self, model) -> None:
        """Set the model reference."""
        self._model = model
        # Update playlist view
        if self._model and self._model.tracks:
            self.to_dict_playlist()
    
    def _on_shuffle(self) -> None:
        """Toggle shuffle playback."""
        messagebox.showinfo("Shuffle", "Shuffle feature coming soon")
    
    def _on_repeat(self) -> None:
        """Toggle repeat playback."""
        messagebox.showinfo("Repeat", "Repeat feature coming soon")