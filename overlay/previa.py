"""Janela comum com a imagem da camera, os pontos das maos e os dados de depuracao."""
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gestures.geometria import CONEXOES


def desenhar_previa(frame_bgr, maos, zona, linhas, largura=800):
    """Devolve uma copia reduzida do quadro com o esqueleto das maos e a zona ativa."""
    h, w = frame_bgr.shape[:2]
    escala = largura / w
    img = cv2.resize(frame_bgr, (largura, int(h * escala)), interpolation=cv2.INTER_AREA)
    ih, iw = img.shape[:2]
    x0, y0, x1, y1 = zona
    cv2.rectangle(img, (int(x0 * iw), int(y0 * ih)), (int(x1 * iw), int(y1 * ih)), (80, 200, 80), 2)
    for pontos in maos:
        px = (pontos[:, 0] * iw).astype(int)
        py = (pontos[:, 1] * ih).astype(int)
        for a, b in CONEXOES:
            cv2.line(img, (px[a], py[a]), (px[b], py[b]), (255, 200, 0), 2)
        for i in range(21):
            cv2.circle(img, (px[i], py[i]), 3, (0, 0, 255), -1)
    for i, linha in enumerate(linhas):
        cv2.putText(img, linha, (10, 24 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, linha, (10, 24 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return img


class Previa(QWidget):
    def __init__(self, fornecedor, mensagem=None):
        super().__init__()
        self._fornecedor = fornecedor
        self._mensagem = mensagem
        self.setWindowTitle("GestureDeck: camera")
        self._rotulo = QLabel("Aguardando a camera...")
        self._rotulo.setAlignment(Qt.AlignCenter)
        self._rotulo.setMinimumSize(640, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._rotulo)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._timer.start(33)

    def _atualizar(self) -> None:
        img = self._fornecedor()
        if img is None:
            texto = self._mensagem() if self._mensagem else None
            if texto:
                self._rotulo.setText(texto)
                self._rotulo.setWordWrap(True)
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format_RGB888)
        self._rotulo.setPixmap(QPixmap.fromImage(qimg.copy()))
