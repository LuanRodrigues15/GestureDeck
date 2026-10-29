"""Icones de maos do cartao de ajuda, um por gesto.

Os desenhos em SVG sao do Twemoji (graficos CC-BY 4.0, veja assets/icones/LICENCA.md) e ficam
em assets/icones/. O Twemoji nao tem a mao em L, entao `dois_dedos_l.png` e uma imagem propria
do projeto. As duas poses da mao esquerda (`trava`, o punho, e `aberta`) sao recoloridas na
leitura para branco, para se distinguirem das poses da mao direita.
"""
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer

POSES = ("trava", "aberta", "laser", "pinca", "dois_dedos", "dois_dedos_l")

_PASTA = Path(__file__).resolve().parent.parent / "assets" / "icones"
_ARQUIVOS = {
    "trava": "punho.svg",
    "aberta": "mao_aberta.svg",
    "laser": "indicador.svg",
    "pinca": "pinca.svg",
    "dois_dedos": "dois_dedos.svg",
    "dois_dedos_l": "dois_dedos_l.png",
}
# troca de cores aplicada ao SVG na leitura: pele amarela e sombra laranja viram branco e cinza
_BRANCO = {"#FFDC5D": "#F5F6F8", "#EF9645": "#A9AFBA"}
_RECOLORIR = {"trava": _BRANCO, "aberta": _BRANCO}      # as duas poses da mao esquerda
_SETAS = {"dois_dedos": 1, "dois_dedos_l": -1}      # sentido da troca de slide
_cache: dict = {}


def _carregar(pose: str):
    """Renderizador SVG ou imagem da pose; None se o arquivo faltar ou nao abrir."""
    if pose not in _cache:
        caminho = _PASTA / _ARQUIVOS[pose]
        fonte = None
        try:
            if caminho.suffix == ".svg":
                texto = caminho.read_text(encoding="utf-8")
                for de, para in _RECOLORIR.get(pose, {}).items():
                    texto = texto.replace(de, para)
                fonte = QSvgRenderer(QByteArray(texto.encode("utf-8")))
                if not fonte.isValid():
                    fonte = None
            else:
                fonte = QImage(str(caminho))
                if fonte.isNull():
                    fonte = None
        except OSError:
            fonte = None
        _cache[pose] = fonte
    return _cache[pose]


def desenhar_mao(p, caixa: QRectF, pose: str, espelhar: bool = False) -> None:
    """Desenha o icone de `pose` dentro de `caixa`, espelhado se `espelhar`."""
    fonte = _carregar(pose)
    if fonte is None:
        return
    p.save()
    if espelhar:
        p.translate(caixa.center().x() * 2, 0)
        p.scale(-1, 1)
    if isinstance(fonte, QSvgRenderer):
        fonte.render(p, caixa)
    else:
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawImage(caixa, fonte)
    p.restore()
    if pose in _SETAS:
        _seta(p, caixa, _SETAS[pose])


def _seta(p, caixa: QRectF, sentido: int) -> None:
    """Selo azul no canto inferior esquerdo, com seta para a direita (1) ou a esquerda (-1)."""
    lado = min(caixa.width(), caixa.height())
    raio = lado * 0.2
    c = QPointF(caixa.left() + raio * 0.9, caixa.bottom() - raio * 0.9)   # longe do polegar
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(10, 132, 255, 245))
    p.drawEllipse(c, raio, raio)
    p.setPen(QPen(QColor(255, 255, 255), max(1.5, lado * 0.05), Qt.SolidLine,
                  Qt.RoundCap, Qt.RoundJoin))
    seta = QPainterPath()
    seta.moveTo(c.x() - sentido * raio * 0.5, c.y())
    seta.lineTo(c.x() + sentido * raio * 0.5, c.y())
    seta.moveTo(c.x() + sentido * raio * 0.5, c.y())
    seta.lineTo(c.x() + sentido * raio * 0.1, c.y() - raio * 0.4)
    seta.moveTo(c.x() + sentido * raio * 0.5, c.y())
    seta.lineTo(c.x() + sentido * raio * 0.1, c.y() + raio * 0.4)
    p.setBrush(Qt.NoBrush)
    p.drawPath(seta)
    p.restore()
