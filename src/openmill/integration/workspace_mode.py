"""Reversible full-workspace mode inside Probe Basic."""

from __future__ import annotations

from openmill.ui.qt_widgets import QWidget


class ProbeBasicWorkspaceController:
    """Temporarily collapse machine controls while the editor tab is visible.

    Probe Basic's official mill UI keeps the main tab area, a right sidebar and
    a fixed bottom control layout in the central widget.  We discover those
    containers structurally, remember their visibility, and restore it exactly
    when OpenMill loses visibility.  No upstream widget is reparented.
    """

    def __init__(self, workspace: QWidget) -> None:
        self._workspace = workspace
        self._hidden: list[tuple[QWidget, bool]] = []

    @property
    def active(self) -> bool:
        return bool(self._hidden)

    def enter(self) -> None:
        if self._hidden or not self._workspace.isVisible():
            return
        window = self._workspace.window()
        central = window.findChild(QWidget, "centralwidget")
        tabs = window.findChild(QWidget, "tabWidget")
        if central is None or tabs is None or central.layout() is None:
            return
        root = central.layout()
        candidates: list[QWidget] = []

        # First row: main tab area then Probe Basic's right sidebar.
        if root.count() > 0 and root.itemAt(0).layout() is not None:
            top = root.itemAt(0).layout()
            if top.count() > 1 and top.itemAt(1).widget() is not None:
                candidates.append(top.itemAt(1).widget())

        # Second row: fixed machine-control frames (cycle, DRO, overrides…).
        if root.count() > 1 and root.itemAt(1).layout() is not None:
            bottom = root.itemAt(1).layout()
            for index in range(bottom.count()):
                widget = bottom.itemAt(index).widget()
                if widget is not None:
                    candidates.append(widget)

        for widget in candidates:
            if widget is self._workspace or widget.isAncestorOf(self._workspace):
                continue
            visible = widget.isVisible()
            self._hidden.append((widget, visible))
            if visible:
                widget.hide()

        if self._hidden:
            root.invalidate()
            central.updateGeometry()

    def exit(self) -> None:
        hidden, self._hidden = self._hidden, []
        for widget, was_visible in hidden:
            if was_visible:
                widget.show()
        if hidden:
            central = self._workspace.window().findChild(QWidget, "centralwidget")
            if central is not None and central.layout() is not None:
                central.layout().invalidate()
                central.updateGeometry()


__all__ = ["ProbeBasicWorkspaceController"]

