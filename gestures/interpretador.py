"""Transforma as maos detectadas em um Quadro (trava, gesto, ponteiro, slide)."""
from .deslize import DetectorDeslize
from .eventos import Gesto, Quadro, Slide
from .filtros import Estabilizador, FiltroUmEuro
from .geometria import Mao, montar_mao

_EXPIRA_HISTORICO_S = 1.5
_PAUSA_ABERTA_S = 0.2


def _dist(a, b) -> float:
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


class Interpretador:
    def __init__(self, cfg, aspecto: float):
        self.cfg = cfg
        self.aspecto = aspecto
        g = cfg.gestos
        m = cfg.mapeamento
        self._trava = Estabilizador(
            False, lambda _ant, novo: g.trava_ativar_s if novo else g.trava_soltar_s
        )
        self._postura = Estabilizador(Gesto.NENHUM, self._atraso_postura)
        self._pinca = False
        self._fx = FiltroUmEuro(m.filtro_min_cutoff, m.filtro_beta, m.filtro_d_cutoff)
        self._fy = FiltroUmEuro(m.filtro_min_cutoff, m.filtro_beta, m.filtro_d_cutoff)
        self._deslize = DetectorDeslize(cfg.deslize)
        self._p_trava = None
        self._p_acao = None
        self._t_historico = -1e9
        self._t_acao_visto = -1e9
        self._t_aberta_visto = -1e9
        self._ponteiro: tuple[float, float] | None = None
        self.depuracao: list[str] = []

    def _atraso_postura(self, anterior: Gesto, novo: Gesto) -> float:
        g = self.cfg.gestos
        if novo == Gesto.DESENHAR:
            return g.pinca_ativar_s
        if anterior == Gesto.DESENHAR:
            return g.pinca_soltar_s
        return g.postura_estavel_s

    # atribuicao das maos: por posicao, nunca pelo rotulo do MediaPipe
    def _atribuir(self, maos: list[Mao], t: float):
        """Escolhe a mao da trava e a mao de acao.

        Sem trava ativa, a mais a esquerda da imagem espelhada e a trava. Com a
        trava ativa, cada mao e acompanhada pela posicao anterior: assim, quando
        a mao direita cruza a esquerda no deslize, os papeis nao se invertem.
        """
        if t - self._t_historico > _EXPIRA_HISTORICO_S:
            self._p_trava = self._p_acao = None
        if not maos:
            return None, None
        tem_historico = self._p_trava is not None and self._p_acao is not None
        if len(maos) >= 2:
            esq, dir_ = sorted(maos, key=lambda m: m.palma[0])[::len(maos) - 1]
            mt, ma = esq, dir_
            if self._trava.valor and tem_historico:
                normal = _dist(esq.palma, self._p_trava) + _dist(dir_.palma, self._p_acao)
                trocado = _dist(dir_.palma, self._p_trava) + _dist(esq.palma, self._p_acao)
                if trocado < normal:
                    mt, ma = dir_, esq
            self._p_trava, self._p_acao, self._t_historico = mt.palma, ma.palma, t
            return mt, ma
        m = maos[0]
        if tem_historico:
            eh_trava = _dist(m.palma, self._p_trava) < _dist(m.palma, self._p_acao)
        else:
            eh_trava = m.fechada
        self._t_historico = t
        if eh_trava:
            self._p_trava = m.palma
            return m, None
        self._p_acao = m.palma
        return None, m

    def _postura_bruta(self, m: Mao) -> Gesto:
        g = self.cfg.gestos
        if self._pinca:
            if m.pinca > g.pinca_abrir:
                self._pinca = False
        elif m.pinca < g.pinca_fechar:
            self._pinca = True
        if self._pinca:
            return Gesto.DESENHAR
        if m.laser:
            return Gesto.LASER
        if m.aberta:
            return Gesto.ABERTA
        return Gesto.NENHUM

    def _mapear(self, m: Mao, t: float) -> tuple[float, float]:
        cfg = self.cfg.mapeamento
        if cfg.ancora == "palma":
            ax, ay = m.palma
        else:
            ax, ay = m.pontos[5][0], m.pontos[5][1]
        x0, y0, x1, y1 = cfg.zona_ativa
        u = min(1.0, max(0.0, (ax - x0) / (x1 - x0)))
        v = min(1.0, max(0.0, (ay - y0) / (y1 - y0)))
        return self._fx(u, t), self._fy(v, t)

    def processar(self, maos_brutas, t: float) -> Quadro:
        g = self.cfg.gestos
        maos = [montar_mao(p, self.aspecto, g.dedo_esticado_limiar) for p in maos_brutas]
        mao_trava, mao_acao = self._atribuir(maos, t)

        trava_bruta = (
            mao_trava is not None
            and mao_trava.fechada
            and mao_trava.palma[1] < g.trava_altura_max
        )
        trava = self._trava.atualizar(trava_bruta, t)

        gesto = Gesto.NENHUM
        slide = None
        if not trava:
            self._resetar_acao(t)
        else:
            if mao_acao is not None:
                self._t_acao_visto = t
                bruto = self._postura_bruta(mao_acao)
            elif t - self._t_acao_visto < g.perda_tolerancia_s:
                bruto = self._postura.valor
            else:
                bruto = Gesto.NENHUM
                self._pinca = False
            gesto = self._postura.atualizar(bruto, t)

            # o cursor acompanha a mao sempre que ela esta visivel, para o
            # apresentador saber onde vai apontar ou comecar a desenhar
            visivel = mao_acao is not None or t - self._t_acao_visto < g.perda_tolerancia_s
            if visivel:
                if mao_acao is not None:
                    self._ponteiro = self._mapear(mao_acao, t)
            else:
                self._ponteiro = None
                self._fx.reiniciar()
                self._fy.reiniciar()

            slide = self._tratar_deslize(mao_acao, t)

        self.depuracao = self._texto_depuracao(mao_trava, mao_acao, trava, gesto)
        return Quadro(
            t=t,
            trava=trava,
            gesto=gesto,
            ponteiro=self._ponteiro if trava else None,
            slide=slide,
            maos=len(maos),
        )

    def _resetar_acao(self, t: float) -> None:
        self._postura.forcar(Gesto.NENHUM, t)
        self._pinca = False
        self._ponteiro = None
        self._fx.reiniciar()
        self._fy.reiniciar()
        self._deslize.reiniciar()

    def _tratar_deslize(self, mao_acao: Mao | None, t: float) -> Slide | None:
        if mao_acao is not None and mao_acao.aberta and not self._pinca:
            self._t_aberta_visto = t
            direcao = self._deslize.atualizar(
                t, mao_acao.palma_c[0], mao_acao.palma_c[1], mao_acao.tamanho
            )
            if direcao is None:
                return None
            avanca = direcao < 0
            if self.cfg.deslize.inverter:
                avanca = not avanca
            return Slide.PROXIMO if avanca else Slide.ANTERIOR
        if t - self._t_aberta_visto > _PAUSA_ABERTA_S:
            self._deslize.reiniciar()
        return None

    def _texto_depuracao(self, mt, ma, trava, gesto) -> list[str]:
        linhas = [f"trava: {'ATIVA' if trava else 'inativa'}   gesto: {gesto.value}"]
        if mt is not None:
            linhas.append(
                f"mao trava: x={mt.palma[0]:.2f} y={mt.palma[1]:.2f} fechada={mt.fechada} "
                f"dedos={mt.esticados}"
            )
        if ma is not None:
            linhas.append(
                f"mao acao: x={ma.palma[0]:.2f} y={ma.palma[1]:.2f} dedos={ma.esticados} "
                f"pinca={ma.pinca:.2f} tam={ma.tamanho:.3f}"
            )
            if self._deslize.info:
                linhas.append(self._deslize.info)
        return linhas
