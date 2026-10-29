# Changelog

## 2026-10-29: modos slides e desenho, cartão de ajuda com mãos

**Problema:** ao fechar os dedos para trocar de slide, a pinça disparava e riscava a tela.

**Decisão (do usuário):** a mão esquerda levantada escolhe o modo. Fechada libera a troca de
slide, aberta libera o desenho. O laser vale nos dois, porque é com ele que se escolhe a cor
na barra. A pinça é ignorada no modo slides e os dois dedos são ignorados no modo desenho.

**Mudanças**
- `gestures/eventos.py`: enum `Modo` (nenhum, slides, desenho) e campo `modo` no `Quadro`.
  `trava` continua significando "algum modo ativo".
- `gestures/interpretador.py`: o modo sai da postura da mão da trava (punho ou mão aberta,
  acima de `trava_altura_max`) e passa por um estabilizador. Entrar ou trocar leva
  `trava_ativar_s`, sair leva `trava_soltar_s`, então a passagem punho para mão aberta não
  derruba a trava. Ao trocar de modo o gesto em andamento é zerado.
- `overlay/janela.py`, `overlay/sessao.py`, `gestures/simulador.py`, `vision/pipeline.py`: o
  modo chega ao indicador na tela (azul em slides, verde em desenho), ao simulador e ao log
  de `--depurar`.
- Cartão de ajuda (`overlay/janela.py`, `overlay/icones.py`): coluna vertical e menor, com um
  ícone de mão por gesto e os dois modos. Ícones SVG do Twemoji (CC-BY 4.0) em
  `assets/icones/`, mais `dois_dedos_l.png` feito pelo grupo. Licença em
  `assets/icones/LICENCA.md`.

**Paleta só no modo desenho (pedido seguinte):** a barra de cores não é mais desenhada nem
selecionável fora do modo desenho. `overlay/sessao.py` restringe o hit-test e a seleção por
permanência ao modo desenho e `overlay/janela.py` só desenha a barra nele. Dois testes novos
em `tests/test_sessao.py`.

**Testes:** 58 testes (eram 46). Novos: modo por postura da mão esquerda, pinça ignorada em
slides, dois dedos ignorados em desenho, laser nos dois modos, troca de modo sem derrubar a
trava e traço encerrado ao sair do modo desenho. Os testes de desenho passaram a usar a mão
esquerda aberta.

**Não verificado:** os dois modos com câmera real. Limiares a calibrar com `--depurar`:
`gestos.trava_ativar_s`, `gestos.trava_soltar_s`, `gestos.dedo_esticado_limiar` (mão aberta
exige os quatro dedos esticados).
