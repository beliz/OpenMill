"""Embeddable widget intended for a future Probe Basic / QtPyVCP tab."""

from __future__ import annotations

from openmill.adapters.linuxcnc import LinuxCNCMachineAdapter
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.models import Project
from openmill.integration.bridge import LinuxCNCProgramBridge, ProgramBridge, SimulatedProgramBridge
from openmill.integration.main_preview import ProbeBasicPreviewController
from openmill.integration.qtpyvcp_compat import silence_gcode_properties_debug_output
from openmill.integration.theme import install_probe_basic_theme
from openmill.integration.workspace_mode import ProbeBasicWorkspaceController
from openmill.ui.qt_core import QTimer
from openmill.ui.workbench import ConversationalWorkbench


class OpenMillConversationalWidget(ConversationalWorkbench):
    """Qt Designer-promotable QWidget; machine integration is deliberately explicit."""

    def __init__(
        self,
        parent=None,
        *,
        simulation: bool = False,
        program_directory: str | None = None,
        program_bridge: ProgramBridge | None = None,
        global_theme: bool = False,
    ) -> None:
        adapter = MockMachineAdapter() if simulation else LinuxCNCMachineAdapter()
        bridge = program_bridge or (SimulatedProgramBridge() if simulation else LinuxCNCProgramBridge())
        super().__init__(
            adapter=adapter,
            project=Project(),
            parent=parent,
            program_bridge=bridge,
            program_directory=program_directory,
            embedded=True,
        )
        self.setObjectName("CONVERSATIONNEL")
        self.setProperty("sidebar", False)
        silence_gcode_properties_debug_output()
        if global_theme:
            install_probe_basic_theme()
        self._main_preview = ProbeBasicPreviewController(self, adapter, bridge)
        self._workspace_mode = ProbeBasicWorkspaceController(self)
        self.program_loaded.connect(self._program_loaded_into_probe_basic)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._workspace_mode.enter)

    def hideEvent(self, event) -> None:
        self._workspace_mode.exit()
        super().hideEvent(event)

    @property
    def program_bridge(self) -> ProgramBridge:
        return self._program_bridge

    def _program_loaded_into_probe_basic(self, filename: str) -> None:
        self._main_preview.show_generated(filename, self.project, self.result)
