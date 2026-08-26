"""Interactive orthographic 3D fallback rendered entirely with Qt's QPainter."""

from __future__ import annotations

from openmill.ui.qt_core import QPoint, QPointF, QRectF, Qt
from openmill.ui.qt_gui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from openmill.ui.qt_widgets import QWidget

from openmill.core.engine import BuildResult
from openmill.core.models import Motion, MotionKind, Point, Project, Toolpath
from openmill.core.view3d import OrbitProjection, stock_corners
from openmill.ui.theme import OPERATION_COLORS


class CompatiblePreview3D(QWidget):
    """Reliable rotatable view for Windows drivers without a usable VTK context."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self._project: Project | None = None
        self._result = BuildResult()
        self._selected_uid: str | None = None
        self._camera: OrbitProjection | None = None
        self._drag_start: QPoint | None = None
        self._scale = 1.0
        self._center = QPointF()
        self._tool_position: Point | None = None
        self._color_mode = "operation"

    def set_content(
        self,
        project: Project,
        result: BuildResult,
        *,
        selected_uid: str | None = None,
        tool_position: Point | None = None,
        color_mode: str = "operation",
    ) -> None:
        if self._project is None or self._project.stock is not project.stock:
            self._camera = OrbitProjection.from_stock(project.stock)
        self._project = project
        self._result = result
        self._selected_uid = selected_uid
        self._tool_position = tool_position
        self._color_mode = color_mode
        self.update()

    def reset_view(self) -> None:
        if self._project is not None:
            self._camera = OrbitProjection.from_stock(self._project.stock)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None and self._camera is not None:
            movement = event.pos() - self._drag_start
            self._camera.orbit(movement.x() * 0.55, movement.y() * 0.42)
            self._drag_start = event.pos()
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        self.unsetCursor()
        event.accept()

    def wheelEvent(self, event) -> None:
        if self._camera is not None:
            self._camera.magnify(1.13 if event.angleDelta().y() > 0 else 1 / 1.13)
            self.update()
            event.accept()

    def _screen(self, point: Point) -> QPointF:
        horizontal, vertical = self._camera.project(point)
        return QPointF(self._center.x() + horizontal * self._scale, self._center.y() - vertical * self._scale)

    def _prepare_camera(self) -> None:
        corners = stock_corners(self._project.stock)
        coordinates = [self._camera.project(point) for point in corners]
        width = max(horizontal for horizontal, _vertical in coordinates) - min(
            horizontal for horizontal, _vertical in coordinates
        )
        height = max(vertical for _horizontal, vertical in coordinates) - min(
            vertical for _horizontal, vertical in coordinates
        )
        width = max(width, 1.0)
        height = max(height, 1.0)
        self._scale = min(max(self.width() - 110, 80) / width, max(self.height() - 120, 80) / height)
        self._scale *= min(self._camera.zoom, 2.8)
        self._center = QPointF(self.width() / 2, self.height() / 2 + 18)

    def _polygon(self, painter: QPainter, points: tuple[Point, ...], fill: QColor, border: QColor) -> None:
        polygon = QPolygonF([self._screen(point) for point in points])
        painter.setPen(QPen(border, 1.25))
        painter.setBrush(fill)
        painter.drawPolygon(polygon)

    def _draw_floor(self, painter: QPainter) -> None:
        stock = self._project.stock
        margin = max(stock.width, stock.height) * 0.11
        level = stock.z_min - 0.4
        floor = (
            Point(stock.x_min - margin, stock.y_min - margin, level),
            Point(stock.x_max + margin, stock.y_min - margin, level),
            Point(stock.x_max + margin, stock.y_max + margin, level),
            Point(stock.x_min - margin, stock.y_max + margin, level),
        )
        self._polygon(painter, floor, QColor(27, 42, 61, 175), QColor(51, 72, 97, 160))
        painter.setPen(QPen(QColor(76, 101, 132, 72), 1))
        step = 10 if max(stock.width, stock.height) <= 180 else 20
        x = int(stock.x_min // step) * step
        while x <= stock.x_max:
            painter.drawLine(self._screen(Point(x, stock.y_min, level)), self._screen(Point(x, stock.y_max, level)))
            x += step
        y = int(stock.y_min // step) * step
        while y <= stock.y_max:
            painter.drawLine(self._screen(Point(stock.x_min, y, level)), self._screen(Point(stock.x_max, y, level)))
            y += step

    def _draw_stock(self, painter: QPainter) -> None:
        stock = self._project.stock
        low, high = stock.z_min, stock.z_max
        faces = (
            (
                Point(stock.x_min, stock.y_min, low),
                Point(stock.x_max, stock.y_min, low),
                Point(stock.x_max, stock.y_min, high),
                Point(stock.x_min, stock.y_min, high),
            ),
            (
                Point(stock.x_max, stock.y_min, low),
                Point(stock.x_max, stock.y_max, low),
                Point(stock.x_max, stock.y_max, high),
                Point(stock.x_max, stock.y_min, high),
            ),
            (
                Point(stock.x_max, stock.y_max, low),
                Point(stock.x_min, stock.y_max, low),
                Point(stock.x_min, stock.y_max, high),
                Point(stock.x_max, stock.y_max, high),
            ),
            (
                Point(stock.x_min, stock.y_max, low),
                Point(stock.x_min, stock.y_min, low),
                Point(stock.x_min, stock.y_min, high),
                Point(stock.x_min, stock.y_max, high),
            ),
        )
        for face in sorted(faces, key=lambda points: sum(self._camera.depth(point) for point in points)):
            self._polygon(painter, face, QColor(77, 105, 132, 64), QColor(111, 140, 166, 125))
        top = (
            Point(stock.x_min, stock.y_min, high),
            Point(stock.x_max, stock.y_min, high),
            Point(stock.x_max, stock.y_max, high),
            Point(stock.x_min, stock.y_max, high),
        )
        self._polygon(painter, top, QColor(105, 134, 159, 43), QColor(155, 179, 201, 185))

    def _draw_toolpaths(self, painter: QPainter) -> None:
        segments: list[tuple[float, Motion, Toolpath, QColor, bool]] = []
        for index, toolpath in enumerate(self._result.toolpaths):
            color = QColor(OPERATION_COLORS[index % len(OPERATION_COLORS)])
            active = self._selected_uid is None or self._selected_uid == toolpath.operation_uid
            for motion in toolpath.motions:
                motion_color = QColor(color)
                if self._color_mode == "movement":
                    motion_color = QColor("#ffbf69" if motion.kind is MotionKind.PLUNGE else "#57d7a8")
                elif self._color_mode == "depth" and motion.kind is not MotionKind.RAPID:
                    ratio = max(0.0, min(1.0, abs(motion.end.z) / self._project.stock.thickness))
                    motion_color = QColor.fromHsvF(0.53 + ratio * 0.27, 0.62, 0.96)
                midpoint = Point(
                    (motion.start.x + motion.end.x) / 2,
                    (motion.start.y + motion.end.y) / 2,
                    (motion.start.z + motion.end.z) / 2,
                )
                segments.append((self._camera.depth(midpoint), motion, toolpath, motion_color, active))

        for _depth, motion, toolpath, color, active in sorted(segments, key=lambda segment: segment[0]):
            if motion.kind is MotionKind.RAPID:
                rapid = QColor(164, 184, 207, 135 if active else 40)
                pen = QPen(rapid, 1.4, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(self._screen(motion.start), self._screen(motion.end))
                continue

            body = QColor(color)
            body.setAlpha(115 if active else 38)
            width = min(max(toolpath.tool.diameter * self._scale, 3.0), 44.0)
            pen = QPen(body, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self._screen(motion.start), self._screen(motion.end))
            centerline = QColor(color)
            centerline.setAlpha(230 if active else 75)
            painter.setPen(QPen(centerline, 1.35, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self._screen(motion.start), self._screen(motion.end))

    def _draw_tool(self, painter: QPainter) -> None:
        selected = next((item for item in self._result.toolpaths if item.operation_uid == self._selected_uid), None)
        if selected is None and self._result.toolpaths:
            selected = self._result.toolpaths[-1]
        if selected is None:
            return
        cuts = [motion for motion in selected.motions if motion.kind is not MotionKind.RAPID]
        if not cuts:
            return
        tip = self._tool_position or cuts[-1].end
        head = Point(tip.x, tip.y, tip.z + min(max(selected.tool.flute_length, 12), 38))
        thickness = min(max(selected.tool.diameter * self._scale, 4), 42)
        painter.setPen(QPen(QColor(212, 224, 236, 215), thickness, Qt.SolidLine, Qt.FlatCap))
        painter.drawLine(self._screen(tip), self._screen(head))
        painter.setPen(QPen(QColor(255, 255, 255, 165), 1.1))
        painter.drawLine(self._screen(tip), self._screen(head))

    def _draw_overlay(self, painter: QPainter) -> None:
        painter.setPen(QColor("#eff5fb"))
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(17, 12, self.width() - 34, 24), Qt.AlignLeft, "3D · rendu compatible")
        painter.setPen(QColor("#90a0b8"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(17, self.height() - 31, self.width() - 34, 20),
            Qt.AlignLeft,
            "Glisser : rotation   ·   Molette : zoom   ·   Aucun OpenGL requis",
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#101a29"))
        gradient.setColorAt(1, QColor("#0a101a"))
        painter.fillRect(self.rect(), QBrush(gradient))
        if self._project is None or self._camera is None:
            return
        self._prepare_camera()
        self._draw_floor(painter)
        self._draw_stock(painter)
        self._draw_toolpaths(painter)
        self._draw_tool(painter)
        self._draw_overlay(painter)
