"""Embeddable conversational workspace independent of its host window."""

from __future__ import annotations

from pathlib import Path

from openmill.ui.qt_core import QLocale, Qt, QTimer, pyqtSignal
from openmill.ui.qt_gui import QKeySequence
from openmill.ui.qt_widgets import (
    QAbstractItemView,
    QAction,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from openmill.adapters.base import MachineAdapter
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import BuildResult, build_project, create_demo_project
from openmill.core.gcode import generate_gcode
from openmill.core.models import OperationRecord, OriginMode, Project
from openmill.core.project_io import load_project, save_project
from openmill.core.registry import registry
from openmill.integration.bridge import ProgramBridge, ProgramLoadError, prepare_and_load_program
from openmill.ui.operation_form import OperationForm
from openmill.ui.operation_picker import OperationPickerDialog
from openmill.ui.preview_2d import VectorPreview
from openmill.ui.theme import STYLESHEET


def _panel() -> QFrame:
    panel = QFrame()
    panel.setObjectName("panel")
    return panel


class ConversationalWorkbench(QWidget):
    """Reusable QWidget: standalone application and future Probe Basic tab."""

    project_changed = pyqtSignal()
    program_loaded = pyqtSignal(str)

    def __init__(
        self,
        adapter: MachineAdapter | None = None,
        project: Project | None = None,
        parent=None,
        *,
        program_bridge: ProgramBridge | None = None,
        program_directory: str | Path | None = None,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("workbench")
        self.setStyleSheet(STYLESHEET)
        self._embedded = embedded
        self._adapter = adapter or MockMachineAdapter()
        self._program_bridge = program_bridge
        self._program_directory = program_directory
        self._project = project or create_demo_project()
        self._result = BuildResult()
        self._path: Path | None = None
        self._plane = "XY"
        self._preview_3d = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self._rebuild)

        outer = QVBoxLayout(self)
        margin = 6 if embedded else 16
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(6 if embedded else 11)
        outer.addWidget(self._create_header())

        columns = QSplitter(Qt.Horizontal)
        columns.setChildrenCollapsible(False)
        columns.setHandleWidth(8)
        columns.addWidget(self._create_operations_panel())
        columns.addWidget(self._create_preview_panel())
        columns.addWidget(self._create_parameters_panel())
        columns.setStretchFactor(0, 0)
        columns.setStretchFactor(1, 1)
        columns.setStretchFactor(2, 0)
        columns.setSizes([250, 660, 330])
        outer.addWidget(columns, 1)
        self._gcode_panel = self._create_gcode_panel()
        outer.addWidget(self._gcode_panel)

        self._populate_stock()
        self._populate_operations()
        self._rebuild()

    @property
    def project(self) -> Project:
        return self._project

    @property
    def result(self) -> BuildResult:
        return self._result

    @property
    def generated_gcode(self) -> str:
        return generate_gcode(self._project, self._result.toolpaths)

    def _create_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 14, 10)
        if self._embedded:
            layout.setContentsMargins(10, 4, 10, 4)
            header.setMaximumHeight(44)
        brand = QLabel("◈  OPENMILL")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        subtitle = QLabel("CONVERSATIONNEL")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(18)
        self._project_name = QLineEdit(self._project.name)
        self._project_name.setMaximumWidth(350)
        self._project_name.setPlaceholderText("Nom de la pièce")
        self._project_name.textChanged.connect(self._rename_project)
        layout.addWidget(self._project_name)
        layout.addStretch()
        self._machine_status = QLabel(f"●  {self._adapter.display_name}")
        self._machine_status.setObjectName("status")
        layout.addWidget(self._machine_status)
        self._header = header
        return header

    def _stock_spinbox(self, value: float) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setLocale(QLocale(QLocale.French, QLocale.France))
        widget.setRange(0.1, 10_000)
        widget.setDecimals(1)
        widget.setSuffix(" mm")
        widget.setValue(value)
        widget.valueChanged.connect(self._stock_changed)
        return widget

    def _create_operations_panel(self) -> QWidget:
        panel = _panel()
        panel.setMinimumWidth(215)
        panel.setMaximumWidth(370)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8 if self._embedded else 13, 6 if self._embedded else 12, 8 if self._embedded else 13, 6 if self._embedded else 12)

        title = QLabel("BRUT")
        title.setObjectName("section")
        layout.addWidget(title)
        dimensions = QHBoxLayout()
        self._stock_width = self._stock_spinbox(self._project.stock.width)
        self._stock_height = self._stock_spinbox(self._project.stock.height)
        self._stock_thickness = self._stock_spinbox(self._project.stock.thickness)
        for axis, control in (("X", self._stock_width), ("Y", self._stock_height), ("Z", self._stock_thickness)):
            column = QVBoxLayout()
            label = QLabel(axis)
            label.setObjectName("muted")
            column.addWidget(label)
            column.addWidget(control)
            dimensions.addLayout(column)
        layout.addLayout(dimensions)

        self._origin = QComboBox()
        self._origin.addItem("Origine · coin inférieur gauche", OriginMode.LOWER_LEFT.value)
        self._origin.addItem("Origine · centre du brut", OriginMode.CENTER.value)
        self._origin.currentIndexChanged.connect(self._stock_changed)
        layout.addWidget(self._origin)

        operations_label = QLabel("OPÉRATIONS")
        operations_label.setObjectName("section")
        layout.addWidget(operations_label)
        self._operations_list = QListWidget()
        self._operations_list.setDragDropMode(QAbstractItemView.InternalMove)
        self._operations_list.currentItemChanged.connect(self._selection_changed)
        self._operations_list.itemChanged.connect(self._operation_item_changed)
        self._operations_list.model().rowsMoved.connect(self._operations_reordered)
        layout.addWidget(self._operations_list, 1)

        add = QPushButton("＋  Ajouter une étape")
        add.setObjectName("addOperation")
        add.setMinimumHeight(40 if self._embedded else 49)
        add.clicked.connect(self.show_operation_picker)
        layout.addWidget(add)

        buttons = QHBoxLayout()
        duplicate = QPushButton("Dupliquer")
        duplicate.clicked.connect(self.duplicate_selected)
        buttons.addWidget(duplicate)
        remove = QPushButton("Supprimer")
        remove.setObjectName("danger")
        remove.clicked.connect(self.remove_selected)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return panel

    def _create_preview_panel(self) -> QWidget:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8 if self._embedded else 12, 5 if self._embedded else 10, 8 if self._embedded else 12, 5 if self._embedded else 10)
        toolbar = QHBoxLayout()
        title = QLabel("APERÇU D’USINAGE")
        title.setObjectName("section")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._view_buttons = QButtonGroup(self)
        self._view_buttons.setExclusive(True)
        for plane, label in (("XY", "Dessus · XY"), ("XZ", "Face · XZ"), ("YZ", "Côté · YZ"), ("3D", "Vue 3D")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(plane == "XY")
            button.clicked.connect(lambda _checked=False, target=plane: self.set_view(target))
            self._view_buttons.addButton(button)
            toolbar.addWidget(button)
        reset = QPushButton("⌖")
        reset.setToolTip("Recentrer l’aperçu")
        reset.clicked.connect(self._reset_view)
        toolbar.addWidget(reset)
        layout.addLayout(toolbar)

        self._preview_stack = QStackedWidget()
        self._preview_2d = VectorPreview()
        self._preview_stack.addWidget(self._preview_2d)
        layout.addWidget(self._preview_stack, 1)

        footer = QHBoxLayout()
        hint = QLabel("Molette : zoom   ·   Glisser : déplacement   ·   Pointillés : rapides")
        hint.setObjectName("muted")
        footer.addWidget(hint)
        footer.addStretch()
        self._summary = QLabel()
        self._summary.setObjectName("status")
        footer.addWidget(self._summary)
        layout.addLayout(footer)
        if self._embedded:
            hint.hide()
        return panel

    def _create_parameters_panel(self) -> QWidget:
        panel = _panel()
        panel.setMinimumWidth(310)
        panel.setMaximumWidth(460)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self._form = OperationForm(self._adapter)
        self._form.operation_changed.connect(self._selected_operation_changed)
        layout.addWidget(self._form)
        return panel

    def _create_gcode_panel(self) -> QWidget:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(11, 8, 11, 9)
        title_row = QHBoxLayout()
        title = QLabel("G-CODE LINUXCNC")
        title.setObjectName("section")
        title_row.addWidget(title)
        self._gcode_toggle = QPushButton("Afficher le programme" if self._embedded else "Masquer le programme")
        self._gcode_toggle.setObjectName("gcodeToggle")
        self._gcode_toggle.setCheckable(True)
        self._gcode_toggle.setChecked(not self._embedded)
        self._gcode_toggle.clicked.connect(self._toggle_gcode)
        title_row.addWidget(self._gcode_toggle)
        self._issues = QLabel()
        self._issues.setObjectName("warning")
        title_row.addWidget(self._issues, 1)
        export = QPushButton("Exporter .ngc")
        export.setObjectName("primary")
        export.clicked.connect(self.export_gcode)
        title_row.addWidget(export)
        if self._program_bridge is not None:
            send_to_machine = QPushButton("Charger dans Probe Basic")
            send_to_machine.setObjectName("primary")
            send_to_machine.setMinimumHeight(38)
            send_to_machine.setToolTip("Crée et ouvre le programme sans démarrer la machine.")
            send_to_machine.clicked.connect(self.load_into_host)
            title_row.addWidget(send_to_machine)
        layout.addLayout(title_row)
        self._gcode = QPlainTextEdit()
        self._gcode.setReadOnly(True)
        self._gcode.setMaximumHeight(132)
        self._gcode.setMinimumHeight(95)
        layout.addWidget(self._gcode)
        self._gcode.setVisible(not self._embedded)
        return panel

    def _toggle_gcode(self, visible: bool) -> None:
        self._gcode.setVisible(visible)
        self._gcode_toggle.setText("Masquer le programme" if visible else "Afficher le programme")

    def _populate_stock(self) -> None:
        for widget, value in (
            (self._stock_width, self._project.stock.width),
            (self._stock_height, self._project.stock.height),
            (self._stock_thickness, self._project.stock.thickness),
        ):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self._origin.blockSignals(True)
        self._origin.setCurrentIndex(max(0, self._origin.findData(self._project.stock.origin.value)))
        self._origin.blockSignals(False)

    def _populate_operations(self, selected_uid: str | None = None) -> None:
        self._operations_list.blockSignals(True)
        self._operations_list.clear()
        selected_row = 0
        for index, operation in enumerate(self._project.operations):
            item = QListWidgetItem(f"{operation.title}\nT{operation.tool_number}")
            item.setData(Qt.UserRole, operation.uid)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if operation.enabled else Qt.Unchecked)
            self._operations_list.addItem(item)
            if operation.uid == selected_uid:
                selected_row = index
        if self._project.operations:
            self._operations_list.setCurrentRow(selected_row)
        self._operations_list.blockSignals(False)
        self._form.set_operation(self._selected_operation())

    def _selected_operation(self) -> OperationRecord | None:
        item = self._operations_list.currentItem()
        if item is None:
            return None
        uid = item.data(Qt.UserRole)
        return next((operation for operation in self._project.operations if operation.uid == uid), None)

    def _selected_uid(self) -> str | None:
        operation = self._selected_operation()
        return operation.uid if operation is not None else None

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()
        self.project_changed.emit()

    def _rebuild(self) -> None:
        self._result = build_project(self._project, self._adapter)
        if self._plane == "3D" and self._preview_3d is not None:
            self._preview_3d.set_content(self._project, self._result, selected_uid=self._selected_uid())
        else:
            self._preview_2d.set_content(self._project, self._result, selected_uid=self._selected_uid(), plane=self._plane)
        self._gcode.setPlainText(self.generated_gcode)
        count = len(self._result.toolpaths)
        self._summary.setText(f"{count} opération{'s' if count != 1 else ''}  ·  ≈ {self._result.estimated_minutes:.1f} min")
        if self._result.errors:
            self._issues.setObjectName("error")
            self._issues.setText(f"⚠ {self._result.errors[0].operation_title} : {self._result.errors[0].message}")
        elif self._result.warnings:
            self._issues.setObjectName("warning")
            self._issues.setText(f"⚠ {self._result.warnings[0].message}")
        else:
            self._issues.setText("Trajectoires générées")
        self._issues.style().unpolish(self._issues)
        self._issues.style().polish(self._issues)

    def _rename_project(self, name: str) -> None:
        self._project.name = name.strip() or "Nouvelle pièce"
        self._schedule_refresh()

    def _stock_changed(self, _value=None) -> None:
        self._project.stock.width = self._stock_width.value()
        self._project.stock.height = self._stock_height.value()
        self._project.stock.thickness = self._stock_thickness.value()
        self._project.stock.origin = OriginMode(self._origin.currentData())
        self._schedule_refresh()

    def _selection_changed(self, current, _previous) -> None:
        self._form.set_operation(self._selected_operation())
        self._schedule_refresh()

    def _operation_item_changed(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        operation = next((entry for entry in self._project.operations if entry.uid == uid), None)
        if operation is not None:
            operation.enabled = item.checkState() == Qt.Checked
            self._schedule_refresh()

    def _operations_reordered(self, *_args) -> None:
        by_uid = {operation.uid: operation for operation in self._project.operations}
        self._project.operations = [
            by_uid[self._operations_list.item(index).data(Qt.UserRole)]
            for index in range(self._operations_list.count())
        ]
        self._schedule_refresh()

    def _selected_operation_changed(self) -> None:
        operation = self._selected_operation()
        item = self._operations_list.currentItem()
        if operation is not None and item is not None:
            self._operations_list.blockSignals(True)
            item.setText(f"{operation.title}\nT{operation.tool_number}")
            self._operations_list.blockSignals(False)
        self._schedule_refresh()

    def add_operation(self, plugin_id: str) -> None:
        plugin = registry.get(plugin_id)
        suggested_tool = 5 if plugin_id.startswith("drill_") else 4 if plugin_id == "facing" else 1
        available = {tool.number for tool in self._adapter.get_tools()}
        if suggested_tool not in available and available:
            suggested_tool = min(available)
        operation = plugin.create_record(self._project.stock, tool_number=suggested_tool)
        self._project.operations.append(operation)
        self._populate_operations(operation.uid)
        self._schedule_refresh()

    def show_operation_picker(self) -> None:
        dialog = OperationPickerDialog(self)
        if dialog.exec() and dialog.selected_plugin_id:
            self.add_operation(dialog.selected_plugin_id)

    def duplicate_selected(self) -> None:
        current = self._selected_operation()
        if current is None:
            return
        duplicate = current.clone()
        self._project.operations.insert(self._project.operations.index(current) + 1, duplicate)
        self._populate_operations(duplicate.uid)
        self._schedule_refresh()

    def remove_selected(self) -> None:
        current = self._selected_operation()
        if current is None:
            return
        self._project.operations.remove(current)
        self._populate_operations()
        self._schedule_refresh()

    def set_view(self, plane: str) -> None:
        self._plane = plane
        if plane == "3D":
            if self._preview_3d is None:
                from openmill.ui.preview_3d import VtkPreview

                self._preview_3d = VtkPreview()
                self._preview_stack.addWidget(self._preview_3d)
            self._preview_stack.setCurrentWidget(self._preview_3d)
        else:
            self._preview_stack.setCurrentWidget(self._preview_2d)
        self._rebuild()

    def _reset_view(self) -> None:
        if self._plane == "3D":
            if self._preview_3d is not None:
                self._preview_3d.reset_view()
            self._rebuild()
        else:
            self._preview_2d.reset_view()

    def new_project(self) -> None:
        self._project = Project()
        self._path = None
        self._project_name.setText(self._project.name)
        self._populate_stock()
        self._populate_operations()
        self._rebuild()

    def open_project(self, filename: str | None = None) -> None:
        if filename is None:
            filename, _filter = QFileDialog.getOpenFileName(
                self,
                "Ouvrir un projet OpenMill",
                "",
                "Projets OpenMill (*.openmill.json *.json);;Tous les fichiers (*)",
            )
        if not filename:
            return
        try:
            self._project = load_project(filename)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Ouverture impossible", str(error))
            return
        self._path = Path(filename)
        self._project_name.setText(self._project.name)
        self._populate_stock()
        self._populate_operations()
        self._rebuild()

    def save_project(self, *, save_as: bool = False) -> bool:
        filename = str(self._path) if self._path is not None and not save_as else ""
        if not filename:
            default = f"{self._project.name}.openmill.json"
            filename, _filter = QFileDialog.getSaveFileName(
                self,
                "Enregistrer le projet OpenMill",
                default,
                "Projets OpenMill (*.openmill.json);;JSON (*.json)",
            )
        if not filename:
            return False
        try:
            save_project(self._project, filename)
        except OSError as error:
            QMessageBox.critical(self, "Enregistrement impossible", str(error))
            return False
        self._path = Path(filename)
        return True

    def export_gcode(self, filename: str | None = None) -> bool:
        self._rebuild()
        if self._result.errors:
            QMessageBox.warning(self, "Export impossible", "Corrige les opérations en erreur avant d’exporter le programme.")
            return False
        if not self._result.toolpaths:
            QMessageBox.warning(self, "Export impossible", "Ajoute au moins une opération valide.")
            return False
        if filename is None:
            filename, _filter = QFileDialog.getSaveFileName(
                self,
                "Exporter le programme LinuxCNC",
                f"{self._project.name}.ngc",
                "Programmes LinuxCNC (*.ngc);;Tous les fichiers (*)",
            )
        if not filename:
            return False
        try:
            Path(filename).write_text(self.generated_gcode, encoding="ascii", newline="\n")
        except OSError as error:
            QMessageBox.critical(self, "Export impossible", str(error))
            return False
        return True

    def load_into_host(self) -> bool:
        if self._program_bridge is None:
            QMessageBox.warning(self, "Chargement indisponible", "Aucune connexion Probe Basic n’est active.")
            return False
        self._rebuild()
        try:
            destination = prepare_and_load_program(
                self._project,
                self._adapter,
                self._program_bridge,
                output_directory=self._program_directory,
            )
        except (ProgramLoadError, OSError, ValueError) as error:
            QMessageBox.warning(self, "Chargement impossible", str(error))
            return False
        self.program_loaded.emit(str(destination))
        self._issues.setText(f"Programme chargé : {destination.name} · départ cycle manuel")
        return True

    def create_file_actions(self, parent: QWidget) -> list[QAction]:
        actions: list[QAction] = []
        for label, shortcut, callback in (
            ("Nouveau projet", QKeySequence.New, self.new_project),
            ("Ouvrir…", QKeySequence.Open, self.open_project),
            ("Enregistrer", QKeySequence.Save, self.save_project),
            ("Enregistrer sous…", QKeySequence.SaveAs, lambda: self.save_project(save_as=True)),
        ):
            action = QAction(label, parent)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda _checked=False, handler=callback: handler())
            actions.append(action)
        return actions
