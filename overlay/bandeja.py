"""Icone na bandeja do Windows: mostra que o programa esta rodando e permite sair.

O overlay nao tem janela visivel nem botao na barra de tarefas, entao sem o
icone nao ha como ver que a camera esta em uso nem como fechar com o mouse.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _icone() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(28, 30, 38))
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 14, 14)
    p.setBrush(QColor(255, 59, 48))
    p.drawEllipse(QRectF(20, 20, 24, 24))
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(QRectF(28, 28, 8, 8))
    p.end()
    return QIcon(pix)


def criar_bandeja(ao_sair):
    """Devolve o icone (guarde a referencia) ou None se a bandeja nao existir."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    bandeja = QSystemTrayIcon(_icone())
    bandeja.setToolTip("GestureDeck em execucao (camera em uso). Botao direito para sair.")
    menu = QMenu()
    titulo = QAction("GestureDeck em execucao")
    titulo.setEnabled(False)
    sair = QAction("Sair e liberar a camera (F10)")
    sair.triggered.connect(ao_sair)
    menu.addAction(titulo)
    menu.addSeparator()
    menu.addAction(sair)
    bandeja.setContextMenu(menu)
    bandeja._menu = menu          # o Qt nao guarda o menu: mantem a referencia viva
    bandeja._acoes = (titulo, sair)
    bandeja.show()
    return bandeja
