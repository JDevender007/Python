"""Image Viewer model - handles image loading and operations."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image as PILImage


class ImageInfo:
    """Holds metadata about an image."""
    
    def __init__(self, pil_image: PILImage.Image, filepath: Path) -> None:
        self.width = pil_image.width
        self.height = pil_image.height
        self.format = pil_image.format
        self.mode = pil_image.mode
        self.size = pil_image.size
        self.filepath = filepath
        self.filename = filepath.name
        selfextension = filepath.suffix.lower()
        
    @property
    def megapixels(self) -> float:
        return (self.width * self.height) / 1_000_000
    
    @property
    def aspect_ratio(self) -> float:
        if self.height == 0:
            return 0.0
        return self.width / self.height


class ImageModel:
    """Manages the image state and operations for the viewer."""
    
    def __init__(self) -> None:
        self.current_image: Optional[PILImage.Image] = None
        self.current_info: Optional[ImageInfo] = None
        self.image_history: List[PILImage.Image] = []
        self.history_max = 20
        self.index_history = -1
        self.zoom_factor = 1.0
        self.fit_to_window = False
        self.rotation_angle = 0
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']
    
    def load_image(self, filepath: Path) -> Optional[ImageInfo]:
        """Load an image from file."""
        try:
            img = PILImage.open(filepath)
            self.current_info = ImageInfo(img, filepath)
            self.current_image = img
            self._add_to_history(img)
            self.zoom_factor = 1.0
            self.rotation_angle = 0
            self.fit_to_window = False
            return self.current_info
        except Exception as e:
            # Could be corrupted image, unsupported format, etc.
            raise ValueError(f"Could not load image: {e}")
    
    def _add_to_history(self, img: PILImage.Image) -> None:
        """Add image to history stack."""
        # If we're not at the end of history (e.g., after undo-like operations),
        # truncate the forward history
        self.image_history = self.image_history[:self.history_max]
        self.image_history.append(img)
        self.index_history = len(self.image_history) - 1
        
        # Trim if exceeds max
        if len(self.image_history) > self.history_max:
            self.image_history = self.image_history[-self.history_max:]
            self.index_history = len(self.image_history) - 1
    
    def zoom(self, factor: float) -> None:
        """Zoom in/out by factor."""
        self.zoom_factor *= factor
        # Clamp zoom between reasonable limits
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
    
    def rotate_clockwise(self) -> None:
        """Rotate image 90 degrees clockwise."""
        if self.current_image:
            self.rotation_angle = (self.rotation_angle + 90) % 360
            # Actually rotate the image
            self.current_image = self.current_image.rotate(90, expand=True)
            # Re-create info
            self.current_info = ImageInfo(self.current_image, self.current_info.filepath)
    
    def rotate_counterclockwise(self) -> None:
        """Rotate image 90 degrees counter-clockwise."""
        if self.current_image:
            self.rotation_angle = (self.rotation_angle - 90) % 360
            self.current_image = self.current_image.rotate(-90, expand=True)
            self.current_info = ImageInfo(self.current_image, self.current_info.filepath)
    
    def flip_horizontal(self) -> None:
        """Flip image horizontally."""
        if self.current_image:
            self.current_image = self.current_image.transpose(PILImage.FLIP_LEFT_RIGHT)
            self.current_info = ImageInfo(self.current_image, self.current_info.filepath)
    
    def flip_vertical(self) -> None:
        """Flip image vertically."""
        if self.current_image:
            self.current_image = self.current_image.transpose(PILImage.FLIP_TOP_BOTTOM)
            self.current_info = ImageInfo(self.current_image, self.current_info.filepath)
    
    def reset_zoom(self) -> None:
        """Reset zoom to 100%."""
        self.zoom_factor = 1.0
    
    def toggle_fit_to_window(self) -> None:
        """Toggle fit-to-window mode."""
        self.fit_to_window = not self.fit_to_window
    
    def undo_last(self) -> bool:
        """Undo to previous image in history."""
        if self.index_history > 0:
            self.index_history -= 1
            self.current_image = self.image_history[self.index_history]
            self.current_info = ImageInfo(self.current_image, self.current_info.filepath)
            return True
        return False