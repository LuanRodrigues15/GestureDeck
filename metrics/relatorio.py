"""Metricas da execucao e relatorio final em JSON."""
import json
import threading
import time
from datetime import datetime
from pathlib import Path

from gestures.eventos import Gesto, Quadro, Slide


class Metricas:
    def __init__(self):
        self._lock = threading.Lock()
        self._inicio = time.monotonic()
        self._inicio_data = datetime.now()
        self.quadros = 0
        self.quadros_com_mao = 0
        self._latencias_ms: list[float] = []
        self._proc_ms: list[float] = []
        self.slides = {"proximo": 0, "anterior": 0}
        self.tracos = 0
        self.gestos = {g.value: 0 for g in Gesto if g != Gesto.NENHUM}
        self.ativacoes_trava = 0
        self._anterior = Quadro(t=0.0)

    def registrar_quadro(self, q: Quadro, proc_ms: float, latencia_ms: float) -> None:
        with self._lock:
            self.quadros += 1
            if q.maos:
                self.quadros_com_mao += 1
            self._proc_ms.append(proc_ms)
            self._latencias_ms.append(latencia_ms)
            if q.trava and not self._anterior.trava:
                self.ativacoes_trava += 1
            if q.trava and q.gesto != Gesto.NENHUM and q.gesto != self._anterior.gesto:
                self.gestos[q.gesto.value] += 1
            if q.slide == Slide.PROXIMO:
                self.slides["proximo"] += 1
            elif q.slide == Slide.ANTERIOR:
                self.slides["anterior"] += 1
            self._anterior = q

    def registrar_traco(self) -> None:
        with self._lock:
            self.tracos += 1

    @staticmethod
    def _estatistica(valores: list[float]) -> dict:
        if not valores:
            return {"media": 0.0, "p95": 0.0, "max": 0.0}
        ordenados = sorted(valores)
        p95 = ordenados[min(len(ordenados) - 1, int(0.95 * len(ordenados)))]
        return {
            "media": round(sum(valores) / len(valores), 2),
            "p95": round(p95, 2),
            "max": round(ordenados[-1], 2),
        }

    def resumo(self) -> dict:
        with self._lock:
            duracao = time.monotonic() - self._inicio
            return {
                "inicio": self._inicio_data.isoformat(timespec="seconds"),
                "duracao_s": round(duracao, 1),
                "quadros_processados": self.quadros,
                "fps_medio": round(self.quadros / duracao, 1) if duracao > 0 else 0.0,
                "quadros_com_mao_pct": round(100 * self.quadros_com_mao / self.quadros, 1)
                if self.quadros
                else 0.0,
                "latencia_camera_ate_acao_ms": self._estatistica(self._latencias_ms),
                "processamento_ms": self._estatistica(self._proc_ms),
                "slides_trocados": dict(self.slides, total=sum(self.slides.values())),
                "tracos_desenhados": self.tracos,
                "ativacoes_da_trava": self.ativacoes_trava,
                "gestos_reconhecidos": dict(self.gestos),
            }

    def salvar(self, pasta: Path) -> Path:
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"relatorio_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.resumo(), f, ensure_ascii=False, indent=2)
        return caminho
