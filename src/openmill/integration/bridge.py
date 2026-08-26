"""Safe program handoff: loading a file never starts a machine or spindle."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import tempfile
from typing import Callable, Protocol
import unicodedata

from openmill.adapters.base import MachineAdapter
from openmill.core.engine import build_project
from openmill.core.gcode import generate_gcode
from openmill.core.models import Project
from openmill.integration.runtime import program_directory


class ProgramLoadError(RuntimeError):
    """The requested program cannot safely be handed to the host."""


@dataclass(frozen=True, slots=True)
class MachineSnapshot:
    connected: bool
    estop: bool
    enabled: bool
    interpreter_idle: bool
    homed: bool
    work_offset: str
    current_program: str | None = None

    @property
    def can_load_program(self) -> bool:
        return self.connected and not self.estop and self.interpreter_idle


class ProgramBridge(Protocol):
    def snapshot(self) -> MachineSnapshot: ...

    def load_program(self, filename: str | Path) -> Path: ...


def _validate_program(filename: str | Path) -> Path:
    program = Path(filename).expanduser().resolve()
    if program.suffix.lower() not in {".ngc", ".nc"}:
        raise ProgramLoadError("Seuls les programmes .ngc et .nc peuvent être chargés.")
    if not program.is_file():
        raise ProgramLoadError(f"Le programme n’existe pas : {program}")
    if program.stat().st_size <= 0:
        raise ProgramLoadError("Le programme généré est vide.")
    return program


class SimulatedProgramBridge:
    """Observable in-memory host for Windows and LinuxCNC-free integration tests."""

    def __init__(self, *, estop: bool = False, interpreter_idle: bool = True) -> None:
        self.estop = estop
        self.interpreter_idle = interpreter_idle
        self.loaded_programs: list[Path] = []

    def snapshot(self) -> MachineSnapshot:
        return MachineSnapshot(
            connected=True,
            estop=self.estop,
            enabled=True,
            interpreter_idle=self.interpreter_idle,
            homed=True,
            work_offset="G54",
            current_program=str(self.loaded_programs[-1]) if self.loaded_programs else None,
        )

    def load_program(self, filename: str | Path) -> Path:
        program = _validate_program(filename)
        state = self.snapshot()
        if state.estop:
            raise ProgramLoadError("Chargement refusé : arrêt d’urgence actif.")
        if not state.interpreter_idle:
            raise ProgramLoadError("Chargement refusé : un programme est déjà en cours.")
        self.loaded_programs.append(program)
        return program


def _qtpyvcp_loader() -> Callable[[str], object] | None:
    try:
        actions = importlib.import_module("qtpyvcp.actions.program_actions")
    except ImportError:
        return None
    loader = getattr(actions, "load", None)
    return loader if callable(loader) else None


class LinuxCNCProgramBridge:
    """Prefer QtPyVCP's load action so the host backplot stays synchronized."""

    def __init__(self, linuxcnc_module=None, *, loader: Callable[[str], object] | None = None) -> None:
        if linuxcnc_module is None:
            try:
                linuxcnc_module = importlib.import_module("linuxcnc")
            except ImportError as error:
                raise ProgramLoadError("LinuxCNC est absent de cet environnement Python.") from error
        self._linuxcnc = linuxcnc_module
        try:
            self._status = linuxcnc_module.stat()
            self._command = linuxcnc_module.command()
        except Exception as error:
            raise ProgramLoadError(f"Connexion LinuxCNC impossible : {error}") from error
        self._loader = loader if loader is not None else _qtpyvcp_loader()

    def snapshot(self) -> MachineSnapshot:
        try:
            self._status.poll()
        except Exception as error:
            raise ProgramLoadError(f"Impossible de lire l’état LinuxCNC : {error}") from error
        joints = tuple(getattr(self._status, "homed", ()))
        offset_index = int(getattr(self._status, "g5x_index", 1) or 1)
        offsets = ("G54", "G55", "G56", "G57", "G58", "G59", "G59.1", "G59.2", "G59.3")
        work_offset = offsets[offset_index - 1] if 1 <= offset_index <= len(offsets) else "G54"
        current = getattr(self._status, "file", None)
        return MachineSnapshot(
            connected=True,
            estop=bool(getattr(self._status, "estop", False)),
            enabled=bool(getattr(self._status, "enabled", False)),
            interpreter_idle=getattr(self._status, "interp_state", None)
            == getattr(self._linuxcnc, "INTERP_IDLE", object()),
            homed=bool(joints) and all(bool(value) for value in joints),
            work_offset=work_offset,
            current_program=str(current) if current else None,
        )

    def load_program(self, filename: str | Path) -> Path:
        program = _validate_program(filename)
        state = self.snapshot()
        if state.estop:
            raise ProgramLoadError("Chargement refusé : arrêt d’urgence actif.")
        if not state.interpreter_idle:
            raise ProgramLoadError("Chargement refusé : l’interpréteur LinuxCNC n’est pas au repos.")
        try:
            if self._loader is not None:
                self._loader(str(program))
            else:
                self._command.program_open(str(program))
        except Exception as error:
            raise ProgramLoadError(f"LinuxCNC a refusé le programme : {error}") from error
        return program


def project_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").lower()[:72]
    return f"openmill-{slug or 'programme'}.ngc"


def prepare_program(
    project: Project,
    adapter: MachineAdapter,
    *,
    output_directory: str | Path | None = None,
) -> Path:
    """Validate operations then atomically publish one clearly named G-code file."""
    result = build_project(project, adapter)
    if result.errors:
        details = "; ".join(issue.message for issue in result.errors)
        raise ProgramLoadError(f"Le projet contient des opérations invalides : {details}")
    if not result.toolpaths:
        raise ProgramLoadError("Ajoute au moins une opération valide avant le chargement.")
    directory = Path(output_directory).expanduser().resolve() if output_directory else program_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / project_filename(project.name)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="ascii", newline="\n", prefix=".openmill-", suffix=".tmp", dir=directory, delete=False
        ) as temporary:
            temporary.write(generate_gcode(project, result.toolpaths))
            temporary_path = Path(temporary.name)
        try:
            temporary_path.replace(destination)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    except OSError as error:
        raise ProgramLoadError(f"Impossible de créer le programme LinuxCNC : {error}") from error
    return destination


def prepare_and_load_program(
    project: Project,
    adapter: MachineAdapter,
    bridge: ProgramBridge,
    *,
    output_directory: str | Path | None = None,
) -> Path:
    return bridge.load_program(prepare_program(project, adapter, output_directory=output_directory))
