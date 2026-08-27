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


def test_cut_at_wraps_every_name_with_the_prefix_and_suffix(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(
        doc, dividers=[0, 4], outdir=tmp_path / "out", prefix="Aula 02", suffix="rev1"
    )
    assert [p.name for p in result.written] == [
        "01 - Aula 02 Capa rev1.pdf",
        "02 - Aula 02 Fontes rev1.pdf",
    ]


def test_cut_at_keeps_the_prefix_around_a_title_the_user_typed(deck, tmp_path):
    """Item 2 do pedido: editar o titulo nao pode derrubar o prefixo escolhido."""
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(
        doc, dividers=[0], outdir=tmp_path / "out",
        custom_titles={0: "Meu nome"}, prefix="Aula 02", suffix="rev1",
    )
    assert result.written[0].name == "01 - Aula 02 Meu nome rev1.pdf"


def test_cut_at_can_write_files_without_the_leading_number(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(
        doc, dividers=[0, 4], outdir=tmp_path / "out",
        prefix="Aula 02", numbered=False,
    )
    assert [p.name for p in result.written] == [
        "Aula 02 Capa.pdf", "Aula 02 Fontes.pdf",
    ]


def test_cut_at_without_prefix_or_suffix_names_files_as_before(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[0, 4], outdir=tmp_path / "out")
    assert [p.name for p in result.written] == ["01 - Capa.pdf", "02 - Fontes.pdf"]


def test_cut_at_leaves_out_the_pages_the_user_unchecked(deck, tmp_path):
    """Item 6: a pagina continua no documento de origem, so nao entra no corte."""
    import pymupdf

    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[0], outdir=tmp_path / "out", excluded_pages={2, 3})
    with pymupdf.open(str(result.written[0])) as saida:
        assert saida.page_count == 5
    with pymupdf.open(str(deck)) as origem:
        assert origem.page_count == 7


def test_cut_at_refuses_to_leave_the_selection_with_no_page_at_all(deck, tmp_path):
    doc = core.prepare(deck, workdir=tmp_path / "work")
    with pytest.raises(NoDividerFound):
        core.cut_at(
            doc, dividers=[0], outdir=tmp_path / "out", excluded_pages=set(range(7))
        )


def test_process_can_skip_numbering_the_output_files(deck, tmp_path):
    result = core.process(
        deck, outdir=tmp_path / "out", prefix="Aula 02", numbered=False
    )
    assert result.written[0].name == "Aula 02 Capa.pdf"


def test_process_passes_the_prefix_and_suffix_down_to_the_file_names(deck, tmp_path):
    result = core.process(deck, outdir=tmp_path / "out", prefix="Aula 02", suffix="rev1")
    assert result.written[0].name == "01 - Aula 02 Capa rev1.pdf"


def test_process_batch_names_every_file_with_the_same_prefix(deck, tmp_path):
    outros = tmp_path / "outro.pdf"
    outros.write_bytes(deck.read_bytes())
    resultados = core.process_batch(
        [deck, outros], outdir=tmp_path / "lote", prefix="Turma A"
    )
    assert all(r.ok for r in resultados)
    gerados = [p.name for r in resultados for p in r.written]
    assert all("Turma A" in nome for nome in gerados)


def test_prepare_uses_the_matrix_page_tone_instead_of_the_most_repeated_one(
    deck_two_divider_colors, tmp_path
):
    """Item 3: o slide matriz manda no padrao de corte."""
    doc = core.prepare(deck_two_divider_colors, workdir=tmp_path / "work", matrix_page=2)
    assert doc.suggested_dividers == [2, 6]


def test_prepare_without_a_matrix_page_keeps_detecting_on_its_own(
    deck_two_divider_colors, tmp_path
):
    doc = core.prepare(deck_two_divider_colors, workdir=tmp_path / "work")
    assert doc.suggested_dividers == [0, 4, 7]


def test_cut_at_groups_pages_per_sheet_when_asked(deck, tmp_path):
    import pymupdf

    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[0], outdir=tmp_path / "out", per_sheet=2)
    with pymupdf.open(str(result.written[0])) as saida:
        assert saida.page_count == 4  # 7 paginas em folhas de 2


def test_cut_at_keeps_one_page_per_sheet_by_default(deck, tmp_path):
    import pymupdf

    doc = core.prepare(deck, workdir=tmp_path / "work")
    result = core.cut_at(doc, dividers=[0], outdir=tmp_path / "out")
    with pymupdf.open(str(result.written[0])) as saida:
        assert saida.page_count == 7


def test_convert_document_produces_a_pdf(deck, tmp_path):
    saida = core.convert_document(deck, tmp_path / "out", to="pdf")
    assert saida.suffix == ".pdf"
    assert saida.is_file()


def test_convert_document_groups_pages(deck, tmp_path):
    import pymupdf

    saida = core.convert_document(deck, tmp_path / "out", to="pdf", per_sheet=4)
    with pymupdf.open(str(saida)) as d:
        assert d.page_count == 2


def test_convert_document_produces_a_docx(deck, tmp_path):
    saida = core.convert_document(deck, tmp_path / "out", to="docx")
    assert saida.suffix == ".docx"
    assert saida.read_bytes()[:2] == b"PK"


