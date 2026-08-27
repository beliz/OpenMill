"""Embeddable conversational workspace independent of its host window."""

from __future__ import annotations

from pathlib import Path

from openmill import __version__
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
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from openmill.adapters.base import MachineAdapter
from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import BuildResult, build_project, create_demo_project
from openmill.core.gcode import generate_gcode
from openmill.core.models import (
    OperationRecord,
    OriginMode,
    Project,
    RepetitionBlock,
    RepetitionOrder,
)
from openmill.core.project_io import load_project, save_project
from openmill.core.registry import registry
from openmill.integration.bridge import ProgramBridge, ProgramLoadError, prepare_and_load_program
from openmill.ui.operation_form import OperationForm
from openmill.ui.operation_picker import OperationPickerDialog
from openmill.ui.preview_2d import VectorPreview
from openmill.ui.repetition_form import RepetitionForm
from openmill.ui.theme import STYLESHEET


ITEM_UID_ROLE = int(Qt.UserRole)
ITEM_KIND_ROLE = ITEM_UID_ROLE + 1


def _panel() -> QFrame:
    panel = QFrame()
    panel.setObjectName("panel")
    return panel


class ProgramTreeWidget(QTreeWidget):
    """Program tree that always publishes completed internal moves."""

    program_reordered = pyqtSignal()

    def dropEvent(self, event) -> None:
        dragged = self.currentItem()
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target = self.itemAt(position)
        if dragged is not None and dragged.data(0, ITEM_KIND_ROLE) == "repetition":
            invalid_parent = target is not None and target.parent() is not None
            indicator_type = getattr(QAbstractItemView, "DropIndicatorPosition", QAbstractItemView)
            invalid_nesting = (
                target is not None
                and self.dropIndicatorPosition() == indicator_type.OnItem
            )
            if invalid_parent or invalid_nesting:
                event.ignore()
                return
        super().dropEvent(event)
        self.program_reordered.emit()


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

        columns = QSplitter(Qt.Horizontal)
        columns.setChildrenCollapsible(False)
        columns.setHandleWidth(8)
        columns.addWidget(self._create_operations_panel())
        columns.addWidget(self._create_parameters_panel())
        columns.addWidget(self._create_preview_panel())
        columns.setStretchFactor(0, 0)
        columns.setStretchFactor(1, 1)
        columns.setStretchFactor(2, 1)
        columns.setSizes([280, 680, 500])
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

        piece_heading = QHBoxLayout()
        piece_label = QLabel("PIÈCE")
        piece_label.setObjectName("section")
        piece_heading.addWidget(piece_label)
        piece_heading.addStretch()
        self._version_label = QLabel(f"v{__version__}")
        self._version_label.setObjectName("version")
        self._version_label.setToolTip("Version installée d’OpenMill")
        piece_heading.addWidget(self._version_label)
        layout.addLayout(piece_heading)

        self._project_name = QLineEdit(self._project.name)
        self._project_name.setObjectName("projectName")
        self._project_name.setMinimumHeight(38)
        self._project_name.setPlaceholderText("Nom de la pièce")
        self._project_name.setAccessibleName("Nom de la pièce")
        self._project_name.textChanged.connect(self._rename_project)
        layout.addWidget(self._project_name)

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

        operations_label = QLabel("PROGRAMME")
        operations_label.setObjectName("section")
        layout.addWidget(operations_label)
        self._program_tree = ProgramTreeWidget()
        self._program_tree.setHeaderHidden(True)
        self._program_tree.setIndentation(18)
        self._program_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self._program_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self._program_tree.currentItemChanged.connect(self._selection_changed)
        self._program_tree.itemChanged.connect(self._program_item_changed)
        self._program_tree.program_reordered.connect(self._program_rows_moved)
        layout.addWidget(self._program_tree, 1)

        add = QPushButton("＋  Ajouter une opération")
        add.setObjectName("addOperation")
        add.setMinimumHeight(40 if self._embedded else 49)
        add.clicked.connect(self.show_operation_picker)
        layout.addWidget(add)

        repetition = QPushButton("＋  Ajouter une répétition")
        repetition.setObjectName("repeatOperation")
        repetition.setMinimumHeight(36)
        repetition.setToolTip("Créer un bloc Unique, Ligne, Grille ou Cercle.")
        repetition.clicked.connect(self.add_repetition)
        layout.addWidget(repetition)

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
        panel.setMinimumWidth(440)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self._form_stack = QStackedWidget()
        self._form = OperationForm(self._adapter)
        self._form.operation_changed.connect(self._selected_operation_changed)
        self._repetition_form = RepetitionForm()
        self._repetition_form.repetition_changed.connect(self._selected_repetition_changed)
        self._form_stack.addWidget(self._form)
        self._form_stack.addWidget(self._repetition_form)
        layout.addWidget(self._form_stack)
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
        self._program_tree.blockSignals(True)
        self._program_tree.clear()
        selected_item = None
        by_uid = {operation.uid: operation for operation in self._project.operations}
        for repetition in self._project.repetitions:
            group_item = QTreeWidgetItem()
            group_item.setText(0, self._repetition_item_text(repetition))
            group_item.setData(0, ITEM_UID_ROLE, repetition.uid)
            group_item.setData(0, ITEM_KIND_ROLE, "repetition")
            group_item.setFlags(
                group_item.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsDragEnabled
                | Qt.ItemIsDropEnabled
            )
            group_item.setCheckState(0, Qt.Checked if repetition.enabled else Qt.Unchecked)
            self._program_tree.addTopLevelItem(group_item)
            if repetition.uid == selected_uid:
                selected_item = group_item
            for operation_uid in repetition.operation_uids:
                operation = by_uid.get(operation_uid)
                if operation is None:
                    continue
                operation_item = QTreeWidgetItem()
                operation_item.setText(0, self._operation_item_text(operation))
                operation_item.setData(0, ITEM_UID_ROLE, operation.uid)
                operation_item.setData(0, ITEM_KIND_ROLE, "operation")
                operation_item.setFlags(
                    (operation_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
                    & ~Qt.ItemIsDropEnabled
                )
                operation_item.setCheckState(0, Qt.Checked if operation.enabled else Qt.Unchecked)
                group_item.addChild(operation_item)
                if operation.uid == selected_uid:
                    selected_item = operation_item
            group_item.setExpanded(True)
        if selected_item is None and self._program_tree.topLevelItemCount():
            selected_item = self._program_tree.topLevelItem(0)
        self._program_tree.setCurrentItem(selected_item)
        self._program_tree.blockSignals(False)
        self._show_selected_form()

    @staticmethod
    def _operation_item_text(operation: OperationRecord) -> str:
        return f"{operation.title}\nT{operation.tool_number}"

    @staticmethod
    def _repetition_item_text(repetition: RepetitionBlock) -> str:
        order = (
            "par position"
            if repetition.execution_order is RepetitionOrder.BY_POSITION
            else "par opération"
        )
        return f"{repetition.title}\n{repetition.placement.summary}  ·  {order}"

    def _selected_operation(self) -> OperationRecord | None:
        item = self._program_tree.currentItem()
        if item is None or item.data(0, ITEM_KIND_ROLE) != "operation":
            return None
        uid = item.data(0, ITEM_UID_ROLE)
        return next((operation for operation in self._project.operations if operation.uid == uid), None)

    def _selected_repetition(self) -> RepetitionBlock | None:
        item = self._program_tree.currentItem()
        if item is None:
            return None
        if item.data(0, ITEM_KIND_ROLE) == "operation":
            item = item.parent()
        if item is None or item.data(0, ITEM_KIND_ROLE) != "repetition":
            return None
        uid = item.data(0, ITEM_UID_ROLE)
        return next((block for block in self._project.repetitions if block.uid == uid), None)

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
        self._show_selected_form()
        self._schedule_refresh()

    def _show_selected_form(self) -> None:
        operation = self._selected_operation()
        if operation is not None:
            self._form.set_operation(operation)
            self._repetition_form.set_repetition(None)
            self._form_stack.setCurrentWidget(self._form)
            return
        self._form.set_operation(None)
        self._repetition_form.set_repetition(self._selected_repetition())
        self._form_stack.setCurrentWidget(self._repetition_form)

    def _program_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        uid = item.data(0, ITEM_UID_ROLE)
        if item.data(0, ITEM_KIND_ROLE) == "repetition":
            repetition = next((entry for entry in self._project.repetitions if entry.uid == uid), None)
            if repetition is not None:
                repetition.enabled = item.checkState(0) == Qt.Checked
        else:
            operation = next((entry for entry in self._project.operations if entry.uid == uid), None)
            if operation is not None:
                operation.enabled = item.checkState(0) == Qt.Checked
        self._schedule_refresh()

    def _program_rows_moved(self, *_args) -> None:
        QTimer.singleShot(0, self._program_reordered)

    def _program_reordered(self) -> None:
        repetitions = {block.uid: block for block in self._project.repetitions}
        operations = {operation.uid: operation for operation in self._project.operations}
        ordered_repetitions: list[RepetitionBlock] = []
        ordered_operation_uids: list[str] = []
        selected_uid = None
        current = self._program_tree.currentItem()
        if current is not None:
            selected_uid = current.data(0, ITEM_UID_ROLE)
        for index in range(self._program_tree.topLevelItemCount()):
            item = self._program_tree.topLevelItem(index)
            kind = item.data(0, ITEM_KIND_ROLE)
            if kind == "operation":
                uid = item.data(0, ITEM_UID_ROLE)
                if uid in operations:
                    block = RepetitionBlock(operation_uids=[uid])
                    ordered_repetitions.append(block)
                    ordered_operation_uids.append(uid)
                continue
            repetition = repetitions.get(item.data(0, ITEM_UID_ROLE))
            if repetition is None:
                continue
            repetition.operation_uids = []
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                if child.data(0, ITEM_KIND_ROLE) != "operation":
                    continue
                uid = child.data(0, ITEM_UID_ROLE)
                if uid in operations and uid not in ordered_operation_uids:
                    repetition.operation_uids.append(uid)
                    ordered_operation_uids.append(uid)
                    operations[uid].placement = repetition.placement
            ordered_repetitions.append(repetition)
        for uid in operations:
            if uid not in ordered_operation_uids:
                block = self._project.repetition_for(uid) or RepetitionBlock(operation_uids=[uid])
                block.operation_uids = [uid]
                operations[uid].placement = block.placement
                ordered_repetitions.append(block)
                ordered_operation_uids.append(uid)
        self._project.repetitions = ordered_repetitions
        self._project.operations = [operations[uid] for uid in ordered_operation_uids]
        self._populate_operations(selected_uid)
        self._schedule_refresh()

    def _selected_operation_changed(self) -> None:
        operation = self._selected_operation()
        item = self._program_tree.currentItem()
        if operation is not None and item is not None:
            self._program_tree.blockSignals(True)
            item.setText(0, self._operation_item_text(operation))
            self._program_tree.blockSignals(False)
        self._schedule_refresh()

    def _selected_repetition_changed(self) -> None:
        repetition = self._selected_repetition()
        item = self._program_tree.currentItem()
        if repetition is not None and item is not None:
            if item.data(0, ITEM_KIND_ROLE) == "operation":
                item = item.parent()
            self._program_tree.blockSignals(True)
            item.setText(0, self._repetition_item_text(repetition))
            self._program_tree.blockSignals(False)
        self._schedule_refresh()

    def add_operation(self, plugin_id: str) -> None:
        plugin = registry.get(plugin_id)
        suggested_tool = 5 if plugin_id.startswith("drill_") else 4 if plugin_id == "facing" else 1
        available = {tool.number for tool in self._adapter.get_tools()}
        if suggested_tool not in available and available:
            suggested_tool = min(available)
        operation = plugin.create_record(self._project.stock, tool_number=suggested_tool)
        self._project.operations.append(operation)
        repetition = self._selected_repetition()
        if repetition is None:
            repetition = RepetitionBlock()
            self._project.repetitions.append(repetition)
        repetition.operation_uids.append(operation.uid)
        operation.placement = repetition.placement
        self._populate_operations(operation.uid)
        self._schedule_refresh()

    def add_repetition(self) -> None:
        repetition = RepetitionBlock()
        self._project.repetitions.append(repetition)
        self._populate_operations(repetition.uid)
        self._schedule_refresh()

    def show_operation_picker(self) -> None:
        dialog = OperationPickerDialog(self)
        if dialog.exec() and dialog.selected_plugin_id:
            self.add_operation(dialog.selected_plugin_id)

    def duplicate_selected(self) -> None:
        current = self._selected_operation()
        repetition = self._selected_repetition()
        if current is not None and repetition is not None:
            duplicate = current.clone()
            self._project.operations.insert(self._project.operations.index(current) + 1, duplicate)
            index = repetition.operation_uids.index(current.uid) + 1
            repetition.operation_uids.insert(index, duplicate.uid)
            duplicate.placement = repetition.placement
            self._populate_operations(duplicate.uid)
            self._schedule_refresh()
            return
        if repetition is None:
            return
        duplicates = []
        by_uid = {operation.uid: operation for operation in self._project.operations}
        for uid in repetition.operation_uids:
            if uid in by_uid:
                duplicates.append(by_uid[uid].clone())
        self._project.operations.extend(duplicates)
        clone = repetition.clone([operation.uid for operation in duplicates])
        for operation in duplicates:
            operation.placement = clone.placement
        index = self._project.repetitions.index(repetition) + 1
        self._project.repetitions.insert(index, clone)
        self._populate_operations(clone.uid)
        self._schedule_refresh()

    def remove_selected(self) -> None:
        current = self._selected_operation()
        repetition = self._selected_repetition()
        if current is not None and repetition is not None:
            repetition.operation_uids.remove(current.uid)
            self._project.operations.remove(current)
            self._populate_operations(repetition.uid)
            self._schedule_refresh()
            return
        if repetition is None:
            return
        operation_uids = set(repetition.operation_uids)
        self._project.operations = [
            operation for operation in self._project.operations if operation.uid not in operation_uids
        ]
        self._project.repetitions.remove(repetition)
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
