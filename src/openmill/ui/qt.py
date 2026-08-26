"""Select the same Qt binding as the host without importing both bindings."""

from __future__ import annotations

import importlib
from openmill.integration.runtime import binding_candidates


def _load_binding():
    failures: list[str] = []
    for binding in binding_candidates():
        try:
            core = importlib.import_module(f"{binding}.QtCore")
            gui = importlib.import_module(f"{binding}.QtGui")
            widgets = importlib.import_module(f"{binding}.QtWidgets")
            return binding, core, gui, widgets
        except ImportError as error:
            failures.append(f"{binding}: {error}")
    raise ImportError(
        "Aucune interface Qt compatible n’a été trouvée. Installe PyQt5 "
        "ou PySide6 dans le même environnement que Probe Basic. "
        + " ; ".join(failures)
    )


QT_BINDING, QtCore, QtGui, QtWidgets = _load_binding()
Signal = QtCore.Signal if QT_BINDING == "PySide6" else QtCore.pyqtSignal
