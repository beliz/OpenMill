from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import ast
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import tomllib
import unittest
from unittest.mock import patch
from xml.etree import ElementTree

from openmill import __version__
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import create_demo_project
from openmill.core.models import Project
from openmill.integration.bridge import (
    LinuxCNCProgramBridge,
    ProgramLoadError,
    SimulatedProgramBridge,
    prepare_and_load_program,
    prepare_program,
    project_filename,
)
from openmill.integration.check import main as check_main
from openmill.integration.qtpyvcp_compat import silence_gcode_properties_debug_output
from openmill.integration.runtime import binding_candidates, inspect_runtime, program_directory


class FakeStatus:
    def __init__(self) -> None:
        self.estop = False
        self.enabled = True
        self.interp_state = 1
        self.homed = (1, 1, 1)
        self.g5x_index = 2
        self.file = "previous.ngc"
        self.poll_count = 0

    def poll(self) -> None:
        self.poll_count += 1


class FakeCommand:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.started = False

    def program_open(self, filename: str) -> None:
        self.opened.append(filename)

    def auto(self, *_args) -> None:
        self.started = True


class IntegrationBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="openmill-integration-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.program = self.directory / "part.ngc"
        self.program.write_text("%\nG90\nM30\n%\n", encoding="utf-8")
        self.status = FakeStatus()
        self.command = FakeCommand()
        self.linuxcnc = SimpleNamespace(
            INTERP_IDLE=1, stat=lambda: self.status, command=lambda: self.command
        )

    def test_simulated_bridge_loads_without_starting_a_machine(self) -> None:
        bridge = SimulatedProgramBridge()
        self.assertEqual(bridge.load_program(self.program), self.program)
        self.assertEqual(bridge.snapshot().current_program, str(self.program))

    def test_simulated_bridge_refuses_estop(self) -> None:
        with self.assertRaisesRegex(ProgramLoadError, "urgence"):
            SimulatedProgramBridge(estop=True).load_program(self.program)

    def test_simulated_bridge_refuses_a_running_interpreter(self) -> None:
        with self.assertRaisesRegex(ProgramLoadError, "cours"):
            SimulatedProgramBridge(interpreter_idle=False).load_program(self.program)

    def test_program_requires_supported_extension(self) -> None:
        invalid = self.directory / "unsafe.txt"
        invalid.write_text("M30", encoding="utf-8")
        with self.assertRaisesRegex(ProgramLoadError, r"\.ngc"):
            SimulatedProgramBridge().load_program(invalid)

    def test_program_must_exist(self) -> None:
        with self.assertRaisesRegex(ProgramLoadError, "existe pas"):
            SimulatedProgramBridge().load_program(self.directory / "missing.ngc")

    def test_program_must_not_be_empty(self) -> None:
        self.program.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ProgramLoadError, "vide"):
            SimulatedProgramBridge().load_program(self.program)

    def test_linuxcnc_snapshot_maps_offset_and_homing(self) -> None:
        bridge = LinuxCNCProgramBridge(self.linuxcnc, loader=lambda _: None)
        state = bridge.snapshot()
        self.assertEqual(state.work_offset, "G55")
        self.assertTrue(state.homed)
        self.assertTrue(state.can_load_program)

    def test_linuxcnc_prefers_qtpyvcp_loader(self) -> None:
        loaded: list[str] = []
        bridge = LinuxCNCProgramBridge(self.linuxcnc, loader=loaded.append)
        self.assertEqual(bridge.load_program(self.program), self.program)
        self.assertEqual(loaded, [str(self.program)])
        self.assertEqual(self.command.opened, [])
        self.assertFalse(self.command.started)

    def test_linuxcnc_falls_back_to_program_open_without_cycle_start(self) -> None:
        with patch("openmill.integration.bridge._qtpyvcp_loader", return_value=None):
            bridge = LinuxCNCProgramBridge(self.linuxcnc)
        bridge.load_program(self.program)
        self.assertEqual(self.command.opened, [str(self.program)])
        self.assertFalse(self.command.started)

    def test_linuxcnc_refuses_busy_interpreter(self) -> None:
        self.status.interp_state = 99
        bridge = LinuxCNCProgramBridge(self.linuxcnc, loader=lambda _: None)
        with self.assertRaisesRegex(ProgramLoadError, "repos"):
            bridge.load_program(self.program)
        self.assertFalse(self.command.started)

    def test_linuxcnc_refuses_emergency_stop(self) -> None:
        self.status.estop = True
        bridge = LinuxCNCProgramBridge(self.linuxcnc, loader=lambda _: None)
        with self.assertRaisesRegex(ProgramLoadError, "urgence"):
            bridge.load_program(self.program)

    def test_linuxcnc_reports_status_errors(self) -> None:
        self.status.poll = lambda: (_ for _ in ()).throw(RuntimeError("NML disconnected"))
        bridge = LinuxCNCProgramBridge(self.linuxcnc, loader=lambda _: None)
        with self.assertRaisesRegex(ProgramLoadError, "NML disconnected"):
            bridge.snapshot()

    def test_filename_is_safe_and_deterministic(self) -> None:
        self.assertEqual(project_filename("Plaque alu Ø 8 / été"), "openmill-plaque-alu-8-ete.ngc")
        self.assertEqual(project_filename("???"), "openmill-programme.ngc")

    def test_prepare_program_generates_complete_linuxcnc_file(self) -> None:
        destination = prepare_program(create_demo_project(), MockMachineAdapter(), output_directory=self.directory)
        content = destination.read_text(encoding="utf-8")
        self.assertIn("OPENMILL_STOCK", content)
        self.assertIn("M30", content)
        self.assertFalse(list(self.directory.glob("*.tmp")))
        destination.read_bytes().decode("ascii")

    def test_prepare_program_refuses_empty_project(self) -> None:
        with self.assertRaisesRegex(ProgramLoadError, "au moins une"):
            prepare_program(Project(), MockMachineAdapter(), output_directory=self.directory)

    def test_prepare_program_refuses_invalid_operation(self) -> None:
        project = create_demo_project()
        project.operations[0].tool_number = 999
        with self.assertRaisesRegex(ProgramLoadError, "T999"):
            prepare_program(project, MockMachineAdapter(), output_directory=self.directory)

    def test_prepare_and_load_connects_generation_to_simulated_host(self) -> None:
        bridge = SimulatedProgramBridge()
        destination = prepare_and_load_program(
            create_demo_project(), MockMachineAdapter(), bridge, output_directory=self.directory
        )
        self.assertEqual(bridge.loaded_programs, [destination])


class RuntimeDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="openmill-runtime-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_existing_pyside6_host_wins_over_requested_pyqt5(self) -> None:
        self.assertEqual(binding_candidates(loaded_modules={"PySide6.QtWidgets"}, requested_api="pyqt5"), ("PySide6",))

    def test_existing_pyqt5_host_wins_over_requested_pyside6(self) -> None:
        self.assertEqual(binding_candidates(loaded_modules={"PyQt5.QtCore"}, requested_api="pyside6"), ("PyQt5",))

    def test_qt_api_selects_pyside6_before_pyqt5(self) -> None:
        self.assertEqual(binding_candidates(loaded_modules=set(), requested_api="pyside6"), ("PySide6", "PyQt5"))

    def test_windows_default_keeps_pyqt5_first(self) -> None:
        self.assertEqual(binding_candidates(loaded_modules=set(), requested_api=""), ("PyQt5", "PySide6"))

    def test_program_directory_reads_relative_linuxcnc_prefix(self) -> None:
        source = self.directory / "machine.ini"
        source.write_text("[DISPLAY]\nPROGRAM_PREFIX = nc_files\n", encoding="utf-8")
        self.assertEqual(program_directory(source), self.directory / "nc_files")

    def test_program_directory_reads_absolute_prefix(self) -> None:
        source = self.directory / "machine.ini"
        destination = self.directory / "parts"
        source.write_text(f"[DISPLAY]\nPROGRAM_PREFIX = {destination}\n", encoding="utf-8")
        self.assertEqual(program_directory(source), destination)

    def test_program_directory_defaults_next_to_machine_configuration(self) -> None:
        source = self.directory / "machine.ini"
        source.write_text("[DISPLAY]\nDISPLAY = probe_basic\n", encoding="utf-8")
        self.assertEqual(program_directory(environ={"INI_FILE_NAME": str(source)}), self.directory / "openmill-programs")

    def test_report_detects_installed_components_without_importing_them(self) -> None:
        available = {"PySide6", "vtk", "linuxcnc", "qtpyvcp", "probe_basic"}
        report = inspect_runtime(
            module_available=lambda name: name in available,
            loaded_modules={"PySide6.QtWidgets"},
            environ={},
        )
        self.assertTrue(report.machine_integration_available)
        self.assertEqual(report.active_qt_binding, "PySide6")
        self.assertFalse(report.pyqt5)

    def test_report_is_json_serializable(self) -> None:
        report = inspect_runtime(module_available=lambda _: False, loaded_modules=set(), environ={})
        self.assertFalse(json.loads(json.dumps(report.to_dict()))["gui_available"])

    def test_cli_smoke_test_works_without_linuxcnc(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = check_main(["--json", "--smoke-test"])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["openmill_version"], __version__)
        self.assertTrue(result["smoke_test"]["passed"])
        self.assertFalse(result["smoke_test"]["machine_started"])


class IntegrationPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_package_version_matches_declared_distribution(self) -> None:
        metadata = tomllib.loads((self.root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["version"], __version__)
        self.assertIn("gui-pyside6", metadata["project"]["optional-dependencies"])

    def test_user_tab_respects_probe_basic_discovery_conventions(self) -> None:
        directory = self.root / "examples/probe_basic/user_tabs/openmill"
        source = ast.parse((directory / "openmill.py").read_text(encoding="utf-8"))
        self.assertIn("UserTab", [node.name for node in source.body if isinstance(node, ast.ClassDef)])
        ui_root = ElementTree.parse(directory / "openmill.ui").getroot()
        widget = ui_root.find("widget")
        self.assertEqual(widget.attrib["name"], "CONVERSATIONNEL")
        self.assertEqual(widget.find("property[@name='sidebar']/bool").text, "false")

    def test_interactions_do_not_force_compatible_renderer(self) -> None:
        source = ast.parse((self.root / "src/openmill/ui/preview_3d.py").read_text(encoding="utf-8"))
        preview = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "VtkPreview")
        methods = {
            node.name: node
            for node in preview.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"_timeline_changed", "_palette_changed", "_toggle_playback"}
        }
        for name, method in methods.items():
            with self.subTest(method=name):
                calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
                self.assertFalse(
                    any(
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "_select_renderer"
                        and call.args
                        and isinstance(call.args[0], ast.Constant)
                        and call.args[0].value == "compatible"
                        for call in calls
                    )
                )

    def test_vtk_framebuffer_diagnostic_does_not_disable_vtk(self) -> None:
        source = ast.parse((self.root / "src/openmill/ui/preview_3d.py").read_text(encoding="utf-8"))
        preview = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "VtkPreview")
        diagnostic = next(node for node in preview.body if isinstance(node, ast.FunctionDef) and node.name == "_verify_vtk_output")
        calls = [node for node in ast.walk(diagnostic) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Attribute) and call.func.attr == "_vtk_failed" for call in calls))

    def test_main_preview_alternates_without_reparenting_native_vtk(self) -> None:
        path = self.root / "src/openmill/integration/main_preview.py"
        source_text = path.read_text(encoding="utf-8")
        source = ast.parse(source_text)
        host = next(
            node
            for node in source.body
            if isinstance(node, ast.ClassDef) and node.name == "ProbeBasicMainPreview"
        )
        methods = {
            node.name: ast.unparse(node)
            for node in host.body
            if isinstance(node, ast.FunctionDef) and node.name in {"show_native", "show_openmill"}
        }
        self.assertIn("self.hide()", methods["show_native"])
        self.assertIn("self._native.show()", methods["show_native"])
        self.assertIn("self._native.hide()", methods["show_openmill"])
        self.assertIn("self.show()", methods["show_openmill"])
        self.assertNotIn("setParent", source_text)
        self.assertIn("layout.insertWidget(index + 1, self.host)", source_text)

    def test_main_preview_switch_stays_available_over_native_vtk(self) -> None:
        source_text = (
            self.root / "src/openmill/integration/main_preview.py"
        ).read_text(encoding="utf-8")
        self.assertIn('QPushButton("OpenMill", self._native)', source_text)
        self.assertIn("self._native.installEventFilter(self)", source_text)
        self.assertIn("self._native_switch.show()", source_text)
        self.assertIn("button.raise_()", source_text)

    def test_gcode_navigation_selects_and_styles_the_current_line(self) -> None:
        source_text = (
            self.root / "src/openmill/integration/main_preview.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"currentLineBackground": "#17372f"', source_text)
        self.assertIn("self._editor.setProperty(property_name, QColor(color))", source_text)
        self.assertIn('getattr(self._editor, "focusLine", None)', source_text)
        self.assertIn("setter(target)", source_text)
        self.assertIn("QTextEdit.ExtraSelection()", source_text)
        self.assertIn('selection.format.setBackground(QColor("#23604c"))', source_text)
        self.assertIn('selection.format.setForeground(QColor("#ffffff"))', source_text)
        self.assertIn("self._editor.setExtraSelections([selection, *search_markers])", source_text)
        self.assertIn("selection-color: #ffffff", source_text)

    def test_gcode_cursor_updates_are_debounced(self) -> None:
        source_text = (
            self.root / "src/openmill/integration/main_preview.py"
        ).read_text(encoding="utf-8")
        self.assertIn("self._editor_timer.setSingleShot(True)", source_text)
        self.assertIn("self._editor_timer.setInterval(75)", source_text)
        self.assertIn("self._editor_timer.start()", source_text)
        self.assertIn("motion_count != self._last_preview_motion_count", source_text)

    def test_preview_renders_only_the_visible_engine(self) -> None:
        source = ast.parse((self.root / "src/openmill/ui/preview_3d.py").read_text(encoding="utf-8"))
        preview = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == "VtkPreview")
        apply_frame = next(
            node for node in preview.body if isinstance(node, ast.FunctionDef) and node.name == "_apply_frame"
        )
        renderer_branch = next(
            node
            for node in ast.walk(apply_frame)
            if isinstance(node, ast.If)
            and "self._requested_mode == 'vtk' and self._vtk_ready" in ast.unparse(node.test)
        )
        self.assertTrue(renderer_branch.orelse)
        self.assertIn("self._compatible.set_content", ast.unparse(renderer_branch.orelse))

    def test_known_qtpyvcp_extent_debug_prints_are_silenced(self) -> None:
        def noisy_extent_parser(sj):
            print(len(sj))
            print(sj)

        module = SimpleNamespace(
            PropertiesCanon=SimpleNamespace(rs274_calc_extents=noisy_extent_parser)
        )
        with patch(
            "openmill.integration.qtpyvcp_compat.importlib.import_module", return_value=module
        ):
            self.assertTrue(silence_gcode_properties_debug_output())
            self.assertTrue(module._openmill_debug_output_silenced)
            self.assertIsNone(module.print("ignored"))


if __name__ == "__main__":
    unittest.main()
