"""Stats plugin: depends on echo; aggregates records into the context."""

from __future__ import annotations

from typing import Any

from plugin_core import Plugin


class StatsPlugin(Plugin):
    """Computes deterministic aggregates and publishes them on context."""

    name = "stats"
    dependencies = ("echo",)

    def setup(self, context: dict[str, Any]) -> None:
        self._context = context

    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary = {
            "count": len(data),
            "total_qty": sum(record["qty"] for record in data),
            "ids": [record["id"] for record in data],
        }
        self.summary = summary
        self._context["stats"] = summary
        return data
