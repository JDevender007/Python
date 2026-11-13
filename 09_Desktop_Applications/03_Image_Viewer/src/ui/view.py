"""Image Viewer view - the graphical user interface."""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional
from PIL import Image, ImageTk


class ImageView(ttk.Frame):
    """The image viewer's graphical user interface."""
    
    def __init__(self, master: tk.Tk, **kwargs: any) -> None:
        super().__init__(master, **kwargs)
        self.master = master
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
        self.file_menu.add_command(label="Open", accelerator="Ctrl+O", command=self._on_open)
        self.file_menu.add_command(label="Open Folder", accelerator="Ctrl+F", command=self._on_open_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_exit)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        
        # Navigation menu
        self.nav_menu = tk.Menu(self.menubar, tearoff=0)
        self.nav_menu.add_command(label="Back", accelerator="Ctrl+Z", command=self._on_undo)
        self.nav_menu.add_command(label="Forward", command=self._on_redo)
        self.menubar.add_cascade(label="Navigation", menu=self.nav_menu)
        
        # Transform menu
        self.transform_menu = tk.Menu(self.menubar, tearoff=0)
        self.transform_menu.add_command(label="Zoom In", accelerator="Ctrl++", command=self._on_zoom_in)
        self.transform_menu.add_command(label="Zoom Out", accelerator="Ctrl+-", command=self._on_zoom_out)
        self.transform_menu.add_command(label="Fit to Window", accelerator="Ctrl+F", command=self._on_fit_window)
        self.transform_menu.add_command(label="Actual Size", accelerator="Ctrl+A", command=self._on_actual_size)
        self.transform_menu.add_separator()
        self.transform_menu.add_command(label="Rotate Left", command=self._on_rotate_left)
        self.transform_menu.add_command(label="Rotate Right", command=self._on_rotate_right)
        self.transform_menu.add_separator()
        self.transform_menu.add_command(label="Flip Horizontal", command=self._on_flip_horizontal)
        self.transform_menu.add_command(label="Flip Vertical", command=self._on_flip_vertical)
        self.menubar.add_cascade(label="Transform", menu=self.transform_menu)
        
        # Help menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label="About", command=self._on_about)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        
        # Toolbar
        self.toolbar = ttk.Frame(self)
        ttk.Button(self.toolbar, label="Open").pack(side="left", padx=2)
        ttk.Button(self.toolbar, label="Fit").pack(side="left", padx=2)
        ttk.Button(self.toolbar, label="Actual").pack(side="left", padx=2)
        
        # Image canvas
        self.canvas = tk.Canvas(self, bg="gray", highlightthickness=0)
        self.h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.config(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)
        
        # Image info label
        self.info_label = ttk.Label(self, text="No image loaded", anchor="w")
        
        # Thumbnail/filmstrip area (optional)
        self.thumbnail_frame = ttk.LabelFrame(self, text="Thumbnails")
        self.thumbnail_canvas = tk.Canvas(self.thumbnail_frame, width=120, bg="lightgray")
        self.thumbnail_scroll = ttk.Scrollbar(self.thumbnail_frame, orient="vertical", command=self.thumbnail_canvas.yview)
        self.thumbnail_canvas.config(yscrollcommand=self.thumbnail_scroll.set)
        self.thumbnail_inner = ttk.Frame(self.thumbnail_canvas)
        
        self.thumbnail_canvas.create_window((0, 0), window=self.thumbnail_inner, anchor="nw")
        self.thumbnail_canvas.config(yscrollcommand=self.thumbnail_scroll.set)
        
    def _setup_layout(self) -> None:
        """Set up the layout manager."""
        # Configure grid weights
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        
        # Pack menu bar
        self.menubar.pack(side="top", fill="x")
        
        # Pack toolbar
        self.toolbar.pack(side="top", fill="x")
        
        # Main area - canvas with scrollbars
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.h_scrollbar.grid(row=2, column=0, sticky="ew")
        self.v_scrollbar.grid(row=1, column=1, sticky="ns")
        
        # Thumbnail frame (collapsible)
        self.thumbnail_frame.grid_remove()  # Hidden by default
        
        # Info label
        self.info_label.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
    
    def _setup_bindings(self) -> None:
        """Set up keyboard and mouse bindings."""
        # Keyboard shortcuts
        self.master.bind("<Control-o>", lambda e: self._on_open())
        self.master.bind("<Control-f>", lambda e: self._on_open_folder())
        self.master.bind("<Alt-F4>", lambda e: self._on_exit())
        self.master.bind("<Control-plus>", lambda e: self._on_zoom_in())
        self.master.bind("<Control-minus>", lambda e: self._on_zoom_out())
        self.master.bind("<Control-a>", lambda e: self._on_actual_size())
        
        # Mouse wheel for zoom
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows
        self.canvas.bind("<Button-4>", lambda e: self._on_zoom_in())  # Linux
        self.canvas.bind("<Button-5>", lambda e: self._on_zoom_out())  # Linux
        
        # Canvas resize
        self.canvas.bind("<Configure>", self._on_canvas_configure)
    
    # --- Event handlers ---

    def _on_open(self) -> None:
        """Open image file dialog."""
        filepath = filedialog.askopenfilename(
            filetypes=[
                ("Image files", "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.tiff;*.webp"),
                ("JPEG files", "*.jpg;*.jpeg"),
                ("PNG files", "*.png"),
                ("All files", "*.*"),
            ]
        )
        if filepath:
            self._load_image(Path(filepath))
    
    def _on_open_folder(self) -> None:
        """Open folder and load first image."""
        folder = filedialog.askdirectory()
        if folder:
            # Load first image from folder
            files = list(Path(folder).glob("*.jpg")) + \
                    list(Path(folder).glob("*.jpeg")) + \
                    list(Path(folder).glob("*.png")) + \
                    list(Path(folder).glob("*.bmp")) + \
                    list(Path(folder).glob("*.gif"))
            if files:
                self._load_image(files[0])
    
    def _on_exit(self) -> None:
        """Exit application."""
        self.master.destroy()
    
    def _on_zoom_in(self) -> None:
        """Zoom in."""
        self.viewer.zoom(1.2) if hasattr(self, 'viewer') else None
    
    def _on_zoom_out(self) -> None:
        """Zoom out."""
        self.viewer.zoom(0.8) if hasattr(self, 'viewer') else None
    
    def _on_actual_size(self) -> None:
        """Reset to actual size."""
        self.viewer.reset_zoom() if hasattr(self, 'viewer') else None
    
    def _on_rotate_left(self) -> None:
        """Rotate left."""
        self.viewer.rotate_counterclockwise() if hasattr(self, 'viewer') else None
    
    def _on_rotate_right(self) -> None:
        """Rotate right."""
        self.viewer.rotate_clockwise() if hasattr(self, 'viewer') else None
    
    def _on_flip_horizontal(self) -> None:
        """Flip horizontal."""
        self.viewer.flip_horizontal() if hasattr(self, 'viewer') else None
    
    def _on_flip_vertical(self) -> None:
        """Flip vertical."""
        self.viewer.flip_vertical() if hasattr(self, 'viewer') else None
    
    def _on_about(self) -> None:
        """Show about dialog."""
        messagebox.showinfo(
            "About Image Viewer",
            "Image Viewer - Python Portfolio Project 03\n"
            "Built with Tkinter and Pillow"
        )
    
    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Handle canvas resize."""
        # Re-draw image on resize
        self._draw_image()
    
    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel (Windows)."""
        delta = event.delta
        if delta > 0:
            self._on_zoom_in()
        else:
            self._on_zoom_out()
    
    # --- Public API ---
    
    def set_viewer(self, viewer) -> None:
        """Set reference to image model."""
        self.viewer = viewer
    
    def load_image(self, filepath: str) -> None:
        """Load an image from file path."""
        self._load_image(Path(filepath))
    
    def _load_image(self, filepath: Path) -> None:
        """Load image into viewer."""
        try:
            info = self.viewer.load_image(filepath)
            self._display_image()
            self._update_info_label(info)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
    
    def _display_image(self) -> None:
        """Display the current image on canvas."""
        if not self.viewer.current_image:
            return
        
        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width < 10 or canvas_height < 10:
            return
        
        # Get image and apply zoom
        img = self.viewer.current_image
        width = int(img.width * self.viewer.zoom_factor)
        height = int(img.height * self.viewer.zoom_factor)
        
        # Resize image
        resized = img.resize((width, height), PILImage.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        
        # Center image on canvas
        self.canvas.delete("all")
        x = (canvas_width - width) // 2
        y = (canvas_height - height) // 2
        self.canvas.create_image(x, y, anchor="nw", image=self.tk_image)
        
        # Update scroll region
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
    
    def _update_info_label(self, info: ImageInfo) -> None:
        """Update the image info label."""
        if info:
            self.info_label.config(
                text=f"{info.filename} | {info.width}x{info.height} | {info.format} | "
                f"{info.mode} | {info.megapixels:.1f} MP"
            )
    
    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Handle canvas resize event."""
        self._draw_image()
    
    def _on_mousewheel(self, event: tk.Event) -> None:
        """Handle mouse wheel for zooming."""
        if event.delta > 0:
            self.viewer.zoom(1.2)
        else:
            self.viewer.zoom(0.8)
        self._draw_image()
    
    def _draw_image(self) -> None:
        """Draw the image on the canvas."""
        if not self.viewer or not self.viewer.current_image:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width < 10 or canvas_height < 10:
            return
        
        img = self.viewer.current_image
        width = int(img.width * self.viewer.zoom_factor)
        height = int(img.height * self.viewer.zoom_factor)
        
        # Resize
        resized = img.resize((width, height), PILImage.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        
        # Center
        x = (canvas_width - width) // 2
        y = (canvas_height - height) // 2
        self.canvas.delete("all")
        self.canvas.create_image(x, y, anchor="nw", image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))