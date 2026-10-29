"""Gera Quadros simulados para testar o overlay sem camera nem maos."""
import math
import threading
import time

from .eventos import Gesto, Modo, Quadro, Slide


class Simulador(threading.Thread):
    """Ciclo de 16 s: laser em circulo, desenho de um oito, selecao na barra e slide."""

    def __init__(self, sessao, metricas=None, ao_trocar_slide=None):
        super().__init__(name="simulador", daemon=True)
        self.sessao = sessao
        self.metricas = metricas
        self.ao_trocar_slide = ao_trocar_slide
        self._parar = threading.Event()
        self.erro = None

    def parar(self) -> None:
        self._parar.set()

    def run(self) -> None:
        inicio = time.monotonic()
        slide_enviado = False
        while not self._parar.is_set():
            t = time.monotonic() - inicio
            fase = t % 16.0
            slide = None
            if fase < 5.0:     # laser em circulo
                a = fase * 1.6
                ponteiro = (0.5 + 0.25 * math.cos(a), 0.45 + 0.22 * math.sin(a))
                gesto = Gesto.LASER
            elif fase < 9.0:   # desenho de um oito
                a = (fase - 5.0) * 1.6
                ponteiro = (0.5 + 0.22 * math.sin(a), 0.45 + 0.18 * math.sin(2 * a))
                gesto = Gesto.DESENHAR
            elif fase < 12.0:  # laser parado sobre o 2o item da barra
                x, y, w, h = self.sessao._painel
                item = self.sessao._itens[1]
                ponteiro = (item.cx / self.sessao._tela[0], item.cy / self.sessao._tela[1])
                gesto = Gesto.LASER
            else:
                ponteiro, gesto = None, Gesto.SLIDE_PROXIMO
                if fase >= 13.0 and not slide_enviado:
                    slide, slide_enviado = Slide.PROXIMO, True
            if fase < 1.0:
                slide_enviado = False
            modo = Modo.SLIDES if gesto == Gesto.SLIDE_PROXIMO else Modo.DESENHO
            q = Quadro(t=t, trava=True, gesto=gesto, ponteiro=ponteiro, slide=slide, maos=2,
                       modo=modo)
            if slide is not None and self.ao_trocar_slide is not None:
                self.ao_trocar_slide(slide)
            self.sessao.aplicar(q)
            if self.metricas is not None:
                self.metricas.registrar_quadro(q, 0.0, 0.0)
            time.sleep(1 / 60)
