"""Echo plugin: the root of the pipeline; passes records through."""

from __future__ import annotations

from typing import Any

from plugin_core import Plugin


class EchoPlugin(Plugin):
    """Marks every record as echoed and seeds the context event log."""

    name = "echo"
    dependencies = ()

    def setup(self, context: dict[str, Any]) -> None:
        context.setdefault("events", []).append("echo.setup")

    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**record, "echoed": True} for record in data]

    def teardown(self, context: dict[str, Any]) -> None:
        context["events"].append("echo.teardown")
