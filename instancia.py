"""Garante uma unica execucao do GestureDeck por vez.

Duas instancias disputam a mesma camera: a segunda recebe imagem preta e a
primeira cai para cerca de 1 FPS. Alem de recusar a segunda, este modulo guarda
o PID para a opcao --encerrar.
"""
import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_NOME_MUTEX = "Local\\GestureDeck_instancia_unica"
_ERRO_JA_EXISTE = 183
_mutex = None   # a referencia mantem o mutex vivo ate o processo terminar


def _arquivo_pid() -> Path:
    return Path(tempfile.gettempdir()) / "gesturedeck.pid"


def _pid_gravado() -> int | None:
    try:
        return int(_arquivo_pid().read_text().strip())
    except (OSError, ValueError):
        return None


def registrar() -> bool:
    """Tenta ser a unica instancia. False se outra ja estiver rodando."""
    global _mutex
    if sys.platform != "win32":
        _arquivo_pid().write_text(str(os.getpid()))
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    _mutex = kernel32.CreateMutexW(None, False, _NOME_MUTEX)
    if ctypes.get_last_error() == _ERRO_JA_EXISTE:
        return False
    _arquivo_pid().write_text(str(os.getpid()))
    return True


def liberar() -> None:
    if _pid_gravado() == os.getpid():
        try:
            _arquivo_pid().unlink()
        except OSError:
            pass


def mensagem_ja_em_execucao() -> str:
    pid = _pid_gravado()
    detalhe = f" (PID {pid})" if pid else ""
    return (
        f"O GestureDeck ja esta em execucao{detalhe}. Duas copias disputam a camera.\n"
        "Feche a outra com F10, pelo icone na bandeja do Windows, ou rode:\n"
        "    python main.py --encerrar"
    )


def encerrar_existente() -> int:
    """Fecha a instancia em execucao, se houver. Devolve o codigo de saida."""
    pid = _pid_gravado()
    if pid is None:
        print("Nenhum GestureDeck em execucao.")
        return 0
    consulta = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    )
    if "python" not in consulta.stdout.lower():
        print("Nenhum GestureDeck em execucao.")
        try:
            _arquivo_pid().unlink()
        except OSError:
            pass
        return 0
    resultado = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, text=True)
    if resultado.returncode == 0:
        print(f"GestureDeck encerrado (PID {pid}). A camera foi liberada.")
        try:
            _arquivo_pid().unlink()
        except OSError:
            pass
        return 0
    print(f"Nao foi possivel encerrar o PID {pid}: {resultado.stderr.strip()}")
    return 1
