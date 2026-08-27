"""Standalone desktop shell around the reusable conversational workbench."""

from __future__ import annotations

import sys

from openmill.ui.qt_core import QLocale, Qt
from openmill.ui.qt_widgets import QApplication, QMainWindow

from openmill.adapters.mock import MockMachineAdapter
from openmill import __version__
from openmill.core.engine import create_demo_project
from openmill.core.models import Project
from openmill.integration.i18n import install_qt_translations, retranslate_widget_tree
from openmill.integration.runtime import configured_language
from openmill.ui.theme import STYLESHEET
from openmill.ui.workbench import ConversationalWorkbench


class OpenMillWindow(QMainWindow):
    def __init__(self, *, project_path: str | None = None, demo: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(f"OpenMill Conversational {__version__} · Fraisage CNC")
        self.resize(1540, 940)
        self.setMinimumSize(1090, 720)
        project = create_demo_project() if demo or project_path is None else Project()
        self.workbench = ConversationalWorkbench(MockMachineAdapter(), project)
        self.setCentralWidget(self.workbench)
        menu = self.menuBar().addMenu("Fichier")
        for action in self.workbench.create_file_actions(self):
            menu.addAction(action)
        menu.addSeparator()
        export = menu.addAction("Exporter le G-code…")
        export.triggered.connect(lambda: self.workbench.export_gcode())
        if project_path:
            self.workbench.open_project(project_path)


def run_application(*, project_path: str | None = None, demo: bool = False) -> int:
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("OpenMill Conversational")
    app.setOrganizationName("OpenMill")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    language = configured_language()
    locale = QLocale(language)
    if locale.language() == QLocale.C:
        locale = QLocale(QLocale.French, QLocale.France)
    QLocale.setDefault(locale)
    install_qt_translations(app, language=language)
    window = OpenMillWindow(project_path=project_path, demo=demo)
    retranslate_widget_tree(window)
    window.show()
    return app.exec()
