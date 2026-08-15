"""Agrupamento de paginas por folha, para economizar papel e espaco em disco.

Um deck de aula tem uma pagina por slide, e cada slide ocupa pouco da folha.
Empilhar 2, 3 ou 4 slides numa folha A4 corta o numero de folhas na mesma
proporcao sem perder nada: as paginas sao inseridas como conteudo vetorial, nao
como imagem, entao o texto continua selecionavel e pesquisavel.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pymupdf

from .document import open_pdf

ALLOWED = (1, 2, 3, 4)
"""Quantas paginas cabem numa folha. Acima de 4 o slide fica ilegivel impresso."""

A4 = pymupdf.paper_size("a4")
MARGIN = 28.0
"""Margem externa da folha, em pontos (~1 cm)."""

GUTTER = 14.0
"""Espaco entre as paginas empilhadas, para nao encostarem uma na outra."""


def describe(per_sheet: int) -> str:
    """Frase curta para menus e relatorios."""
    if per_sheet == 1:
        return "uma página por folha"
    return f"{per_sheet} páginas por folha"


def sheet_count(pages: int, per_sheet: int) -> int:
    """Quantas folhas saem de um documento com esse agrupamento."""
    if pages <= 0:
        return 0
    return math.ceil(pages / per_sheet)


def _cell(index: int, per_sheet: int) -> pymupdf.Rect:
    """Area util da folha destinada a n-esima pagina empilhada.

    O empilhamento e sempre vertical: slides sao largos e baixos, entao dividir
    a altura mantem cada um o mais largo possivel, que e o que preserva a
    legibilidade do texto.
    """
    width, height = A4
    usable = height - 2 * MARGIN - GUTTER * (per_sheet - 1)
    cell_height = usable / per_sheet
    top = MARGIN + index * (cell_height + GUTTER)
    return pymupdf.Rect(MARGIN, top, width - MARGIN, top + cell_height)


def _fitted(cell: pymupdf.Rect, page: pymupdf.Rect) -> pymupdf.Rect:
    """Encaixa a pagina na celula preservando a proporcao e centralizando."""
    scale = min(cell.width / page.width, cell.height / page.height)
    width, height = page.width * scale, page.height * scale
    x = cell.x0 + (cell.width - width) / 2
    y = cell.y0 + (cell.height - height) / 2
    return pymupdf.Rect(x, y, x + width, y + height)


def group_pages(source: str | Path, target: str | Path, per_sheet: int = 2) -> Path:
    """Grava uma copia de source com per_sheet paginas em cada folha A4."""
    if per_sheet not in ALLOWED:
        raise ValueError(
            f"agrupamento invalido: {per_sheet}. Use um destes: {', '.join(map(str, ALLOWED))}"
        )

    source = Path(source)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Agrupar sobre o proprio arquivo e o caso comum (pos-processar os cortes),
    # mas o PDF de origem fica aberto durante a montagem e o Windows nao deixa
    # sobrescrever um arquivo em uso. Monta ao lado e troca no fim.
    in_place = target.exists() and source.exists() and target.samefile(source)
    written_to = target.with_name(target.name + ".montando") if in_place else target

    try:
        with open_pdf(source) as origin:
            if per_sheet == 1:
                origin.save(str(written_to))
            else:
                sheets = pymupdf.open()
                try:
                    for start in range(0, origin.page_count, per_sheet):
                        sheet = sheets.new_page(width=A4[0], height=A4[1])
                        for slot, index in enumerate(
                            range(start, min(start + per_sheet, origin.page_count))
                        ):
                            box = _fitted(_cell(slot, per_sheet), origin[index].rect)
                            sheet.show_pdf_page(box, origin, index)
                    sheets.save(str(written_to), garbage=3, deflate=True)
                finally:
                    sheets.close()

        if in_place:
            os.replace(written_to, target)
    finally:
        if in_place and written_to.exists():
            written_to.unlink(missing_ok=True)
    return target
