"""Baixa o modelo HandLandmarker do MediaPipe para models/hand_landmarker.task."""
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)
DESTINO = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"
TAMANHO_MINIMO = 1_000_000


def main() -> int:
    if DESTINO.exists() and DESTINO.stat().st_size > TAMANHO_MINIMO:
        print(f"Modelo ja existe: {DESTINO}")
        return 0
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {URL}")
    temporario = DESTINO.with_suffix(".baixando")
    urllib.request.urlretrieve(URL, temporario)
    if temporario.stat().st_size < TAMANHO_MINIMO:
        temporario.unlink()
        print("Download incompleto, tente de novo.")
        return 1
    temporario.replace(DESTINO)
    print(f"Pronto: {DESTINO} ({DESTINO.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
