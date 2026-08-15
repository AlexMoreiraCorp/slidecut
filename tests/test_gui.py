"""Testa a logica pura da janela. Widgets Tkinter nao sao exercitados aqui: a
pratica e nao testar o toolkit, e sim as funcoes que alimentam e interpretam o
que a tela mostra."""

from __future__ import annotations

from pathlib import Path

from slidecut import core, gui


def test_format_result_summary_reports_written_files(tmp_path):
    result = core.ProcessResult(
        divider_color_hex="#B06E03", chapters=[], outdir=tmp_path,
        written=[tmp_path / "01 - Capa.pdf", tmp_path / "02 - Fim.pdf"],
    )
    summary = gui.format_result_summary(result)
    assert "2 arquivo" in summary
    assert str(tmp_path) in summary


def test_conversion_prompt_names_the_converter_that_will_run():
    prompt = gui.conversion_prompt(Path("C:/x/Aula 01.pptx"), "Microsoft Office")
    assert "Aula 01.pptx" in prompt
    assert "Microsoft Office" in prompt
    assert "não altera o arquivo original" in prompt


def test_conversion_prompt_does_not_hardcode_libreoffice():
    """A mensagem antiga citava LibreOffice mesmo em maquina com Office."""
    assert "LibreOffice" not in gui.conversion_prompt(Path("a.pptx"), "Microsoft Office")


def test_no_converter_message_says_what_still_works():
    text = gui.no_converter_message(Path("aula.pptx"))
    assert "Office" in text and "LibreOffice" in text
    assert "PDF" in text


def test_selection_summary_counts_files_that_will_be_generated():
    assert "3 arquivo(s)" in gui.selection_summary(3, 145)
    assert "145 páginas" in gui.selection_summary(3, 145)


def test_selection_summary_warns_when_nothing_is_marked():
    assert "nenhum corte" in gui.selection_summary(0, 20)


def test_chapter_ranges_match_the_marked_pages():
    assert gui.chapter_ranges([0, 4, 6], 8) == [(1, 0, 3), (2, 4, 5), (3, 6, 7)]


def test_chapter_ranges_open_with_an_intro_when_the_deck_starts_uncut():
    assert gui.chapter_ranges([3], 6) == [(1, 0, 2), (2, 3, 5)]


def test_chapter_ranges_without_marks_is_a_single_block():
    assert gui.chapter_ranges([], 5) == [(1, 0, 4)]


def test_chapter_ranges_of_an_empty_document_is_empty():
    assert gui.chapter_ranges([], 0) == []


def test_dropped_path_with_spaces_comes_wrapped_in_braces(tmp_path):
    target = tmp_path / "Aula 01 com espaço.pptx"
    target.write_bytes(b"x")
    assert gui.parse_dropped_path("{" + str(target) + "}") == target


def test_dropped_path_without_spaces_is_read_directly(tmp_path):
    target = tmp_path / "aula.pptx"
    target.write_bytes(b"x")
    assert gui.parse_dropped_path(str(target)) == target


def test_dropping_several_files_takes_the_first(tmp_path):
    first = tmp_path / "um.pdf"
    first.write_bytes(b"x")
    second = tmp_path / "dois.pdf"
    second.write_bytes(b"x")
    payload = "{" + str(first) + "} {" + str(second) + "}"
    assert gui.parse_dropped_path(payload) == first


def test_dropping_something_that_is_not_a_file_is_refused():
    assert gui.parse_dropped_path("") is None
    assert gui.parse_dropped_path("{C:/nao/existe.pptx}") is None


def test_primary_file_types_lead_with_the_formats_people_actually_bring():
    first_label, first_pattern = gui.PRIMARY_TYPES[0]
    assert "*.pptx" in first_pattern
    assert "*.docx" in first_pattern
    assert "*.pdf" in first_pattern


def test_layout_choices_offer_one_to_four_with_two_as_default():
    rotulos = [rotulo for rotulo, _valor in gui.LAYOUT_CHOICES]
    valores = [valor for _rotulo, valor in gui.LAYOUT_CHOICES]
    assert valores == [1, 2, 3, 4]
    assert gui.DEFAULT_PER_SHEET == 2
    assert any("1" in r for r in rotulos)


def test_mode_choices_cover_cutting_and_converting():
    valores = [valor for _rotulo, valor in gui.MODE_CHOICES]
    assert "cortar" in valores
    assert "converter" in valores


def test_conversion_summary_names_the_file_and_layout(tmp_path):
    texto = gui.conversion_summary(tmp_path / "Aula 01.docx", per_sheet=2)
    assert "Aula 01.docx" in texto
    assert "2 páginas por folha" in texto


def test_conversion_summary_omits_layout_when_one_per_sheet(tmp_path):
    texto = gui.conversion_summary(tmp_path / "Aula.pdf", per_sheet=1)
    assert "por folha" not in texto


def test_batch_summary_counts_ok_and_failed():
    from slidecut import core

    resultados = [
        core.BatchItemResult(source=Path("a.pdf"), ok=True, written=[Path("a1.pdf")]),
        core.BatchItemResult(source=Path("b.pdf"), ok=False, error="deu ruim"),
    ]
    texto = gui.batch_summary(resultados)
    assert "1" in texto and "2" in texto
    assert "b.pdf" in texto
    assert "deu ruim" in texto


def test_batch_summary_all_ok_has_no_failure_list():
    from slidecut import core

    resultados = [core.BatchItemResult(source=Path("a.pdf"), ok=True, written=[Path("a1.pdf")])]
    texto = gui.batch_summary(resultados)
    assert "falh" not in texto.lower()


def test_batch_item_label_shows_position_and_name(tmp_path):
    texto = gui.batch_item_label(2, 5, tmp_path / "Aula 03.pptx")
    assert texto == "Arquivo 2 de 5: Aula 03.pptx"
