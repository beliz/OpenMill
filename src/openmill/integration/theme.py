"""Opt-in application theme shared by Probe Basic and OpenMill."""

from __future__ import annotations

from openmill.ui.qt_core import QTimer
from openmill.ui.qt_widgets import QApplication, QWidget
from openmill.ui.theme import compose_probe_basic_theme, probe_basic_widget_override


_ORIGINAL_STYLE_PROPERTY = "openmillOriginalApplicationStyleSheet"
_THEME_ACTIVE_PROPERTY = "openmillGlobalThemeActive"
_ORIGINAL_WIDGET_STYLE_PROPERTY = "openmillOriginalWidgetStyleSheet"
_WIDGET_THEME_ACTIVE_PROPERTY = "openmillWidgetThemeActive"

_QT_CLASSES = (
    "QPushButton", "QToolButton", "ActionButton", "QLineEdit", "QPlainTextEdit",
    "QTextEdit", "QSpinBox", "QDoubleSpinBox", "QComboBox", "QSlider",
    "QTableView", "QTreeView", "QListView", "QListWidget", "QTableWidget",
    "QTreeWidget", "QProgressBar", "QTabBar", "QLabel", "QGroupBox", "QFrame",
    "QScrollArea", "QStackedWidget", "QWidget",
)


def _is_openmill_descendant(widget) -> bool:
    current = widget
    while current is not None:
        name = current.objectName() if hasattr(current, "objectName") else ""
        if name in {"workbench", "CONVERSATIONNEL"} or str(name).startswith("openmill"):
            return True
        current = current.parentWidget() if hasattr(current, "parentWidget") else None
    return False


def _application_widgets(app) -> list:
    widgets = []
    seen = set()
    for top in app.topLevelWidgets():
        for widget in (top, *top.findChildren(QWidget)):
            identity = id(widget)
            if identity not in seen:
                widgets.append(widget)
                seen.add(identity)
    return widgets


def apply_probe_basic_widget_theme(application=None) -> int:
    """Override legacy inline styles while preserving machine-driven widgets."""
    app = application or QApplication.instance()
    if app is None or not bool(app.property(_THEME_ACTIVE_PROPERTY)):
        return 0
    changed = 0
    for widget in _application_widgets(app):
        if _is_openmill_descendant(widget) or bool(widget.property(_WIDGET_THEME_ACTIVE_PROPERTY)):
            continue
        classes = {name for name in _QT_CLASSES if widget.inherits(name)}
        meta = widget.metaObject()
        if meta is not None:
            classes.add(str(meta.className()))
        override = probe_basic_widget_override(
            classes,
            object_name=str(widget.objectName() or ""),
            rules=str(widget.property("rules") or ""),
        )
        if not override:
            continue
        original = widget.styleSheet() or ""
        widget.setProperty(_ORIGINAL_WIDGET_STYLE_PROPERTY, original)
        widget.setStyleSheet(f"{original}\n{override}")
        widget.setProperty(_WIDGET_THEME_ACTIVE_PROPERTY, True)
        changed += 1
    return changed


def restore_probe_basic_widget_theme(application=None) -> int:
    app = application or QApplication.instance()
    if app is None:
        return 0
    changed = 0
    for widget in _application_widgets(app):
        if not bool(widget.property(_WIDGET_THEME_ACTIVE_PROPERTY)):
            continue
        original = widget.property(_ORIGINAL_WIDGET_STYLE_PROPERTY)
        widget.setStyleSheet(original if isinstance(original, str) else "")
        widget.setProperty(_WIDGET_THEME_ACTIVE_PROPERTY, False)
        changed += 1
    return changed


def install_probe_basic_theme(application=None) -> bool:
    """Append the modern theme once while retaining an exact restore point."""
    app = application or QApplication.instance()
    if app is None:
        return False
    if bool(app.property(_THEME_ACTIVE_PROPERTY)):
        return False
    existing = app.styleSheet() or ""
    app.setProperty(_ORIGINAL_STYLE_PROPERTY, existing)
    app.setStyleSheet(compose_probe_basic_theme(existing))
    app.setProperty(_THEME_ACTIVE_PROPERTY, True)
    # User tabs are created during Probe Basic's UI setup. Two deferred passes
    # cover the current window and widgets finalized just after this callback.
    QTimer.singleShot(0, lambda: apply_probe_basic_widget_theme(app))
    QTimer.singleShot(250, lambda: apply_probe_basic_widget_theme(app))
    return True


def restore_probe_basic_theme(application=None) -> bool:
    """Restore exactly the stylesheet captured before OpenMill changed it."""
    app = application or QApplication.instance()
    if app is None or not bool(app.property(_THEME_ACTIVE_PROPERTY)):
        return False
    restore_probe_basic_widget_theme(app)
    original = app.property(_ORIGINAL_STYLE_PROPERTY)
    app.setStyleSheet(original if isinstance(original, str) else "")
    app.setProperty(_THEME_ACTIVE_PROPERTY, False)
    return True


def probe_basic_theme_active(application=None) -> bool:
    app = application or QApplication.instance()
    return bool(app is not None and app.property(_THEME_ACTIVE_PROPERTY))
