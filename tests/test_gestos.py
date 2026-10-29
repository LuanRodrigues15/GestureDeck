import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as configuracao  # noqa: E402
import maos_sinteticas as ms  # noqa: E402
from gestures.eventos import Gesto, Slide  # noqa: E402
from gestures.geometria import montar_mao  # noqa: E402
from gestures.interpretador import Interpretador  # noqa: E402

ASPECTO = 16 / 9
FPS = 30.0


def novo():
    return Interpretador(configuracao.carregar(RAIZ / "config.json"), ASPECTO)


def rodar(interp, quadros, t0=0.0, duracao=1.0):
    """Alimenta o interpretador a 30 FPS com `quadros()` e devolve os Quadros."""
    resultados = []
    n = int(duracao * FPS)
    for i in range(n):
        t = t0 + i / FPS
        resultados.append(interp.processar(quadros(i, n), t))
    return resultados


class TestGeometria(unittest.TestCase):
    def setUp(self):
        self.limiar = configuracao.carregar(RAIZ / "config.json").gestos.dedo_esticado_limiar

    def test_postura_de_cada_gesto(self):
        self.assertTrue(montar_mao(ms.punho(), ASPECTO, self.limiar).fechada)
        self.assertTrue(montar_mao(ms.laser(), ASPECTO, self.limiar).laser)
        self.assertTrue(montar_mao(ms.aberta(), ASPECTO, self.limiar).aberta)

    def test_pinca_tem_razao_pequena(self):
        m = montar_mao(ms.pinca(), ASPECTO, self.limiar)
        self.assertLess(m.pinca, 0.30)
        self.assertGreater(montar_mao(ms.laser(), ASPECTO, self.limiar).pinca, 0.50)

    def test_independe_da_distancia(self):
        for escala in (0.05, 0.12, 0.30):
            m = montar_mao(ms.laser(escala=escala), ASPECTO, self.limiar)
            self.assertTrue(m.laser, f"escala {escala}")

    def test_independe_da_rotacao(self):
        # mao de cabeca para baixo: pontos refletidos em torno do pulso
        pts = ms.laser().copy()
        pulso = pts[0].copy()
        pts[:, 1] = pulso[1] - (pts[:, 1] - pulso[1])
        self.assertTrue(montar_mao(pts, ASPECTO, self.limiar).laser)


class TestTrava(unittest.TestCase):
    def test_sem_trava_nada_acontece(self):
        interp = novo()
        qs = rodar(interp, lambda i, n: [ms.laser()], duracao=1.0)
        self.assertTrue(all(not q.trava for q in qs))
        self.assertTrue(all(q.gesto == Gesto.NENHUM and q.ponteiro is None for q in qs))

    def test_punho_levantado_ativa_a_trava(self):
        interp = novo()
        qs = rodar(interp, lambda i, n: [ms.punho()], duracao=1.0)
        self.assertFalse(qs[2].trava)          # ainda dentro do tempo de ativacao
        self.assertTrue(qs[-1].trava)

    def test_punho_baixo_nao_ativa(self):
        interp = novo()
        qs = rodar(interp, lambda i, n: [ms.punho(centro=(0.3, 0.85))], duracao=1.0)
        self.assertTrue(all(not q.trava for q in qs))

    def test_soltar_a_trava_apos_atraso(self):
        interp = novo()
        rodar(interp, lambda i, n: [ms.punho()], duracao=1.0)
        qs = rodar(interp, lambda i, n: [ms.aberta(centro=(0.3, 0.5))], t0=1.0, duracao=1.0)
        self.assertTrue(qs[3].trava)           # tolera falha curta
        self.assertFalse(qs[-1].trava)

    def test_trava_a_mais_a_esquerda(self):
        interp = novo()
        # punho na direita e mao aberta na esquerda: a trava NAO e a da direita
        qs = rodar(interp, lambda i, n: [ms.punho(centro=(0.8, 0.5)), ms.aberta(centro=(0.3, 0.5))])
        self.assertFalse(qs[-1].trava)


