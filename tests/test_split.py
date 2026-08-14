from __future__ import annotations

import pytest
from pypdf import PdfReader

from slidecut import split


def test_build_chapters_creates_one_chapter_per_divider():
    chapters = split.build_chapters([0, 1, 4, 6], page_count=7, titles=["Capa", "Conceito", "Fontes", "Fim"])
    assert [(c.start, c.end) for c in chapters] == [(0, 1), (1, 4), (4, 6), (6, 7)]
    assert [c.title for c in chapters] == ["Capa", "Conceito", "Fontes", "Fim"]


def test_build_chapters_prepends_intro_when_deck_starts_with_content():
    chapters = split.build_chapters([2], page_count=5, titles=["Tema"])
    assert [(c.start, c.end, c.title) for c in chapters] == [(0, 2, "Abertura"), (2, 5, "Tema")]


def test_build_chapters_without_dividers_yields_single_chapter():
    chapters = split.build_chapters([], page_count=3, titles=[])
    assert [(c.start, c.end) for c in chapters] == [(0, 3)]


def test_build_chapters_rejects_mismatched_titles():
    with pytest.raises(ValueError):
        split.build_chapters([0, 2], page_count=4, titles=["so um"])


def test_write_chapters_produces_numbered_files(deck, tmp_path):
    chapters = split.build_chapters([0, 1, 4, 6], page_count=7, titles=["Capa", "Conceito", "Fontes", "Fim"])
    outdir = tmp_path / "out"
    written = split.write_chapters(deck, chapters, outdir)

    assert [p.name for p in written] == [
        "01 - Capa.pdf",
        "02 - Conceito.pdf",
        "03 - Fontes.pdf",
        "04 - Fim.pdf",
    ]
    assert len(PdfReader(str(written[1])).pages) == 3


def test_write_chapters_dedupes_repeated_titles(deck, tmp_path):
    chapters = split.build_chapters([0, 1], page_count=7, titles=["Tema", "Tema"])
    written = split.write_chapters(deck, chapters, tmp_path / "out")
    assert [p.name for p in written] == ["01 - Tema.pdf", "02 - Tema (2).pdf"]


def test_write_chapters_creates_output_directory(deck, tmp_path):
    outdir = tmp_path / "nao" / "existe"
    split.write_chapters(deck, split.build_chapters([], 7, []), outdir)
    assert outdir.is_dir()


def test_write_chapters_releases_the_input_file_handle(deck, tmp_path):
    """No Windows um handle aberto impede apagar o PDF temporario da conversao."""
    split.write_chapters(deck, split.build_chapters([], 7, []), tmp_path / "out")
    deck.unlink()
    assert not deck.exists()
