import sys

from PySide6.QtWidgets import QApplication

from controllers.main_controller import MainController
from database.config_manager import carregar_config
from database.logger import configurar_logger
from views.main_window import MainWindow


def main():
    configurar_logger()
    config = carregar_config()
    app = QApplication(sys.argv)
    window = MainWindow()
    controller = MainController(window, config)
    window.show()
    result = app.exec()
    del controller
    sys.exit(result)


if __name__ == "__main__":
    main()
