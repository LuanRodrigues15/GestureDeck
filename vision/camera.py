"""Captura da camera em uma thread propria, sempre entregando o quadro mais novo."""
import threading
import time

import cv2

_BACKENDS = {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "auto": cv2.CAP_ANY}
_FALHAS_MAXIMAS = 150


class Camera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.largura = 0
        self.altura = 0
        self.formato = ""
        self.falhou = False
        self._cap = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._cond = threading.Condition()
        self._frame = None
        self._id = 0
        self._ts = 0.0

    def abrir(self) -> None:
        c = self.cfg
        backend = _BACKENDS.get(c.backend, cv2.CAP_ANY)
        cap = cv2.VideoCapture(c.indice, backend)
        if not cap.isOpened():
            raise RuntimeError(
                f"Nao foi possivel abrir a camera {c.indice}. Tente --camera N ou "
                f"mude 'backend' no config.json (dshow, msmf, auto)."
            )
        # o formato vem primeiro: sem MJPG a maioria das cameras USB nao entrega 1080p a 30 FPS
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*c.formato))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, c.largura)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, c.altura)
        cap.set(cv2.CAP_PROP_FPS, c.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        exposicao = getattr(c, "exposicao", None)
        if exposicao is not None:
            # exposicao manual evita a queda de FPS da camera em ambiente escuro
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_EXPOSURE, exposicao)
        self.largura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.altura = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        codigo = int(cap.get(cv2.CAP_PROP_FOURCC))
        self.formato = "".join(chr((codigo >> (8 * i)) & 0xFF) for i in range(4)).strip()
        self._cap = cap

    def iniciar(self) -> None:
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="camera", daemon=True)
        self._thread.start()

    def _laco(self) -> None:
        falhas = 0
        while not self._parar.is_set():
            ok, frame = self._cap.read()
            if not ok or frame is None:
                falhas += 1
                if falhas >= _FALHAS_MAXIMAS:
                    self.falhou = True
                    with self._cond:
                        self._cond.notify_all()
                    return
                time.sleep(0.005)
                continue
            falhas = 0
            with self._cond:
                self._frame = frame
                self._ts = time.monotonic()
                self._id += 1
                self._cond.notify_all()

    def proximo_quadro(self, ultimo_id: int, timeout: float = 0.5):
        """Espera um quadro mais novo que `ultimo_id`. Devolve (frame, id, instante) ou None."""
        with self._cond:
            if not self._cond.wait_for(
                lambda: self._id > ultimo_id or self.falhou or self._parar.is_set(), timeout
            ):
                return None
            if self._id <= ultimo_id:
                return None
            return self._frame, self._id, self._ts

    def fechar(self) -> None:
        self._parar.set()
        with self._cond:
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None
