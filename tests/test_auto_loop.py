import ast
from pathlib import Path
import re
import unittest
from unittest.mock import Mock


source = Path(__file__).resolve().parents[1] / 'src/tasks/DailyTask.py'
task_class = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                  if isinstance(n, ast.ClassDef) and n.name == 'DailyTask')
method = next(n for n in task_class.body
              if isinstance(n, ast.FunctionDef) and n.name == 'auto_loop')
namespace = {'re': re}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)


class AutoLoopTest(unittest.TestCase):
    def make_task(self, confirm=False):
        task = Mock()
        task.wait_ocr.return_value = confirm
        task._auto_loop_step_with_retry.return_value = True
        task.wait_click_ocr.return_value = True
        return task

    def test_no_confirmation_continues_without_failure_notification(self):
        task = self.make_task()
        namespace['auto_loop'](task)
        self.assertEqual([1, 2, 5], [c.kwargs['step_num']
                                    for c in task._auto_loop_step_with_retry.call_args_list])
        task.wait_click_ocr.assert_called_once()
        self.assertEqual('循环结束', task.wait_click_ocr.call_args.kwargs['match'].pattern)
        task.log_info.assert_not_called()

    def test_present_confirmation_is_handled_before_waiting(self):
        task = self.make_task(confirm=True)
        namespace['auto_loop'](task)
        self.assertEqual([1, 2, 3, 5], [c.kwargs['step_num']
                                       for c in task._auto_loop_step_with_retry.call_args_list])
        task.wait_click_ocr.assert_called_once()

    def test_failed_present_confirmation_stops(self):
        task = self.make_task(confirm=True)
        task._auto_loop_step_with_retry.side_effect = [True, True, False]
        namespace['auto_loop'](task)
        task.wait_click_ocr.assert_not_called()

    def test_loop_timeout_still_reports_failure(self):
        task = self.make_task()
        task.wait_click_ocr.return_value = False
        namespace['auto_loop'](task)
        task.log_info.assert_called_once_with('自主循环步骤4未完成，退出循环', notify=True)


if __name__ == '__main__':
    unittest.main()
