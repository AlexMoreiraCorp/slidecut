"""Testa so a logica pura da GUI. Widgets Tkinter nao sao exercitados aqui:
a pratica da industria e nao testar toolkits de UI, e sim as funcoes que
alimentam e interpretam o que a tela mostra."""

from __future__ import annotations

from pathlib import Path

from slidecut import core, gui


def test_format_result_summary_reports_written_files(tmp_path):
    result = core.ProcessResult(
        divider_color_hex="#B06E03",
        chapters=[],
        outdir=tmp_path,
        written=[tmp_path / "01 - Capa.pdf", tmp_path / "02 - Fim.pdf"],
    )
    summary = gui.format_result_summary(result)
    assert "2 arquivo" in summary
    assert str(tmp_path) in summary


def test_conversion_prompt_names_the_file_and_explains_why():
    prompt = gui.conversion_prompt(Path("C:/x/Aula 01.pptx"))
    assert "Aula 01.pptx" in prompt
    assert "PDF" in prompt
    assert "original" in prompt


def test_selection_summary_counts_marked_cuts():
    assert "3 corte(s)" in gui.selection_summary(3, 145)
    assert "145 paginas" in gui.selection_summary(3, 145)


def test_selection_summary_warns_when_nothing_is_marked():
    assert "Nenhum corte" in gui.selection_summary(0, 20)


def test_input_filetypes_cover_pdf_and_slide_formats():
    all_patterns = " ".join(pattern for _label, pattern in gui.INPUT_FILETYPES)
    assert "*.pdf" in all_patterns
    assert "*.pptx" in all_patterns
    assert "*.docx" in all_patterns
