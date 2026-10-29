"""Envio das teclas de seta para o PowerPoint."""
import ctypes
import sys
from ctypes import wintypes

from gestures.eventos import Slide

_CLASSE_APRESENTACAO = "screenClass"   # janela do PowerPoint em modo apresentacao


def _preparar_user32():
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [
        ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM,
    ]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    return user32


def achar_apresentacao() -> int | None:
    """Janela do PowerPoint em modo apresentacao (F5), ou None."""
    if sys.platform != "win32":
        return None
    user32 = _preparar_user32()
    achadas: list[int] = []

    def ao_achar(hwnd, _):
        buffer = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buffer, 64)
        if buffer.value == _CLASSE_APRESENTACAO and user32.IsWindowVisible(hwnd):
            achadas.append(hwnd)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(ao_achar), 0)
    return achadas[0] if achadas else None


def focar_janela(hwnd: int) -> bool:
    """Traz a janela para o primeiro plano. O Windows so permite isso a quem esta
    ligado a fila de entrada da janela que esta em foco, por isso o AttachThreadInput."""
    user32 = _preparar_user32()
    kernel32 = ctypes.windll.kernel32
    if user32.GetForegroundWindow() == hwnd:
        return True
    em_foco = user32.GetForegroundWindow()
    thread_foco = user32.GetWindowThreadProcessId(em_foco, None) if em_foco else 0
    thread_atual = kernel32.GetCurrentThreadId()
    ligado = bool(thread_foco) and thread_foco != thread_atual and bool(
        user32.AttachThreadInput(thread_atual, thread_foco, True)
    )
    try:
        user32.SetForegroundWindow(hwnd)
    finally:
        if ligado:
            user32.AttachThreadInput(thread_atual, thread_foco, False)
    return user32.GetForegroundWindow() == hwnd


class Teclas:
    def __init__(self, cfg_acoes, ensaio: bool = False):
        self.cfg = cfg_acoes
        self.ensaio = ensaio
        self._pyautogui = None
        if not ensaio:
            # importado aqui de proposito: o PyAutoGUI mexe na escala (DPI) do
            # processo ao ser importado, e isso precisa acontecer depois do Qt
            import pyautogui

            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0
            self._pyautogui = pyautogui

    def enviar(self, slide: Slide) -> str:
        tecla = self.cfg.tecla_proximo if slide == Slide.PROXIMO else self.cfg.tecla_anterior
        if self._pyautogui is None:
            return tecla
        # o overlay nunca toma o foco, entao a janela em foco pode ser o terminal
        # em vez do PowerPoint: traz a apresentacao para a frente antes da seta
        destino = "janela em foco"
        if getattr(self.cfg, "enviar_para_apresentacao", True):
            hwnd = achar_apresentacao()
            if hwnd is not None:
                destino = "apresentacao" if focar_janela(hwnd) else "apresentacao sem foco"
        self._pyautogui.press(tecla)
        return f"{tecla} ({destino})"
