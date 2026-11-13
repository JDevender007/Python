"""Text editor controller - connects view and model."""

from __future__ import annotations
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from .model import Document, EditorModel
from .services.file_service import FileService


def init_editor(controller: "EditorController", root: tk.Tk) -> None:
    """Initialize the editor with controller and root window."""
    view = EditorView(root)
    view.pack(fill="both", expand=True)
    controller.view = view
    controller.model = EditorModel()
    controller.file_service = FileService(controller.model)
    
    # Wire view to model and services
    view.register_handlers(
        new=lambda: controller.handle_new(),
        open=lambda: controller.handle_open(),
        save=lambda: controller.handle_save(),
        save_as=lambda: controller.handle_save_as(),
        close=lambda: controller.handle_close(),
        undo=lambda: controller.handle_undo(),
        redo=lambda: controller.handle_redo(),
        cut=lambda: controller.handle_cut(),
        copy=lambda: controller.handle_copy(),
        paste=lambda: controller.handle_paste(),
        select_all=lambda: controller.handle_select_all(),
        find=lambda: controller.handle_find(),
        replace=lambda: controller.handle_replace(),
        toggle_wrap=lambda: controller.handle_toggle_wrap(),
    )
    
    # Set up view with controller
    view.set_controller(controller.model)
    EditorView.init_view(view, controller.model)
    
    # Initialize with a new document
    controller.handle_new()


class EditorController:
    """Main controller for the text editor application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.view: Optional[EditorView] = None
        self.model: Optional[EditorModel] = None
        self.file_service: Optional[FileService] = None
        self._unsaved_prompt: bool = True  # Track if we should prompt for unsaved changes
        
        # Set up the view and wire everything
        self._setup()
    
    def _setup(self) -> None:
        """Set up the editor components."""
        init_editor(self, self.root)
    
    # --- Handler methods for view events ---

    def handle_new(self) -> None:
        """Handle New file."""
        # Close current if dirty, or just start fresh
        if self.model and self.model.current_document and self.model.current_document.is_modified():
            if messagebox.askyesno(
                "Unsaved Changes",
                "Do you want to save changes to the current document?"
            ):
                self.handle_save()
        self.model = EditorModel()
        self.file_service = FileService(self.model)
        doc = self.model.new_document()
        self.view.set_text(doc.content)
        self.root.title(f"Text Editor - {doc.title}")
        self._update_title()
        self._update_status_bar()

    def handle_open(self) -> None:
        """Handle Open file."""
        filepath = filedialog.askopenfilename(
            filetypes=[
                ("Text files", "*.txt"),
                ("Python files", "*.py"),
                ("All files", "*.*"),
            ]
        )
        if filepath:
            doc = self.file_service.open_file(pathlib.Path(filepath))
            if doc:
                self.view.set_text(doc.content)
                self.root.title(f"Text Editor - {doc.title}")
                self._update_title()
                self._update_status_bar()

    def handle_save(self) -> None:
        """Handle Save."""
        if self.model and self.model.current_document:
            doc = self.model.current_document
            if doc.filepath:
                success = doc.save(doc.filepath)
                if success:
                    self._update_status_bar()
                    self._update_title()
            else:
                self.handle_save_as()

    def handle_save_as(self) -> None:
        """Handle Save As."""
        if self.model and self.model.current_document:
            doc = self.model.current_document
            default_path = pathlib.Path.home() / "Documents" / f"{doc.title}.txt"
            filepath = filedialog.asksaveasfilename(
                initialfile=default_path.name,
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if filepath:
                success = doc.save(pathlib.Path(filepath))
                if success:
                    self._update_status_bar()
                    self._update_title()

    def handle_close(self) -> bool:
        """Handle Close."""
        if self.model and self.model.current_document and self.model.current_document.is_modified():
            result = messagebox.askyesno(
                "Unsaved Changes",
                "Do you want to save changes to the current document?"
            )
            if result:
                return self.handle_save()
        return True

    def handle_undo(self) -> None:
        """Handle Undo."""
        if self.model and self.model.current_document:
            success = self.model.current_document.undo()
            if success:
                self.view.set_text(self.model.current_document.content)
                self._update_status_bar()

    def handle_redo(self) -> None:
        """Handle Redo."""
        if self.model and self.model.current_document:
            success = self.model.current_document.redo()
            if success:
                self.view.set_text(self.model.current_document.content)
                self._update_status_bar()

    def handle_cut(self) -> None:
        """Handle Cut."""
        if self.view and self.view.text_area:
            try:
                self.view.text_area.event_generate("<<Cut>>")
            except tk.TclError:
                pass
            self._update_status_bar()

    def handle_copy(self) -> None:
        """Handle Copy."""
        if self.view and self.view.text_area:
            try:
                self.view.text_area.event_generate("<<Copy>>")
            except tk.TclError:
                pass
            self._update_status_bar()

    def handle_paste(self) -> None:
        """Handle Paste."""
        if self.view and self.view.text_area:
            try:
                self.view.text_area.event_generate("<<Paste>>")
            except tk.TclError:
                pass
            self._update_status_bar()

    def handle_select_all(self) -> None:
        """Handle Select All."""
        if self.view and self.view.text_area:
            self.view.text_area.tag_add("sel", "1.0", "end")

    def handle_find(self) -> None:
        """Handle Find."""
        messagebox.showinfo("Find", "Find functionality coming soon!")

    def handle_replace(self) -> None:
        """Handle Replace."""
        messagebox.showinfo("Replace", "Replace functionality coming soon!")

    def handle_toggle_wrap(self) -> None:
        """Toggle word wrap."""
        if self.view and hasattr(self.view, 'word_wrap_var'):
            self.view.word_wrap_var.set(not self.view.word_wrap_var.get())
            self.view._on_toggle_word_wrap()

    # --- Utility methods ---

    def _update_title(self) -> None:
        """Update the window title."""
        if self.model and self.model.current_document:
            title = self.model.current_document.title
            unsaved = " * " if self.model.current_document.is_modified() else ""
            self.root.title(f"Text Editor {unsaved}{title}")
        else:
            self.root.title("Text Editor")

    def _update_status_bar(self) -> None:
        """Update the status bar."""
        if self.model and self.model.current_document:
            # Word count, char count
            words, chars, lines = self.model.current_document.get_stats()
            # Cursor position
            try:
                idx = self.view.text_area.index("insert")
                line, col = idx.split(".")
                self.view.line_var.set(f"Line: {int(line)}")
                self.view.col_var.set(f"Col: {int(float(col))}")
            except Exception:
                pass
            
            self.view.word_count_var.set(f"Words: {words}")
            self.view.char_count_var.set(f"Chars: {chars}")
        else:
            self.view.line_var.set("Line: 1")
            self.view.col_var.set("Col: 1")
            self.view.word_count_var.set("Words: 0")
            self.view.char_count_var.set("Chars: 0")