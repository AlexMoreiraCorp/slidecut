from __future__ import annotations

import re

import pytest

from slidecut import theme

HEX = re.compile(r"^#[0-9A-F]{6}$")

TOKENS = [
    "INK", "PAPER", "SURFACE", "SURFACE_SUNK", "SLATE", "SLATE_LIGHT",
    "EDGE", "EDGE_SOFT", "CUT", "CUT_DARK", "CUT_SOFT", "GREEN", "RED",
]


@pytest.mark.parametrize("name", TOKENS)
def test_every_colour_token_is_a_valid_hex(name):
    assert HEX.match(getattr(theme, name)), f"{name} nao e hexadecimal valido"


def test_pick_family_prefers_the_first_available():
    available = {"Segoe UI", "Arial"}
    assert theme.pick_family(("Bahnschrift", "Segoe UI", "Arial"), available) == "Segoe UI"


def test_pick_family_takes_the_first_choice_when_present():
    available = {"Bahnschrift", "Segoe UI"}
    assert theme.pick_family(("Bahnschrift", "Segoe UI"), available) == "Bahnschrift"


def test_pick_family_never_returns_nothing():
    """Sem nenhuma das fontes instaladas, ainda tem de sair um nome utilizavel."""
    assert theme.pick_family(("Bahnschrift", "Segoe UI", "Helvetica"), set()) == "Helvetica"


def test_cut_colour_is_distinct_from_every_neutral():
    neutrals = {theme.INK, theme.PAPER, theme.SURFACE, theme.SLATE, theme.EDGE}
    assert theme.CUT not in neutrals
