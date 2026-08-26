"""Probe Basic user tab: copy the openmill directory into USER_TABS_PATH."""

from __future__ import annotations

import os

from openmill.integration.probe_basic import OpenMillConversationalWidget


class UserTab(OpenMillConversationalWidget):
    """Probe Basic discovers this conventional class automatically."""

    def __init__(self, parent=None) -> None:
        simulation = os.environ.get("OPENMILL_SIMULATION", "").lower() in {"1", "true", "yes"}
        theme = os.environ.get("OPENMILL_THEME", "modern").strip().lower()
        global_theme = theme not in {"original", "off", "none", "0", "false"}
        super().__init__(parent=parent, simulation=simulation, global_theme=global_theme)
        self.setObjectName("CONVERSATIONNEL")
        self.setWindowTitle("OpenMill · usinage conversationnel")
        self.setProperty("sidebar", False)
