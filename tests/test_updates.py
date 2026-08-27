from __future__ import annotations

import pytest

from slidecut import updates


# ------------------------------------------------------ leitura da versao
def test_parse_version_reads_the_string_from_the_init_file():
    texto = '"""slidecut"""\n\n__version__ = "0.10.4"\n\n__all__ = ["__version__"]\n'
    assert updates.parse_version(texto) == "0.10.4"


def test_parse_version_returns_none_when_nothing_matches():
    assert updates.parse_version("arquivo sem versao nenhuma") is None


# ------------------------------------------------------- comparar versoes
def test_is_newer_detects_a_higher_patch():
    assert updates.is_newer("0.10.3", "0.10.4") is True


def test_is_newer_detects_a_higher_minor_even_with_lower_patch():
    assert updates.is_newer("0.10.9", "0.11.0") is True


def test_is_newer_is_false_for_the_same_version():
    assert updates.is_newer("0.10.3", "0.10.3") is False


def test_is_newer_is_false_when_remote_is_older():
    assert updates.is_newer("0.10.3", "0.9.9") is False


def test_is_newer_tolerates_a_leading_v():
    assert updates.is_newer("0.10.3", "v0.10.4") is True


def test_is_newer_treats_garbage_as_not_newer():
    """Uma resposta inesperada nao pode acender um alarme falso de atualizacao."""
    assert updates.is_newer("0.10.3", "isso nao e versao nenhuma") is False


# -------------------------------------------------- verificacao ponta a ponta
def test_check_for_update_reports_a_newer_version_available():
    resultado = updates.check_for_update("0.10.3", fetch=lambda url: '__version__ = "0.10.4"')
    assert resultado is not None
    assert resultado.version == "0.10.4"
    assert resultado.url == updates.RELEASES_URL


def test_check_for_update_is_none_when_already_up_to_date():
    resultado = updates.check_for_update("0.10.4", fetch=lambda url: '__version__ = "0.10.4"')
    assert resultado is None


def test_check_for_update_is_none_when_the_network_fails():
    """Sem internet, ou GitHub fora do ar: o app segue normal, sem travar nem avisar errado."""
    def falha(_url):
        raise OSError("sem rede")

    assert updates.check_for_update("0.10.3", fetch=falha) is None


def test_check_for_update_is_none_when_the_response_is_unparseable():
    resultado = updates.check_for_update("0.10.3", fetch=lambda url: "pagina de erro do github")
    assert resultado is None


def test_check_for_update_never_raises_even_on_a_surprising_error():
    def explode(_url):
        raise ValueError("qualquer coisa inesperada")

    assert updates.check_for_update("0.10.3", fetch=explode) is None
