"""Alternative integration for Probe Basic installations without user tabs."""

from __future__ import annotations

from probe_basic.probe_basic import ProbeBasic

from openmill.integration.probe_basic import OpenMillConversationalWidget


class CustomProbeBasic(ProbeBasic):
    """Documented custom_config.yml provider; no upstream source is patched."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        tabs = getattr(self, "tabWidget", None)
        if tabs is None:
            raise RuntimeError("Impossible de trouver tabWidget dans cette version de Probe Basic.")
        self.openmill_conversational = OpenMillConversationalWidget(parent=tabs)
        tabs.addTab(self.openmill_conversational, "CONVERSATIONNEL")

