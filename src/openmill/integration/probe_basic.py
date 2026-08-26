"""Embeddable widget intended for a future Probe Basic / QtPyVCP tab."""

from __future__ import annotations

from openmill.adapters.linuxcnc import LinuxCNCMachineAdapter
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.models import Project
from openmill.integration.bridge import LinuxCNCProgramBridge, ProgramBridge, SimulatedProgramBridge
from openmill.integration.main_preview import ProbeBasicPreviewController
from openmill.integration.qtpyvcp_compat import silence_gcode_properties_debug_output
from openmill.integration.theme import (
    install_probe_basic_theme,
    probe_basic_theme_active,
    restore_probe_basic_theme,
)
from openmill.ui.qt_widgets import QPushButton
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
        self._theme_button = QPushButton()
        self._theme_button.setObjectName("themeToggle")
        self._theme_button.setCheckable(True)
        self._theme_button.setToolTip("Basculer le thème global de Probe Basic")
        self._theme_button.clicked.connect(self._toggle_global_theme)
        self._header.layout().insertWidget(self._header.layout().count() - 1, self._theme_button)
        self._update_theme_button()
        self._main_preview = ProbeBasicPreviewController(self, adapter, bridge)
        self.program_loaded.connect(self._program_loaded_into_probe_basic)

    @property
    def program_bridge(self) -> ProgramBridge:
        return self._program_bridge

    def _toggle_global_theme(self) -> None:
        if probe_basic_theme_active():
            restore_probe_basic_theme()
        else:
            install_probe_basic_theme()
        self._update_theme_button()

    def _update_theme_button(self) -> None:
        active = probe_basic_theme_active()
        self._theme_button.setText("Thème PB · moderne" if active else "Thème PB · original")
        self._theme_button.setChecked(active)

    def _program_loaded_into_probe_basic(self, filename: str) -> None:
        self._main_preview.show_generated(filename, self.project, self.result)
