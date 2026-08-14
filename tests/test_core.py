from __future__ import annotations

import pytest

from slidecut import core
from slidecut.errors import NoDividerFound


def test_process_detects_and_writes_chapters(deck, tmp_path):
    outdir = tmp_path / "out"
    result = core.process(deck, outdir=outdir)

    assert result.divider_color_hex == "#AF6D02"
    assert len(result.chapters) == 4
    assert [p.name for p in result.written] == [
        "01 - Capa.pdf",
        "02 - Conceito.pdf",
        "03 - Fontes.pdf",
        "04 - Encerramento.pdf",
    ]
    assert result.outdir == outdir


def test_process_list_only_skips_writing(deck, tmp_path):
    result = core.process(deck, outdir=tmp_path / "out", list_only=True)
    assert result.written == []
    assert not (tmp_path / "out").exists()
    assert len(result.chapters) == 4


def test_process_without_dividers_raises(deck_no_dividers, tmp_path):
    with pytest.raises(NoDividerFound):
        core.process(deck_no_dividers, outdir=tmp_path / "out")


def test_process_reports_progress_milestones(deck, tmp_path):
    messages = []
    core.process(deck, outdir=tmp_path / "out", on_progress=messages.append)
    joined = " ".join(messages)
    assert "reparando" in joined
    assert any("ivisor" in m or "or" in m for m in messages)
    assert any("ravad" in m or "scrit" in m for m in messages)


def test_process_uses_default_outdir_when_none_given(deck):
    result = core.process(deck, outdir=None)
    try:
        assert result.outdir == deck.parent / f"{deck.stem} - cortes"
        assert result.outdir.is_dir()
    finally:
        for f in result.outdir.glob("*.pdf"):
            f.unlink()
        result.outdir.rmdir()


def test_process_honours_explicit_color_and_ascii(tmp_path):
    from tests.conftest import ORANGE, WHITE, build_pdf

    src = build_pdf(
        tmp_path / "acentos.pdf",
        [(ORANGE, "Cooperação"), (WHITE, "x"), (ORANGE, "Isonomia"), (WHITE, "y")],
    )
    result = core.process(src, outdir=tmp_path / "out", color=(176, 110, 3), ascii_only=True)
    assert [p.name for p in result.written] == ["01 - Cooperacao.pdf", "02 - Isonomia.pdf"]


def test_prepare_reports_pages_and_suggested_dividers(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    assert doc.pdf_path == deck
    assert doc.page_count == 7
    assert doc.suggested_dividers == [0, 1, 4, 6]
    assert doc.divider_color_hex == "#AF6D02"


def test_prepare_without_dividers_suggests_nothing_and_does_not_raise(
    deck_no_dividers, tmp_path
):
    doc = core.prepare(deck_no_dividers, workdir=tmp_path / "work")
    assert doc.suggested_dividers == []
    assert doc.divider_color_hex is None
    assert doc.page_count == 4


def test_cut_at_uses_the_pages_the_user_marked(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[2, 5], outdir=tmp_path / "out")
    assert [p.name for p in result.written] == [
        "01 - Abertura.pdf",
        "02 - conteudo 1.pdf",
        "03 - conteudo 3.pdf",
    ]


def test_cut_at_rejects_an_empty_selection(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    with pytest.raises(NoDividerFound):
        core.cut_at(doc, dividers=[], outdir=tmp_path / "out")


def test_cut_at_ignores_out_of_range_and_repeated_pages(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[4, 4, 99, -3], outdir=tmp_path / "out")
    assert [p.name for p in result.written] == ["01 - Abertura.pdf", "02 - Fontes.pdf"]


def test_cut_at_uses_custom_titles_when_given(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(
        doc, dividers=[0, 4], outdir=tmp_path / "out", custom_titles={4: "Nome que eu escolhi"}
    )
    assert [p.name for p in result.written] == [
        "01 - Capa.pdf",
        "02 - Nome que eu escolhi.pdf",
    ]


def test_cut_at_sanitises_custom_titles(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(
        doc, dividers=[0], outdir=tmp_path / "out", custom_titles={0: 'barra/aqui: "aspas"?'}
    )
    assert result.written[0].name == "01 - barra-aqui - aspas.pdf"


def test_cut_at_falls_back_to_page_text_when_custom_title_is_blank(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[4], outdir=tmp_path / "out", custom_titles={4: "   "})
    assert [p.name for p in result.written] == ["01 - Abertura.pdf", "02 - Fontes.pdf"]
