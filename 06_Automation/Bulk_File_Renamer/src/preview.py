from __future__ import annotations

from pathlib import Path


class PreviewGenerator:

    def generate(
        self,
        files: list[str],
        prefix: str = "",
        suffix: str = "",
        replace_from: str = "",
        replace_to: str = "",
        remove_text: str = "",
        numbering: bool = False,
        uppercase: bool = False,
        lowercase: bool = False,
        titlecase: bool = False,
    ) -> list[str]:

        preview = []

        for index, file in enumerate(files, start=1):

            name = Path(file).stem

            if replace_from:

                name = name.replace(
                    replace_from,
                    replace_to,
                )

            if remove_text:

                name = name.replace(
                    remove_text,
                    "",
                )

            if prefix:

                name = prefix + name

            if suffix:

                name = name + suffix

            if numbering:

                name = f"{index:03d}_{name}"

            if uppercase:

                name = name.upper()

            elif lowercase:

                name = name.lower()

            elif titlecase:

                name = name.title()

            preview.append(name)

        return preview
