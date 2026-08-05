from __future__ import annotations

import json

from pathlib import Path


class TemplateManager:

    def __init__(self):

        self.directory = Path("templates")

        self.directory.mkdir(
            exist_ok=True,
        )

    def save_template(
        self,
        name: str,
        subject: str,
        body: str,
    ):

        file = self.directory / f"{name}.json"

        data = {
            "subject": subject,
            "body": body,
        }

        with open(
            file,
            "w",
            encoding="utf-8",
        ) as output:

            json.dump(
                data,
                output,
                indent=4,
            )

    def load_template(
        self,
        name: str,
    ):

        file = self.directory / f"{name}.json"

        if not file.exists():

            return None

        with open(
            file,
            "r",
            encoding="utf-8",
        ) as input_file:

            return json.load(input_file)

    def get_templates(self):

        return sorted([file.stem for file in self.directory.glob("*.json")])

    def delete_template(
        self,
        name: str,
    ):

        file = self.directory / f"{name}.json"

        if file.exists():

            file.unlink()
