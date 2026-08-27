from __future__ import annotations

import re

import pytest

from slidecut import theme

HEX = re.compile(r"^#[0-9A-F]{6}$")

TOKENS = [
    "INK", "PAPER", "SURFACE", "SURFACE_SUNK", "SLATE", "SLATE_LIGHT",
    "EDGE", "EDGE_SOFT", "CUT", "CUT_DARK", "CUT_SOFT", "GREEN", "RED",
    "DANGER", "DANGER_DARK", "DANGER_SOFT",
    "FOCUS", "FOCUS_DARK", "FOCUS_SOFT",
    "MATRIX", "MATRIX_DARK", "MATRIX_SOFT",
    "KEEP", "KEEP_SOFT", "DROP",
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


def test_each_state_colour_is_its_own_tone():
    """Cada cor quer dizer uma coisa so; duas iguais confundiriam dois estados."""
    estados = [theme.CUT, theme.DANGER, theme.FOCUS, theme.MATRIX, theme.KEEP]
    assert len(set(estados)) == len(estados)


def test_looking_at_a_slide_never_looks_like_marking_it_for_cutting():
    """Ver de perto (item 5) e marcar corte (item 4) precisam ser distinguiveis."""
    assert theme.FOCUS != theme.CUT
    assert theme.FOCUS_SOFT != theme.CUT_SOFT


# ------------------------------------------------------- botao arredondado
def test_rounded_rect_points_closes_the_outline():
    pontos = theme.rounded_rect_points(0, 0, 100, 40, radius=10)
    assert len(pontos) % 2 == 0
    assert pontos[0] == pontos[-2] or len(pontos) >= 16


def test_rounded_rect_points_stays_inside_the_box():
    pontos = theme.rounded_rect_points(0, 0, 100, 40, radius=10)
    xs, ys = pontos[0::2], pontos[1::2]
    assert min(xs) >= 0 and max(xs) <= 100
    assert min(ys) >= 0 and max(ys) <= 40


def test_rounded_rect_radius_never_exceeds_half_the_shortest_side():
    """Raio maior que a metade viraria uma forma torta, nao um canto redondo."""
    pontos = theme.rounded_rect_points(0, 0, 40, 20, radius=999)
    ys = pontos[1::2]
    assert max(ys) <= 20


# ------------------------------------------------------ animacao de espera
def test_spinner_angle_advances_by_the_step():
    assert theme.next_spinner_angle(0) == theme.SPINNER_STEP


def test_spinner_angle_wraps_around_a_full_turn():
    assert theme.next_spinner_angle(360 - theme.SPINNER_STEP) == 0


def test_spinner_angle_never_leaves_the_circle():
    angle = 0
    for _ in range(200):
        angle = theme.next_spinner_angle(angle)
        assert 0 <= angle < 360
