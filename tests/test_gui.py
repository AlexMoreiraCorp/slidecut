"""Testa so a logica pura da GUI. Widgets Tkinter nao sao exercitados aqui:
a pratica da industria e nao testar toolkits de UI, e sim as funcoes que
alimentam e interpretam o que a tela mostra."""

from __future__ import annotations

from slidecut import core, gui


def test_format_result_summary_reports_written_files(tmp_path):
    result = core.ProcessResult(
        divider_color_hex="#B06E03",
        chapters=[],
        outdir=tmp_path,
        written=[tmp_path / "01 - Capa.pdf", tmp_path / "02 - Fim.pdf"],
    )
    assert "2 arquivo" in gui.format_result_summary(result, list_only=False)
    assert str(tmp_path) in gui.format_result_summary(result, list_only=False)


def test_format_result_summary_reports_preview_without_files(tmp_path):
    result = core.ProcessResult(
        divider_color_hex="#B06E03",
        chapters=[object(), object(), object()],
        outdir=tmp_path,
        written=[],
    )
    summary = gui.format_result_summary(result, list_only=True)
    assert "3 capitulos" in summary
    assert "nada foi gravado" in summary


def test_input_filetypes_cover_pdf_and_slide_formats():
    all_patterns = " ".join(pattern for _label, pattern in gui.INPUT_FILETYPES)
    assert "*.pdf" in all_patterns
    assert "*.pptx" in all_patterns
    assert "*.docx" in all_patterns
