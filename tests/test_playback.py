from __future__ import annotations

import unittest

from openmill.adapters.mock import MockMachineAdapter
from openmill.core.engine import BuildResult, build_project, create_demo_project
from openmill.core.models import MotionKind
from openmill.core.playback import ToolpathPlayback


class PlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = create_demo_project()
        self.result = build_project(self.project, MockMachineAdapter())
        self.playback = ToolpathPlayback(self.result)

    def test_empty_timeline_is_safe(self) -> None:
        timeline = ToolpathPlayback(BuildResult())
        frame = timeline.frame(0.5)
        self.assertEqual(frame.total_motion_count, 0)
        self.assertIsNone(frame.tool_position)

    def test_beginning_contains_no_completed_motion(self) -> None:
        frame = self.playback.frame(0)
        self.assertEqual(frame.motion_count, 0)
        self.assertIsNotNone(frame.tool_position)

    def test_end_contains_every_motion(self) -> None:
        frame = self.playback.frame(1)
        self.assertEqual(frame.motion_count, self.playback.motion_count)
        self.assertEqual(len(frame.result.toolpaths), len(self.result.toolpaths))

    def test_middle_interpolates_a_partial_path(self) -> None:
        frame = self.playback.frame(0.5)
        self.assertGreater(frame.motion_count, 0)
        self.assertLess(frame.motion_count, self.playback.motion_count)
        self.assertIsNotNone(frame.tool_position)

    def test_progress_is_clamped(self) -> None:
        self.assertEqual(self.playback.frame(-5).progress, 0)
        self.assertEqual(self.playback.frame(5).progress, 1)

    def test_motion_count_can_drive_timeline_from_gcode_line(self) -> None:
        self.assertEqual(self.playback.progress_for_motion_count(0), 0)
        middle = self.playback.progress_for_motion_count(1)
        self.assertGreater(middle, 0)
        self.assertLessEqual(middle, 1)
        self.assertEqual(self.playback.frame(middle).motion_count, 1)
        self.assertEqual(self.playback.progress_for_motion_count(999999), 1)

    def test_depths_are_sorted_from_surface_to_bottom(self) -> None:
        self.assertTrue(self.playback.depths)
        self.assertEqual(self.playback.depths, tuple(sorted(self.playback.depths, reverse=True)))

    def test_depth_filter_hides_deeper_cuts(self) -> None:
        frame = self.playback.frame(1, deepest_visible_z=-1)
        cuts = [
            motion
            for path in frame.result.toolpaths
            for motion in path.motions
            if motion.kind is not MotionKind.RAPID
        ]
        self.assertTrue(cuts)
        self.assertTrue(all(motion.end.z >= -1 for motion in cuts))

    def test_frame_preserves_tool_information(self) -> None:
        frame = self.playback.frame(1)
        self.assertIsNotNone(frame.active_tool)
        self.assertEqual(frame.active_tool.number, 5)

    def test_timeline_is_renderer_independent(self) -> None:
        self.assertTrue(self.playback.total_distance > 0)
        self.assertEqual(self.playback.motion_count, sum(len(path.motions) for path in self.result.toolpaths))


if __name__ == "__main__":
    unittest.main()
