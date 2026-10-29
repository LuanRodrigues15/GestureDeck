"""Teclas de atalho globais (F1, F2, F9, F10) que funcionam com o PowerPoint em foco.

A janela do overlay nao recebe foco, entao os atalhos sao registrados no
Windows com RegisterHotKey e chegam como mensagens WM_HOTKEY.
"""
import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter

_WM_HOTKEY = 0x0312
_MOD_NOREPEAT = 0x4000
_TECLAS = {"F1": 0x70, "F2": 0x71, "F9": 0x78, "F10": 0x79}


class AtalhosGlobais(QAbstractNativeEventFilter):
    def __init__(self, acoes: dict):
        super().__init__()
        self._acoes = {}
        self.falhas: list[str] = []
        if sys.platform != "win32":
            self.falhas = list(acoes)
            return
        user32 = ctypes.windll.user32
        for i, (nome, funcao) in enumerate(acoes.items(), start=1):
            if user32.RegisterHotKey(None, i, _MOD_NOREPEAT, _TECLAS[nome]):
                self._acoes[i] = funcao
            else:
                self.falhas.append(nome)

    def nativeEventFilter(self, tipo, mensagem):
        if "windows_generic_MSG" in str(tipo):
            msg = wintypes.MSG.from_address(int(mensagem))
            if msg.message == _WM_HOTKEY:
                funcao = self._acoes.get(msg.wParam)
                if funcao is not None:
                    funcao()
                    return True, 0
        return False, 0

    def liberar(self) -> None:
        if sys.platform != "win32":
            return
        user32 = ctypes.windll.user32
        for i in self._acoes:
            user32.UnregisterHotKey(None, i)
        self._acoes = {}
