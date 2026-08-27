"""Qt translation catalogs loaded without modifying Probe Basic sources."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from openmill.integration.runtime import configured_language

_TRANSLATORS: list[object] = []
_LOADED: set[tuple[int, str, str]] = set()


def language_variants(language: str) -> tuple[str, ...]:
    """Return generic then specific suffixes so Qt gives the latter priority."""

    normalized = language.replace("-", "_")
    generic = normalized.split("_", 1)[0]
    return (generic, normalized) if normalized != generic else (generic,)


def translation_directories(
    *,
    environ: Mapping[str, str] | None = None,
    extra: Iterable[str | Path] = (),
) -> tuple[Path, ...]:
    """Discover package, machine and explicitly configured catalog folders."""

    environment = os.environ if environ is None else environ
    candidates = [Path(__file__).resolve().parents[1] / "translations"]
    ini_path = environment.get("INI_FILE_NAME") or environment.get("LINUXCNC_INI")
    if ini_path:
        candidates.append(Path(ini_path).expanduser().resolve().parent / "openmill-translations")
    configured = environment.get("OPENMILL_TRANSLATIONS", "")
    if configured:
        candidates.extend(Path(item).expanduser() for item in configured.split(os.pathsep) if item)
    candidates.extend(Path(item).expanduser() for item in extra)
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return tuple(unique)


def catalog_candidates(language: str, directories: Iterable[Path]) -> tuple[Path, ...]:
    """Return OpenMill, Probe Basic and QtPyVCP catalogs in stable order."""

    paths: list[Path] = []
    for directory in directories:
        for variant in language_variants(language):
            for stem in ("qtpyvcp", "probe_basic", "openmill"):
                candidate = directory / f"{stem}_{variant}.qm"
                if candidate.is_file() and candidate not in paths:
                    paths.append(candidate)
    return tuple(paths)


def install_qt_translations(
    application=None,
    *,
    language: str | None = None,
    directories: Iterable[str | Path] = (),
) -> tuple[Path, ...]:
    """Install available ``.qm`` catalogs on the active Qt application."""

    from openmill.ui.qt import QtCore, QtWidgets

    app = application or QtWidgets.QApplication.instance()
    if app is None:
        return ()
    selected = language or configured_language()
    paths = catalog_candidates(selected, translation_directories(extra=directories))
    installed: list[Path] = []
    for path in paths:
        key = (id(app), selected, str(path))
        if key in _LOADED:
            installed.append(path)
            continue
        translator = QtCore.QTranslator(app)
        if translator.load(str(path)) and app.installTranslator(translator):
            _TRANSLATORS.append(translator)
            _LOADED.add(key)
            installed.append(path)
    return tuple(installed)


try:
    from qtpyvcp.plugins.base_plugins import Plugin
except ImportError:  # pragma: no cover - only imported by a real QtPyVCP host
    Plugin = object


class TranslationPlugin(Plugin):
    """QtPyVCP plugin installing catalogs before Probe Basic loads its windows."""

    def initialise(self) -> None:
        if Plugin is object:
            raise RuntimeError("QtPyVCP est requis pour activer TranslationPlugin.")
        install_qt_translations()
        super().initialise()
