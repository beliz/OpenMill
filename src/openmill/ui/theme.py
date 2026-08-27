"""A compact dark visual language shared by desktop and embedded views."""

from __future__ import annotations

import re


COLORS = {
    "background": "#0b101a",
    "surface": "#111827",
    "surface_alt": "#172133",
    "border": "#233047",
    "text": "#e7edf7",
    "muted": "#90a0b8",
    "accent": "#57d7a8",
    "cyan": "#62c6ff",
    "amber": "#ffbf69",
    "danger": "#ff7383",
}

OPERATION_COLORS = (
    "#57d7a8",
    "#62c6ff",
    "#b69cff",
    "#ffbf69",
    "#ff7383",
    "#64dfdf",
    "#f2a9ff",
)


STYLESHEET = """
QWidget {
    background-color: #0b101a;
    color: #e7edf7;
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    font-size: 12px;
}
QMainWindow, #workbench { background-color: #0b101a; }
QFrame#panel, QFrame#header, QFrame#editor {
    background-color: #111827;
    border: 1px solid #233047;
    border-radius: 12px;
}
QFrame#panel QLabel, QFrame#header QLabel, QFrame#editor QLabel {
    background-color: transparent;
}
QLabel#brand { font-size: 19px; font-weight: 700; color: #f4f7fc; }
QLabel#dialogTitle { font-size: 23px; font-weight: 700; color: #f4f7fc; }
QLabel#subtitle, QLabel#muted { color: #90a0b8; }
QLabel#version {
    color: #718198;
    font-size: 10px;
    font-weight: 600;
    padding-top: 8px;
}
QLabel#section {
    color: #90a0b8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-top: 8px;
}
QLabel#status { color: #57d7a8; font-weight: 600; }
QLabel#pickerCategory { color: #a7b5c8; font-size: 11px; font-weight: 700; padding: 3px 0; }
QLabel#parameterLabel { color: #b9c7d8; font-size: 11px; font-weight: 600; }
QLabel#error { color: #ff7383; }
QLabel#warning { color: #ffbf69; }
QPushButton, QToolButton {
    background-color: #172133;
    border: 1px solid #28374d;
    border-radius: 7px;
    min-height: 30px;
    padding: 0 10px;
    color: #dce7f5;
}
QPushButton:hover, QToolButton:hover { border-color: #57d7a8; background-color: #1c2b39; }
QPushButton:checked, QToolButton:checked {
    background-color: #17362f;
    border-color: #57d7a8;
    color: #76efbf;
}
QPushButton#primary { background-color: #57d7a8; color: #082018; font-weight: 700; }
QPushButton#primary:hover { background-color: #75e8bb; }
QPushButton#addOperation {
    background-color: #15362d;
    border: 1px solid #397d65;
    border-radius: 9px;
    color: #83efc4;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#addOperation:hover { background-color: #1b4639; border-color: #76efbf; }
QPushButton#valueStepper {
    background-color: #182638;
    border: 1px solid #30425a;
    border-radius: 8px;
    color: #cde0ef;
    font-size: 20px;
    font-weight: 600;
    padding: 0;
}
QPushButton#valueStepper:hover { color: #76efbf; border-color: #57d7a8; }
QPushButton#segmentedChoice { min-height: 40px; font-weight: 600; }
QPushButton#danger:hover { border-color: #ff7383; }
QDialog#operationPicker { background-color: #0c121d; }
QFrame#parameterCard {
    background-color: #101a28;
    border: 1px solid #1d2b3d;
    border-radius: 9px;
}
QFrame#parameterCard QLabel { background: transparent; border: none; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0d1522;
    border: 1px solid #27364b;
    border-radius: 6px;
    min-height: 29px;
    padding-left: 8px;
    selection-background-color: #23604c;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #57d7a8;
}
QLineEdit#operationSearch { font-size: 13px; padding-left: 13px; border-radius: 9px; }
QLineEdit#projectName { font-size: 13px; font-weight: 600; padding-left: 10px; }
QLineEdit#scrubValue, QSpinBox#scrubValue, QDoubleSpinBox#scrubValue {
    background-color: #0b131e;
    color: #e9f3fb;
    font-size: 13px;
    font-weight: 600;
    border: 1px solid #2c3e54;
    border-radius: 8px;
    padding: 0 5px;
}
QLineEdit#scrubValue[expressionError="true"] {
    border-color: #ff7383;
    color: #ffb3bd;
}
QFrame#parameterCard[placementDriven="true"] {
    background-color: #0d1420;
    border-color: #172231;
}
QFrame#parameterCard[placementDriven="true"] QLabel,
QFrame#parameterCard[placementDriven="true"] QLineEdit,
QFrame#parameterCard[placementDriven="true"] QPushButton {
    color: #5f6d80;
}
QSlider#touchFader::groove:horizontal {
    background: #25354a;
    height: 8px;
    border-radius: 4px;
}
QSlider#touchFader::sub-page:horizontal { background: #57d7a8; border-radius: 4px; }
QSlider#touchFader::handle:horizontal {
    background: #d8fff0;
    border: 2px solid #57d7a8;
    width: 22px;
    margin: -8px 0;
    border-radius: 11px;
}
QSlider#playbackTimeline::groove:horizontal {
    background: #26364a;
    height: 7px;
    border-radius: 3px;
}
QSlider#playbackTimeline::sub-page:horizontal { background: #62c6ff; border-radius: 3px; }
QSlider#playbackTimeline::handle:horizontal {
    background: #e3f4ff;
    border: 2px solid #62c6ff;
    width: 20px;
    margin: -8px 0;
    border-radius: 10px;
}
QPushButton#playbackButton {
    color: #092019;
    background: #57d7a8;
    font-size: 17px;
    font-weight: 700;
    padding: 0;
}
QComboBox QAbstractItemView {
    background: #172133;
    border: 1px solid #28374d;
    selection-background-color: #234238;
}
QListWidget, QTreeWidget {
    background: #0d1522;
    border: 1px solid #233047;
    border-radius: 8px;
    padding: 5px;
    outline: none;
}
QListWidget::item, QTreeWidget::item {
    border-radius: 6px;
    min-height: 37px;
    padding: 4px 6px;
}
QListWidget::item:selected, QTreeWidget::item:selected { background: #18332e; color: #8cf0c7; }
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected { background: #172133; }
QPlainTextEdit {
    background: #0a111b;
    border: 1px solid #233047;
    border-radius: 8px;
    color: #99d3e6;
    font-family: "Cascadia Code", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 11px;
    padding: 7px;
}
QGraphicsView { background: #0b101a; border: none; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 13px; }
QScrollBar::handle:vertical { background: #30405a; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #172133; border: 1px solid #30405a; padding: 5px; }
QMenu::item { padding: 7px 22px; border-radius: 4px; }
QMenu::item:selected { background: #234238; }
QMenu::separator { height: 1px; background: #30405a; margin: 5px 8px; }
QSplitter::handle { background: transparent; }
QToolTip { color: #edf4fc; background: #172133; border: 1px solid #30405a; padding: 4px; }
"""