def com_trava(interp, acao, duracao, t0=1.0):
    """Roda a trava por 1 s e depois a acao da mao direita."""
    rodar(interp, lambda i, n: [ms.punho()], duracao=1.0)
    return rodar(interp, lambda i, n: [ms.punho(), acao(i, n)], t0=t0, duracao=duracao)


class TestGestosComTrava(unittest.TestCase):
    def test_laser_gera_ponteiro(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.laser(centro=(0.63, 0.40)), 1.0)
        q = qs[-1]
        self.assertTrue(q.trava)
        self.assertEqual(q.gesto, Gesto.LASER)
        self.assertIsNotNone(q.ponteiro)
        self.assertTrue(0.0 <= q.ponteiro[0] <= 1.0 and 0.0 <= q.ponteiro[1] <= 1.0)

    def test_ponteiro_acompanha_a_mao(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.laser(centro=(0.50 + 0.30 * i / n, 0.40)), 1.5)
        self.assertGreater(qs[-1].ponteiro[0], qs[10].ponteiro[0])

    def test_pinca_vira_desenhar(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.pinca(centro=(0.63, 0.40)), 1.0)
        self.assertEqual(qs[-1].gesto, Gesto.DESENHAR)
        self.assertIsNotNone(qs[-1].ponteiro)

    def test_pinca_exige_debounce(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.pinca(centro=(0.63, 0.40)), 1.0)
        self.assertNotEqual(qs[1].gesto, Gesto.DESENHAR)

    def test_piscada_da_pinca_nao_quebra_o_traco(self):
        interp = novo()
        def acao(i, n):
            # 2 quadros soltando a pinca no meio (menos que o debounce de soltar)
            return ms.laser() if i in (15, 16) else ms.pinca()
        qs = com_trava(interp, acao, 1.0)
        self.assertTrue(all(q.gesto == Gesto.DESENHAR for q in qs[-14:]))

    def test_mao_aberta_nao_mostra_ponteiro(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.aberta(), 1.0)
        self.assertEqual(qs[-1].gesto, Gesto.ABERTA)
        self.assertIsNone(qs[-1].ponteiro)


class TestDeslize(unittest.TestCase):
    def _deslizar(self, x_ini, x_fim, duracao=0.45, extra=0.0):
        interp = novo()
        qs = com_trava(
            interp,
            lambda i, n: ms.aberta(centro=(x_ini + (x_fim - x_ini) * min(1.0, i / (n - 1)), 0.40)),
            duracao + extra,
        )
        return [q.slide for q in qs if q.slide is not None]

    def test_esquerda_avanca(self):
        self.assertEqual(self._deslizar(0.85, 0.55), [Slide.PROXIMO])

    def test_direita_volta(self):
        self.assertEqual(self._deslizar(0.55, 0.85), [Slide.ANTERIOR])

    def test_movimento_curto_nao_dispara(self):
        self.assertEqual(self._deslizar(0.70, 0.66), [])

    def test_ida_e_volta_so_conta_a_ida(self):
        interp = novo()
        def acao(i, n):
            # 0.4 s indo para a esquerda e 0.4 s voltando
            frac = i / n
            x = 0.85 - 0.30 * (frac / 0.5) if frac < 0.5 else 0.55 + 0.30 * ((frac - 0.5) / 0.5)
            return ms.aberta(centro=(x, 0.40))
        qs = com_trava(interp, acao, 0.8)
        eventos = [q.slide for q in qs if q.slide is not None]
        self.assertEqual(eventos, [Slide.PROXIMO])

    def test_sem_trava_nao_desliza(self):
        interp = novo()
        qs = rodar(
            interp,
            lambda i, n: [ms.aberta(centro=(0.85 - 0.30 * i / n, 0.40))],
            duracao=0.5,
        )
        self.assertTrue(all(q.slide is None for q in qs))

    def test_laser_se_movendo_nao_dispara(self):
        interp = novo()
        qs = com_trava(
            interp, lambda i, n: ms.laser(centro=(0.85 - 0.35 * i / n, 0.40)), 0.5
        )
        self.assertTrue(all(q.slide is None for q in qs))


if __name__ == "__main__":
    unittest.main()
