import os
import gc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"))

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow
from shiboken6 import isValid


@pytest.fixture(scope="session")
def _aplicacao():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def app(_aplicacao):
    instancia = _aplicacao
    yield instancia
    instancia.closeAllWindows()
    for janela in instancia.topLevelWidgets():
        if isValid(janela) and isinstance(janela, (QMainWindow, QDialog)) and janela.parent() is None:
            janela.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    instancia.processEvents()
    gc.collect()
