"""Geometria da barra de ferramentas (cores, borracha, desfazer, limpar)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ItemBarra:
    id: str
    cx: float
    cy: float
    r: float


def montar_barra(largura: float, altura: float, n_cores: int, lado: str = "direita"):
    """Devolve ((x, y, w, h) do painel, itens) em pixels de tela."""
    r = max(24.0, altura * 0.028)
    folga = r * 0.55
    margem_interna = r * 0.6
    ids = [f"cor:{i}" for i in range(n_cores)] + ["borracha", "desfazer", "limpar"]
    n = len(ids)
    miolo = n * 2 * r + (n - 1) * folga
    larg_painel = 2 * r + 2 * margem_interna
    alt_painel = miolo + 2 * margem_interna
    margem_tela = altura * 0.02
    x = largura - margem_tela - larg_painel if lado == "direita" else margem_tela
    y = (altura - alt_painel) / 2
    cx = x + larg_painel / 2
    itens = [
        ItemBarra(id_, cx, y + margem_interna + r + k * (2 * r + folga), r)
        for k, id_ in enumerate(ids)
    ]
    return (x, y, larg_painel, alt_painel), itens