# Appended to Probe Basic's existing stylesheet. Per-widget safety rules from
# Probe Basic remain authoritative (notably E-STOP's live red/grey rule).
PROBE_BASIC_MODERN_STYLESHEET = """
QWidget {
    background-color: #0b101a;
    color: #e7edf7;
}
QMainWindow, QMainWindow > QWidget, QStatusBar {
    background-color: #0b101a;
    color: #e7edf7;
}
QMenuBar {
    background: #111827;
    color: #cbd7e7;
    border-bottom: 1px solid #233047;
    spacing: 4px;
}
QMenuBar::item { padding: 5px 9px; background: transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #1e2b3d; color: #ffffff; }
QMenu {
    background: #172133;
    color: #e7edf7;
    border: 1px solid #30405a;
    padding: 5px;
}
QMenu::item { padding: 7px 22px; border-radius: 4px; }
QMenu::item:selected { background: #234238; color: #8cf0c7; }
QFrame {
    color: #dce7f5;
    border-color: #34445a;
}
QLabel { color: #e1e9f4; background-color: transparent; }
QPushButton, QToolButton {
    color: #e8eef7;
    background: #182334;
    border: 1px solid #3a4a61;
    border-radius: 6px;
}
QPushButton:hover, QToolButton:hover {
    background: #223147;
    border-color: #65d9ae;
}
QPushButton:pressed, QToolButton:pressed { background: #101a28; }
QPushButton:checked, QToolButton:checked {
    background: #174638;
    border-color: #57d7a8;
    color: #9af2cf;
}
QPushButton:disabled, QToolButton:disabled {
    background: #111823;
    border-color: #273243;
    color: #68768a;
}
QPushButton#exit_button {
    color: white;
    border: 2px solid #ff7383;
    font-weight: 800;
}
QPushButton#power_button:checked {
    background: #174638;
    border: 2px solid #57d7a8;
    color: #b6ffe1;
}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    color: #edf4fc;
    background: #0d1522;
    border: 1px solid #33445b;
    border-radius: 5px;
    selection-background-color: #23604c;
    selection-color: #ffffff;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #57d7a8; }
QComboBox QAbstractItemView {
    color: #edf4fc;
    background: #172133;
    border: 1px solid #33445b;
    selection-background-color: #234238;
}
QTabWidget::pane { background: #0f1724; border: 1px solid #26364a; }
QTabBar::tab {
    color: #aebdd0;
    background: #131d2b;
    border: 1px solid #2b3a50;
    border-radius: 5px;
    padding: 5px 12px;
    margin: 2px;
}
QTabBar::tab:hover { color: #ffffff; border-color: #4c647e; }
QTabBar::tab:selected { color: #9af2cf; background: #174638; border-color: #57d7a8; }
QTableView, QTreeView, QListView, QListWidget {
    alternate-background-color: #101a28;
    background: #0d1522;
    color: #e0e9f5;
    gridline-color: #27364b;
    border: 1px solid #2b3b51;
    selection-background-color: #234238;
    selection-color: #a7f5d6;
}
QHeaderView::section {
    color: #b9c7d8;
    background: #182334;
    border: none;
    border-right: 1px solid #2b3b51;
    border-bottom: 1px solid #2b3b51;
    padding: 5px;
    font-weight: 700;
}
QSlider::groove:horizontal { background: #26364a; height: 7px; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #57d7a8; border-radius: 3px; }
QSlider::handle:horizontal {
    background: #e3fff4;
    border: 2px solid #57d7a8;
    width: 18px;
    margin: -7px 0;
    border-radius: 9px;
}
QProgressBar {
    color: #eaf4ff;
    background: #101925;
    border: 1px solid #324258;
    border-radius: 5px;
    text-align: center;
}
QProgressBar::chunk { background: #57d7a8; border-radius: 4px; }
QScrollBar:vertical { background: #0e1622; width: 12px; }
QScrollBar::handle:vertical { background: #3b4d66; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { color: #ffffff; background: #172133; border: 1px solid #57d7a8; padding: 5px; }
"""


