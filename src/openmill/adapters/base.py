"""Protocol shared by desktop development and LinuxCNC integration."""

from __future__ import annotations

from typing import Protocol

from openmill.core.models import Tool


class MachineAdapter(Protocol):
    @property
    def display_name(self) -> str: ...

    @property
    def is_connected(self) -> bool: ...

    def get_tools(self) -> tuple[Tool, ...]: ...

    def get_tool(self, number: int) -> Tool: ...

