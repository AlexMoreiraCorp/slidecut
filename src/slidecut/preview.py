"""Miniaturas das paginas, usadas na tela de selecao manual dos cortes.

Devolve PNG em bytes em vez de um objeto de imagem do Tkinter: assim a
renderizacao (cara) pode rodar numa thread de fundo, e a janela so monta o
widget quando a imagem chega.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pymupdf

from .document import open_pdf
from .titles import clean_title, safe_filename

DEFAULT_WIDTH = 170
INSPECT_WIDTH = 420
"""Largura da pagina no painel de inspecao: grande o bastante para ler o slide
sem abrir outra janela."""
CAPTION_LIMIT = 42
BLANK_CAPTION = "(pagina sem texto)"


@dataclass(frozen=True)
class Thumbnail:
    """Miniatura de uma pagina, pronta para virar widget."""

    index: int
    png: bytes
    width: int
    height: int
    caption: str
    title: str
    """Nome de arquivo sugerido caso o usuario corte nesta pagina."""


def page_caption(raw_text: str, limit: int = CAPTION_LIMIT) -> str:
    """Resumo curto do texto da pagina, para o usuario reconhecer o slide."""
    text = clean_title(raw_text, max_lines=3)
    if not text:
        return BLANK_CAPTION
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _thumbnail_of(page: pymupdf.Page, index: int, width: int) -> Thumbnail:
    scale = width / page.rect.width if page.rect.width else 1.0
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False
    )
    text = page.get_text()
    return Thumbnail(
        index=index,
        png=pixmap.tobytes("png"),
        width=pixmap.width,
        height=pixmap.height,
        caption=page_caption(text),
        title=safe_filename(clean_title(text)),
    )


def render_page(
    pdf_path: str | Path, index: int, width: int = INSPECT_WIDTH
) -> Thumbnail:
    """Uma pagina so, no tamanho pedido — o "ver de perto" da tela de selecao.

    Renderizado na hora em vez de guardado junto com as miniaturas: um deck de
    145 paginas em tamanho grande ocuparia memoria a toa, e so uma pagina fica
    em tela por vez.
    """
    with open_pdf(pdf_path) as doc:
        if not 0 <= index < doc.page_count:
            raise IndexError(f"pagina {index} fora do documento ({doc.page_count} paginas)")
        return _thumbnail_of(doc[index], index, width)


def render_thumbnails(
    pdf_path: str | Path, width: int = DEFAULT_WIDTH
) -> Iterator[Thumbnail]:
    """Gera as miniaturas na ordem das paginas, uma de cada vez.

    E um gerador de proposito: a janela vai preenchendo a grade conforme as
    imagens ficam prontas, em vez de esperar o documento inteiro.
    """
    with open_pdf(pdf_path) as doc:
        for index, page in enumerate(doc):
            yield _thumbnail_of(page, index, width)
