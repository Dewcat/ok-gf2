"""Keep the automatic update check from reopening a deliberately closed launcher."""

from functools import wraps

from ok.util.GlobalConfig import KILL_LAUNCHER_AFTER_START


def install_startup_update_guard(window):
    # ok-script calls the application's on_show_main_window hook before showEvent.
    if getattr(window, '_gf2_startup_update_guard', False):
        return
    schedule = window._schedule_update_check

    @wraps(schedule)
    def schedule_if_launcher_is_kept():
        if window.basic_global_config.get(KILL_LAUNCHER_AFTER_START):
            return
        return schedule()

    window._schedule_update_check = schedule_if_launcher_is_kept
    window._gf2_startup_update_guard = True
