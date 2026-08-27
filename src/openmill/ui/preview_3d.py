"""Interactive slicer-style preview with VTK and a reliable software fallback."""

from __future__ import annotations

import math

from openmill.ui.qt import QT_BINDING
from openmill.ui.qt_core import Qt, QTimer
from openmill.ui.qt_widgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QStackedWidget, QVBoxLayout, QWidget

from openmill.core.engine import BuildResult
from openmill.core.models import MotionKind, Point, Project, Toolpath
from openmill.core.playback import PlaybackFrame, ToolpathPlayback
from openmill.ui.preview_3d_compatible import CompatiblePreview3D
from openmill.ui.theme import OPERATION_COLORS


def _rgb(hex_color: str) -> tuple[float, float, float]:
    return tuple(int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5))


class VtkPreview(QWidget):
    """Timeline-driven view; VTK is initialized only after its native window exists."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._vtk = None
        self._renderer = None
        self._interactor = None
        self._vtk_ready = False
        self._vtk_verified = False
        self._project: Project | None = None
        self._source_result = BuildResult()
        self._selected_uid: str | None = None
        self._playback: ToolpathPlayback | None = None
        self._motion_progress_override: float | None = None
        self._signature = None
        self._speed = 1.0
        self._play_progress = 1000.0
        self._camera_needs_reset = True
        self._requested_mode = "vtk"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        modes = QHBoxLayout()
        modes.setContentsMargins(5, 3, 5, 0)
        self._vtk_button = QPushButton("VTK")
        self._vtk_button.setCheckable(True)
        self._vtk_button.setMinimumHeight(36)
        self._vtk_button.clicked.connect(lambda: self._select_renderer("vtk"))
        modes.addWidget(self._vtk_button)
        self._compatible_button = QPushButton("Compatible")
        self._compatible_button.setCheckable(True)
        self._compatible_button.setChecked(True)
        self._compatible_button.setMinimumHeight(36)
        self._compatible_button.clicked.connect(lambda: self._select_renderer("compatible"))
        modes.addWidget(self._compatible_button)
        self._renderer_status = QLabel("Rendu 3D en préparation…")
        self._renderer_status.setObjectName("muted")
        modes.addWidget(self._renderer_status, 1)
        layout.addLayout(modes)

        self._stack = QStackedWidget()
        self._compatible = CompatiblePreview3D()
        self._stack.addWidget(self._compatible)
        self._stack.setCurrentWidget(self._compatible)
        layout.addWidget(self._stack, 1)

        controls = QHBoxLayout()
        controls.setContentsMargins(5, 0, 5, 0)
        self._play_button = QPushButton("▶")
        self._play_button.setObjectName("playbackButton")
        self._play_button.setFixedSize(45, 39)
        self._play_button.setToolTip("Lire ou mettre en pause la simulation")
        self._play_button.clicked.connect(self._toggle_playback)
        controls.addWidget(self._play_button)
        self._timeline = QSlider(Qt.Horizontal)
        self._timeline.setObjectName("playbackTimeline")
        self._timeline.setRange(0, 1000)
        self._timeline.setValue(1000)
        self._timeline.setMinimumHeight(34)
        self._timeline.valueChanged.connect(self._timeline_changed)
        controls.addWidget(self._timeline, 1)
        self._progress_label = QLabel("100 %")
        self._progress_label.setMinimumWidth(49)
        controls.addWidget(self._progress_label)
        self._speed_button = QPushButton("× 1")
        self._speed_button.setMinimumWidth(63)
        self._speed_button.setMinimumHeight(38)
        self._speed_button.clicked.connect(self._change_speed)
        controls.addWidget(self._speed_button)
        layout.addLayout(controls)

        settings = QHBoxLayout()
        settings.setContentsMargins(5, 0, 5, 4)
        depth_label = QLabel("Passe")
        depth_label.setObjectName("muted")
        settings.addWidget(depth_label)
        self._depth = QComboBox()
        self._depth.setMinimumHeight(37)
        self._depth.addItem("Toutes les profondeurs", None)
        self._depth.currentIndexChanged.connect(lambda _index: self._apply_frame())
        settings.addWidget(self._depth, 1)
        palette_label = QLabel("Couleurs")
        palette_label.setObjectName("muted")
        settings.addWidget(palette_label)
        self._palette = QComboBox()
        self._palette.setMinimumHeight(37)
        self._palette.addItem("Opération", "operation")
        self._palette.addItem("Type de mouvement", "movement")
        self._palette.addItem("Profondeur", "depth")
        self._palette.currentIndexChanged.connect(self._palette_changed)
        settings.addWidget(self._palette, 1)
        layout.addLayout(settings)

        self._animation = QTimer(self)
        self._animation.setInterval(40)
        self._animation.timeout.connect(self._advance_playback)

        try:
            import vtk
            import vtkmodules.qt

            vtkmodules.qt.PyQtImpl = QT_BINDING
            from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        except ImportError:
            self._vtk_button.setEnabled(False)
            self._requested_mode = "compatible"
            self._renderer_status.setText("Mode compatible · VTK non installé")
            return

        self._vtk = vtk
        self._interactor = QVTKRenderWindowInteractor(self)
        self._interactor.setAttribute(Qt.WA_NativeWindow, True)
        self._interactor.setAutoFillBackground(False)
        self._stack.addWidget(self._interactor)
        self._renderer = vtk.vtkRenderer()
        self._renderer.SetBackground(0.043, 0.063, 0.102)
        self._renderer.SetBackground2(0.075, 0.11, 0.17)
        self._renderer.GradientBackgroundOn()
        window = self._interactor.GetRenderWindow()
        window.SetMultiSamples(0)
        window.AddRenderer(self._renderer)
        style = vtk.vtkInteractorStyleTrackballCamera()
        self._interactor.SetInteractorStyle(style)
        self._renderer_status.setText("Initialisation VTK différée…")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._requested_mode == "vtk" and self._interactor is not None and not self._vtk_ready:
            QTimer.singleShot(0, self._start_vtk)

    def reset_view(self) -> None:
        self._compatible.reset_view()
        self._camera_needs_reset = True
        self._apply_frame()

    def set_motion_index(self, motion_count: int) -> None:
        """Move the animated preview to a parsed G-code movement index."""
        if self._playback is None:
            return
        self._animation.stop()
        self._play_button.setText("▶")
        progress = self._playback.progress_for_motion_count(motion_count)
        self._motion_progress_override = progress
        self._timeline.blockSignals(True)
        self._timeline.setValue(max(0, min(1000, round(progress * 1000))))
        self._timeline.blockSignals(False)
        self._progress_label.setText(f"{round(progress * 100)} %")
        self._apply_frame()

    def _select_renderer(self, mode: str) -> None:
        if mode == "vtk" and self._interactor is None:
            mode = "compatible"
        self._requested_mode = mode
        vtk_selected = mode == "vtk"
        self._vtk_button.setChecked(vtk_selected)
        self._compatible_button.setChecked(not vtk_selected)
        if vtk_selected:
            self._stack.setCurrentWidget(self._interactor)
            if not self._vtk_ready:
                QTimer.singleShot(0, self._start_vtk)
            else:
                self._renderer_status.setText("VTK · accélération graphique")
                self._apply_frame()
        else:
            self._stack.setCurrentWidget(self._compatible)
            self._renderer_status.setText("Rendu compatible · sans OpenGL")
            self._apply_frame()

    def _start_vtk(self) -> None:
        if self._requested_mode != "vtk" or self._interactor is None or not self.isVisible():
            return
        try:
            self._stack.setCurrentWidget(self._interactor)
            self._interactor.winId()
            self._interactor.Initialize()
            self._vtk_ready = True
            self._vtk_button.setChecked(True)
            self._compatible_button.setChecked(False)
            self._renderer_status.setText("VTK · accélération graphique")
            self._apply_frame()
            QTimer.singleShot(140, self._verify_vtk_output)
        except Exception as error:
            self._vtk_failed(error)

    def _verify_vtk_output(self) -> None:
        if self._vtk_verified or not self._vtk_ready or self._requested_mode != "vtk":
            return
        try:
            window = self._interactor.GetRenderWindow()
            width, height = window.GetSize()
            if width <= 2 or height <= 2:
                raise RuntimeError("La fenêtre OpenGL ne possède pas de dimensions valides.")
            capture = self._vtk.vtkWindowToImageFilter()
            capture.SetInput(window)
            capture.ReadFrontBufferOff()
            capture.Update()
            image = capture.GetOutput()
            image_width, image_height, _depth = image.GetDimensions()
            if image_width <= 2 or image_height <= 2:
                raise RuntimeError("Le pilote graphique ne renvoie aucune image.")
            samples = []
            for row in range(1, 8):
                for column in range(1, 8):
                    x = min(image_width - 1, column * image_width // 8)
                    y = min(image_height - 1, row * image_height // 8)
                    samples.extend(image.GetScalarComponentAsDouble(x, y, 0, channel) for channel in range(3))
            if not samples or max(samples) < 8 or max(samples) - min(samples) < 4:
                raise RuntimeError("VTK produit une image noire sur ce pilote.")
            self._vtk_verified = True
        except Exception as error:
            # Windows drivers can draw valid frames while denying framebuffer reads.
            # This optional diagnostic must not override the selected renderer.
            self._vtk_verified = True
            self._renderer_status.setText("VTK actif · vérification graphique limitée")
            self._renderer_status.setToolTip(str(error))

    def _vtk_failed(self, error: Exception) -> None:
        self._vtk_ready = False
        self._requested_mode = "compatible"
        self._vtk_button.setChecked(False)
        self._compatible_button.setChecked(True)
        self._stack.setCurrentWidget(self._compatible)
        self._renderer_status.setText("VTK indisponible · mode compatible actif")
        self._renderer_status.setToolTip(str(error))
        self._apply_frame()

    def _toggle_playback(self) -> None:
        if self._animation.isActive():
            self._animation.stop()
            self._play_button.setText("▶")
            return
        if self._timeline.value() >= 1000:
            self._timeline.setValue(0)
        self._motion_progress_override = None
        self._play_progress = float(self._timeline.value())
        self._renderer_status.setText("Animation de la trajectoire")
        self._play_button.setText("Ⅱ")
        self._animation.start()

    def _advance_playback(self) -> None:
        distance = self._playback.total_distance if self._playback is not None else 0
        duration_ms = max(8_000, min(36_000, distance / 150 * 1000))
        self._play_progress += self._animation.interval() * 1000 / duration_ms * self._speed
        self._timeline.setValue(min(1000, round(self._play_progress)))
        if self._play_progress >= 1000:
            self._animation.stop()
            self._play_button.setText("▶")

    def _change_speed(self) -> None:
        speeds = (0.5, 1.0, 2.0, 4.0)
        self._speed = speeds[(speeds.index(self._speed) + 1) % len(speeds)]
        self._speed_button.setText(f"× {self._speed:g}")

    def _timeline_changed(self, value: int) -> None:
        self._motion_progress_override = None
        self._progress_label.setText(f"{round(value / 10)} %")
        self._apply_frame()

    def _palette_changed(self, _index: int) -> None:
        self._apply_frame()

    def _apply_frame(self) -> None:
        if self._project is None or self._playback is None:
            return
        progress = self._motion_progress_override
        if progress is None:
            progress = self._timeline.value() / 1000
        frame = self._playback.frame(progress, deepest_visible_z=self._depth.currentData())
        active_uid = self._selected_uid
        if self._animation.isActive() and frame.active_operation_uid is not None:
            active_uid = frame.active_operation_uid
        if self._requested_mode == "vtk" and self._vtk_ready:
            try:
                self._render_vtk_frame(frame, active_uid)
            except Exception as error:
                self._vtk_failed(error)
        else:
            # Rendering both engines for every animation frame doubled the UI
            # thread workload even though only one preview can be visible.
            self._compatible.set_content(
                self._project,
                frame.result,
                selected_uid=active_uid,
                tool_position=frame.tool_position,
                color_mode=self._palette.currentData() or "operation",
            )

    def _actor(self, source, color: str, *, opacity: float = 1.0):
        vtk = self._vtk
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*_rgb(color))
        actor.GetProperty().SetOpacity(opacity)
        self._renderer.AddActor(actor)
        return actor

    def _add_stock(self, project: Project) -> None:
        vtk = self._vtk
        stock = project.stock
        cube = vtk.vtkCubeSource()
        cube.SetBounds(stock.x_min, stock.x_max, stock.y_min, stock.y_max, stock.z_min, stock.z_max)
        material = self._actor(cube, "#65809b", opacity=0.18)
        material.GetProperty().SetSpecular(0.25)
        material.GetProperty().SetSpecularPower(26)

        outline = vtk.vtkOutlineFilter()
        outline.SetInputConnection(cube.GetOutputPort())
        outline_actor = self._actor(outline, "#9ab4ce", opacity=0.88)
        outline_actor.GetProperty().SetLineWidth(1.3)

        floor = vtk.vtkPlaneSource()
        margin = max(stock.width, stock.height) * 0.14
        floor.SetOrigin(stock.x_min - margin, stock.y_min - margin, stock.z_min - 0.1)
        floor.SetPoint1(stock.x_max + margin, stock.y_min - margin, stock.z_min - 0.1)
        floor.SetPoint2(stock.x_min - margin, stock.y_max + margin, stock.z_min - 0.1)
        self._actor(floor, "#243349", opacity=0.42)

    def _motion_polydata(self, toolpath: Toolpath, kinds: set[MotionKind]):
        vtk = self._vtk
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()
        for motion in toolpath.motions:
            if motion.kind not in kinds:
                continue
            first = points.InsertNextPoint(motion.start.x, motion.start.y, motion.start.z)
            last = points.InsertNextPoint(motion.end.x, motion.end.y, motion.end.z)
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, first)
            line.GetPointIds().SetId(1, last)
            lines.InsertNextCell(line)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)
        return polydata

    def _add_toolpath(self, toolpath: Toolpath, color: str, *, active: bool) -> None:
        vtk = self._vtk
        cuts = self._motion_polydata(
            toolpath,
            {MotionKind.CUT, MotionKind.PLUNGE, MotionKind.TAP, MotionKind.TAP_RETURN},
        )
        tube = vtk.vtkTubeFilter()
        tube.SetInputData(cuts)
        tube.SetRadius(toolpath.tool.diameter / 2)
        tube.SetNumberOfSides(12)
        tube.CappingOn()
        cut_actor = self._actor(tube, color, opacity=0.68 if active else 0.20)
        cut_actor.GetProperty().SetSpecular(0.35)
        cut_actor.GetProperty().SetSpecularPower(32)

        rapid = self._motion_polydata(toolpath, {MotionKind.RAPID})
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(rapid)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.64, 0.72, 0.82)
        actor.GetProperty().SetOpacity(0.34 if active else 0.10)
        actor.GetProperty().SetLineWidth(1.4)
        self._renderer.AddActor(actor)

    def _add_tool(self, toolpath: Toolpath, *, position: Point | None = None) -> None:
        vtk = self._vtk
        cuts = [motion for motion in toolpath.motions if motion.kind is not MotionKind.RAPID]
        if not cuts:
            return
        position = position or cuts[-1].end
        length = min(max(toolpath.tool.flute_length, 12), 40)
        cylinder = vtk.vtkCylinderSource()
        cylinder.SetRadius(toolpath.tool.diameter / 2)
        cylinder.SetHeight(length)
        cylinder.SetResolution(28)
        cylinder.SetCenter(0, 0, 0)

        transform = vtk.vtkTransform()
        transform.Translate(position.x, position.y, position.z + length / 2)
        transform.RotateX(90)
        transformed = vtk.vtkTransformPolyDataFilter()
        transformed.SetInputConnection(cylinder.GetOutputPort())
        transformed.SetTransform(transform)
        actor = self._actor(transformed, "#d4dee8", opacity=0.92)
        if hasattr(actor.GetProperty(), "SetMetallic"):
            actor.GetProperty().SetMetallic(0.75)
        if hasattr(actor.GetProperty(), "SetRoughness"):
            actor.GetProperty().SetRoughness(0.23)

    def set_content(self, project: Project, result: BuildResult, *, selected_uid: str | None = None) -> None:
        self._project = project
        self._source_result = result
        self._selected_uid = selected_uid
        signature = (
            project.stock.width,
            project.stock.height,
            project.stock.thickness,
            project.stock.origin,
            tuple(
                (
                    path.operation_uid,
                    len(path.motions),
                    round(path.cutting_length, 5),
                    tuple(round(coordinate, 5) for coordinate in (
                        path.motions[0].end.x,
                        path.motions[0].end.y,
                        path.motions[0].end.z,
                        path.motions[-1].end.x,
                        path.motions[-1].end.y,
                        path.motions[-1].end.z,
                    )) if path.motions else (),
                    path.tool.number,
                    path.tool.diameter,
                    path.spindle_rpm,
                )
                for path in result.toolpaths
            ),
        )
        if signature != self._signature:
            self._signature = signature
            self._playback = ToolpathPlayback(result)
            self._motion_progress_override = None
            previous_depth = self._depth.currentData()
            self._depth.blockSignals(True)
            self._depth.clear()
            self._depth.addItem("Toutes les profondeurs", None)
            for depth in self._playback.depths:
                self._depth.addItem(f"Jusqu’à Z {depth:g} mm", depth)
            selected_depth = self._depth.findData(previous_depth)
            self._depth.setCurrentIndex(selected_depth if selected_depth >= 0 else 0)
            self._depth.blockSignals(False)
            if not self._animation.isActive():
                self._timeline.blockSignals(True)
                self._timeline.setValue(1000)
                self._timeline.blockSignals(False)
                self._progress_label.setText("100 %")
            self._camera_needs_reset = True
        self._apply_frame()

    def _render_vtk_frame(self, frame: PlaybackFrame, selected_uid: str | None) -> None:
        if self._renderer is None or self._project is None:
            return
        self._renderer.RemoveAllViewProps()
        self._add_stock(self._project)
        selected = None
        for index, toolpath in enumerate(frame.result.toolpaths):
            active = selected_uid is None or selected_uid == toolpath.operation_uid
            self._add_toolpath(toolpath, OPERATION_COLORS[index % len(OPERATION_COLORS)], active=active)
            if selected_uid == toolpath.operation_uid:
                selected = toolpath
        if selected is None and frame.result.toolpaths:
            selected = frame.result.toolpaths[-1]
        if selected is not None:
            self._add_tool(selected, position=frame.tool_position)

        stock = self._project.stock
        if self._camera_needs_reset:
            distance = math.hypot(stock.width, stock.height) * 1.35
            camera = self._renderer.GetActiveCamera()
            camera.SetFocalPoint(stock.center_x, stock.center_y, -stock.thickness * 0.25)
            camera.SetPosition(stock.center_x + distance, stock.center_y - distance, distance * 0.82)
            camera.SetViewUp(0, 0, 1)
            self._renderer.ResetCamera()
            self._camera_needs_reset = False
        self._renderer.ResetCameraClippingRange()
        self._interactor.GetRenderWindow().Render()
