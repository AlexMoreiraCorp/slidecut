"""Extracao e sanitizacao dos titulos usados como nome de arquivo."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .document import open_pdf

MAX_TITLE_LINES = 6
MAX_FILENAME_LENGTH = 80
FALLBACK_TITLE = "Sem titulo"

SPEAKER_RE = re.compile(r"^(prof|profa|professora?|by|apresentad[oa] por)\.?(?:\s|$)", re.IGNORECASE)
"""Linhas de credito do palestrante nao entram no nome do arquivo."""

COLON_RE = re.compile(r"\s*:\s*")
CONTROL_RE = re.compile(r"[\x00-\x1f]")
RESERVED_CHARS_RE = re.compile(r'[<>"|?*]')
SLASH_RE = re.compile(r"[\\/]+")
WHITESPACE_RE = re.compile(r"\s+")
ORPHAN_HYPHEN_RE = re.compile(r"\s+-(?=\w)")
"""PDFs quebram 'Boa-fe' em 'Boa -fe' ao juntar linhas; recola o hifen."""

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def clean_title(raw: str, max_lines: int = MAX_TITLE_LINES) -> str:
    """Junta as primeiras linhas uteis da pagina, descartando credito de autor."""
    lines = [line.strip() for line in raw.splitlines()]
    useful = [line for line in lines if line and not SPEAKER_RE.match(line)]
    return WHITESPACE_RE.sub(" ", " ".join(useful[:max_lines])).strip()


def safe_filename(title: str, ascii_only: bool = False) -> str:
    """Transforma o titulo num nome de arquivo valido no Windows e no POSIX."""
    name = unicodedata.normalize("NFC", title)
    if ascii_only:
        name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")

    name = CONTROL_RE.sub(" ", name)
    name = COLON_RE.sub(" - ", name)
    name = SLASH_RE.sub("-", name)
    name = RESERVED_CHARS_RE.sub("", name)
    name = WHITESPACE_RE.sub(" ", name)
    name = ORPHAN_HYPHEN_RE.sub("-", name).strip(" .")

    if not name:
        return FALLBACK_TITLE
    if name.upper() in WINDOWS_RESERVED:
        return f"{name} (doc)"
    return name[:MAX_FILENAME_LENGTH].strip()


def decorate(title: str, prefix: str = "", suffix: str = "", ascii_only: bool = False) -> str:
    """Envolve o titulo com o prefixo e o sufixo escolhidos pelo usuario.

    Prefixo e sufixo sao digitados, entao passam pela mesma limpeza do titulo:
    uma barra ou dois-pontos ali dentro quebraria o nome do arquivo. O limite de
    tamanho vale para o conjunto, nao para cada pedaco — o nome final e que
    precisa caber.
    """
    joined = " ".join(part.strip() for part in (prefix, title, suffix) if part.strip())
    return safe_filename(joined, ascii_only)


def page_titles(pdf_path: str | Path, indices: list[int], ascii_only: bool = False) -> list[str]:
    """Titulo de cada pagina indicada, ja pronto para virar nome de arquivo."""
    titles: list[str] = []
    with open_pdf(pdf_path) as doc:
        for index in indices:
            titles.append(safe_filename(clean_title(doc[index].get_text()), ascii_only))
    return titles
