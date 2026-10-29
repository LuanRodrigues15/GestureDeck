"""Contrato entre visao e overlay.

A visao produz um Quadro por imagem processada. O overlay (e o simulador de
testes) so conhece este contrato, nunca o MediaPipe.
"""
from dataclasses import dataclass
from enum import Enum


class Gesto(Enum):
    NENHUM = "nenhum"
    LASER = "laser"
    DESENHAR = "desenhar"
    SLIDE_PROXIMO = "slide seguinte"      # dois dedos para cima
    SLIDE_ANTERIOR = "slide anterior"     # dois dedos para baixo


GESTOS_DE_SLIDE = (Gesto.SLIDE_PROXIMO, Gesto.SLIDE_ANTERIOR)


class Slide(Enum):
    PROXIMO = 1
    ANTERIOR = -1


@dataclass(frozen=True)
class Quadro:
    t: float                                   # segundos (relogio monotonico)
    trava: bool = False                        # comandos habilitados
    gesto: Gesto = Gesto.NENHUM                # gesto estavel da mao direita
    ponteiro: tuple[float, float] | None = None  # posicao na tela, 0..1
    slide: Slide | None = None                 # troca de slide neste quadro
    maos: int = 0                              # maos visiveis
    segurando: tuple[Gesto, float] | None = None  # gesto de slide em confirmacao, 0..1
