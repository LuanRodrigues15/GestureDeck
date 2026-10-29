"""Thread de visao: camera, MediaPipe, interpretacao dos gestos e acoes."""
import copy
import threading
import time
import traceback
from datetime import datetime

import cv2

from gestures.eventos import Quadro
from gestures.interpretador import Interpretador
from overlay.previa import desenhar_previa

from .camera import Camera
from .rastreador import Rastreador


class ThreadVisao(threading.Thread):
    def __init__(self, cfg, raiz, sessao, metricas, teclas, previa: bool = False,
                 depurar: bool = False):
        super().__init__(name="visao", daemon=True)
        self.depurar = depurar
        self.cfg = cfg
        self.raiz = raiz
        self.sessao = sessao
        self.metricas = metricas
        self.teclas = teclas
        self.previa = previa
        self.erro: str | None = None
        self._parar = threading.Event()
        self._previa_img = None
        self._previa_lock = threading.Lock()

    def parar(self) -> None:
        self._parar.set()

    def ultima_previa(self):
        with self._previa_lock:
            return self._previa_img

    def run(self) -> None:
        camera = None
        rastreador = None
        try:
            camera = self._abrir_camera()
            print(
                f"Camera {camera.indice}: {camera.largura}x{camera.altura} "
                f"{camera.formato or '?'} ({camera.backend})"
            )
            self.sessao.definir_mensagem("Carregando o reconhecimento das maos...")
            rastreador = Rastreador(self.cfg.mediapipe, self.raiz)
            self.sessao.definir_mensagem(None)
            self._laco(camera, rastreador)
        except Exception as e:
            self.erro = traceback.format_exc()
            self.sessao.definir_mensagem(f"ERRO: {e}. Feche com F10.", erro=True)
        finally:
            if rastreador is not None:
                rastreador.fechar()
            if camera is not None:
                camera.fechar()

    def _abrir_camera(self) -> Camera:
        """Abre a camera com algumas tentativas e os dois backends do Windows.

        A camera so atende um programa por vez, e a abertura as vezes falha ou
        abre sem enviar imagem, entao tenta de novo antes de desistir.
        """
        backends = [self.cfg.camera.backend] + [
            b for b in ("dshow", "msmf") if b != self.cfg.camera.backend
        ]
        ultimo_erro = "motivo desconhecido"
        for tentativa in range(1, 4):
            for backend in backends:
                if self._parar.is_set():
                    raise RuntimeError("encerrado")
                self.sessao.definir_mensagem(
                    f"Abrindo a camera ({backend}, tentativa {tentativa} de 3)..."
                )
                cfg_camera = copy.copy(self.cfg.camera)
                cfg_camera.backend = backend
                camera = Camera(cfg_camera)
                try:
                    camera.abrir()
                    camera.iniciar()
                    if camera.proximo_quadro(0, 5.0) is not None:
                        self.sessao.definir_mensagem(None)
                        return camera
                    ultimo_erro = f"a camera abriu ({backend}) mas nao enviou imagem"
                except RuntimeError as e:
                    ultimo_erro = str(e)
                camera.fechar()
            time.sleep(1.0)
        raise RuntimeError(
            f"Camera indisponivel ({ultimo_erro}). Feche outros programas que usam a "
            f"camera (navegador, Discord, outra janela do GestureDeck)"
        )

    def _abrir_log(self):
        if not self.depurar:
            return None
        pasta = self.raiz / self.cfg.relatorio.pasta
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"depuracao_{datetime.now():%Y%m%d_%H%M%S}.log"
        print(f"Depuracao gravada em {caminho}")
        return open(caminho, "w", encoding="utf-8")

    def _laco(self, camera: Camera, rastreador: Rastreador) -> None:
        log = self._abrir_log()
        try:
            self._processar(camera, rastreador, log)
        finally:
            if log is not None:
                log.close()

    def _processar(self, camera: Camera, rastreador: Rastreador, log) -> None:
        cfg = self.cfg
        x0, y0, x1, y1 = cfg.roi
        escala = cfg.escala_processamento
        interp = None
        ultimo_id = 0
        ultimo_t = time.monotonic()
        fps = 0.0
        proximo_fps = 0.0
        inicio_log = time.monotonic()
        while not self._parar.is_set():
            if camera.falhou:
                raise RuntimeError("A camera parou de enviar imagens.")
            r = camera.proximo_quadro(ultimo_id, 0.5)
            if r is None:
                continue
            frame, ultimo_id, ts_captura = r
            inicio = time.perf_counter()

            if cfg.camera.espelhar:
                frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            if (x0, y0, x1, y1) != (0.0, 0.0, 1.0, 1.0):
                frame = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
            if escala != 1.0:
                frame = cv2.resize(frame, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
            if interp is None:
                interp = Interpretador(cfg, frame.shape[1] / frame.shape[0])

            maos = rastreador.processar(frame, int(time.monotonic() * 1000))
            agora = time.monotonic()
            if self.sessao.pausado:
                q = Quadro(t=agora, maos=len(maos))
            else:
                q = interp.processar(maos, agora)
            if q.slide is not None:
                self.teclas.enviar(q.slide)
            self.sessao.aplicar(q)

            if log is not None:   # uma linha por quadro
                log.write(
                    f"{agora - inicio_log:7.2f}s maos={len(maos)} trava={int(q.trava)} "
                    f"gesto={q.gesto.value} cursor={'sim' if q.ponteiro else 'nao'} "
                    f"slide={q.slide.name if q.slide else '-'} fps={fps:.0f} | "
                    + " | ".join(interp.depuracao[1:]) + "\n"
                )

            fim = time.perf_counter()
            self.metricas.registrar_quadro(
                q, (fim - inicio) * 1000, (time.monotonic() - ts_captura) * 1000
            )
            dt = agora - ultimo_t
            ultimo_t = agora
            if dt > 0:
                fps = 0.9 * fps + 0.1 / dt if fps else 1.0 / dt
            if agora >= proximo_fps:
                self.sessao.definir_fps(fps)
                proximo_fps = agora + 0.5
            if self.previa:
                img = desenhar_previa(
                    frame, maos, cfg.mapeamento.zona_ativa,
                    interp.depuracao + [f"{fps:.0f} FPS"],
                )
                with self._previa_lock:
                    self._previa_img = img
