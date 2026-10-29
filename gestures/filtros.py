"""Filtros de tempo: estabilizador (debounce) e suavizacao exponencial adaptativa."""
import math


class Estabilizador:
    """Aceita um novo valor so depois que ele se mantem pelo tempo de atraso.

    `atraso(anterior, novo)` devolve quantos segundos o novo valor precisa
    durar para ser adotado. Isso da histerese temporal e debounce.
    """

    def __init__(self, inicial, atraso):
        self.valor = inicial
        self._atraso = atraso
        self._candidato = inicial
        self._desde = 0.0

    @property
    def candidato(self):
        """Valor que esta esperando o tempo de atraso para ser adotado."""
        return self._candidato

    @property
    def desde(self) -> float:
        return self._desde

    def atualizar(self, bruto, t: float):
        if bruto == self.valor:
            self._candidato = bruto
            return self.valor
        if bruto != self._candidato:
            self._candidato = bruto
            self._desde = t
        if t - self._desde >= self._atraso(self.valor, bruto):
            self.valor = bruto
        return self.valor

    def forcar(self, valor, t: float) -> None:
        self.valor = valor
        self._candidato = valor
        self._desde = t


def _alfa(dt: float, corte: float) -> float:
    tau = 1.0 / (2.0 * math.pi * corte)
    return 1.0 / (1.0 + tau / dt)


class FiltroUmEuro:
    """Suavizacao exponencial com corte adaptativo (filtro 1 euro).

    Parada, a mao treme pouco e o filtro suaviza forte. Em movimento rapido o
    corte sobe e o laser nao fica para tras.
    """

    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reiniciar()

    def reiniciar(self) -> None:
        self._x = None
        self._dx = 0.0
        self._t = 0.0

    def __call__(self, x: float, t: float) -> float:
        if self._x is None:
            self._x, self._dx, self._t = x, 0.0, t
            return x
        dt = max(t - self._t, 1e-3)
        derivada = (x - self._x) / dt
        a_d = _alfa(dt, self.d_cutoff)
        self._dx = a_d * derivada + (1.0 - a_d) * self._dx
        corte = self.min_cutoff + self.beta * abs(self._dx)
        a = _alfa(dt, corte)
        self._x = a * x + (1.0 - a) * self._x
        self._t = t
        return self._x
