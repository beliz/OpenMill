"""Large tactile value controls, percentage faders and 360° angle dials."""

from __future__ import annotations

import math

from openmill.ui.qt_core import QEvent, QPointF, QRectF, Qt, QLocale, pyqtSignal
from openmill.ui.qt_gui import QColor, QFont, QPainter, QPen
from openmill.ui.qt_widgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from openmill.core.parameter_controls import normalize_dial_angle, recommended_step
from openmill.core.registry import FieldSpec


class TouchNumberControl(QWidget):
    value_changed = pyqtSignal(object)

    def __init__(self, specification: FieldSpec, value, parent=None) -> None:
        super().__init__(parent)
        self._specification = specification
        self._drag_origin = None
        self._drag_value = 0.0
        self._dragging = False
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

        if specification.kind == "int":
            self._field = QSpinBox()
            self._field.setRange(int(specification.minimum), int(specification.maximum))
            self._field.setSingleStep(int(recommended_step(specification)))
            self._field.setValue(int(value))
        else:
            self._field = QDoubleSpinBox()
            self._field.setLocale(QLocale(QLocale.French, QLocale.France))
            self._field.setDecimals(specification.decimals)
            self._field.setRange(specification.minimum, specification.maximum)
            self._field.setSingleStep(recommended_step(specification))
            self._field.setValue(float(value))
        self._field.setObjectName("scrubValue")
        self._field.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._field.setAlignment(Qt.AlignCenter)
        self._field.setMinimumHeight(40)
        self._field.setMinimumWidth(85)
        self._field.lineEdit().installEventFilter(self)
        self._field.lineEdit().setToolTip("Glisse horizontalement pour ajuster la valeur, ou clique pour la saisir.")
        if specification.unit:
            self._field.setSuffix(f" {specification.unit}")
        self._field.valueChanged.connect(lambda current: self.value_changed.emit(current))
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
        return self._field.value()

    def set_value(self, value) -> None:
        self._field.setValue(int(value) if self._specification.kind == "int" else float(value))

    def _adjust(self, direction: int) -> None:
        self._field.stepBy(direction)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._field.lineEdit():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_origin = event.globalPos()
                self._drag_value = float(self.value())
                self._dragging = False
            elif event.type() == QEvent.MouseMove and self._drag_origin is not None:
                delta = event.globalPos().x() - self._drag_origin.x()
                if abs(delta) > 5 or self._dragging:
                    self._dragging = True
                    self._field.lineEdit().setCursor(Qt.SizeHorCursor)
                    increment = recommended_step(self._specification) * delta / 9
                    self.set_value(self._drag_value + increment)
                    return True
            elif event.type() == QEvent.MouseButtonRelease and self._drag_origin is not None:
                consumed = self._dragging
                self._drag_origin = None
                self._dragging = False
                self._field.lineEdit().unsetCursor()
                return consumed
        return super().eventFilter(watched, event)


class PercentageControl(QWidget):
    value_changed = pyqtSignal(object)

    def __init__(self, specification: FieldSpec, value: float, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self._number = TouchNumberControl(specification, value)
        self._number.value_changed.connect(self._number_changed)
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

    def __init__(self, specification: FieldSpec, value: float, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self._dial = AngleDial(specification, value)
        self._dial.angle_changed.connect(self._dial_changed)
        layout.addWidget(self._dial)
        self._number = TouchNumberControl(specification, value)
        self._number.value_changed.connect(self._number_changed)
        layout.addWidget(self._number)

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
