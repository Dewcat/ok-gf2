"""Disable the automatic update check when the main window opens."""


def install_startup_update_guard(window):
    # ok-script calls the application's on_show_main_window hook before showEvent.
    if getattr(window, '_gf2_startup_update_guard', False):
        return
    def skip_startup_update_check():
        return

    window._schedule_update_check = skip_startup_update_check
    window._gf2_startup_update_guard = True
