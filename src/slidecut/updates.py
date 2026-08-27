"""Verifica se ha uma versao mais nova no GitHub.

So avisa — nunca baixa nem instala nada sozinho. Baixar e substituir o proprio
executavel em execucao e um problema bem maior (processo a parte, reinicio,
permissao de admin) e fora do escopo daqui: o usuario decide quando atualizar,
o programa so evita que ele descubra tarde demais que existe uma versao nova.

A checagem le o arquivo __init__.py direto do branch principal no GitHub (raw,
sem autenticacao — o repositorio e publico) e compara com a versao instalada.
Qualquer falha (sem internet, GitHub fora do ar, resposta inesperada) e
silenciosa: checar atualizacao nunca pode atrapalhar quem so quer cortar um
PDF.
"""

from __future__ import annotations

import re
import urllib.request
from dataclasses import dataclass
from typing import Callable

VERSION_URL = (
    "https://raw.githubusercontent.com/AlexMoreiraCorp/slidecut/master/"
    "src/slidecut/__init__.py"
)
RELEASES_URL = "https://github.com/AlexMoreiraCorp/slidecut/releases/latest"

_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
_VERSION_TUPLE_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

Fetcher = Callable[[str], str]


@dataclass(frozen=True)
class UpdateAvailable:
    """Ha uma versao mais nova: numero dela e onde baixar."""

    version: str
    url: str = RELEASES_URL


def parse_version(text: str) -> str | None:
    """Extrai o valor de __version__ de dentro do texto de __init__.py."""
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _as_tuple(version: str) -> tuple[int, int, int] | None:
    match = _VERSION_TUPLE_RE.match(version.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer(current: str, candidate: str) -> bool:
    """Se candidate e uma versao maior que current.

    Compara numero a numero (major, minor, patch), nao texto: "0.9.9" nao pode
    parecer maior que "0.10.0" so porque "9" > "1" na comparacao de strings.
    Qualquer coisa que nao pareca X.Y.Z (resposta inesperada do servidor,
    pagina de erro) nunca conta como mais nova — evita alarme falso.
    """
    parsed_current = _as_tuple(current)
    parsed_candidate = _as_tuple(candidate)
    if parsed_current is None or parsed_candidate is None:
        return False
    return parsed_candidate > parsed_current


def _fetch_from_github(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - URL fixa, https
        return response.read().decode("utf-8", errors="replace")


def check_for_update(
    current_version: str, fetch: Fetcher = _fetch_from_github
) -> UpdateAvailable | None:
    """Devolve a versao nova disponivel, ou None (nada novo, ou a checagem falhou)."""
    try:
        text = fetch(VERSION_URL)
    except Exception:
        return None

    remote_version = parse_version(text)
    if remote_version is None or not is_newer(current_version, remote_version):
        return None

    return UpdateAvailable(version=remote_version)
