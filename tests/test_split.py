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


# --------------------------------------------- paginas fora do corte
def test_chapter_without_an_explicit_page_list_covers_its_whole_range():
    assert split.Chapter(2, 5, "Tema").page_numbers == (2, 3, 4)


def test_build_chapters_leaves_out_the_pages_the_user_unchecked():
    """Item excluido some do arquivo gerado, mas o intervalo do capitulo nao muda."""
    chapters = split.build_chapters([0, 4], page_count=7, titles=["Capa", "Fim"],
                                    excluded={2, 5})
    assert [c.page_numbers for c in chapters] == [(0, 1, 3), (4, 6)]
    assert [(c.start, c.end) for c in chapters] == [(0, 4), (4, 7)]


def test_build_chapters_drops_a_chapter_left_without_any_page():
    chapters = split.build_chapters([0, 4], page_count=7, titles=["Capa", "Fim"],
                                    excluded={4, 5, 6})
    assert [c.title for c in chapters] == ["Capa"]


def test_page_count_of_a_chapter_counts_only_the_pages_that_will_be_written():
    chapter = split.build_chapters([0], page_count=4, titles=["Capa"], excluded={1})[0]
    assert chapter.page_count == 3


def test_write_chapters_skips_the_excluded_pages(deck, tmp_path):
    chapters = split.build_chapters([0], page_count=7, titles=["Tudo"], excluded={1, 2})
    written = split.write_chapters(deck, chapters, tmp_path / "out")
    assert len(PdfReader(str(written[0])).pages) == 5


# ---------------------------------------------------- numeracao opcional
def test_write_chapters_numbers_by_default(deck, tmp_path):
    chapters = split.build_chapters([0, 1], page_count=7, titles=["Capa", "Fim"])
    written = split.write_chapters(deck, chapters, tmp_path / "out")
    assert [p.name for p in written] == ["01 - Capa.pdf", "02 - Fim.pdf"]


def test_write_chapters_can_skip_the_number(deck, tmp_path):
    chapters = split.build_chapters([0, 1], page_count=7, titles=["Capa", "Fim"])
    written = split.write_chapters(deck, chapters, tmp_path / "out", numbered=False)
    assert [p.name for p in written] == ["Capa.pdf", "Fim.pdf"]


def test_write_chapters_without_numbers_still_dedupes_repeated_titles(deck, tmp_path):
    chapters = split.build_chapters([0, 1], page_count=7, titles=["Tema", "Tema"])
    written = split.write_chapters(deck, chapters, tmp_path / "out", numbered=False)
    assert [p.name for p in written] == ["Tema.pdf", "Tema (2).pdf"]