def test_convert_document_rejects_an_unknown_target(deck, tmp_path):
    with pytest.raises(ValueError):
        core.convert_document(deck, tmp_path / "out", to="pptx")


def test_process_batch_cuts_every_file(deck, deck_no_dividers, tmp_path):
    entradas = [deck, deck]  # dois arquivos com o mesmo padrao de cor
    resultados = core.process_batch(entradas, outdir=tmp_path / "out")
    assert len(resultados) == 2
    assert all(r.ok for r in resultados)
    assert len(list((tmp_path / "out" / deck.stem).glob("*.pdf"))) == 4


def test_process_batch_keeps_going_after_one_file_fails(deck, deck_no_dividers, tmp_path):
    entradas = [deck, deck_no_dividers]
    resultados = core.process_batch(entradas, outdir=tmp_path / "out")
    assert resultados[0].ok
    assert not resultados[1].ok
    assert resultados[1].error is not None


def test_process_batch_reports_progress_per_file(deck, tmp_path):
    mensagens = []
    core.process_batch([deck, deck], outdir=tmp_path / "out",
                       on_progress=lambda msg: mensagens.append(msg))
    assert any(deck.name in m for m in mensagens)


def test_process_batch_separates_each_file_into_its_own_subfolder(deck, tmp_path):
    core.process_batch([deck], outdir=tmp_path / "out")
    assert (tmp_path / "out" / deck.stem).is_dir()


def test_convert_batch_converts_every_file_to_pdf(deck, tmp_path):
    from tests.conftest import ORANGE, WHITE, build_pdf

    outro = build_pdf(tmp_path / "outro.pdf", [(ORANGE, "Tema"), (WHITE, "x")])
    resultados = core.convert_batch([deck, outro], outdir=tmp_path / "out", to="pdf")
    assert len(resultados) == 2
    assert all(r.ok for r in resultados)
    assert (tmp_path / "out" / f"{deck.stem}.pdf").is_file()
    assert (tmp_path / "out" / "outro.pdf").is_file()


def test_convert_batch_keeps_going_after_one_file_fails(deck, tmp_path):
    ruim = tmp_path / "quebrado.pdf"
    ruim.write_bytes(b"nao sou pdf")
    resultados = core.convert_batch([deck, ruim], outdir=tmp_path / "out", to="pdf")
    assert resultados[0].ok
    assert not resultados[1].ok


def test_convert_batch_applies_the_same_layout_to_all(deck, tmp_path):
    import pymupdf

    resultados = core.convert_batch([deck], outdir=tmp_path / "out", to="pdf", per_sheet=4)
    with pymupdf.open(str(resultados[0].output)) as d:
        assert d.page_count == 2


def test_convert_batch_detects_name_collisions_instead_of_overwriting(tmp_path):
    """Duas entradas de nomes iguais em pastas diferentes nao podem se apagar."""
    from tests.conftest import ORANGE, WHITE, build_pdf

    pasta_a = tmp_path / "turma_a"
    pasta_b = tmp_path / "turma_b"
    pasta_a.mkdir()
    pasta_b.mkdir()
    um = build_pdf(pasta_a / "aula.pdf", [(ORANGE, "Um"), (WHITE, "x")])
    dois = build_pdf(pasta_b / "aula.pdf", [(ORANGE, "Dois"), (WHITE, "y")])

    resultados = core.convert_batch([um, dois], outdir=tmp_path / "out", to="pdf")

    assert resultados[0].ok
    assert not resultados[1].ok
    assert "aula.pdf" in resultados[1].error
    assert (tmp_path / "out" / "aula.pdf").is_file()


def test_process_batch_survives_a_source_path_that_cannot_be_resolved(deck, tmp_path):
    """Um item ruim na lista nao pode derrubar o laco inteiro."""
    entradas = [deck, "\x00caminho-invalido"]
    resultados = core.process_batch(entradas, outdir=tmp_path / "out")
    assert len(resultados) == 2
    assert resultados[0].ok
    assert not resultados[1].ok


def test_process_batch_reports_structured_item_progress(deck, tmp_path):
    """O indice do lote nao pode depender de parsing de texto: canal proprio."""
    eventos = []
    core.process_batch(
        [deck, deck], outdir=tmp_path / "out",
        on_item=lambda index, total, source: eventos.append((index, total, source.name)),
    )
    assert eventos == [(1, 2, deck.name), (2, 2, deck.name)]


def test_convert_batch_reports_structured_item_progress(deck, tmp_path):
    eventos = []
    core.convert_batch(
        [deck], outdir=tmp_path / "out", to="pdf",
        on_item=lambda index, total, source: eventos.append((index, total, source.name)),
    )
    assert eventos == [(1, 1, deck.name)]


def test_batch_item_progress_fires_even_when_the_item_fails(deck_no_dividers, tmp_path):
    eventos = []
    core.process_batch(
        [deck_no_dividers], outdir=tmp_path / "out",
        on_item=lambda index, total, source: eventos.append(index),
    )
    assert eventos == [1]
