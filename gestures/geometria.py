"""Geometria da mao a partir dos 21 pontos do MediaPipe.

Todas as distancias sao divididas pelo tamanho da mao, entao os limiares nao
dependem da distancia entre a pessoa e a camera nem da direcao da mao.
"""
from dataclasses import dataclass

import numpy as np

PULSO = 0
POLEGAR_PONTA = 4
INDICADOR = (5, 6, 7, 8)   # base, articulacao do meio, articulacao da ponta, ponta
MEDIO = (9, 10, 11, 12)
ANELAR = (13, 14, 15, 16)
MINIMO = (17, 18, 19, 20)
DEDOS = (INDICADOR, MEDIO, ANELAR, MINIMO)

CONEXOES = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
    (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


def distancia(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def corrigir_aspecto(pontos: np.ndarray, aspecto: float) -> np.ndarray:
    """Pontos normalizados (0..1) viram unidades com x e y na mesma escala."""
    p = np.asarray(pontos, dtype=np.float64)[:, :2].copy()
    p[:, 0] *= aspecto
    return p


def tamanho_mao(p: np.ndarray) -> float:
    """Pulso ate a base do dedo medio, ou a largura da palma se for maior."""
    return max(distancia(p[0], p[9]), 1.15 * distancia(p[5], p[17]), 1e-6)


def dedo_esticado(p: np.ndarray, dedo: tuple, tamanho: float, limiar: float) -> bool:
    """Ponta mais longe do pulso que a articulacao do meio do dedo."""
    _, meio, _, ponta = dedo
    return (distancia(p[0], p[ponta]) - distancia(p[0], p[meio])) / tamanho > limiar


def razao_pinca(p: np.ndarray, tamanho: float) -> float:
    return distancia(p[POLEGAR_PONTA], p[8]) / tamanho


def centro_palma(p: np.ndarray) -> np.ndarray:
    return p[[0, 5, 9, 13, 17]].mean(axis=0)


@dataclass
class Mao:
    pontos: np.ndarray        # (21, 3) normalizados na imagem espelhada
    palma: np.ndarray         # centro da palma, normalizado
    palma_c: np.ndarray       # centro da palma, escala corrigida pelo aspecto
    tamanho: float
    esticados: tuple          # (indicador, medio, anelar, minimo)
    pinca: float              # distancia polegar-indicador / tamanho

    @property
    def fechada(self) -> bool:
        return not any(self.esticados)

    @property
    def laser(self) -> bool:
        return self.esticados == (True, False, False, False)

    @property
    def aberta(self) -> bool:
        return all(self.esticados)


def montar_mao(pontos: np.ndarray, aspecto: float, limiar: float) -> Mao:
    p = corrigir_aspecto(pontos, aspecto)
    tam = tamanho_mao(p)
    esticados = tuple(dedo_esticado(p, d, tam, limiar) for d in DEDOS)
    return Mao(
        pontos=np.asarray(pontos),
        palma=centro_palma(np.asarray(pontos)[:, :2]),
        palma_c=centro_palma(p),
        tamanho=tam,
        esticados=esticados,
        pinca=razao_pinca(p, tam),
    )
