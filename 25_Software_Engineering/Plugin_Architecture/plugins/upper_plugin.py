"""Upper plugin: depends on echo; upper-cases the text field."""

from __future__ import annotations

from typing import Any

from plugin_core import Plugin


class UpperPlugin(Plugin):
    """Runs only after its dependency ``echo`` has marked the records."""

    name = "upper"
    dependencies = ("echo",)

    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**record, "text": record["text"].upper()} for record in data]
