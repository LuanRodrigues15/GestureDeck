"""Envio das teclas de seta para o PowerPoint."""
from gestures.eventos import Slide


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
        if self._pyautogui is not None:
            self._pyautogui.press(tecla)
        return tecla
