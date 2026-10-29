"""GestureDeck: controla o PowerPoint com gestos das maos."""
import argparse
import signal
import sys
from pathlib import Path

import config as configuracao

RAIZ = Path(__file__).resolve().parent


def ler_argumentos():
    p = argparse.ArgumentParser(description="Controle do PowerPoint por gestos")
    p.add_argument("--ensaio", action="store_true",
                   help="mostra a acao na tela sem enviar teclas")
    p.add_argument("--sem-overlay", action="store_true",
                   help="nao cria a janela transparente (abre so a previa da camera)")
    p.add_argument("--camera", type=int, help="indice da camera (padrao: config.json)")
    p.add_argument("--monitor", type=int, help="monitor do overlay (padrao: config.json)")
    p.add_argument("--previa", action="store_true",
                   help="abre uma janela com a camera e os pontos das maos")
    p.add_argument("--depurar", action="store_true",
                   help="grava em relatorios/ um log do que a camera e os gestos estao vendo")
    p.add_argument("--simular", action="store_true",
                   help="usa gestos simulados em vez da camera (teste do overlay)")
    p.add_argument("--config", help="caminho de um config.json alternativo")
    return p.parse_args()


def main() -> int:
    args = ler_argumentos()
    cfg = configuracao.carregar(args.config)
    if args.camera is not None:
        cfg.camera.indice = args.camera
    if args.monitor is not None:
        cfg.overlay.monitor = args.monitor

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("GestureDeck")

    from actions.teclas import Teclas
    from gestures.simulador import Simulador
    from metrics.relatorio import Metricas
    from overlay.atalhos import AtalhosGlobais
    from overlay.janela import JanelaOverlay
    from overlay.previa import Previa
    from overlay.sessao import Sessao
    from vision.pipeline import ThreadVisao

    metricas = Metricas()
    sessao = Sessao(cfg.overlay, ensaio=args.ensaio, metricas=metricas)
    teclas = Teclas(cfg.acoes, ensaio=args.ensaio)

    if args.simular:
        trabalho = Simulador(sessao, metricas, ao_trocar_slide=teclas.enviar)
    else:
        trabalho = ThreadVisao(cfg, RAIZ, sessao, metricas, teclas,
                               previa=args.previa or args.sem_overlay, depurar=args.depurar)

    janelas = []
    if not args.sem_overlay:
        telas = app.screens()
        indice = cfg.overlay.monitor if 0 <= cfg.overlay.monitor < len(telas) else 0
        overlay = JanelaOverlay(sessao, telas[indice])
        overlay.mostrar()
        janelas.append(overlay)
    if (args.previa or args.sem_overlay) and not args.simular:
        previa = Previa(trabalho.ultima_previa)
        previa.show()
        janelas.append(previa)

    atalhos = AtalhosGlobais({
        "F1": sessao.alternar_ajuda,
        "F2": sessao.alternar_holofote,
        "F9": sessao.alternar_pausa,
        "F10": app.quit,
    })
    if atalhos.falhas:
        print(f"Aviso: atalhos ocupados por outro programa: {', '.join(atalhos.falhas)}")
    app.installNativeEventFilter(atalhos)

    saida = {"codigo": 0}

    def vigiar():
        if getattr(trabalho, "erro", None):
            print(trabalho.erro, file=sys.stderr)
            saida["codigo"] = 1
            app.quit()

    vigia = QTimer()
    vigia.timeout.connect(vigiar)
    vigia.start(250)
    signal.signal(signal.SIGINT, lambda *_: app.quit())   # Ctrl+C no terminal

    def encerrar():
        atalhos.liberar()
        trabalho.parar()
        trabalho.join(timeout=3.0)
        caminho = metricas.salvar(RAIZ / cfg.relatorio.pasta)
        print(f"Relatorio salvo em {caminho}")

    app.aboutToQuit.connect(encerrar)
    trabalho.start()
    print("GestureDeck em execucao. F1 ajuda, F2 laser/holofote, F9 pausa, F10 sai.")
    app.exec()
    return saida["codigo"]


if __name__ == "__main__":
    sys.exit(main())
