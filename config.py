"""Carregamento do config.json como objetos com acesso por atributo."""
import json
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent


def _como_objeto(dado):
    if isinstance(dado, dict):
        return SimpleNamespace(**{k: _como_objeto(v) for k, v in dado.items()})
    return dado


def carregar(caminho: str | Path | None = None) -> SimpleNamespace:
    """Le o config.json. Se existir config.local.json, ele sobrescreve as chaves."""
    base = Path(caminho) if caminho else RAIZ / "config.json"
    with open(base, encoding="utf-8") as f:
        dados = json.load(f)
    local = RAIZ / "config.local.json"
    if caminho is None and local.exists():
        with open(local, encoding="utf-8") as f:
            _mesclar(dados, json.load(f))
    return _como_objeto(dados)


def _mesclar(base: dict, extra: dict) -> None:
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(chave), dict):
            _mesclar(base[chave], valor)
        else:
            base[chave] = valor
