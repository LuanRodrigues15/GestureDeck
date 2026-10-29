"""Rastreamento das maos com o MediaPipe HandLandmarker (21 pontos por mao)."""
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


class Rastreador:
    def __init__(self, cfg, raiz: Path):
        caminho = raiz / cfg.modelo
        if not caminho.exists():
            raise FileNotFoundError(
                f"Modelo nao encontrado em {caminho}. Rode: python scripts/baixar_modelo.py"
            )
        # le o arquivo na memoria: o MediaPipe falha com caminhos que tem acentos
        opcoes = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=caminho.read_bytes()),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=cfg.confianca_deteccao,
            min_hand_presence_confidence=cfg.confianca_presenca,
            min_tracking_confidence=cfg.confianca_rastreio,
        )
        self._lm = vision.HandLandmarker.create_from_options(opcoes)
        self._ultimo_ts = -1

    def processar(self, frame_bgr: np.ndarray, ts_ms: int) -> list[np.ndarray]:
        """Devolve uma lista de arrays (21, 3) com x e y normalizados (0..1)."""
        if ts_ms <= self._ultimo_ts:   # o MediaPipe exige tempo estritamente crescente
            ts_ms = self._ultimo_ts + 1
        self._ultimo_ts = ts_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagem = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        resultado = self._lm.detect_for_video(imagem, ts_ms)
        return [
            np.array([(p.x, p.y, p.z) for p in mao], dtype=np.float32)
            for mao in resultado.hand_landmarks
        ]

    def fechar(self) -> None:
        self._lm.close()
