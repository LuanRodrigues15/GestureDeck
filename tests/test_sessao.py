import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config as configuracao  # noqa: E402
from gestures.eventos import Gesto, Quadro, Slide  # noqa: E402
from overlay.sessao import Sessao  # noqa: E402


def nova_sessao():
    s = Sessao(configuracao.carregar(RAIZ / "config.json").overlay, ensaio=True)
    s.definir_tela(1920, 1080)
    return s


def q(t, gesto, ponteiro=None, trava=True, slide=None):
    return Quadro(t=t, trava=trava, gesto=gesto, ponteiro=ponteiro, slide=slide, maos=2)


def desenhar(s, pontos, t0=0.0):
    for i, p in enumerate(pontos):
        s.aplicar(q(t0 + i * 0.03, Gesto.DESENHAR, p))
    s.aplicar(q(t0 + len(pontos) * 0.03, Gesto.LASER, pontos[-1]))


LINHA = [(0.2 + i * 0.01, 0.4) for i in range(20)]


class TestTracos(unittest.TestCase):
    def test_pinca_gera_um_traco(self):
        s = nova_sessao()
        desenhar(s, LINHA)
        self.assertEqual(len(s.tracos), 1)
        self.assertEqual(s.tracos[0].cor, s.cfg.cores[0])

    def test_sem_trava_nao_desenha(self):
        s = nova_sessao()
        for i, p in enumerate(LINHA):
            s.aplicar(q(i * 0.03, Gesto.DESENHAR, p, trava=False))
        self.assertEqual(len(s.tracos), 0)

    def test_traco_curto_e_descartado(self):
        s = nova_sessao()
        desenhar(s, LINHA[:1])
        self.assertEqual(len(s.tracos), 0)

    def test_troca_de_slide_limpa_os_tracos(self):
        s = nova_sessao()
        desenhar(s, LINHA)
        s.aplicar(q(2.0, Gesto.ABERTA, slide=Slide.PROXIMO))
        self.assertEqual(len(s.tracos), 0)

    def test_nao_desenha_sobre_a_barra(self):
        s = nova_sessao()
        item = s._itens[0]
        sobre = (item.cx / 1920, item.cy / 1080)
        desenhar(s, [sobre] * 5)
        self.assertEqual(len(s.tracos), 0)


class TestBarra(unittest.TestCase):
    def _permanecer(self, s, item, segundos, t0=0.0):
        alvo = (item.cx / 1920, item.cy / 1080)
        passos = int(segundos / 0.03)
        for i in range(passos + 1):
            s.aplicar(q(t0 + i * 0.03, Gesto.LASER, alvo))
            # o tempo de permanencia usa o relogio real; simula a passagem dele
            s._hover_desde -= 0.03

    def test_permanencia_seleciona_a_cor(self):
        s = nova_sessao()
        self._permanecer(s, s._itens[2], 1.1)
        self.assertEqual(s.cor_indice, 2)
        self.assertEqual(s.ferramenta, "caneta")

    def test_permanencia_curta_nao_seleciona(self):
        s = nova_sessao()
        self._permanecer(s, s._itens[2], 0.4)
        self.assertEqual(s.cor_indice, 0)

    def test_borracha_apaga_o_traco_tocado(self):
        s = nova_sessao()
        desenhar(s, LINHA)
        s.ferramenta = "borracha"
        meio = LINHA[10]
        s.aplicar(q(5.0, Gesto.DESENHAR, meio))
        self.assertEqual(len(s.tracos), 0)

    def test_desfazer_remove_o_ultimo(self):
        s = nova_sessao()
        desenhar(s, LINHA)
        desenhar(s, [(x, 0.6) for x, _ in LINHA], t0=3.0)
        self.assertEqual(len(s.tracos), 2)
        desfazer = next(i for i in s._itens if i.id == "desfazer")
        self._permanecer(s, desfazer, 1.1, t0=6.0)
        self.assertEqual(len(s.tracos), 1)

    def test_limpar_apaga_tudo(self):
        s = nova_sessao()
        desenhar(s, LINHA)
        limpar = next(i for i in s._itens if i.id == "limpar")
        self._permanecer(s, limpar, 1.1, t0=3.0)
        self.assertEqual(len(s.tracos), 0)


if __name__ == "__main__":
    unittest.main()
