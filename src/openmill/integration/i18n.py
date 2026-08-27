"""Qt translation catalogs loaded without modifying Probe Basic sources."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

from openmill.integration.runtime import configured_language

_TRANSLATORS: list[object] = []
_EVENT_FILTERS: list[object] = []
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
    """Return compiled or editable translation catalogs in stable order."""

    paths: list[Path] = []
    for directory in directories:
        for variant in language_variants(language):
            for stem in ("qtpyvcp", "probe_basic", "openmill"):
                for suffix in (".qm", ".json"):
                    candidate = directory / f"{stem}_{variant}{suffix}"
                    if candidate.is_file() and candidate not in paths:
                        paths.append(candidate)
    return tuple(paths)


def _json_translator(QtCore, application, path: Path):
    """Build a QTranslator backed by an auditable UTF-8 JSON dictionary."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    messages = payload.get("messages", payload)
    contexts = payload.get("contexts", {})
    if not isinstance(messages, dict) or not isinstance(contexts, dict):
        raise ValueError(f"Catalogue de traduction invalide : {path}")

    class JsonTranslator(QtCore.QTranslator):
        def translate(
            self,
            context: str,
            source_text: str,
            disambiguation: str | None = None,
            n: int = -1,
        ) -> str:
            del disambiguation, n
            contextual = contexts.get(context, {})
            if isinstance(contextual, dict) and source_text in contextual:
                return str(contextual[source_text])
            translated = messages.get(source_text, "")
            if not translated and source_text.strip() != source_text:
                translated = messages.get(source_text.strip(), "")
            return str(translated) if translated else ""

    translator = JsonTranslator(application)
    translator.setObjectName(f"OpenMill JSON translator: {path.name}")
    return translator


def translate_text(source_text: str, context: str = "OpenMill") -> str:
    """Translate a Python-created label through the active Qt translators."""

    from openmill.ui.qt import QtCore

    translated = QtCore.QCoreApplication.translate(context, source_text)
    return translated or source_text


def retranslate_widget_tree(root) -> None:
    """Translate an existing Qt widget tree without touching Probe Basic code."""

    from openmill.ui.qt import QtCore, QtGui, QtWidgets

    if root is None:
        return
    try:
        objects = [root, *root.findChildren(QtCore.QObject)]
    except (AttributeError, RuntimeError):
        return
    action_type = getattr(QtWidgets, "QAction", getattr(QtGui, "QAction", ()))
    for item in objects:
        try:
            if isinstance(item, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
                item.setText(translate_text(item.text(), item.metaObject().className()))
                if isinstance(item, QtWidgets.QAbstractButton) and item.text():
                    available = max(1, item.width() - 12)
                    font = item.font()
                    original_size = font.pointSizeF() if font.pointSizeF() > 0 else 10.0
                    while font.pointSizeF() > 7.0 and QtGui.QFontMetrics(font).horizontalAdvance(item.text()) > available:
                        font.setPointSizeF(font.pointSizeF() - 0.5)
                    if font.pointSizeF() < original_size:
                        item.setFont(font)
            elif isinstance(item, QtWidgets.QGroupBox):
                item.setTitle(translate_text(item.title(), item.metaObject().className()))
            elif isinstance(item, QtWidgets.QComboBox):
                for index in range(item.count()):
                    item.setItemText(index, translate_text(item.itemText(index), "QComboBox"))
            elif isinstance(item, QtWidgets.QTabWidget):
                for index in range(item.count()):
                    item.setTabText(index, translate_text(item.tabText(index), "QTabWidget"))
            elif action_type and isinstance(item, action_type):
                item.setText(translate_text(item.text(), "QAction"))

            if isinstance(item, QtWidgets.QLineEdit):
                item.setPlaceholderText(
                    translate_text(item.placeholderText(), item.metaObject().className())
                )
            if isinstance(item, QtWidgets.QWidget):
                item.setWindowTitle(
                    translate_text(item.windowTitle(), item.metaObject().className())
                )
            for getter_name, setter_name in (
                ("toolTip", "setToolTip"),
                ("statusTip", "setStatusTip"),
                ("whatsThis", "setWhatsThis"),
                ("accessibleName", "setAccessibleName"),
                ("accessibleDescription", "setAccessibleDescription"),
            ):
                getter = getattr(item, getter_name, None)
                setter = getattr(item, setter_name, None)
                if getter is not None and setter is not None:
                    current = getter()
                    if current:
                        setter(translate_text(current, item.metaObject().className()))
        except (AttributeError, RuntimeError, TypeError):
            continue


def _install_event_filter(application, QtCore) -> None:
    key = (id(application), "event-filter", "show")
    if key in _LOADED:
        return

    class TranslationEventFilter(QtCore.QObject):
        def eventFilter(self, watched, event) -> bool:
            if event.type() == QtCore.QEvent.Show:
                QtCore.QTimer.singleShot(0, lambda target=watched: retranslate_widget_tree(target))
            return False

    event_filter = TranslationEventFilter(application)
    application.installEventFilter(event_filter)
    _EVENT_FILTERS.append(event_filter)
    _LOADED.add(key)


def install_qt_translations(
    application=None,
    *,
    language: str | None = None,
    directories: Iterable[str | Path] = (),
) -> tuple[Path, ...]:
    """Install available Qt/JSON catalogs on the active Qt application."""

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
        if path.suffix == ".json":
            try:
                translator = _json_translator(QtCore, app, path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            loaded = True
        else:
            translator = QtCore.QTranslator(app)
            loaded = translator.load(str(path))
        if loaded:
            # PyQt5 can return False for a Python QTranslator subclass even
            # though Qt installs it correctly; ownership and retention below
            # are the reliable cross-binding contract.
            app.installTranslator(translator)
            _TRANSLATORS.append(translator)
            _LOADED.add(key)
            installed.append(path)
    _install_event_filter(app, QtCore)
    for widget in app.topLevelWidgets():
        retranslate_widget_tree(widget)
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
