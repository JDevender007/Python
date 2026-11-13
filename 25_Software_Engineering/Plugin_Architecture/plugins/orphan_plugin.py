"""Orphan plugin: depends on a plugin that does not exist."""

from __future__ import annotations

from typing import Any

from plugin_core import Plugin


class OrphanPlugin(Plugin):
    """Never runs: its dependency is missing, so the planner skips it."""

    name = "orphan"
    dependencies = ("not_installed",)

    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return data
