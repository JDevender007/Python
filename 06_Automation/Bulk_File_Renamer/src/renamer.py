from __future__ import annotations

from pathlib import Path
from shutil import move


class FileRenamer:

    def __init__(self):

        self.history = []

    def rename_files(
        self,
        files: list[str],
        new_names: list[str],
    ) -> int:

        self.history.clear()

        renamed = 0

        for old_path, new_name in zip(files, new_names):

            old_file = Path(old_path)

            new_file = old_file.with_name(new_name + old_file.suffix)

            move(
                str(old_file),
                str(new_file),
            )

            self.history.append(
                (
                    str(new_file),
                    str(old_file),
                )
            )

            renamed += 1

        return renamed

    def undo(self):

        for current, previous in reversed(self.history):

            move(
                current,
                previous,
            )

        self.history.clear()

    def has_history(self) -> bool:

        return len(self.history) > 0
