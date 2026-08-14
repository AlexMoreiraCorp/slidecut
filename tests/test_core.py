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
    assert "onvert" in joined or "PDF" in joined
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
