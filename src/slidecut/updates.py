"""Verifica se ha uma versao mais nova no GitHub, baixa e instala sob confirmacao.

A checagem le o arquivo __init__.py direto do branch principal no GitHub (raw,
sem autenticacao — o repositorio e publico) e compara com a versao instalada.
Qualquer falha (sem internet, GitHub fora do ar, resposta inesperada) e
silenciosa: checar atualizacao nunca pode atrapalhar quem so quer cortar um
PDF.

Baixar e instalar so acontece se o usuario pedir explicitamente (a janela
sempre confirma antes). O instalador baixado e conferido contra um checksum
SHA-256 publicado junto do release antes de rodar — sem isso, qualquer um no
meio do caminho (proxy, DNS, mirror comprometido) poderia trocar o .exe por
outra coisa e o programa executaria sem perceber.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO = "AlexMoreiraCorp/slidecut"
VERSION_URL = (
    f"https://raw.githubusercontent.com/{REPO}/master/src/slidecut/__init__.py"
)
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"

_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
_VERSION_TUPLE_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_HEX_RE = re.compile(r"[0-9a-fA-F]{64}")

Fetcher = Callable[[str], str]
BytesFetcher = Callable[[str], bytes]


class UpdateDownloadError(Exception):
    """Baixar ou conferir o instalador falhou. A mensagem e para mostrar na tela."""


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


def _fetch_bytes_from_github(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - URL fixa, https
        return response.read()


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


def installer_url(version: str) -> str:
    """Onde o instalador dessa versao fica publicado, seguindo o padrao do build."""
    return f"https://github.com/{REPO}/releases/download/v{version}/slidecut-setup-{version}.exe"


def checksum_url(version: str) -> str:
    return f"{installer_url(version)}.sha256"


def verify_sha256(data: bytes, expected: str) -> bool:
    """Confere o hash dos bytes baixados contra o que veio no arquivo .sha256.

    O arquivo .sha256 costuma vir no formato `HASH  nome-do-arquivo`, entao so
    o primeiro token hexadecimal de 64 caracteres importa; o resto (nome do
    arquivo, quebra de linha) e ignorado.
    """
    match = _HEX_RE.search(expected)
    if match is None:
        return False
    return hashlib.sha256(data).hexdigest().lower() == match.group(0).lower()


def download_installer(
    version: str, dest_dir: str | Path, fetch_bytes: BytesFetcher = _fetch_bytes_from_github
) -> Path:
    """Baixa o instalador da versao pedida, confere a integridade e grava em disco.

    So grava o arquivo se o hash bater. Uma verificacao que falha nunca deixa
    um instalador incompleto ou adulterado no disco esperando alguem clicar
    nele sem saber o que e.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"slidecut-setup-{version}.exe"

    try:
        checksum_text = fetch_bytes(checksum_url(version)).decode("ascii", errors="replace")
        installer_bytes = fetch_bytes(installer_url(version))
    except Exception as exc:
        raise UpdateDownloadError(f"não consegui baixar o instalador: {exc}") from exc

    if not verify_sha256(installer_bytes, checksum_text):
        raise UpdateDownloadError(
            "o instalador baixado não bateu com a verificação de integridade "
            "(checksum). Por segurança, ele não foi executado."
        )

    target.write_bytes(installer_bytes)
    return target
