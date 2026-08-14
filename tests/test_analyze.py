from __future__ import annotations

import pytest

from slidecut import analyze
from slidecut.errors import AnalysisError


def test_page_colors_returns_one_entry_per_page(deck):
    colors = analyze.page_colors(deck)
    assert len(colors) == 7
    assert all(0.0 <= c.coverage <= 1.0 for c in colors)


def test_page_colors_detects_flat_orange_fill(deck):
    colors = analyze.page_colors(deck)
    r, g, b = colors[1].rgb
    assert r > 150 and 80 < g < 140 and b < 60
    assert colors[1].coverage > 0.8


def test_find_dividers_locates_every_colored_page(deck):
    assert analyze.find_dividers(deck) == [0, 1, 4, 6]


def test_find_dividers_returns_empty_when_no_recurring_color(deck_no_dividers):
    assert analyze.find_dividers(deck_no_dividers) == []


def test_find_dividers_honours_explicit_color(deck):
    assert analyze.find_dividers(deck, color=(176, 110, 3)) == [0, 1, 4, 6]


def test_find_dividers_with_wrong_explicit_color_finds_nothing(deck):
    assert analyze.find_dividers(deck, color=(10, 200, 10)) == []


def test_parse_color_accepts_hex_forms():
    assert analyze.parse_color("#B06E03") == (176, 110, 3)
    assert analyze.parse_color("b06e03") == (176, 110, 3)


@pytest.mark.parametrize("bad", ["", "xyz", "#12345", "12345678"])
def test_parse_color_rejects_garbage(bad):
    with pytest.raises(ValueError):
        analyze.parse_color(bad)


def test_is_divider_candidate_rejects_neutral_light_pages():
    assert not analyze.is_divider_candidate((240, 240, 238), 0.95)


def test_is_divider_candidate_accepts_saturated_pages():
    assert analyze.is_divider_candidate((176, 110, 3), 0.9)


def test_is_divider_candidate_rejects_low_coverage():
    assert not analyze.is_divider_candidate((176, 110, 3), 0.2)


def test_is_divider_candidate_accepts_dark_neutral_pages():
    assert analyze.is_divider_candidate((20, 20, 22), 0.9)


def test_find_divider_color_groups_a_slowly_drifting_color():
    """Gradientes e compressao fazem a mesma cor variar entre paginas."""
    drift = [
        analyze.PageColor(0, (180, 110, 0), 0.9),
        analyze.PageColor(1, (195, 110, 0), 0.9),
        analyze.PageColor(2, (210, 110, 0), 0.9),
    ]
    assert analyze.find_divider_color(drift, tolerance=20) == (195, 110, 0)


def test_find_divider_color_keeps_distinct_colors_apart():
    mixed = [
        analyze.PageColor(0, (180, 110, 0), 0.9),
        analyze.PageColor(1, (182, 110, 0), 0.9),
        analyze.PageColor(2, (10, 40, 200), 0.9),
    ]
    assert analyze.find_divider_color(mixed, tolerance=20) == (181, 110, 0)


def test_page_colors_rejects_a_corrupt_pdf(tmp_path):
    broken = tmp_path / "quebrado.pdf"
    broken.write_bytes(b"nao sou um pdf")
    with pytest.raises(AnalysisError):
        analyze.page_colors(broken)
