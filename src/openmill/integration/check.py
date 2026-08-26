"""Small integration diagnostic runnable without Qt, VTK or LinuxCNC."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from openmill import __version__
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import create_demo_project
from openmill.integration.bridge import SimulatedProgramBridge, prepare_and_load_program
from openmill.integration.runtime import inspect_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostic d’intégration Probe Basic / LinuxCNC.")
    parser.add_argument("--json", action="store_true", help="Produire un diagnostic JSON.")
    parser.add_argument("--smoke-test", action="store_true", help="Tester génération et chargement simulé.")
    options = parser.parse_args(argv)
    report = inspect_runtime().to_dict()
    report["openmill_version"] = __version__
    if options.smoke_test:
        with tempfile.TemporaryDirectory(prefix="openmill-smoke-") as directory:
            bridge = SimulatedProgramBridge()
            generated = prepare_and_load_program(
                create_demo_project(), MockMachineAdapter(), bridge, output_directory=directory
            )
            report["smoke_test"] = {
                "passed": len(bridge.loaded_programs) == 1,
                "filename": generated.name,
                "bytes": generated.stat().st_size,
                "machine_started": False,
            }
    if options.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"OpenMill {__version__} · diagnostic Probe Basic")
    for label, key in (
        ("Python", "python"),
        ("PyQt5", "pyqt5"),
        ("PySide6", "pyside6"),
        ("VTK", "vtk"),
        ("LinuxCNC", "linuxcnc"),
        ("QtPyVCP", "qtpyvcp"),
        ("Probe Basic", "probe_basic"),
        ("Qt actif", "active_qt_binding"),
        ("Configuration INI", "ini_path"),
        ("Dossier programmes", "program_directory"),
    ):
        value = report[key]
        formatted = "oui" if value is True else "non" if value is False else value or "—"
        print(f"  {label:<20} {formatted}")
    if options.smoke_test:
        smoke = report["smoke_test"]
        print(f"  Test simulé          OK · {smoke['filename']} · {smoke['bytes']} octets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

