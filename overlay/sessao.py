"""Estado da apresentacao: tracos, ferramenta, barra e avisos.

A thread de visao escreve (aplicar) e a thread da interface le (instantaneo).
Tudo que e compartilhado passa pelo mesmo lock.
"""
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from gestures.eventos import Gesto, Modo, Quadro, Slide

from .barra import montar_barra

_RASTRO_S = 0.35
_AVISO_S = 1.2


@dataclass
class Traco:
    cor: str
    pontos: list = field(default_factory=list)   # (x, y) normalizados na tela


@dataclass(frozen=True)
class Instantaneo:
    tracos: list
    trava: bool
    gesto: Gesto
    ponteiro: tuple | None
    rastro: list
    cor_atual: str
    ferramenta: str
    modo_holofote: bool
    pausado: bool
    ensaio: bool
    ajuda: bool
    fps: float
    maos: int
    aviso: str | None
    aviso_alfa: float
    hover: str | None
    progresso: float
    barra_painel: tuple
    barra_itens: list
    cor_indice: int
    versao: int
    segurando: tuple | None = None
    mensagem: tuple | None = None
    modo: Modo = Modo.NENHUM


class Sessao:
    def __init__(self, cfg_overlay, ensaio: bool = False, metricas=None):
        self.cfg = cfg_overlay
        self.ensaio = ensaio
        self.metricas = metricas
        self._lock = threading.RLock()
        self.tracos: list[Traco] = []
        self._atual: Traco | None = None
        self.cor_indice = 0
        self.ferramenta = "caneta"
        self.modo_holofote = cfg_overlay.modo_inicial == "holofote"
        self.ajuda = bool(cfg_overlay.ajuda_inicial)
        self.pausado = False
        self.fps = 0.0
        self._quadro = Quadro(t=0.0)
        self._rastro: deque = deque()
        self._aviso: tuple[str, float] | None = None
        self._hover: str | None = None
        self._hover_desde = 0.0
        self._travado_ate_sair = False
        self._progresso = 0.0
        self._versao = 0
        self._mensagem: tuple[str, bool] | None = None
        self.definir_tela(1920, 1080)

    @property
    def mensagem(self) -> str | None:
        with self._lock:
            return self._mensagem[0] if self._mensagem else None

    # --- configuracao ---------------------------------------------------
    def definir_tela(self, largura: float, altura: float) -> None:
        with self._lock:
            self._tela = (float(largura), float(altura))
            self._painel, self._itens = montar_barra(
                largura, altura, len(self.cfg.cores), self.cfg.barra_lado
            )

    # --- teclas de atalho -----------------------------------------------
    def alternar_ajuda(self) -> None:
        with self._lock:
            self.ajuda = not self.ajuda
            self._versao += 1

    def alternar_holofote(self) -> None:
        with self._lock:
            self.modo_holofote = not self.modo_holofote
            self._versao += 1

    def alternar_pausa(self) -> None:
        with self._lock:
            self.pausado = not self.pausado
            if self.pausado:
                self._fechar_traco()
            self._versao += 1

    def definir_mensagem(self, texto: str | None, erro: bool = False) -> None:
        """Mensagem de estado no indicador da tela (abrindo a camera, falhas)."""
        with self._lock:
            self._mensagem = (texto, erro) if texto else None
            self._versao += 1

    def definir_fps(self, fps: float) -> None:
        with self._lock:
            self.fps = fps
            self._versao += 1

    # --- entrada de quadros -----------------------------------------------
    def aplicar(self, q: Quadro) -> None:
        with self._lock:
            self._quadro = q
            agora = time.monotonic()
            if q.slide is not None:
                self._limpar()
                texto = "Slide seguinte" if q.slide == Slide.PROXIMO else "Slide anterior"
                self._aviso = (("ENSAIO: " if self.ensaio else "") + texto, agora)

            # a barra so existe no modo desenho: fora dele nao e vista nem selecionavel
            barra = q.trava and q.modo == Modo.DESENHO
            ponteiro_px = self._em_pixels(q.ponteiro)
            sobre_item = self._item_sob(ponteiro_px) if barra else None
            na_barra = barra and ponteiro_px is not None and self._na_barra(ponteiro_px)

            self._tratar_permanencia(q, sobre_item, agora)
            self._tratar_rastro(q, agora)

            desenhando = (
                q.trava and q.gesto == Gesto.DESENHAR and ponteiro_px is not None and not na_barra
            )
            if desenhando:
                if self.ferramenta == "borracha":
                    self._fechar_traco()
                    self._apagar_perto(ponteiro_px)
                else:
                    self._acrescentar(q.ponteiro, ponteiro_px)
            else:
                self._fechar_traco()
            self._versao += 1

    # --- interno ------------------------------------------------------------
    def _em_pixels(self, ponteiro):
        if ponteiro is None:
            return None
        return ponteiro[0] * self._tela[0], ponteiro[1] * self._tela[1]

    def _item_sob(self, px):
        if px is None:
            return None
        for item in self._itens:
            if math.hypot(px[0] - item.cx, px[1] - item.cy) <= item.r * 1.25:
                return item.id
        return None

    def _na_barra(self, px) -> bool:
        x, y, w, h = self._painel
        folga = self._itens[0].r * 0.5
        return x - folga <= px[0] <= x + w + folga and y - folga <= px[1] <= y + h + folga

    def _tratar_permanencia(self, q: Quadro, item, agora: float) -> None:
        if not (q.trava and q.modo == Modo.DESENHO and q.gesto == Gesto.LASER and item):
            self._hover = None
            self._progresso = 0.0
            self._travado_ate_sair = False if item is None else self._travado_ate_sair
            return
        if item != self._hover:
            self._hover = item
            self._hover_desde = agora
            self._travado_ate_sair = False
        if self._travado_ate_sair:
            self._progresso = 0.0
            return
        self._progresso = min(1.0, (agora - self._hover_desde) / self.cfg.permanencia_s)
        if self._progresso >= 1.0:
            self._executar_item(item)
            self._travado_ate_sair = True
            self._progresso = 0.0

    def _executar_item(self, item: str) -> None:
        if item.startswith("cor:"):
            self.cor_indice = int(item.split(":")[1])
            self.ferramenta = "caneta"
        elif item == "borracha":
            self.ferramenta = "borracha"
        elif item == "desfazer":
            if self.tracos:
                self.tracos.pop()
        elif item == "limpar":
            self.tracos.clear()

    def _tratar_rastro(self, q: Quadro, agora: float) -> None:
        while self._rastro and agora - self._rastro[0][0] > _RASTRO_S:
            self._rastro.popleft()
        if q.trava and q.gesto == Gesto.LASER and q.ponteiro is not None:
            self._rastro.append((agora, q.ponteiro[0], q.ponteiro[1]))
        elif q.gesto != Gesto.LASER:
            self._rastro.clear()

    def _acrescentar(self, ponteiro, px) -> None:
        if self._atual is None:
            self._atual = Traco(cor=self.cfg.cores[self.cor_indice])
        pts = self._atual.pontos
        if pts:
            ultimo = (pts[-1][0] * self._tela[0], pts[-1][1] * self._tela[1])
            if math.hypot(px[0] - ultimo[0], px[1] - ultimo[1]) < 1.5:
                return
        pts.append(ponteiro)

    def _fechar_traco(self) -> None:
        if self._atual is None:
            return
        if len(self._atual.pontos) >= 2:
            self.tracos.append(self._atual)
            if self.metricas is not None:
                self.metricas.registrar_traco()
        self._atual = None

    def _apagar_perto(self, px) -> None:
        raio = self.cfg.borracha_raio * self._tela[1]
        mantidos = []
        for t in self.tracos:
            tocado = any(
                math.hypot(x * self._tela[0] - px[0], y * self._tela[1] - px[1]) <= raio
                for x, y in t.pontos
            )
            if not tocado:
                mantidos.append(t)
        self.tracos = mantidos

    def _limpar(self) -> None:
        self.tracos.clear()
        self._atual = None

    # --- leitura pela interface --------------------------------------------
    def instantaneo(self) -> Instantaneo:
        with self._lock:
            q = self._quadro
            agora = time.monotonic()
            aviso, alfa = None, 0.0
            if self._aviso is not None:
                idade = agora - self._aviso[1]
                if idade < _AVISO_S:
                    aviso = self._aviso[0]
                    alfa = 1.0 if idade < _AVISO_S * 0.6 else 1.0 - (idade - _AVISO_S * 0.6) / (_AVISO_S * 0.4)
                else:
                    self._aviso = None
            tracos = [(t.cor, tuple(t.pontos)) for t in self.tracos]
            if self._atual is not None and self._atual.pontos:
                tracos.append((self._atual.cor, tuple(self._atual.pontos)))
            return Instantaneo(
                tracos=tracos,
                trava=q.trava and not self.pausado,
                gesto=q.gesto,
                ponteiro=q.ponteiro if not self.pausado else None,
                rastro=[(agora - t, x, y) for t, x, y in self._rastro],
                cor_atual=self.cfg.cores[self.cor_indice],
                ferramenta=self.ferramenta,
                modo_holofote=self.modo_holofote,
                pausado=self.pausado,
                ensaio=self.ensaio,
                ajuda=self.ajuda,
                fps=self.fps,
                maos=q.maos,
                aviso=aviso,
                aviso_alfa=max(0.0, alfa),
                hover=self._hover,
                progresso=self._progresso,
                barra_painel=self._painel,
                barra_itens=list(self._itens),
                cor_indice=self.cor_indice,
                versao=self._versao,
                segurando=q.segurando if not self.pausado else None,
                mensagem=self._mensagem,
                modo=q.modo,
            )
