# Image Viewer

## Overview

A desktop image viewer application built with Python's Tkinter library and Pillow
for image processing. View, zoom, rotate, and flip images in common formats.

## Features

### Image Operations
- Open image files and image folders
- Navigate: First, Previous, Next, Last
- Zoom In and Zoom Out
- Fit to Window and Actual Size
- Rotate Clockwise and Counter-Clockwise
- Flip Horizontal and Flip Vertical
- Undo last image operation

### Image Information
- Display image metadata (dimensions, format, mode, file size)
- Megapixels calculation
- Aspect ratio display
- Real-time info panel

### Interface
- Menu bar with File, Navigation, Transform, and Help menus
- Toolbar with quick-access buttons
- Image canvas with scrollbars
- Image info panel
- Thumbnail/filmstrip area

### Supported Formats
- **JPG** and **JPEG**
- **PNG**
- **BMP**
- **GIF**
- **TIFF**
- **WEBP** (where Pillow supports it)

### Display Quality
- High-quality resampling with LANCZOS filter
- Zoom up to 10x with smooth scaling
- Fit-to-window mode
- Actual size mode
- Image centering on canvas

## Technologies

- Python 3.12+
- Tkinter (standard GUI library)
- Pillow (Python Imaging Library)
- No other third-party dependencies

## Project Structure

```
03_Image_Viewer/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── model.py
│   ├── ui/
│   │   └── view.py
│   └── controller.py
├── assets/
└── docs/
    └── screenshots/
```

## Installation

```bash
# Clone the repository
git clone https://github.com/JDevender007/Python.git

# Navigate to the image viewer project
cd Python/09_Desktop_Applications/03_Image_Viewer

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

### Opening Images

- **Open (Ctrl+O)**: Select an image file to view
- **Open Folder (Ctrl+F)**: Select a folder to browse images
- The first image in the folder will be displayed

### Navigation

- **First Image**: Go to the first image in the current folder
- **Previous**: Navigate to the previous image in history
- **Next**: Navigate to the next image in history
- **Last Image**: Go to the last image viewed

### Zoom and Fit

- **Zoom In (Ctrl++)**: Increase zoom by 20%
- **Zoom Out (Ctrl+-)**: Decrease zoom by 20%
- **Fit to Window (Ctrl+F)**: Fit the image to the canvas size
- **Actual Size (Ctrl+A)**: Reset to 100% zoom (1:1 ratio)

### Rotation and Flip

- **Rotate Left**: Rotate 90 degrees counter-clockwise
- **Rotate Right**: Rotate 90 degrees clockwise
- **Flip Horizontal**: Mirror the image left-to-right
- **Flip Vertical**: Mirror the image top-to-bottom

### Undo

- **Undo**: Go back to the previously viewed image
- History is maintained for the current session

### Image Information

The info panel displays:
- Filename
- Dimensions (width × height)
- Image format (JPG, PNG, etc.)
- Color mode (RGB, RGBA, L, etc.)
- Megapixels (calculated from dimensions)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open image file |
| `Ctrl+F` | Open image folder |
| `Ctrl++` | Zoom In |
| `Ctrl+-` | Zoom Out |
| `Ctrl+A` | Actual Size / Fit to Window toggle |
| `Left` | Rotate Left (90° CCW) |
| `Right` | Rotate Right (90° CW) |
| `Up` | Flip Horizontal |
| `Down` | Flip Vertical |
| `Ctrl+Z` | Undo |
| `Alt+F4` | Exit |

### Mouse Controls

- **Mouse Wheel**: Zoom in/out over the image area
- **Canvas Scrollbars**: Navigate large images
- **Double-Click**: Fit image to canvas

## Error Handling

- **Unsupported format**: Shows error message if format is not supported by Pillow
- **Corrupted image**: Detects and reports corrupted/damaged image files
- **Missing file**: Informs user if selected file no longer exists
- **Out of memory**: Handles large images gracefully with warnings
- **Canvas resize**: Re-draws image when window is resized

## Future Improvements

- Batch image processing
- Slideshow mode
- Image format conversion
- EXIF data display and rotation
- Color adjustment tools (brightness, contrast, saturation)
- Selection and cropping tools
- Fullscreen mode
- Multi-monitor support
- Drag-and-drop image opening
- Recent files list

## Screenshots

![Image Viewer](docs/screenshots/placeholder.png)

*Placeholder screenshot - add actual screenshots to `docs/screenshots/` directory*