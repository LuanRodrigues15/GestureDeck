"""Thread de visao: camera, MediaPipe, interpretacao dos gestos e acoes."""
import threading
import time
import traceback

import cv2

from gestures.eventos import Quadro
from gestures.interpretador import Interpretador
from overlay.previa import desenhar_previa

from .camera import Camera
from .rastreador import Rastreador


class ThreadVisao(threading.Thread):
    def __init__(self, cfg, raiz, sessao, metricas, teclas, previa: bool = False):
        super().__init__(name="visao", daemon=True)
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
            camera = Camera(self.cfg.camera)
            camera.abrir()
            print(
                f"Camera {self.cfg.camera.indice}: {camera.largura}x{camera.altura} "
                f"{camera.formato or '?'}"
            )
            camera.iniciar()
            rastreador = Rastreador(self.cfg.mediapipe, self.raiz)
            self._laco(camera, rastreador)
        except Exception:
            self.erro = traceback.format_exc()
        finally:
            if rastreador is not None:
                rastreador.fechar()
            if camera is not None:
                camera.fechar()

    def _laco(self, camera: Camera, rastreador: Rastreador) -> None:
        cfg = self.cfg
        x0, y0, x1, y1 = cfg.roi
        escala = cfg.escala_processamento
        interp = None
        ultimo_id = 0
        ultimo_t = time.monotonic()
        fps = 0.0
        proximo_fps = 0.0
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
