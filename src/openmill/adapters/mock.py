"""A useful virtual machine for developing natively on Windows."""

from __future__ import annotations

from openmill.core.models import Tool


class MockMachineAdapter:
    def __init__(self, tools: tuple[Tool, ...] | None = None) -> None:
        self._tools = tools or (
            Tool(1, 6.0, "Fraise carbure Ø 6 mm", 22.0),
            Tool(2, 10.0, "Fraise deux tailles Ø 10 mm", 28.0),
            Tool(3, 3.0, "Fraise de finition Ø 3 mm", 14.0),
            Tool(4, 16.0, "Fraise à surfacer Ø 16 mm", 18.0),
            Tool(5, 5.0, "Foret Ø 5 mm", 38.0),
        )

    @property
    def display_name(self) -> str:
        return "Machine simulée · Windows / développement"

    @property
    def is_connected(self) -> bool:
        return True

    def get_tools(self) -> tuple[Tool, ...]:
        return self._tools

    def get_tool(self, number: int) -> Tool:
        for tool in self._tools:
            if tool.number == number:
                return tool
        raise ValueError(f"L’outil T{number} est absent de la bibliothèque.")

