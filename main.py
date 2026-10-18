import sys
from PySide6.QtWidgets import QApplication

from database.logger import configurar_logger
from database.connection import init_db
from database.config_manager import carregar_config
from controllers.main_controller import MainController


def main():
    configurar_logger()
    init_db()
    config = carregar_config()
    app = QApplication(sys.argv)
    window = MainController(config=config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()