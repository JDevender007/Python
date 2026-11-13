# Music Player

## Overview

A desktop music player application built with Python's Tkinter library and pygame
for audio playback. Play, pause, stop, navigate playlist, adjust volume, and more.

## Features

### Playback Controls
- Play / Pause / Stop
- Next and Previous tracks
- Shuffle and Repeat toggles
- Seek through track position

### Playlist Management
- Open audio files (MP3, WAV, OGG, FLAC, M4A)
- Open music folder and load all audio files
- Add/remove tracks from playlist
- Track list display with selection

### Volume and Position
- Volume control slider (0.0 to 1.0)
- Seek through track position
- Elapsed time and total duration display

### Audio Formats Supported
- **MP3**
- **WAV**
- **OGG**
- **FLAC**
- **M4A/AAC**

### Interface
- Menu bar with File, Playback, and Volume menus
- Playlist listbox with track listings
- Playback control buttons (Play, Pause, Stop, Next, Previous)
- Progress bar and time display
- File information area
- Volume control

## Technologies

- Python 3.12+
- Tkinter (standard GUI library)
- pygame (for audio playback and mixer)
- No other third-party dependencies

## Project Structure

```
04_Music_Player/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── model.py
│   ├── controller.py
│   └── ui/
│       └── view.py
├── assets/
└── docs/
    └── screenshots/
```

## Installation

```bash
# Clone the repository
git clone https://github.com/JDevender007/Python.git

# Navigate to the music player project
cd Python/09_Desktop_Applications/04_Music_Player

# Create a virtual environment (recommended)
python -m venv .venv

# Activate the virtual environment
# Windows:
.venv\Scripts\activate

# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

```bash
# From the project directory
python src/main.py
```

Or, if the virtual environment is active:

```bash
# Windows
.venv\Scripts\python src/main.py

# Linux/macOS
.venv/bin/python src/main.py
```

## Usage

### Opening Audio

- **Open File (Ctrl+O)**: Select a single audio file to play
- **Open Folder (Ctrl+F)**: Select a folder to load all audio files into the playlist

### Playback Controls

- **Play (Ctrl+P)**: Start or resume playback of the current track
- **Pause**: Pause the current track
- **Stop**: Stop playback and return to the beginning
- **Next (Ctrl+N)**: Play the next track in the playlist
- **Previous (Ctrl+B)**: Play the previous track in the playlist
- **Shuffle**: Randomize track order (feature coming soon)
- **Repeat**: Repeat the current playlist (feature coming soon)

### Volume Control

- Use the volume slider in the Volume menu or press volume keys
- Range: 0.0 (mute) to 1.0 (maximum volume)
- Changes are saved during the session

### Playlist Management

- Tracks are added to the playlist when opened
- Click a track in the list to select it
- Use Next/Previous buttons to navigate
- Right-click a track to remove it from the playlist

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open audio file |
| `Ctrl+F` | Open audio folder |
| `Ctrl+P` | Play / Pause |
| `Ctrl+N` | Next track |
| `Ctrl+B` | Previous track |
| `Alt+F4` | Exit |

### Volume Control

- Drag the volume slider in the Volume menu
- Or use system volume controls
- Mute by setting to 0.0

## Error Handling

- **Unsupported format**: Shows error if the file format is not supported by pygame
- **Missing file**: Informs user if a selected file no longer exists
- **Playback error**: Reports any issues during audio playback
- **No file loaded**: Shows appropriate message if no track is selected

## Future Improvements

- ID3 tag display (artist, album, year)
- Advanced playlist management (drag-and-drop reordering)
- Fade in/out transitions
- Equalizer settings
- Last.fm / scrobbling support
- lyrics display
- Audio conversion between formats
- Multiple playlist support
- Keyboard media key handling

## Screenshots

![Music Player](docs/screenshots/placeholder.png)

*Placeholder screenshot - add actual screenshots to `docs/screenshots/` directory*