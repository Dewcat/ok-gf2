import ast
import itertools
from pathlib import Path
import re
import unittest
from unittest.mock import Mock


# Load the navigation method without starting the Qt/game capture runtime.
source = Path(__file__).resolve().parents[1] / 'src/tasks/DailyTask.py'
task_class = next(node for node in ast.parse(source.read_text(encoding='utf-8')).body
                  if isinstance(node, ast.ClassDef) and node.name == 'DailyTask')
method = next(node for node in task_class.body
              if isinstance(node, ast.FunctionDef) and node.name == 'water_flowers')
namespace = {'re': re}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
water_flowers = namespace['water_flowers']
layer_method = next(node for node in task_class.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'free_time_layer')
exec(compile(ast.Module(body=[layer_method], type_ignores=[]), str(source), 'exec'), namespace)
free_time_layer = namespace['free_time_layer']


class ActivityLayerRoutingTest(unittest.TestCase):
    def make_task(self, drink, eat, water, food_ok=True, can_reuse=True):
        task = Mock()
        task.config = dict(zip(('活动层喝水', '活动层吃饭', '活动层浇花'), (drink, eat, water)))
        events = []
        task.wait_click_ocr.side_effect = lambda **kw: events.append('enter' if kw['match'] == '活动层' else 'claim')
        task.is_free_layer.side_effect = lambda **kw: can_reuse if kw.get('time_out') == 3 else True

        def food(**kw):
            events.append('drink' if kw['enter_func'] is task.go_drink else 'eat')
            return food_ok

        task.do_food_flow.side_effect = food
        task.water_flowers.side_effect = lambda: events.append('water') or True
        task.ensure_main.side_effect = lambda **kw: events.append('exit')
        return task, events

    def test_all_switch_combinations_preserve_required_resets(self):
        for drink, eat, water in itertools.product((False, True), repeat=3):
            with self.subTest(drink=drink, eat=eat, water=water):
                task, events = self.make_task(drink, eat, water)
                self.assertTrue(free_time_layer(task))
                groups = [[name] for name, enabled in (('drink', drink), ('eat', eat)) if enabled]
                if water:
                    if groups:
                        groups[-1].append('water')
                    else:
                        groups.append(['water'])
                groups.append(['claim'])
                expected = [event for group in groups for event in ['enter', *group, 'exit']]
                self.assertEqual(expected, events)

    def test_failed_food_or_unknown_page_reenters_before_watering(self):
        for food_ok, can_reuse in ((False, True), (True, False)):
            with self.subTest(food_ok=food_ok, can_reuse=can_reuse):
                task, events = self.make_task(True, False, True, food_ok, can_reuse)
                free_time_layer(task)
                self.assertEqual(['enter', 'drink', 'exit', 'enter', 'water', 'exit',
                                  'enter', 'claim', 'exit'], events)


class WaterFlowersTest(unittest.TestCase):
    def make_task(self, overview=False, already_done=False, succeeds=True, missing_tab=False):
        task = Mock()
        task.box.right = 'right'
        task.box.bottom_right = 'bottom_right'
        task.box_of_screen.side_effect = lambda *bounds: bounds
        state = {'page': 'tabs', 'done': already_done}
        clicks = []

        def matches(pattern, text):
            return bool(pattern.search(text)) if isinstance(pattern, re.Pattern) else pattern == text

        def click_ocr(*, match, **kwargs):
            labels = {'tabs': '' if missing_tab else '上栽培',
                      'overview': '前往', 'plant': '浇灌'}
            label = labels[state['page']]
            if not matches(match, label):
                return False
            clicks.append(label)
            if state['page'] == 'tabs':
                state['page'] = 'overview' if overview else 'plant'
            elif state['page'] == 'overview':
                state['page'] = 'plant'
            else:
                state['done'] = succeeds
            return True

        def ocr(*, match, box, **kwargs):
            if state['page'] != 'plant':
                return False
            text = '浇灌' if box == 'right' else ('1/1' if state['done'] else '0/1')
            return matches(match, text)

        task.wait_click_ocr.side_effect = click_ocr
        task.wait_ocr.side_effect = ocr
        return task, clicks

    def test_icon_prefix_from_failure_log_is_accepted(self):
        task, clicks = self.make_task()
        self.assertTrue(water_flowers(task))
        self.assertEqual(['上栽培', '浇灌'], clicks)
        task.back.assert_called_once()

    def test_overview_requires_go_button(self):
        task, clicks = self.make_task(overview=True)
        self.assertTrue(water_flowers(task))
        self.assertEqual(['上栽培', '前往', '浇灌'], clicks)

    def test_already_watered_does_not_click_again(self):
        task, clicks = self.make_task(already_done=True)
        self.assertTrue(water_flowers(task))
        self.assertEqual(['上栽培'], clicks)
        task.back.assert_called_once()

    def test_click_without_updated_count_is_failure(self):
        task, _ = self.make_task(succeeds=False)
        self.assertFalse(water_flowers(task))
        task.back.assert_called_once()

    def test_missing_tab_does_not_water(self):
        task, clicks = self.make_task(missing_tab=True)
        self.assertFalse(water_flowers(task))
        self.assertEqual([], clicks)


if __name__ == '__main__':
    unittest.main()
