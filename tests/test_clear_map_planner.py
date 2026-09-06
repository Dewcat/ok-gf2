import unittest

import cv2
import numpy as np

from ok import Box

from src.tasks.ClearMapTask import (
    associate_completion_icons,
    build_stage_nodes,
    find_orange_check_icons,
    infer_main_row,
    map_view_changed,
    plan_stage_nodes,
)


class ClearMapPlannerTest(unittest.TestCase):

    def test_detects_orange_check_but_rejects_flat_battle_badge(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        orange = cv2.cvtColor(
            np.uint8([[[12, 230, 250]]]),
            cv2.COLOR_HSV2BGR,
        )[0, 0].tolist()
        cv2.circle(frame, (500, 400), 13, orange, -1)
        cv2.rectangle(frame, (180, 500), (205, 514), orange, -1)

        icons = find_orange_check_icons(frame, Box(0, 100, 1920, 880))

        self.assertEqual(1, len(icons))
        self.assertAlmostEqual(500, icons[0].center()[0], delta=2)

    def test_merges_ocr_variants_but_not_adjacent_stages(self):
        boxes = [
            Box(70, 530, 100, 30, 0.99, 'SL-10-2'),
            Box(85, 531, 85, 30, 0.80, 'L-10-2'),
            Box(535, 530, 100, 30, 0.99, '10-5'),
        ]

        nodes = build_stage_nodes(boxes, 1920, 1080)

        self.assertEqual(['10-5', 'SL-10-2'], sorted(node.name for node in nodes))
        sl_node = next(node for node in nodes if node.name == 'SL-10-2')
        self.assertEqual({'SL-10-2', 'L-10-2'}, sl_node.aliases)

    def test_orange_check_is_attached_to_stage_down_left(self):
        boxes = [
            Box(70, 530, 100, 30, 0.99, 'SL-10-2'),
            Box(535, 530, 100, 30, 0.99, '10-5'),
        ]
        nodes = build_stage_nodes(boxes, 1920, 1080)
        icons = [Box(190, 495, 25, 13, 0.99, 'now_icon')]

        associate_completion_icons(nodes, icons, 1920, 1080)

        completed = {node.name for node in nodes if node.completed}
        self.assertEqual({'SL-10-2'}, completed)

    def test_plans_upper_and_lower_branches_before_main_row(self):
        boxes = [
            Box(150, 500, 100, 30, 0.99, 'AA-2-7'),
            Box(700, 500, 100, 30, 0.99, 'AA-2-8'),
            Box(980, 280, 100, 30, 0.99, 'AZ-2-3'),
            Box(1050, 700, 100, 30, 0.99, 'AZ-2-2'),
        ]
        nodes = build_stage_nodes(boxes, 1920, 1080)

        planned, main_y = plan_stage_nodes(nodes, set(), set(), 1080)

        self.assertAlmostEqual(515, main_y)
        self.assertEqual(['AZ-2-3', 'AZ-2-2'], [node.name for node in planned[:2]])
        self.assertEqual({'AA-2-7', 'AA-2-8'}, {node.name for node in planned[2:]})

    def test_main_row_tie_prefers_vertical_center_not_wider_upper_branch(self):
        boxes = [
            Box(70, 320, 100, 30, 0.99, 'BH-10-3'),
            Box(640, 320, 100, 30, 0.99, 'BH-10-4'),
            Box(1200, 320, 100, 30, 0.99, 'BH-10-5'),
            Box(360, 500, 100, 30, 0.99, '10-10'),
            Box(900, 500, 100, 30, 0.99, '10-11'),
            Box(1430, 500, 100, 30, 0.99, 'SL-10-6'),
        ]
        nodes = build_stage_nodes(boxes, 1920, 1080)

        planned, main_y = plan_stage_nodes(nodes, set(), set(), 1080)

        self.assertAlmostEqual(515, main_y)
        self.assertEqual(
            ['BH-10-3', 'BH-10-4', 'BH-10-5'],
            [node.name for node in planned[:3]],
        )

    def test_completed_and_locked_nodes_leave_unlocked_main_stage(self):
        boxes = [
            Box(70, 530, 100, 30, 0.99, 'SL-10-2'),
            Box(535, 530, 100, 30, 0.99, '10-5'),
            Box(980, 530, 100, 30, 0.99, 'SL-10-3'),
            Box(1220, 700, 100, 30, 0.99, 'BH-10-1'),
        ]
        nodes = build_stage_nodes(boxes, 1920, 1080)
        next(node for node in nodes if node.name == 'SL-10-2').completed = True

        planned, _ = plan_stage_nodes(
            nodes,
            processed=set(),
            blocked={'SL-10-3', 'BH-10-1'},
            screen_height=1080,
        )

        self.assertEqual(['10-5'], [node.name for node in planned])

    def test_pan_verification_requires_material_node_movement(self):
        before = build_stage_nodes([
            Box(800, 500, 100, 30, 0.99, '10-1'),
            Box(1350, 500, 100, 30, 0.99, '10-2'),
        ], 1920, 1080)
        jitter = build_stage_nodes([
            Box(802, 500, 100, 30, 0.99, '10-1'),
            Box(1349, 500, 100, 30, 0.99, '10-2'),
        ], 1920, 1080)
        moved = build_stage_nodes([
            Box(250, 500, 100, 30, 0.99, '10-1'),
            Box(800, 500, 100, 30, 0.99, '10-2'),
        ], 1920, 1080)

        self.assertFalse(map_view_changed(before, jitter, 1920))
        self.assertTrue(map_view_changed(before, moved, 1920))


if __name__ == '__main__':
    unittest.main()
