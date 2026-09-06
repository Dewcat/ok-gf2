import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ok.util.GlobalConfig import KILL_LAUNCHER_AFTER_START
from src.globals import Globals


class StartupUpdateGuardTest(unittest.TestCase):
    def make_window(self, kill_launcher):
        callbacks = []
        manual_check = Mock()
        window = SimpleNamespace(
            basic_global_config={KILL_LAUNCHER_AFTER_START: kill_launcher},
            about_tab=SimpleNamespace(check_for_updates=manual_check),
            _schedule_update_check=Mock(side_effect=lambda: callbacks.append(manual_check)),
        )
        Globals.on_show_main_window(None, window)
        return window, callbacks, manual_check

    def test_closed_launcher_is_not_reopened_by_delayed_check(self):
        window, callbacks, check = self.make_window(True)
        window._schedule_update_check()
        for callback in callbacks:
            callback()
        self.assertEqual([], callbacks)
        check.assert_not_called()
        # The about-page button is still wired to the original manual check.
        window.about_tab.check_for_updates()
        check.assert_called_once_with()

    def test_kept_launcher_still_gets_automatic_check(self):
        window, callbacks, check = self.make_window(False)
        window._schedule_update_check()
        self.assertEqual(1, len(callbacks))
        callbacks[0]()
        check.assert_called_once_with()

    def test_reads_current_setting_and_does_not_wrap_twice(self):
        window, callbacks, _ = self.make_window(False)
        wrapped = window._schedule_update_check
        Globals.on_show_main_window(None, window)
        self.assertIs(wrapped, window._schedule_update_check)
        window.basic_global_config[KILL_LAUNCHER_AFTER_START] = True
        window._schedule_update_check()
        self.assertEqual([], callbacks)


if __name__ == '__main__':
    unittest.main()
