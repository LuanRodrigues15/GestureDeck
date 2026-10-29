"""Janela transparente por cima da tela: laser, holofote, tracos, barra e indicadores."""
import ctypes
import math
import sys
from ctypes import wintypes

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from gestures.eventos import Gesto

_AJUDA = [
    "GestureDeck",
    "Mao esquerda fechada e levantada: habilita",
    "Indicador esticado: laser",
    "Pinca (polegar e indicador): desenhar",
    "Mao direita aberta deslizando: slide",
    "F1 ajuda   F2 laser/holofote   F9 pausa   F10 sair",
]
_FONTE = "Segoe UI"


class JanelaOverlay(QWidget):
    def __init__(self, sessao, tela, intervalo_ms: int = 16):
        super().__init__()
        self.sessao = sessao
        self.cfg = sessao.cfg
        self._ultima_versao = -1
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        geo = tela.geometry()
        self.setGeometry(geo)
        sessao.definir_tela(geo.width(), geo.height())

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._timer.start(intervalo_ms)
        self._timer_topo = QTimer(self)
        self._timer_topo.timeout.connect(self._reafirmar_topo)
        self._timer_topo.start(1500)

    # --- janela -------------------------------------------------------------
    def mostrar(self) -> None:
        self.show()
        self._reafirmar_topo()

    def _reafirmar_topo(self) -> None:
        """O PowerPoint em F5 tambem fica no topo; reafirma o overlay acima dele."""
        if sys.platform != "win32":
            return
        funcao = ctypes.windll.user32.SetWindowPos
        funcao.argtypes = [
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        # HWND_TOPMOST=-1; SWP_NOSIZE|NOMOVE|NOACTIVATE|SHOWWINDOW
        funcao(int(self.winId()), -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)

    def _atualizar(self) -> None:
        s = self.sessao.instantaneo()
        precisa = (
            s.versao != self._ultima_versao
            or s.aviso is not None
            or len(s.rastro) > 0
        )
        if precisa:
            self._ultima_versao = s.versao
            self.update()

    # --- desenho --------------------------------------------------------------
    def paintEvent(self, _evento):
        s = self.sessao.instantaneo()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()

        self._tracos(p, s, h)
        if s.trava:
            self._barra(p, s, h)
            self._ponteiro(p, s, w, h)
        self._indicador(p, s, w, h)
        if s.ajuda:
            self._ajuda(p, h)
        if s.aviso:
            self._aviso(p, s, w, h)
        p.end()

    def _tracos(self, p, s, h):
        largura = max(3.0, self.cfg.espessura * h)
        for cor, pontos in s.tracos:
            if len(pontos) < 2:
                continue
            caminho = self._suavizar(pontos, self.width(), h)
            brilho = QColor(cor)
            brilho.setAlpha(55)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(brilho, largura * 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(caminho)
            p.setPen(QPen(QColor(cor), largura, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(caminho)

    @staticmethod
    def _suavizar(pontos, w, h) -> QPainterPath:
        pts = [QPointF(x * w, y * h) for x, y in pontos]
        caminho = QPainterPath(pts[0])
        for i in range(1, len(pts) - 1):
            meio = QPointF((pts[i].x() + pts[i + 1].x()) / 2, (pts[i].y() + pts[i + 1].y()) / 2)
            caminho.quadTo(pts[i], meio)
        caminho.lineTo(pts[-1])
        return caminho

    def _ponteiro(self, p, s, w, h):
        if s.ponteiro is None or s.gesto not in (Gesto.LASER, Gesto.DESENHAR):
            return
        x, y = s.ponteiro[0] * w, s.ponteiro[1] * h
        if s.gesto == Gesto.DESENHAR:
            if s.ferramenta == "borracha":
                raio = self.cfg.borracha_raio * h
                p.setBrush(QColor(255, 255, 255, 40))
                p.setPen(QPen(QColor(255, 255, 255, 230), 2.5))
                p.drawEllipse(QPointF(x, y), raio, raio)
            else:
                raio = max(4.0, self.cfg.espessura * h * 0.9)
                p.setPen(QPen(QColor(255, 255, 255, 230), 2))
                p.setBrush(QColor(s.cor_atual))
                p.drawEllipse(QPointF(x, y), raio, raio)
            return
        if s.modo_holofote:
            self._holofote(p, x, y, self.cfg.holofote_raio * h)
        else:
            self._laser(p, s, x, y, self.cfg.laser_raio * h)

    @staticmethod
    def _laser(p, s, x, y, raio):
        p.setPen(Qt.NoPen)
        # rastro curto que se apaga
        for idade, rx, ry in s.rastro:
            alfa = max(0.0, 1.0 - idade / 0.35)
            r = raio * (0.25 + 0.55 * alfa)
            p.setBrush(QColor(255, 40, 40, int(90 * alfa)))
            p.drawEllipse(QPointF(rx * p.device().width(), ry * p.device().height()), r, r)
        halo = QRadialGradient(QPointF(x, y), raio * 2.6)
        halo.setColorAt(0.0, QColor(255, 40, 40, 200))
        halo.setColorAt(0.35, QColor(255, 20, 20, 90))
        halo.setColorAt(1.0, QColor(255, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(x, y), raio * 2.6, raio * 2.6)
        miolo = QRadialGradient(QPointF(x, y), raio)
        miolo.setColorAt(0.0, QColor(255, 255, 255, 255))
        miolo.setColorAt(0.45, QColor(255, 70, 70, 255))
        miolo.setColorAt(1.0, QColor(255, 0, 0, 230))
        p.setBrush(QBrush(miolo))
        p.drawEllipse(QPointF(x, y), raio, raio)

    @staticmethod
    def _holofote(p, x, y, raio):
        luz = QRadialGradient(QPointF(x, y), raio)
        luz.setColorAt(0.0, QColor(255, 250, 225, 150))
        luz.setColorAt(0.55, QColor(255, 250, 225, 95))
        luz.setColorAt(0.85, QColor(255, 250, 225, 28))
        luz.setColorAt(1.0, QColor(255, 250, 225, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(luz))
        p.drawEllipse(QPointF(x, y), raio, raio)

    def _barra(self, p, s, h):
        x, y, w, hh = s.barra_painel
        r = s.barra_itens[0].r
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
        p.setBrush(QColor(20, 22, 28, 175))
        p.drawRoundedRect(QRectF(x, y, w, hh), r * 0.9, r * 0.9)
        cores = self.cfg.cores
        for item in s.barra_itens:
            centro = QPointF(item.cx, item.cy)
            ativo = (
                (item.id.startswith("cor:") and s.ferramenta == "caneta"
                 and int(item.id.split(":")[1]) == s.cor_indice)
                or (item.id == "borracha" and s.ferramenta == "borracha")
            )
            if item.id.startswith("cor:"):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(cores[int(item.id.split(":")[1])]))
                p.drawEllipse(centro, item.r * 0.78, item.r * 0.78)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 255, 255, 38))
                p.drawEllipse(centro, item.r * 0.78, item.r * 0.78)
                self._icone(p, item)
            if ativo:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 240), 3))
                p.drawEllipse(centro, item.r * 0.98, item.r * 0.98)
            if s.hover == item.id and s.progresso > 0:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 255), 5, Qt.SolidLine, Qt.RoundCap))
                caixa = QRectF(item.cx - item.r * 1.12, item.cy - item.r * 1.12,
                               item.r * 2.24, item.r * 2.24)
                p.drawArc(caixa, 90 * 16, int(-360 * 16 * s.progresso))

    @staticmethod
    def _icone(p, item):
        c = QPointF(item.cx, item.cy)
        r = item.r * 0.42
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 235), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        if item.id == "borracha":
            p.save()
            p.translate(c)
            p.rotate(-35)
            p.drawRoundedRect(QRectF(-r * 1.1, -r * 0.6, r * 2.2, r * 1.2), 3, 3)
            p.drawLine(QPointF(-r * 0.2, -r * 0.6), QPointF(-r * 0.2, r * 0.6))
            p.restore()
        elif item.id == "desfazer":
            caminho = QPainterPath()
            caminho.moveTo(c.x() - r * 0.9, c.y() - r * 0.2)
            caminho.cubicTo(c.x() - r * 0.2, c.y() - r * 1.3, c.x() + r * 1.2, c.y() - r * 0.7,
                            c.x() + r * 0.9, c.y() + r * 0.7)
            p.drawPath(caminho)
            p.drawLine(QPointF(c.x() - r * 0.9, c.y() - r * 0.2), QPointF(c.x() - r * 0.9, c.y() - r * 1.0))
            p.drawLine(QPointF(c.x() - r * 0.9, c.y() - r * 0.2), QPointF(c.x() - r * 0.1, c.y() - r * 0.2))
        elif item.id == "limpar":
            p.drawLine(QPointF(c.x() - r, c.y() - r), QPointF(c.x() + r, c.y() + r))
            p.drawLine(QPointF(c.x() - r, c.y() + r), QPointF(c.x() + r, c.y() - r))

    def _indicador(self, p, s, w, h):
        if s.pausado:
            texto, cor = "PAUSADO (F9 retoma)", QColor(255, 159, 10)
        elif s.trava:
            nomes = {Gesto.NENHUM: "aguardando gesto", Gesto.LASER: "laser",
                     Gesto.DESENHAR: "desenhando", Gesto.ABERTA: "mao aberta"}
            if s.gesto == Gesto.LASER and s.modo_holofote:
                nomes[Gesto.LASER] = "holofote"
            texto, cor = f"Trava ativa  |  {nomes[s.gesto]}", QColor(52, 199, 89)
        else:
            texto, cor = ("Trava inativa" if s.maos else "Sem maos"), QColor(142, 142, 147)
        partes = [texto, f"{s.fps:.0f} FPS"]
        if s.ensaio:
            partes.insert(0, "ENSAIO")
        self._pilula(p, " | ".join(partes), cor, h * 0.02, h - h * 0.02, h, ancora_baixo=True)

    def _pilula(self, p, texto, cor, x, y, h, ancora_baixo=False):
        fonte = QFont(_FONTE, max(9, int(h * 0.0145)))
        fonte.setWeight(QFont.DemiBold)
        p.setFont(fonte)
        fm = QFontMetrics(fonte)
        alt = fm.height() + h * 0.014
        larg = fm.horizontalAdvance(texto) + h * 0.05
        topo = y - alt if ancora_baixo else y
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 22, 28, 190))
        p.drawRoundedRect(QRectF(x, topo, larg, alt), alt / 2, alt / 2)
        p.setBrush(cor)
        p.drawEllipse(QPointF(x + alt * 0.5, topo + alt / 2), alt * 0.18, alt * 0.18)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(QRectF(x + alt * 0.85, topo, larg, alt), Qt.AlignVCenter | Qt.AlignLeft, texto)

    def _ajuda(self, p, h):
        fonte = QFont(_FONTE, max(8, int(h * 0.0105)))
        p.setFont(fonte)
        fm = QFontMetrics(fonte)
        margem = h * 0.02
        pad = h * 0.012
        larg = max(fm.horizontalAdvance(t) for t in _AJUDA) + 2 * pad
        alt = fm.height() * len(_AJUDA) + 2 * pad
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(20, 22, 28, 170))
        p.drawRoundedRect(QRectF(margem, margem, larg, alt), pad, pad)
        for i, linha in enumerate(_AJUDA):
            negrito = QFont(fonte)
            negrito.setBold(i == 0)
            p.setFont(negrito)
            p.setPen(QColor(255, 255, 255, 245 if i == 0 else 215))
            p.drawText(QPointF(margem + pad, margem + pad + fm.ascent() + i * fm.height()), linha)

    def _aviso(self, p, s, w, h):
        fonte = QFont(_FONTE, max(14, int(h * 0.03)))
        fonte.setWeight(QFont.DemiBold)
        p.setFont(fonte)
        fm = QFontMetrics(fonte)
        larg = fm.horizontalAdvance(s.aviso) + h * 0.08
        alt = fm.height() + h * 0.03
        x = (w - larg) / 2
        y = h * 0.06
        p.setOpacity(s.aviso_alfa)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 22, 28, 215))
        p.drawRoundedRect(QRectF(x, y, larg, alt), alt / 2, alt / 2)
        p.setPen(QColor(255, 255, 255, 255))
        p.drawText(QRectF(x, y, larg, alt), Qt.AlignCenter, s.aviso)
        p.setOpacity(1.0)
