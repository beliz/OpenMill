"""Large tactile value controls, percentage faders and 360° angle dials."""

from __future__ import annotations

import math
from collections.abc import Mapping

from openmill.core.parameter_controls import (
    NumericExpressionError,
    evaluate_field_expression,
    is_calculation_expression,
    normalize_dial_angle,
    recommended_step,
)
from openmill.core.registry import FieldSpec
from openmill.ui.qt_core import QEvent, QPointF, QRectF, Qt, pyqtSignal
from openmill.ui.qt_gui import QColor, QFont, QPainter, QPen
from openmill.ui.qt_widgets import (
    QButtonGroup,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class TouchNumberControl(QWidget):
    value_changed = pyqtSignal(object)
    expression_changed = pyqtSignal(str)

    def __init__(
        self,
        specification: FieldSpec,
        value,
        parent=None,
        *,
        expression: str = "",
        variables: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self._specification = specification
        self._value = self._normalized_value(value)
        self._expression = expression.strip()
        self._variables = dict(variables or {})
        self._drag_origin = None
        self._drag_value = 0.0
        self._dragging = False
        self._showing_result = True
        self._base_tooltip = (
            "Clique pour saisir une valeur ou un calcul (+, -, *, /, parenthèses). "
            "Variables : tool_diam, stock_x, stock_y (alias brut_x, brut_y). "
            "Exemple : stock_x/2-tool_diam. Glisse horizontalement pour ajuster."
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        minus = QPushButton("−")
        minus.setObjectName("valueStepper")
        minus.setFixedSize(43, 40)
        minus.setAutoRepeat(True)
        minus.setAutoRepeatDelay(330)
        minus.setAutoRepeatInterval(85)
        minus.setAccessibleName(f"Diminuer {specification.label}")
        minus.clicked.connect(lambda: self._adjust(-1))
        layout.addWidget(minus)

        self._field = QLineEdit()
        self._field.setObjectName("scrubValue")
        self._field.setAlignment(Qt.AlignCenter)
        self._field.setMinimumHeight(40)
        self._field.setMinimumWidth(85)
        self._field.setAccessibleName(specification.label)
        self._field.installEventFilter(self)
        self._field.setToolTip(self._base_tooltip)
        self._field.textEdited.connect(self._editing_started)
        self._field.editingFinished.connect(self._commit_text)
        self._show_display_value()
        layout.addWidget(self._field, 1)

        plus = QPushButton("+")
        plus.setObjectName("valueStepper")
        plus.setFixedSize(43, 40)
        plus.setAutoRepeat(True)
        plus.setAutoRepeatDelay(330)
        plus.setAutoRepeatInterval(85)
        plus.setAccessibleName(f"Augmenter {specification.label}")
        plus.clicked.connect(lambda: self._adjust(1))
        layout.addWidget(plus)

    def value(self):
        return self._value

    def expression(self) -> str:
        return self._expression

    def set_value(self, value, *, clear_expression: bool = True) -> None:
        normalized = self._normalized_value(value)
        changed = not math.isclose(float(self._value), float(normalized), abs_tol=1e-12)
        self._value = normalized
        if clear_expression:
            self._set_expression("")
        self._show_editable_value() if self._field.hasFocus() else self._show_display_value()
        if changed:
            self.value_changed.emit(self._value)

    def set_variables(self, variables: Mapping[str, float] | None) -> bool:
        """Update formula variables and recompute the persisted expression."""

        self._variables = dict(variables or {})
        if not self._expression:
            return True
        try:
            normalized = evaluate_field_expression(
                self._specification,
                self._expression,
                self._variables,
            )
        except NumericExpressionError as error:
            self._set_error(str(error))
            return False
        self._set_error()
        changed = not math.isclose(float(self._value), float(normalized), abs_tol=1e-12)
        self._value = normalized
        self._show_editable_value() if self._field.hasFocus() else self._show_display_value()
        if changed:
            self.value_changed.emit(self._value)
        return True

    def _adjust(self, direction: int) -> None:
        step = recommended_step(self._specification)
        self.set_value(float(self._value) + direction * step)

    def _normalized_value(self, value):
        bounded = min(self._specification.maximum, max(self._specification.minimum, float(value)))
        if self._specification.kind == "int":
            return int(round(bounded))
        return round(bounded, self._specification.decimals)

    def _editable_value(self) -> str:
        if self._specification.kind == "int":
            return str(int(self._value))
        return f"{float(self._value):.{self._specification.decimals}f}".replace(".", ",")

    def _display_value(self) -> str:
        suffix = f" {self._specification.unit}" if self._specification.unit else ""
        return f"{self._editable_value()}{suffix}"

    def _show_editable_value(self) -> None:
        self._showing_result = False
        self._field.setText(self._expression or self._editable_value())

    def _show_display_value(self) -> None:
        self._showing_result = True
        self._field.setText(self._display_value())

    def _editing_started(self, _text: str) -> None:
        self._showing_result = False

    def _set_expression(self, expression: str) -> None:
        expression = expression.strip()
        if expression == self._expression:
            return
        self._expression = expression
        self.expression_changed.emit(expression)

    def _set_error(self, message: str = "") -> None:
        self._field.setProperty("expressionError", bool(message))
        self._field.setToolTip(message or self._base_tooltip)
        self._field.style().unpolish(self._field)
        self._field.style().polish(self._field)

    def _commit_text(self) -> None:
        if self._showing_result:
            return
        raw = self._field.text().strip()
        unit = self._specification.unit
        if unit and raw.endswith(unit):
            raw = raw[: -len(unit)].strip()
        try:
            result = evaluate_field_expression(self._specification, raw, self._variables)
        except NumericExpressionError as error:
            self._set_error(str(error))
            self._show_display_value()
            return
        self._set_error()
        expression = raw if is_calculation_expression(raw) else ""
        self._set_expression(expression)
        normalized = self._normalized_value(result)
        changed = not math.isclose(float(self._value), float(normalized), abs_tol=1e-12)
        self._value = normalized
        self._show_display_value()
        if changed:
            self.value_changed.emit(self._value)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._field:
            if event.type() == QEvent.FocusIn:
                self._show_editable_value()
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_origin = event.globalPos()
                self._drag_value = float(self.value())
                self._dragging = False
            elif event.type() == QEvent.MouseMove and self._drag_origin is not None:
                delta = event.globalPos().x() - self._drag_origin.x()
                if abs(delta) > 5 or self._dragging:
                    self._dragging = True
                    self._field.setCursor(Qt.SizeHorCursor)
                    increment = recommended_step(self._specification) * delta / 9
                    self.set_value(self._drag_value + increment)
                    return True
            elif event.type() == QEvent.MouseButtonRelease and self._drag_origin is not None:
                consumed = self._dragging
                self._drag_origin = None
                self._dragging = False
                self._field.unsetCursor()
                return consumed
        return super().eventFilter(watched, event)


class PercentageControl(QWidget):
    value_changed = pyqtSignal(object)
    expression_changed = pyqtSignal(str)

    def __init__(
        self,
        specification: FieldSpec,
        value: float,
        parent=None,
        *,
        expression: str = "",
        variables: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self._number = TouchNumberControl(
            specification,
            value,
            expression=expression,
            variables=variables,
        )
        self._number.value_changed.connect(self._number_changed)
        self._number.expression_changed.connect(self.expression_changed.emit)
        layout.addWidget(self._number)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setObjectName("touchFader")
        self._slider.setMinimumHeight(31)
        self._slider.setRange(round(specification.minimum * 10), round(specification.maximum * 10))
        self._slider.setSingleStep(10)
        self._slider.setPageStep(50)
        self._slider.setValue(round(float(value) * 10))
        self._slider.valueChanged.connect(self._slider_changed)
        layout.addWidget(self._slider)

    def set_variables(self, variables: Mapping[str, float] | None) -> bool:
        return self._number.set_variables(variables)

    def _number_changed(self, value) -> None:
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(round(float(value) * 10))
        self._updating = False
        self.value_changed.emit(value)

    def _slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        self._number.set_value(value / 10)
        self._updating = False
        self.value_changed.emit(value / 10)


class AngleDial(QWidget):
    angle_changed = pyqtSignal(float)

    def __init__(self, specification: FieldSpec, value: float, parent=None) -> None:
        super().__init__(parent)
        self._specification = specification
        self._value = float(value)
        self.setMinimumHeight(139)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.OpenHandCursor)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

    def set_value(self, value: float) -> None:
        if not math.isclose(self._value, float(value), abs_tol=1e-9):
            self._value = float(value)
            self.update()

    def _set_from_position(self, position: QPointF) -> None:
        center = QPointF(self.width() / 2, self.height() / 2)
        angle = math.degrees(math.atan2(center.y() - position.y(), position.x() - center.x()))
        value = normalize_dial_angle(angle, self._specification.minimum, self._specification.maximum)
        self._value = round(value, self._specification.decimals)
        self.angle_changed.emit(self._value)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self._set_from_position(QPointF(event.pos()))
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self._set_from_position(QPointF(event.pos()))
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.height() * 0.38, self.width() * 0.31)
        ring = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        painter.setPen(QPen(QColor("#26374b"), 9, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring)

        for index in range(12):
            radians = math.radians(index * 30)
            inside = QPointF(center.x() + (radius - 15) * math.cos(radians), center.y() - (radius - 15) * math.sin(radians))
            outside = QPointF(center.x() + (radius - 10) * math.cos(radians), center.y() - (radius - 10) * math.sin(radians))
            painter.setPen(QPen(QColor("#61758f"), 1.3))
            painter.drawLine(inside, outside)

        painter.setPen(QPen(QColor("#57d7a8"), 8, Qt.SolidLine, Qt.RoundCap))
        span = max(-360.0, min(360.0, self._value))
        painter.drawArc(ring, 0, round(span * 16))
        radians = math.radians(self._value)
        handle = QPointF(center.x() + radius * math.cos(radians), center.y() - radius * math.sin(radians))
        painter.setPen(QPen(QColor("#0d1522"), 2))
        painter.setBrush(QColor("#87f1c6"))
        painter.drawEllipse(handle, 7.5, 7.5)

        painter.setPen(QColor("#eff6fc"))
        font = QFont("Segoe UI", 11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(ring.adjusted(13, 13, -13, -13), Qt.AlignCenter, f"{self._value:g}°")


class AngleControl(QWidget):
    value_changed = pyqtSignal(object)
    expression_changed = pyqtSignal(str)

    def __init__(
        self,
        specification: FieldSpec,
        value: float,
        parent=None,
        *,
        expression: str = "",
        variables: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._dial = AngleDial(specification, value)
        self._dial.angle_changed.connect(self._dial_changed)
        layout.addWidget(self._dial)
        self._number = TouchNumberControl(
            specification,
            value,
            expression=expression,
            variables=variables,
        )
        self._number.value_changed.connect(self._number_changed)
        self._number.expression_changed.connect(self.expression_changed.emit)
        layout.addWidget(self._number)

    def set_variables(self, variables: Mapping[str, float] | None) -> bool:
        return self._number.set_variables(variables)

    def _dial_changed(self, value: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._number.set_value(value)
        self._updating = False
        self.value_changed.emit(value)

    def _number_changed(self, value) -> None:
        if self._updating:
            return
        self._updating = True
        self._dial.set_value(float(value))
        self._updating = False
        self.value_changed.emit(value)


class SegmentedChoice(QWidget):
    value_changed = pyqtSignal(object)

    def __init__(self, specification: FieldSpec, value: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for index, (key, label) in enumerate(specification.choices):
            short_label = label.split("·", 1)[0].strip()
            button = QPushButton(short_label)
            button.setObjectName("segmentedChoice")
            button.setCheckable(True)
            button.setChecked(key == value or (index == 0 and value not in dict(specification.choices)))
            button.setMinimumHeight(42)
            button.setToolTip(label)
            button.clicked.connect(lambda _checked=False, selected=key: self.value_changed.emit(selected))
            self._group.addButton(button)
            layout.addWidget(button, 1)
