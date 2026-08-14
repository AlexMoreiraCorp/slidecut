"""Abertura de PDFs com erro traduzido para a linguagem da aplicacao."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pymupdf

from .errors import AnalysisError


@contextmanager
def open_pdf(path: str | Path):
    """Abre o PDF e garante o fechamento do handle.

    O handle importa: no Windows um arquivo aberto nao pode ser apagado, e o PDF
    convertido vive num diretorio temporario que precisa sumir no fim.
    """
    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:  # pymupdf levanta tipos variados conforme o defeito
        raise AnalysisError(f"nao foi possivel ler o PDF {Path(path).name}: {exc}") from exc

    try:
        if doc.needs_pass:
            raise AnalysisError(f"PDF protegido por senha: {Path(path).name}")
        yield doc
    finally:
        doc.close()
