"""Gera maos sinteticas (21 pontos) para testar o reconhecimento sem camera.

Unidades do molde: tamanho da mao = 1 (pulso ate a base do dedo medio),
y negativo aponta para cima.
"""
import numpy as np

_ESTICADO = {
    "indicador": [(-0.32, -0.95), (-0.38, -1.45), (-0.41, -1.75), (-0.43, -2.00)],
    "medio": [(0.00, -1.00), (0.00, -1.55), (0.00, -1.90), (0.00, -2.15)],
    "anelar": [(0.30, -0.95), (0.34, -1.45), (0.36, -1.72), (0.38, -1.95)],
    "minimo": [(0.55, -0.85), (0.62, -1.25), (0.66, -1.50), (0.68, -1.70)],
}
_DOBRADO = {
    "indicador": [(-0.32, -0.95), (-0.36, -1.40), (-0.33, -1.20), (-0.30, -0.90)],
    "medio": [(0.00, -1.00), (0.00, -1.45), (0.00, -1.22), (0.00, -0.90)],
    "anelar": [(0.30, -0.95), (0.33, -1.40), (0.32, -1.18), (0.30, -0.85)],
    "minimo": [(0.55, -0.85), (0.60, -1.20), (0.58, -1.00), (0.55, -0.80)],
}
_POLEGAR_ABERTO = [(-0.35, -0.25), (-0.60, -0.50), (-0.80, -0.75), (-0.95, -0.95)]
_POLEGAR_FECHADO = [(-0.35, -0.25), (-0.45, -0.55), (-0.30, -0.70), (-0.05, -0.70)]
_POLEGAR_PINCA = [(-0.35, -0.25), (-0.55, -0.80), (-0.50, -1.40), (-0.45, -1.95)]
_POLEGAR_L = [(-0.35, -0.25), (-0.70, -0.55), (-0.95, -0.85), (-1.15, -1.00)]
_POLEGAR_MEIO = [(-0.35, -0.25), (-0.65, -0.55), (-0.85, -0.80), (-1.02, -0.95)]
_POLEGARES = {"L": _POLEGAR_L, "meio": _POLEGAR_MEIO, "dobrado": _POLEGAR_FECHADO}

NOMES = ("indicador", "medio", "anelar", "minimo")


def mao(esticados=(False, False, False, False), pinca=False, centro=(0.6, 0.5),
        escala=0.12, aspecto=16 / 9, polegar=None) -> np.ndarray:
    """`centro` e a posicao normalizada da base do dedo medio; `escala` e o
    tamanho da mao como fracao da altura da imagem. `polegar` pode ser "L"
    (aberto), "meio" (solto, ambiguo) ou "dobrado"."""
    pts = [(0.0, 0.0)]
    if polegar is not None:
        pts += _POLEGARES[polegar]
    else:
        pts += _POLEGAR_PINCA if pinca else (_POLEGAR_ABERTO if all(esticados) else _POLEGAR_FECHADO)
    for nome, aberto in zip(NOMES, esticados):
        pts += (_ESTICADO if aberto else _DOBRADO)[nome]
    pts = np.array(pts, dtype=float)
    # origem no pulso; a base do dedo medio fica em (0, -1) -> centro
    x = centro[0] + pts[:, 0] * escala / aspecto
    y = centro[1] + (pts[:, 1] + 1.0) * escala
    return np.stack([x, y, np.zeros(21)], axis=1)


def girar(pontos: np.ndarray, graus: float, aspecto: float = 16 / 9) -> np.ndarray:
    """Gira a mao em torno do pulso (sentido horario na imagem, como o relogio)."""
    p = pontos.copy()
    p[:, 0] *= aspecto
    origem = p[0, :2].copy()
    a = np.radians(graus)
    c, s = np.cos(a), np.sin(a)
    rel = p[:, :2] - origem
    # o y da imagem cresce para baixo, entao esta rotacao e horaria na tela
    p[:, 0] = origem[0] + rel[:, 0] * c - rel[:, 1] * s
    p[:, 1] = origem[1] + rel[:, 0] * s + rel[:, 1] * c
    p[:, 0] /= aspecto
    return p


def dois_dedos(centro=(0.7, 0.4), graus=0.0, **kw):
    """Indicador e medio esticados; `graus` gira a mao (0 = para cima, 180 = para baixo).

    Com `polegar="L"` e o gesto de voltar (dois dedos e polegar aberto)."""
    return girar(mao((True, True, False, False), centro=centro, **kw), graus)


def punho(centro=(0.3, 0.5), **kw):
    return mao((False, False, False, False), centro=centro, **kw)


def laser(centro=(0.7, 0.4), **kw):
    return mao((True, False, False, False), centro=centro, **kw)


def aberta(centro=(0.7, 0.4), **kw):
    return mao((True, True, True, True), centro=centro, **kw)


def pinca(centro=(0.7, 0.4), **kw):
    return mao((True, False, False, False), pinca=True, centro=centro, **kw)
