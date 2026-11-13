"""Faulty plugin: always fails in process() to exercise the sandbox."""

from __future__ import annotations

from typing import Any

from plugin_core import Plugin


class FaultyPlugin(Plugin):
    """Setup succeeds, process raises: the pipeline must survive this."""

    name = "faulty"
    dependencies = ()

    def process(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise RuntimeError("simulated plugin failure")
