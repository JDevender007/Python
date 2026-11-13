"""Music Player model - handles audio playback state and playlist management."""

from __future__ import annotations
import os
import json
import pathlib
from typing import Optional, List, Dict, Any
try:
    import pygame.mixer
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class Track:
    """Represents a single track in the playlist."""
    
    def __init__(self, filepath: pathlib.Path, title: Optional[str] = None, 
                 artist: Optional[str] = None, album: Optional[str] = None) -> None:
        self.filepath = pathlib.Path(filepath)
        self.title = title or self.filepath.stem
        self.artist = artist
        self.album = album
        self.duration: Optional[float] = None
        self.size: Optional[int] = None
        
        # Try to read metadata
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.load(str(self.filepath))
                self.duration = pygame.mixer.music.get_length()
            except Exception:
                pass
    
    def __repr__(self) -> str:
        return f"Track(title='{self.title}', artist='{self.artist}')"
    
    def get_path(self) -> str:
        """Get the full file path."""
        return str(self.filepath)


class Playlist:
    """Manages a list of tracks for playback."""
    
    def __init__(self) -> None:
        self.tracks: List[Track] = []
        self.current_index: int = -1
        self.save_file: Optional[pathlib.Path] = None
    
    def add(self, filepath: pathlib.Path) -> Optional[Track]:
        """Add a track to the playlist."""
        # Check if already in playlist
        for track in self.tracks:
            if track.filepath == filepath:
                return None  # Already exists
        
        track = Track(filepath)
        self.tracks.append(track)
        
        # If this is the first track, set as current
        if len(self.tracks) == 1:
            self.current_index = 0
        
        return track
    
    def remove(self, index: int) -> Optional[Track]:
        """Remove a track at the given index."""
        if 0 <= index < len(self.tracks):
            removed = self.tracks.pop(index)
            # Adjust current index if needed
            if self.current_index >= len(self.tracks):
                self.current_index = len(self.tracks) - 1
            elif self.current_index == index:
                self.current_index = max(0, index - 1)
            return removed
        return None
    
    def clear(self) -> None:
        """Clear the entire playlist."""
        self.tracks = []
        self.current_index = -1
    
    def next(self) -> Optional[Track]:
        """Get the next track, wrapping around."""
        if not self.tracks:
            return None
        self.current_index = (self.current_index + 1) % len(self.tracks)
        return self.tracks[self.current_index]
    
    def previous(self) -> Optional[Track]:
        """Get the previous track, wrapping around."""
        if not self.tracks:
            return None
        self.current_index = (self.current_index - 1) % len(self.tracks)
        return self.tracks[self.current_index]
    
    def move_to(self, index: int) -> Optional[Track]:
        """Move to track at given index."""
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.tracks[index]
        return None
    
    def get_current(self) -> Optional[Track]:
        """Get the currently playing track."""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None
    
    def get_count(self) -> int:
        """Get the number of tracks in the playlist."""
        return len(self.tracks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert playlist to dictionary for serialization."""
        return {
            "tracks": [
                {
                    "filepath": str(t.filepath),
                    "title": t.title,
                    "artist": t.artist,
                    "album": t.album,
                    "duration": t.duration,
                }
                for t in self.tracks
            ],
            "current_index": self.current_index,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Playlist":
        """Create playlist from dictionary."""
        playlist = cls()
        for track_data in data.get("tracks", []):
            filepath = pathlib.Path(track_data["filepath"])
            track = Track(filepath, 
                         title=track_data.get("title"),
                         artist=track_data.get("artist"),
                         album=track_data.get("album"))
            playlist.tracks.append(track)
        
        playlist.current_index = data.get("current_index", -1)
        return playlist


class PlayerState:
    """Manages the playback state."""
    
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    
    def __init__(self) -> None:
        self.state: str = self.STOPPED
        self.volume: float = 0.5
        self.elapsed: float = 0.0
        self.total_duration: float = 0.0
    
    def play(self) -> None:
        """Start or resume playback."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.play()
        self.state = self.PLAYING
        self.elapsed = 0.0
    
    def pause(self) -> None:
        """Pause playback."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.pause()
        self.state = self.PAUSED
    
    def resume(self) -> None:
        """Resume playback from paused state."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.unpause()
        self.state = self.PLAYING
    
    def stop(self) -> None:
        """Stop playback."""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
        self.state = self.STOPPED
        self.elapsed = 0.0
    
    def set_volume(self, volume: float) -> None:
        """Set volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))
        if PYGAME_AVAILABLE:
            pygame.mixer.music.set_volume(self.volume)
    
    def toggle(self) -> None:
        """Toggle between play and pause."""
        if self.state == self.PLAYING:
            self.pause()
        elif self.state == self.PAUSED:
            self.resume()
        elif self.state == self.STOPPED:
            self.play()
    
    def update_elapsed(self, dt: float) -> None:
        """Update elapsed time (call periodically)."""
        self.elapsed += dt