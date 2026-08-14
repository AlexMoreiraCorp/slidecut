"""Montagem dos capitulos e escrita dos PDFs de saida."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter

INTRO_TITLE = "Abertura"
"""Nome do bloco de paginas que vem antes do primeiro divisor."""

WHOLE_DOC_TITLE = "Documento completo"


@dataclass(frozen=True)
class Chapter:
    """Intervalo de paginas [start, end) com o titulo lido do slide divisor."""

    start: int
    end: int
    title: str

    @property
    def page_count(self) -> int:
        return self.end - self.start


def build_chapters(dividers: list[int], page_count: int, titles: list[str]) -> list[Chapter]:
    """Converte os indices dos divisores em intervalos continuos que cobrem o PDF."""
    if len(dividers) != len(titles):
        raise ValueError(f"{len(dividers)} divisores para {len(titles)} titulos")
    if page_count <= 0:
        return []
    if not dividers:
        return [Chapter(0, page_count, WHOLE_DOC_TITLE)]

    starts = list(dividers)
    names = list(titles)
    if starts[0] > 0:
        starts.insert(0, 0)
        names.insert(0, INTRO_TITLE)

    bounds = starts[1:] + [page_count]
    return [Chapter(s, e, t) for s, e, t in zip(starts, bounds, names) if e > s]


def _unique(name: str, used: set[str]) -> str:
    """Evita sobrescrever arquivos quando dois capitulos tem o mesmo titulo."""
    if name not in used:
        used.add(name)
        return name
    suffix = 2
    while f"{name} ({suffix})" in used:
        suffix += 1
    unique = f"{name} ({suffix})"
    used.add(unique)
    return unique


def write_chapters(pdf_path: str | Path, chapters: list[Chapter], outdir: str | Path) -> list[Path]:
    """Grava um PDF por capitulo em outdir e devolve os caminhos criados."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    width = max(2, len(str(len(chapters))))
    used: set[str] = set()
    written: list[Path] = []

    # O handle e fechado antes de retornar: o PDF de origem pode estar num
    # diretorio temporario que o chamador precisa apagar logo em seguida.
    with open(pdf_path, "rb") as source:
        reader = PdfReader(source)
        for number, chapter in enumerate(chapters, start=1):
            writer = PdfWriter()
            for page in range(chapter.start, chapter.end):
                writer.add_page(reader.pages[page])

            name = _unique(chapter.title, used)
            target = outdir / f"{number:0{width}d} - {name}.pdf"
            with target.open("wb") as handle:
                writer.write(handle)
            written.append(target)

    return written
