"""Optional OpenMill preview embedded beside Probe Basic's native backplot."""

from __future__ import annotations

import importlib
from pathlib import Path

from openmill.adapters.base import MachineAdapter
from openmill.core.engine import BuildResult
from openmill.core.gcode_parser import ParsedGcode, parse_gcode_file
from openmill.core.models import Project
from openmill.integration.bridge import ProgramBridge
from openmill.ui.preview_3d import VtkPreview
from openmill.ui.qt_core import QEvent, QTimer
from openmill.ui.qt_gui import QColor, QTextCursor, QTextFormat
from openmill.ui.qt_widgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget
from openmill.ui.theme import STYLESHEET


_DARK_SYNTAX_COLORS = {
    "#0f0f0f": "#d6e4f0",  # numbers
    "#800000": "#ff8a80",  # maroon
    "#808000": "#d8d46a",  # olive
    "#008000": "#57d7a8",  # green
    "#800080": "#d291ff",  # purple
    "#a52a2a": "#ff967d",  # brown
    "#008080": "#4dd8d8",  # teal
    "#0000ff": "#7aa7ff",  # blue
    "#000080": "#91b4ff",  # navy
    "#808080": "#aab8c8",  # gray
    "#006400": "#72d49b",  # dark green
    "#76af00": "#9bd35a",  # X axis
    "#0080c0": "#57bde9",  # Y axis
}


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
        self._pending_editor_line: int | None = None
        self._last_preview_motion_count: int | None = None
        self._styled_highlighter = None
        self._editor_timer = QTimer(owner)
        self._editor_timer.setSingleShot(True)
        self._editor_timer.setInterval(75)
        self._editor_timer.timeout.connect(self._apply_pending_editor_line)
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
        # Probe Basic exposes two GcodeTextEdit instances. The unsuffixed one
        # belongs to the FILE editor; MAIN uses gcodetextedit_2. Older layouts
        # may only contain the unsuffixed widget, hence the fallback.
        self._editor = window.findChild(QWidget, "gcodetextedit_2")
        if self._editor is None:
            self._editor = window.findChild(QWidget, "gcodetextedit")
        self._style_gcode_editor()
        # Versions of GcodeTextEdit differ in when focusLine is emitted. Listen
        # to both signals; the single-shot timer below coalesces the duplicate.
        if self._editor is not None:
            for signal_name in ("focusLine", "cursorPositionChanged"):
                signal = getattr(self._editor, signal_name, None)
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
QWidget#gcodetextedit,
QWidget#gcodetextedit_2 {{
    color: #dce7f5;
    background-color: #0d1522;
    selection-background-color: #23604c;
    selection-color: #ffffff;
}}
"""
            )
        # These are Qt properties, not setCurrentLineBackground-style methods.
        # setProperty invokes the Python Property setter used by GcodeTextEdit.
        current_line = self._editor.textCursor().blockNumber() + 1
        colors = {
            "currentLineBackground": "#17372f",
            "marginCurrentLineBackground": "#23604c",
            "marginCurrentLineColor": "#ffffff",
        }
        for property_name, color in colors.items():
            self._editor.setProperty(property_name, QColor(color))
        self._enable_syntax_highlighting()
        setter = getattr(self._editor, "setCurrentLine", None)
        if callable(setter):
            setter(current_line)
        else:
            viewport = getattr(self._editor, "viewport", lambda: None)()
            if viewport is not None:
                viewport.update()
        self._highlight_editor_line(current_line)

    def _enable_syntax_highlighting(self) -> bool:
        """Enable QtPyVCP's native G-code highlighter now and after reloads."""
        if self._editor is None:
            return False
        self._editor.setProperty("syntaxHighlighting", True)
        if hasattr(self._editor, "syntax_highlighting"):
            self._editor.syntax_highlighting = True
        current = getattr(self._editor, "gCodeHighlighter", None)
        if current is not None:
            try:
                if current.document() is self._editor.document():
                    self._apply_dark_syntax_palette()
                    return True
            except (AttributeError, RuntimeError):
                pass
        try:
            module = importlib.import_module(type(self._editor).__module__)
            highlighter_type = getattr(module, "GcodeSyntaxHighlighter")
            self._editor.gCodeHighlighter = highlighter_type(
                self._editor.document(), self._editor.font
            )
        except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
            return False
        self._apply_dark_syntax_palette()
        return True

    def _apply_dark_syntax_palette(self) -> bool:
        """Replace QtPyVCP's light-theme token colors with readable variants."""
        if self._editor is None:
            return False
        highlighter = getattr(self._editor, "gCodeHighlighter", None)
        if highlighter is None:
            return False
        if highlighter is self._styled_highlighter:
            return True
        try:
            for _pattern, text_format in highlighter.rules:
                source = text_format.foreground().color().name().lower()
                replacement = _DARK_SYNTAX_COLORS.get(source)
                if replacement is not None:
                    text_format.setForeground(QColor(replacement))
            highlighter.rehighlight()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
        self._styled_highlighter = highlighter
        return True

    def _highlight_editor_line(self, line: int) -> None:
        """Draw a stable full-width marker independent of QtPyVCP internals."""
        if self._editor is None:
            return
        document = self._editor.document()
        block = document.findBlockByLineNumber(max(0, line - 1))
        if not block.isValid():
            return
        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(block)
        selection.cursor.clearSelection()
        selection.format.setBackground(QColor("#23604c"))
        selection.format.setForeground(QColor("#ffffff"))
        full_width = getattr(QTextFormat, "FullWidthSelection", None)
        if full_width is None:
            full_width = QTextFormat.Property.FullWidthSelection
        selection.format.setProperty(full_width, True)
        # Preserve QtPyVCP's optional search-result markers. Calling
        # setExtraSelections directly is intentional: recent GcodeTextEdit
        # versions lose their native marker whenever setDocument() reloads a
        # program while the cursor remains on the same block number.
        search_markers = list(getattr(self._editor, "highlight_selections", []))
        self._editor.setExtraSelections([selection, *search_markers])

    def _editor_cursor_changed(self, line: int | None = None, *_args) -> None:
        if self._editor is None or self.host is None or self._parsed is None:
            return
        if not isinstance(line, int) or isinstance(line, bool):
            line = self._editor.textCursor().blockNumber() + 1
        self._pending_editor_line = max(1, line)
        # Moving quickly through a large file used to rebuild the complete VTK
        # scene once per cursor event. Coalesce the burst into one render.
        self._editor_timer.start()

    def _apply_pending_editor_line(self) -> None:
        if self.host is None or self._parsed is None or self._pending_editor_line is None:
            return
        line = self._pending_editor_line
        self._pending_editor_line = None
        motion_counts = self._parsed.line_motion_counts
        motion_count = motion_counts.get(line)
        if motion_count is None:
            preceding = (source_line for source_line in motion_counts if source_line <= line)
            nearest = max(preceding, default=None)
            motion_count = motion_counts.get(nearest, 0)
        if motion_count != self._last_preview_motion_count:
            self.host.set_motion_index(motion_count)
            self._last_preview_motion_count = motion_count
        self._apply_dark_syntax_palette()
        self._highlight_editor_line(line)
        self.host.show_openmill()
        if self._status is not None:
            total = max(motion_counts, default=0)
            self._status.setText(f"Ligne {line}/{total}")

    def _move_editor_line(self, direction: int) -> None:
        if self._editor is None:
            return
        current = self._editor.textCursor().blockNumber() + 1
        document = self._editor.document()
        target = max(1, min(document.blockCount(), current + (1 if direction > 0 else -1)))
        if target == current:
            return
        setter = getattr(self._editor, "setCurrentLine", None)
        if callable(setter):
            setter(target)
        else:
            cursor = QTextCursor(document.findBlockByLineNumber(target - 1))
            self._editor.setTextCursor(cursor)
        self._highlight_editor_line(target)
        if hasattr(self._editor, "ensureCursorVisible"):
            self._editor.ensureCursorVisible()
        if hasattr(self._editor, "setFocus"):
            self._editor.setFocus()
        # Queue explicitly as a compatibility fallback for older QtPyVCP
        # versions that do not expose GcodeTextEdit.focusLine.
        self._editor_cursor_changed(target)

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
        self._last_preview_motion_count = None
        try:
            self._parsed = parse_gcode_file(path, tool_lookup=self.adapter.get_tool)
        except (OSError, TypeError, ValueError):
            self._parsed = None
        self._editor_cursor_changed()
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
        self._last_preview_motion_count = None
        warning = f" · {len(parsed.warnings)} avertissement(s)" if parsed.warnings else ""
        self.host.set_content(parsed.project, parsed.result, source=f"G-code · {path.name}{warning}")
        self._editor_cursor_changed()
        if self._status is not None:
            self._status.setText(f"G-code · {path.name}{warning}")
