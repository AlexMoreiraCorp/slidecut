from __future__ import annotations

import pymupdf
import pytest

from slidecut import layout


def test_one_per_sheet_keeps_the_page_count(deck, tmp_path):
    alvo = tmp_path / "igual.pdf"
    layout.group_pages(deck, alvo, per_sheet=1)
    with pymupdf.open(str(alvo)) as doc:
        assert doc.page_count == 7


def test_two_per_sheet_halves_the_sheets(deck, tmp_path):
    alvo = tmp_path / "duas.pdf"
    layout.group_pages(deck, alvo, per_sheet=2)
    with pymupdf.open(str(alvo)) as doc:
        assert doc.page_count == 4  # 7 paginas -> 4 folhas, a ultima com uma so


def test_three_per_sheet(deck, tmp_path):
    alvo = tmp_path / "tres.pdf"
    layout.group_pages(deck, alvo, per_sheet=3)
    with pymupdf.open(str(alvo)) as doc:
        assert doc.page_count == 3


def test_four_per_sheet(deck, tmp_path):
    alvo = tmp_path / "quatro.pdf"
    layout.group_pages(deck, alvo, per_sheet=4)
    with pymupdf.open(str(alvo)) as doc:
        assert doc.page_count == 2


def test_grouped_sheets_are_a4_portrait(deck, tmp_path):
    alvo = tmp_path / "a4.pdf"
    layout.group_pages(deck, alvo, per_sheet=2)
    with pymupdf.open(str(alvo)) as doc:
        rect = doc[0].rect
        assert abs(rect.width - 595) < 2
        assert abs(rect.height - 842) < 2
        assert rect.height > rect.width


def test_grouping_keeps_the_text_searchable(deck, tmp_path):
    """Agrupar nao pode virar imagem: o texto tem de continuar selecionavel."""
    alvo = tmp_path / "texto.pdf"
    layout.group_pages(deck, alvo, per_sheet=2)
    with pymupdf.open(str(alvo)) as doc:
        assert "Conceito" in doc[0].get_text()


def test_grouping_preserves_page_order(deck, tmp_path):
    alvo = tmp_path / "ordem.pdf"
    layout.group_pages(deck, alvo, per_sheet=2)
    with pymupdf.open(str(alvo)) as doc:
        primeira = doc[0].get_text()
        assert primeira.index("Capa") < primeira.index("Conceito")


@pytest.mark.parametrize("invalido", [0, -1, 5, 99])
def test_rejects_layouts_that_are_not_offered(deck, tmp_path, invalido):
    with pytest.raises(ValueError):
        layout.group_pages(deck, tmp_path / "x.pdf", per_sheet=invalido)


def test_sheet_count_matches_the_formula():
    assert layout.sheet_count(7, 1) == 7
    assert layout.sheet_count(7, 2) == 4
    assert layout.sheet_count(7, 3) == 3
    assert layout.sheet_count(7, 4) == 2
    assert layout.sheet_count(0, 2) == 0


def test_describe_layout_is_readable():
    assert layout.describe(1) == "uma página por folha"
    assert "2" in layout.describe(2)


def test_grouping_in_place_overwrites_the_same_file(deck):
    """Agrupar sobre o proprio arquivo e o caso normal ao pos-processar cortes."""
    import pymupdf

    layout.group_pages(deck, deck, per_sheet=2)
    with pymupdf.open(str(deck)) as doc:
        assert doc.page_count == 4


def test_grouping_in_place_leaves_no_temporary_behind(deck):
    layout.group_pages(deck, deck, per_sheet=2)
    restos = list(deck.parent.glob("*.tmp")) + list(deck.parent.glob("*~"))
    assert restos == []


def test_grouping_in_place_retries_a_transient_windows_lock(deck, monkeypatch):
    """WinError 5 passageiro (antivirus/indexador travando o arquivo recem-gravado)
    nao pode derrubar o agrupamento: poucas tentativas resolvem sozinhas."""
    tentativas = {"n": 0}
    original_replace = layout.os.replace

    def falha_duas_vezes(origem, destino):
        tentativas["n"] += 1
        if tentativas["n"] <= 2:
            raise PermissionError("[WinError 5] Acesso negado")
        return original_replace(origem, destino)

    monkeypatch.setattr(layout.os, "replace", falha_duas_vezes)
    monkeypatch.setattr(layout.time, "sleep", lambda _s: None)

    layout.group_pages(deck, deck, per_sheet=2)
    assert tentativas["n"] == 3


def test_grouping_in_place_gives_up_after_repeated_lock_failures(deck, monkeypatch):
    def sempre_falha(origem, destino):
        raise PermissionError("[WinError 5] Acesso negado")

    monkeypatch.setattr(layout.os, "replace", sempre_falha)
    monkeypatch.setattr(layout.time, "sleep", lambda _s: None)

    with pytest.raises(PermissionError):
        layout.group_pages(deck, deck, per_sheet=2)
