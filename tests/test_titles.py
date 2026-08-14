from __future__ import annotations

import pytest

from slidecut import titles


def test_clean_title_drops_speaker_line():
    assert titles.clean_title("Conceito\nProf. Rodrigo Vaslin") == "Conceito"


def test_clean_title_joins_wrapped_lines():
    raw = "Novo Codigo de \nProcesso\nCivil: Historia\nProfa. Ana"
    assert titles.clean_title(raw) == "Novo Codigo de Processo Civil: Historia"


def test_clean_title_returns_empty_for_blank_page():
    assert titles.clean_title("   \n\n ") == ""


def test_clean_title_caps_line_count():
    raw = "\n".join(f"linha {i}" for i in range(10))
    assert titles.clean_title(raw, max_lines=3) == "linha 0 linha 1 linha 2"


def test_safe_filename_strips_reserved_characters():
    assert titles.safe_filename('Art. 5º: "ampla/defesa"?') == "Art. 5º - ampla-defesa"


def test_safe_filename_collapses_whitespace():
    assert titles.safe_filename("Principio   da\tBoa-fe") == "Principio da Boa-fe"


def test_safe_filename_ascii_mode_removes_accents():
    assert titles.safe_filename("Princípio da Cooperação", ascii_only=True) == "Principio da Cooperacao"


def test_safe_filename_falls_back_when_empty():
    assert titles.safe_filename("???") == "Sem titulo"


def test_safe_filename_truncates_long_titles():
    assert len(titles.safe_filename("x" * 200)) <= 80


@pytest.mark.parametrize("reserved", ["CON", "nul", "LPT1"])
def test_safe_filename_escapes_windows_reserved_names(reserved):
    assert titles.safe_filename(reserved) != reserved


def test_safe_filename_glues_hyphen_that_pdf_split_from_its_word():
    assert titles.safe_filename("Principio da Boa -fe") == "Principio da Boa-fe"


def test_safe_filename_keeps_spaced_dash_between_words():
    assert titles.safe_filename("Parte 1 - Fontes") == "Parte 1 - Fontes"