def compose_probe_basic_theme(existing_stylesheet: str) -> str:
    """Append one idempotent theme block to the host stylesheet."""
    marker = "/* OPENMILL_PROBE_BASIC_THEME */"
    if marker in existing_stylesheet:
        return existing_stylesheet
    return f"{existing_stylesheet}\n{marker}\n{PROBE_BASIC_MODERN_STYLESHEET}"


_SAFE_OBJECT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def probe_basic_widget_override(
    class_names: set[str] | tuple[str, ...],
    *,
    object_name: str = "",
    rules: str = "",
) -> str:
    """Return a local override for legacy Probe Basic widget styles.

    Probe Basic's UI contains many per-widget stylesheets, which take precedence
    over an application stylesheet.  This block is appended locally and uses the
    object id when possible. Widgets whose appearance is driven by QtPyVCP rules
    are deliberately left untouched (E-STOP in particular).
    """
    names = set(class_names)
    compact_rules = "".join(str(rules).lower().replace("_", " ").split())
    if (
        object_name == "exit_button"
        or object_name.startswith("openmill")
        or "stylesheet" in compact_rules
        or any(token in name.lower() for name in names for token in ("vtk", "backplot", "opengl", "video"))
    ):
        return ""

    def selector(base: str) -> str:
        if object_name and _SAFE_OBJECT_NAME.fullmatch(object_name):
            return f"{base}#{object_name}"
        return base

    marker = "/* OPENMILL_WIDGET_THEME */"
    if names & {"QPushButton", "QToolButton", "ActionButton"}:
        base = "QToolButton" if "QToolButton" in names else "QPushButton"
        target = selector(base)
        return f"""{marker}
{target} {{ color: #e8eef7; background: #182334; border: 1px solid #3a4a61;
    border-radius: 6px; }}
{target}:hover {{ background: #223147; border-color: #65d9ae; }}
{target}:pressed {{ background: #101a28; }}
{target}:checked {{ background: #174638; border-color: #57d7a8; color: #9af2cf; }}
{target}:disabled {{ background: #111823; border-color: #273243; color: #68768a; }}
"""

    if names & {"QLineEdit", "QPlainTextEdit", "QTextEdit", "QSpinBox", "QDoubleSpinBox", "QComboBox"}:
        base = next(name for name in ("QLineEdit", "QPlainTextEdit", "QTextEdit", "QSpinBox", "QDoubleSpinBox", "QComboBox") if name in names)
        target = selector(base)
        return f"""{marker}
{target} {{ color: #edf4fc; background: #0d1522; border: 1px solid #33445b;
    border-radius: 5px; selection-background-color: #23604c; }}
{target}:focus {{ border-color: #57d7a8; }}
"""

    if "QSlider" in names:
        target = selector("QSlider")
        return f"""{marker}
{target} {{ background: transparent; }}
{target}::groove:horizontal {{ background: #26364a; height: 7px; border-radius: 3px; }}
{target}::sub-page:horizontal {{ background: #57d7a8; border-radius: 3px; }}
{target}::handle:horizontal {{ background: #e3fff4; border: 2px solid #57d7a8;
    width: 18px; margin: -7px 0; border-radius: 9px; }}
"""

    if names & {"QTableView", "QTreeView", "QListView", "QListWidget", "QTableWidget", "QTreeWidget"}:
        base = next(name for name in ("QTableView", "QTreeView", "QListView", "QListWidget", "QTableWidget", "QTreeWidget") if name in names)
        target = selector(base)
        return f"""{marker}
{target} {{ alternate-background-color: #101a28; background: #0d1522; color: #e0e9f5;
    gridline-color: #27364b; border: 1px solid #2b3b51;
    selection-background-color: #234238; selection-color: #a7f5d6; }}
"""

    if "QProgressBar" in names:
        target = selector("QProgressBar")
        return f"""{marker}
{target} {{ color: #eaf4ff; background: #101925; border: 1px solid #324258;
    border-radius: 5px; text-align: center; }}
{target}::chunk {{ background: #57d7a8; border-radius: 4px; }}
"""

    if "QTabBar" in names:
        target = selector("QTabBar")
        return f"""{marker}
{target} {{ background: #0f1724; color: #aebdd0; }}
{target}::tab {{ color: #aebdd0; background: #131d2b; border: 1px solid #2b3a50;
    border-radius: 5px; margin: 2px; }}
{target}::tab:selected {{ color: #9af2cf; background: #174638; border-color: #57d7a8; }}
"""

    if "QLabel" in names:
        target = selector("QLabel")
        return f"{marker}\n{target} {{ color: #e1e9f4; background: transparent; }}\n"

    if "QGroupBox" in names:
        target = selector("QGroupBox")
        return f"""{marker}
{target} {{ color: #dce7f5; background: #111827; border: 1px solid #2b3b51;
    border-radius: 7px; }}
"""

    if names & {"QFrame", "QScrollArea", "QStackedWidget"}:
        base = next(name for name in ("QFrame", "QScrollArea", "QStackedWidget") if name in names)
        target = selector(base)
        return f"{marker}\n{target} {{ color: #dce7f5; background: #111827; border-color: #2b3b51; }}\n"

    if "QWidget" in names:
        target = selector("QWidget")
        return f"{marker}\n{target} {{ color: #e7edf7; background: #0b101a; }}\n"
    return ""
