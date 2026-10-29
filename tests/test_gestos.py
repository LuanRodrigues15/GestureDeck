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

    def test_cursor_aparece_antes_de_qualquer_gesto(self):
        interp = novo()
        # indicador e anelar esticados nao e laser, pinca nem gesto de slide
        qs = com_trava(interp, lambda i, n: ms.mao((True, False, True, False), centro=(0.63, 0.40)), 1.0)
        self.assertEqual(qs[-1].gesto, Gesto.NENHUM)
        self.assertIsNotNone(qs[-1].ponteiro)

    def test_cursor_some_quando_a_mao_sai_da_imagem(self):
        interp = novo()
        com_trava(interp, lambda i, n: ms.laser(centro=(0.63, 0.40)), 1.0)
        qs = rodar(interp, lambda i, n: [ms.punho()], t0=2.0, duracao=0.6)
        self.assertIsNone(qs[-1].ponteiro)

    def test_mao_aberta_mantem_o_cursor_sem_gesto(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.aberta(), 1.0)
        self.assertEqual(qs[-1].gesto, Gesto.NENHUM)
        self.assertIsNotNone(qs[-1].ponteiro)

    def test_so_a_mao_da_trava_nao_mostra_cursor(self):
        interp = novo()
        qs = rodar(interp, lambda i, n: [ms.punho()], duracao=1.0)
        self.assertTrue(qs[-1].trava)
        self.assertIsNone(qs[-1].ponteiro)


def eventos(qs):
    return [q.slide for q in qs if q.slide is not None]


class TestSlide(unittest.TestCase):
    """Dois dedos esticados: para cima avanca, para baixo volta."""

    def test_dois_dedos_para_cima_avanca_uma_vez(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(), 2.0)
        self.assertEqual(eventos(qs), [Slide.PROXIMO])
        self.assertEqual(qs[-1].gesto, Gesto.SLIDE_PROXIMO)

    def test_dois_dedos_para_baixo_volta(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(graus=180), 2.0)
        self.assertEqual(eventos(qs), [Slide.ANTERIOR])

    def test_so_dispara_depois_de_segurar(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(), 1.0)
        primeiro = next(i for i, q in enumerate(qs) if q.slide is not None)
        self.assertGreaterEqual(primeiro / FPS, 0.30)

    def test_gesto_curto_nao_dispara(self):
        interp = novo()
        # 0.2 s com dois dedos e depois so o indicador
        qs = com_trava(
            interp, lambda i, n: ms.dois_dedos() if i < 6 else ms.laser(), 1.0
        )
        self.assertEqual(eventos(qs), [])

    def test_de_lado_nao_dispara(self):
        interp = novo()
        for graus in (90, 270):
            qs = com_trava(novo(), lambda i, n, g=graus: ms.dois_dedos(graus=g), 1.5)
            self.assertEqual(eventos(qs), [], f"{graus} graus")

    def test_inclinado_ate_o_limite_ainda_avanca(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(graus=25), 1.5)
        self.assertEqual(eventos(qs), [Slide.PROXIMO])

    def test_sem_trava_nao_troca(self):
        interp = novo()
        qs = rodar(interp, lambda i, n: [ms.dois_dedos()], duracao=2.0)
        self.assertEqual(eventos(qs), [])

    def test_repete_so_depois_de_sair_do_gesto(self):
        interp = novo()
        def acao(i, n):
            # 1,2 s com dois dedos, 0,6 s so o indicador, 1,2 s com dois dedos
            t = i / FPS
            return ms.dois_dedos() if t < 1.2 or t >= 1.8 else ms.laser()
        qs = com_trava(interp, acao, 3.0)
        self.assertEqual(eventos(qs), [Slide.PROXIMO, Slide.PROXIMO])

    def test_cooldown_impede_repeticao_rapida(self):
        interp = novo()
        def acao(i, n):
            # sai e volta ao gesto em menos de 1 s: o segundo e ignorado
            t = i / FPS
            return ms.laser() if 0.6 <= t < 0.9 else ms.dois_dedos()
        qs = com_trava(interp, acao, 1.6)
        self.assertEqual(eventos(qs), [Slide.PROXIMO])

    def test_mostra_o_progresso_enquanto_segura(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(), 1.0)
        parciais = [q.segurando[1] for q in qs if q.segurando is not None]
        self.assertTrue(parciais)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in parciais))
        self.assertEqual(sorted(parciais), parciais)
        self.assertIsNone(qs[-1].segurando)

    def test_dois_dedos_nao_e_pinca_nem_laser(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.dois_dedos(), 1.0)
        self.assertNotIn(Gesto.DESENHAR, [q.gesto for q in qs])
        self.assertNotIn(Gesto.LASER, [q.gesto for q in qs])

    def test_laser_continua_funcionando(self):
        interp = novo()
        qs = com_trava(interp, lambda i, n: ms.laser(), 1.0)
        self.assertEqual(qs[-1].gesto, Gesto.LASER)
        self.assertEqual(eventos(qs), [])

    def test_maos_que_se_cruzam_nao_invertem_os_papeis(self):
        interp = novo()
        rodar(interp, lambda i, n: [ms.punho(centro=(0.45, 0.5))], duracao=1.0)
        qs = rodar(
            interp,
            lambda i, n: [
                ms.punho(centro=(0.45, 0.5)),
                ms.laser(centro=(0.60 - 0.40 * min(1.0, i / (n - 1)), 0.40)),
            ],
            t0=1.0,
            duracao=0.6,
        )
        self.assertTrue(all(q.trava for q in qs))
        self.assertEqual(qs[-1].gesto, Gesto.LASER)


if __name__ == "__main__":
    unittest.main()
