from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from openmill.adapters.linuxcnc import (
    LinuxCNCMachineAdapter,
    configured_tool_table,
    read_tool_table,
)
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.models import Stock, Tool


class AdapterAndModelTests(unittest.TestCase):
    def test_mock_machine_has_realistic_tool_library(self) -> None:
        adapter = MockMachineAdapter()
        self.assertGreaterEqual(len(adapter.get_tools()), 5)
        self.assertEqual(adapter.get_tool(4).diameter, 16)

    def test_missing_tool_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "T999"):
            MockMachineAdapter().get_tool(999)

    def test_linuxcnc_adapter_fails_clearly_when_unavailable(self) -> None:
        try:
            __import__("linuxcnc")
        except ImportError:
            with self.assertRaisesRegex(RuntimeError, "MockMachineAdapter"):
                LinuxCNCMachineAdapter()

    def test_linuxcnc_tool_table_keeps_only_explicit_valid_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "tool.tbl"
            table.write_text(
                "T1 P1 D6.0 ; Fraise 6 mm\n"
                "T2 P2 D0.000001 ; valeur residuelle\n"
                "T7 P7 D12.5 ; Fraise a surfacer\n"
                "T-1 P0 D0\n",
                encoding="utf-8",
            )
            tools = read_tool_table(table)
        self.assertEqual([tool.number for tool in tools], [1, 7])
        self.assertEqual([tool.name for tool in tools], ["Fraise 6 mm", "Fraise a surfacer"])

    def test_configured_tool_table_resolves_relative_path_and_inch_units(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tool.tbl").write_text("T3 P3 D0.25 ; Fraise quart de pouce\n", encoding="utf-8")
            ini = root / "machine.ini"
            ini.write_text(
                "[EMCIO]\nTOOL_TABLE = tool.tbl\n[TRAJ]\nLINEAR_UNITS = inch\n",
                encoding="utf-8",
            )
            previous = os.environ.get("INI_FILE_NAME")
            os.environ["INI_FILE_NAME"] = str(ini)
            try:
                tools = configured_tool_table()
            finally:
                if previous is None:
                    os.environ.pop("INI_FILE_NAME", None)
                else:
                    os.environ["INI_FILE_NAME"] = previous
        self.assertIsNotNone(tools)
        self.assertAlmostEqual(tools[0].diameter, 6.35)

    def test_stock_rejects_invalid_dimensions(self) -> None:
        with self.assertRaises(ValueError):
            Stock(width=-1)

    def test_tool_rejects_invalid_diameter(self) -> None:
        with self.assertRaises(ValueError):
            Tool(1, 0, "Outil impossible")


if __name__ == "__main__":
    unittest.main()
