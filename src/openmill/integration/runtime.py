"""Qt and LinuxCNC environment discovery without importing graphical modules."""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Callable, Mapping
from configparser import ConfigParser
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path


def binding_candidates(
    *, loaded_modules: set[str] | None = None, requested_api: str | None = None
) -> tuple[str, ...]:
    """Never load a second binding into an already-running Probe Basic process."""
    loaded = set(sys.modules) if loaded_modules is None else loaded_modules
    if "PySide6" in loaded or any(name.startswith("PySide6.") for name in loaded):
        return ("PySide6",)
    if "PyQt5" in loaded or any(name.startswith("PyQt5.") for name in loaded):
        return ("PyQt5",)
    preference = (os.environ.get("QT_API", "") if requested_api is None else requested_api).lower()
    return ("PySide6", "PyQt5") if preference in {"pyside", "pyside6"} else ("PyQt5", "PySide6")


def program_directory(
    ini_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    fallback: str | Path | None = None,
) -> Path:
    """Resolve [DISPLAY] PROGRAM_PREFIX without depending on the linuxcnc module."""
    environment = os.environ if environ is None else environ
    configured = ini_path or environment.get("INI_FILE_NAME") or environment.get("LINUXCNC_INI")
    if configured:
        source = Path(configured).expanduser().resolve()
        if source.is_file():
            parser = ConfigParser(interpolation=None, strict=False)
            parser.read(source, encoding="utf-8")
            prefix = parser.get("DISPLAY", "PROGRAM_PREFIX", fallback="").strip()
            if prefix:
                candidate = Path(os.path.expandvars(prefix)).expanduser()
                return (candidate if candidate.is_absolute() else source.parent / candidate).resolve()
            return (source.parent / "openmill-programs").resolve()
    return Path(fallback or Path.cwd() / "openmill-programs").expanduser().resolve()


def configured_theme(
    *,
    environ: Mapping[str, str] | None = None,
    default: str = "modern",
) -> str:
    """Read the OpenMill theme from the environment or the active machine INI."""

    environment = os.environ if environ is None else environ
    override = environment.get("OPENMILL_THEME", "").strip().lower()
    if override:
        return override
    configured = environment.get("INI_FILE_NAME") or environment.get("LINUXCNC_INI")
    if configured:
        source = Path(configured).expanduser()
        if source.is_file():
            parser = ConfigParser(interpolation=None, strict=False)
            parser.read(source, encoding="utf-8")
            value = parser.get("DISPLAY", "OPENMILL_THEME", fallback=default).strip().lower()
            if value:
                return value
    return default


def configured_language(
    *,
    environ: Mapping[str, str] | None = None,
    default: str = "fr",
) -> str:
    """Read and normalize the OpenMill language from the environment or INI."""

    environment = os.environ if environ is None else environ
    value = environment.get("OPENMILL_LANGUAGE", "").strip()
    configured = environment.get("INI_FILE_NAME") or environment.get("LINUXCNC_INI")
    if not value and configured:
        source = Path(configured).expanduser()
        if source.is_file():
            parser = ConfigParser(interpolation=None, strict=False)
            parser.read(source, encoding="utf-8")
            value = parser.get("DISPLAY", "OPENMILL_LANGUAGE", fallback="").strip()
    if not value:
        value = default
    if value.lower() in {"auto", "system", "default"}:
        value = next(
            (
                environment.get(name, "")
                for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG")
                if environment.get(name, "")
            ),
            default,
        )
    value = value.split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    value = value.replace("-", "_").strip()
    if not value or value.upper() in {"C", "POSIX"}:
        return default
    parts = value.split("_", 1)
    language = parts[0].lower()
    if not language.isalpha() or not 2 <= len(language) <= 3:
        return default
    if len(parts) == 1 or not parts[1]:
        return language
    territory = parts[1].upper()
    return f"{language}_{territory}" if territory.isalpha() else language


@dataclass(frozen=True, slots=True)
class RuntimeReport:
    platform: str
    python: str
    pyqt5: bool
    pyside6: bool
    vtk: bool
    linuxcnc: bool
    qtpyvcp: bool
    probe_basic: bool
    active_qt_binding: str | None
    ini_path: str | None
    program_directory: str

    @property
    def gui_available(self) -> bool:
        return self.pyqt5 or self.pyside6

    @property
    def machine_integration_available(self) -> bool:
        return self.gui_available and self.linuxcnc

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["gui_available"] = self.gui_available
        payload["machine_integration_available"] = self.machine_integration_available
        return payload


def inspect_runtime(
    *,
    module_available: Callable[[str], bool] | None = None,
    loaded_modules: set[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeReport:
    environment = os.environ if environ is None else environ

    def installed(name: str) -> bool:
        if module_available is not None:
            return module_available(name)
        try:
            return find_spec(name) is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            return False

    loaded = set(sys.modules) if loaded_modules is None else loaded_modules
    active = next((name for name in ("PyQt5", "PySide6") if name in loaded or any(item.startswith(f"{name}.") for item in loaded)), None)
    ini = environment.get("INI_FILE_NAME") or environment.get("LINUXCNC_INI")
    return RuntimeReport(
        platform=platform.platform(),
        python=platform.python_version(),
        pyqt5=installed("PyQt5"),
        pyside6=installed("PySide6"),
        vtk=installed("vtk"),
        linuxcnc=installed("linuxcnc"),
        qtpyvcp=installed("qtpyvcp"),
        probe_basic=installed("probe_basic"),
        active_qt_binding=active,
        ini_path=ini,
        program_directory=str(program_directory(environ=environment)),
    )
