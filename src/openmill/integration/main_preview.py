"""Optional OpenMill preview embedded beside Probe Basic's native backplot."""

from __future__ import annotations

from pathlib import Path

from openmill.adapters.base import MachineAdapter
from openmill.core.engine import BuildResult
from openmill.core.gcode_parser import ParsedGcode, parse_gcode_file
from openmill.core.models import Project
from openmill.integration.bridge import ProgramBridge
from openmill.ui.preview_3d import VtkPreview
from openmill.ui.qt_core import QEvent, QTimer
from openmill.ui.qt_gui import QColor, QTextCursor
from openmill.ui.qt_widgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from openmill.ui.theme import STYLESHEET


def select_probe_basic_main(source_widget) -> bool:
    window = source_widget.window()
    tabs = window.findChild(QWidget, "tabWidget")
    main_tab = window.findChild(QWidget, "main_tab")
    if tabs is None or main_tab is None or not hasattr(tabs, "setCurrentWidget"):
        return False
    tabs.setCurrentWidget(main_tab)
    return True


class ProbeBasicMainPreview(QWidget):
    """Alternative renderer kept as a sibling of Probe Basic's native VTK."""

    def __init__(self, native_preview, adapter: MachineAdapter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("openmillMainPreview")
        self.setStyleSheet(STYLESHEET)
        self._native = native_preview
        self._has_content = False

        # This button is deliberately a floating child of the native backplot:
        # it remains available while OpenMill is hidden without taking space
        # from Probe Basic's horizontal VTK layout.
        self._native_switch = QPushButton("OpenMill", self._native)
        self._native_switch.setObjectName("openmillNativePreviewSwitch")
        self._native_switch.setStyleSheet(STYLESHEET)
        self._native_switch.setToolTip("Afficher l’aperçu animé OpenMill")
        self._native_switch.setMinimumSize(132, 42)
        self._native_switch.setEnabled(False)
        self._native_switch.clicked.connect(lambda _checked=False: self.show_openmill())
        self._native.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 0)
        native_button = QPushButton("Probe Basic")
        native_button.clicked.connect(lambda _checked=False: self.show_native())
        toolbar.addWidget(native_button)
        self.previous_button = QPushButton("◀ Ligne précédente")
        toolbar.addWidget(self.previous_button)
        self._status = QLabel("Aperçu OpenMill")
        self._status.setObjectName("muted")
        toolbar.addWidget(self._status, 1)
        self.next_button = QPushButton("Ligne suivante ▶")
        toolbar.addWidget(self.next_button)
        layout.addLayout(toolbar)
        self._openmill = VtkPreview()
        layout.addWidget(self._openmill, 1)
        self.show_native()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._native and event.type() in (QEvent.Resize, QEvent.Show):
            QTimer.singleShot(0, self._position_native_switch)
        return super().eventFilter(watched, event)

    def _position_native_switch(self) -> None:
        button = self._native_switch
        width = max(button.minimumWidth(), button.sizeHint().width() + 20)
        height = max(button.minimumHeight(), button.sizeHint().height() + 8)
        button.resize(width, height)
        button.move(max(8, self._native.width() - width - 12), 12)
        button.raise_()

    def show_native(self) -> None:
        self.hide()
        self._native.show()
        self._native_switch.show()
        self._position_native_switch()

    def show_openmill(self) -> None:
        if not self._has_content:
            return
        self._native.hide()
        self.show()

    def set_content(self, project: Project, result: BuildResult, *, source: str) -> None:
        self._openmill.set_content(project, result)
        self._status.setText(source)
        self._has_content = True
        self._native_switch.setEnabled(True)
        self.show_openmill()

    def set_motion_index(self, motion_count: int) -> None:
        self._openmill.set_motion_index(motion_count)


