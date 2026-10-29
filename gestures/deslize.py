"""Detector de deslize lateral da palma aberta."""
from collections import deque


class DetectorDeslize:
    """Acusa um deslize quando a palma percorre varios tamanhos de mao rapido.

    A distancia e medida em tamanhos de mao, entao funciona perto e longe.
    Depois de um deslize ha um cooldown, para o retorno da mao nao virar o
    comando contrario.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._amostras: deque = deque()
        self._livre_em = -1e9

    def reiniciar(self) -> None:
        self._amostras.clear()

    def atualizar(self, t: float, x: float, y: float, tamanho: float) -> int | None:
        """Devolve -1 (movimento para a esquerda da imagem), +1 (direita) ou None."""
        if t < self._livre_em:
            self._amostras.clear()
            return None
        a = self._amostras
        a.append((t, x, y, tamanho))
        while a and t - a[0][0] > self.cfg.janela_s:
            a.popleft()
        if len(a) < 4:
            return None
        xs = [s[1] for s in a]
        i_max = max(range(len(xs)), key=xs.__getitem__)
        i_min = min(range(len(xs)), key=xs.__getitem__)
        deslocamento = xs[i_max] - xs[i_min]
        media_tamanho = sum(s[3] for s in a) / len(a)
        if deslocamento < self.cfg.distancia_tamanhos * media_tamanho:
            return None
        if abs(a[i_max][2] - a[i_min][2]) > self.cfg.vertical_max * deslocamento:
            return None
        self._livre_em = t + self.cfg.cooldown_s
        a.clear()
        # maximo antes do minimo: a mao foi da direita para a esquerda da imagem
        return -1 if i_max < i_min else 1
