from PySide6.QtCore import QObject

from ok import Logger
from src.ui.startup_update_guard import install_startup_update_guard

logger = Logger.get_logger(__name__)


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        # ok.og.executor.ocr_lib.add_text_fix({"a": "b"})

    def on_show_main_window(self, window):
        install_startup_update_guard(window)


if __name__ == "__main__":
    glbs = Globals(exit_event=None)