class ProbeBasicPreviewController:
    """Attach lazily, follow loaded files and switch Probe Basic to MAIN."""

    def __init__(self, owner, adapter: MachineAdapter, bridge: ProgramBridge) -> None:
        self.owner = owner
        self.adapter = adapter
        self.bridge = bridge
        self.host: ProbeBasicMainPreview | None = None
        self._status: QLabel | None = None
        self._editor = None
        self._parsed: ParsedGcode | None = None
        self._current_signature: tuple[str, int, int] | None = None
        self._timer = QTimer(owner)
        self._timer.setInterval(750)
        self._timer.timeout.connect(self.refresh_loaded_program)
        QTimer.singleShot(0, self.attach)
        QTimer.singleShot(500, self.attach)

    def attach(self) -> bool:
        if self.host is not None:
            return True
        window = self.owner.window()
        native = window.findChild(QWidget, "vtk")
        if native is None:
            return False
        parent = native.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is None:
            return False
        index = layout.indexOf(native)
        if index < 0:
            return False
        self.host = ProbeBasicMainPreview(native, self.adapter, parent)
        if hasattr(layout, "insertWidget"):
            layout.insertWidget(index + 1, self.host)
        else:
            layout.addWidget(self.host)
        self._status = self.host._status
        self.host.previous_button.clicked.connect(lambda _checked=False: self._move_editor_line(-1))
        self.host.next_button.clicked.connect(lambda _checked=False: self._move_editor_line(1))
        self._connect_gcode_editor(window)
        self._compact_main_layout(window)
        self._timer.start()
        self.refresh_loaded_program()
        return True

    def _connect_gcode_editor(self, window) -> None:
        self._editor = window.findChild(QWidget, "gcodetextedit")
        self._style_gcode_editor()
        signal = getattr(self._editor, "cursorPositionChanged", None) if self._editor is not None else None
        if signal is not None:
            signal.connect(self._editor_cursor_changed)

    def _style_gcode_editor(self) -> None:
        if self._editor is None:
            return
        marker = "/* OPENMILL_GCODE_SELECTION */"
        current = self._editor.styleSheet() or ""
        if marker not in current:
            self._editor.setStyleSheet(
                f"""{current}
{marker}
QWidget#gcodetextedit {{
    selection-background-color: #23604c;
    selection-color: #ffffff;
}}
"""
            )
        # GcodeTextEdit exposes these Qt Designer properties. Probe Basic's
        # default current-line background is almost white and clashes with the
        # modern light text, so use a dark high-contrast line instead.
        colors = {
            "setCurrentLineBackground": "#17372f",
            "setMarginCurrentLineBackground": "#23604c",
            "setMarginCurrentLineColor": "#ffffff",
        }
        for setter_name, color in colors.items():
            setter = getattr(self._editor, setter_name, None)
            if callable(setter):
                setter(QColor(color))

    def _editor_cursor_changed(self) -> None:
        if self._editor is None or self.host is None or self._parsed is None:
            return
        line = self._editor.textCursor().blockNumber() + 1
        motion_count = self._parsed.line_motion_counts.get(line, 0)
        self.host.set_motion_index(motion_count)
        self.host.show_openmill()
        if self._status is not None:
            total = max(self._parsed.line_motion_counts, default=0)
            self._status.setText(f"Ligne {line}/{total}")

    def _move_editor_line(self, direction: int) -> None:
        if self._editor is None:
            return
        cursor = self._editor.textCursor()
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.StartOfBlock)
        operation = QTextCursor.Down if direction > 0 else QTextCursor.Up
        if not cursor.movePosition(operation):
            return
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        self._editor.setTextCursor(cursor)
        if hasattr(self._editor, "ensureCursorVisible"):
            self._editor.ensureCursorVisible()
        if hasattr(self._editor, "setFocus"):
            self._editor.setFocus()

    @staticmethod
    def _compact_main_layout(window) -> None:
        splitter = window.findChild(QWidget, "splitter")
        if splitter is not None and hasattr(splitter, "setSizes"):
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(6)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 5)
            available = max(splitter.width(), 1200)
            splitter.setSizes([round(available * 0.38), round(available * 0.62)])

    def show_generated(self, filename: str, project: Project, result: BuildResult) -> None:
        if not self.attach() or self.host is None:
            select_probe_basic_main(self.owner)
            return
        path = Path(filename)
        try:
            stat = path.stat()
            self._current_signature = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        except OSError:
            self._current_signature = None
        self.host.set_content(project, result, source=f"OpenMill · {path.name}")
        try:
            self._parsed = parse_gcode_file(path, tool_lookup=self.adapter.get_tool)
        except (OSError, TypeError, ValueError):
            self._parsed = None
        if self._status is not None:
            self._status.setText(f"OpenMill · {path.name}")
        select_probe_basic_main(self.owner)

    def refresh_loaded_program(self) -> None:
        if self.host is None:
            return
        try:
            current = self.bridge.snapshot().current_program
        except Exception:
            return
        if not current:
            return
        path = Path(current)
        try:
            stat = path.stat()
            signature = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return
        if signature == self._current_signature:
            return
        self._current_signature = signature
        try:
            parsed = parse_gcode_file(path, tool_lookup=self.adapter.get_tool)
        except (OSError, TypeError, ValueError) as error:
            if self._status is not None:
                self._status.setText(f"Aperçu impossible · {error}")
            return
        self._parsed = parsed
        warning = f" · {len(parsed.warnings)} avertissement(s)" if parsed.warnings else ""
        self.host.set_content(parsed.project, parsed.result, source=f"G-code · {path.name}{warning}")
        if self._status is not None:
            self._status.setText(f"G-code · {path.name}{warning}")
