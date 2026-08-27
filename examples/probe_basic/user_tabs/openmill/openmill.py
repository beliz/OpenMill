"""Probe Basic user tab: copy the openmill directory into USER_TABS_PATH."""

from __future__ import annotations

import os

from openmill.integration.i18n import install_qt_translations
from openmill.integration.probe_basic import OpenMillConversationalWidget
from openmill.integration.runtime import configured_theme


class UserTab(OpenMillConversationalWidget):
    """Probe Basic discovers this conventional class automatically."""

    def __init__(self, parent=None) -> None:
        install_qt_translations()
        simulation = os.environ.get("OPENMILL_SIMULATION", "").lower() in {"1", "true", "yes"}
        theme = configured_theme()
        global_theme = theme not in {"original", "off", "none", "0", "false"}
        super().__init__(parent=parent, simulation=simulation, global_theme=global_theme)
        self.setObjectName("CONVERSATIONNEL")
        self.setWindowTitle("OpenMill · usinage conversationnel")
        self.setProperty("sidebar", False)
