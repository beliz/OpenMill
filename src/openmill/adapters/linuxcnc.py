"""Optional LinuxCNC adapter; importing the package never requires LinuxCNC."""

from __future__ import annotations

import configparser
import math
import os
from pathlib import Path
import re

from openmill.core.models import Tool


_TOOL_WORD = re.compile(r"([A-Za-z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")


def read_tool_table(path: str | Path, *, unit_scale: float = 1.0) -> tuple[Tool, ...]:
    """Read only explicit T/D records from a LinuxCNC tool table."""
    tools: dict[int, Tool] = {}
    for source_line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        code, _separator, comment = source_line.partition(";")
        words = {letter.upper(): float(value) for letter, value in _TOOL_WORD.findall(code)}
        number = int(words.get("T", 0))
        diameter = words.get("D", 0.0) * unit_scale
        if number <= 0 or not math.isfinite(diameter) or diameter < 0.05:
            continue
        name = comment.strip() or f"Outil T{number} · Ø {diameter:g} mm"
        tools[number] = Tool(number, diameter, name)
    return tuple(tools[number] for number in sorted(tools))


def configured_tool_table() -> tuple[Tool, ...] | None:
    ini_name = os.environ.get("INI_FILE_NAME")
    if not ini_name:
        return None
    ini_path = Path(ini_name).expanduser().resolve()
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(ini_path, encoding="utf-8")
        configured = parser.get("EMCIO", "TOOL_TABLE", fallback="").strip()
    except (configparser.Error, OSError):
        return None
    if not configured:
        return None
    table_path = Path(configured).expanduser()
    if not table_path.is_absolute():
        table_path = ini_path.parent / table_path
    units = parser.get("TRAJ", "LINEAR_UNITS", fallback="mm").strip().lower()
    scale = 25.4 if units in {"inch", "inches", "in"} else 1.0
    try:
        return read_tool_table(table_path, unit_scale=scale)
    except OSError:
        return None


class LinuxCNCMachineAdapter:
    def __init__(self) -> None:
        try:
            import linuxcnc
        except ImportError as error:
            raise RuntimeError(
                "LinuxCNC n’est pas disponible. Utilise MockMachineAdapter sous Windows."
            ) from error
        self._linuxcnc = linuxcnc
        self._status = linuxcnc.stat()

    @property
    def display_name(self) -> str:
        return "LinuxCNC · machine connectée"

    @property
    def is_connected(self) -> bool:
        try:
            self._status.poll()
        except self._linuxcnc.error:
            return False
        return True

    def get_tools(self) -> tuple[Tool, ...]:
        configured = configured_tool_table()
        if configured is not None:
            return configured
        self._status.poll()
        result: dict[int, Tool] = {}
        for entry in self._status.tool_table:
            number = int(getattr(entry, "id", 0) or 0)
            diameter = float(getattr(entry, "diameter", 0.0) or 0.0)
            if number > 0 and math.isfinite(diameter) and diameter >= 0.05:
                # A LinuxCNC Z tool offset is not the flute length. Keep the
                # conservative model default until a tool-geometry source exists.
                result[number] = Tool(number, diameter, f"Outil T{number} · Ø {diameter:g} mm")
        return tuple(result[number] for number in sorted(result))

    def get_tool(self, number: int) -> Tool:
        for tool in self.get_tools():
            if tool.number == number:
                return tool
        raise ValueError(f"L’outil T{number} est absent de la table LinuxCNC.")
