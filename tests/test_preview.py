from __future__ import annotations

from slidecut import preview

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_render_thumbnails_yields_one_png_per_page(deck):
    thumbs = list(preview.render_thumbnails(deck, width=120))
    assert len(thumbs) == 7
    assert [t.index for t in thumbs] == list(range(7))
    assert all(t.png.startswith(PNG_MAGIC) for t in thumbs)


def test_render_thumbnails_respects_requested_width(deck):
    narrow = next(iter(preview.render_thumbnails(deck, width=80)))
    wide = next(iter(preview.render_thumbnails(deck, width=200)))
    assert narrow.width < wide.width
    assert abs(narrow.width - 80) <= 2
    assert abs(wide.width - 200) <= 2


def test_thumbnail_carries_the_page_caption(deck):
    thumbs = list(preview.render_thumbnails(deck, width=100))
    assert thumbs[1].caption == "Conceito"
    assert thumbs[2].caption == "conteudo 1"


def test_caption_is_shortened_for_long_text():
    long_text = "palavra " * 40
    assert len(preview.page_caption(long_text, limit=30)) <= 30


def test_caption_of_a_blank_page_is_labelled():
    assert preview.page_caption("   ") == preview.BLANK_CAPTION


def test_thumbnail_carries_a_ready_to_use_filename(deck):
    thumbs = list(preview.render_thumbnails(deck, width=100))
    assert thumbs[1].title == "Conceito"
    assert thumbs[0].title == "Capa"


def test_thumbnail_title_of_a_blank_page_falls_back(tmp_path):
    from tests.conftest import WHITE, build_pdf

    src = build_pdf(tmp_path / "vazio.pdf", [(WHITE, "")])
    thumb = next(iter(preview.render_thumbnails(src, width=80)))
    assert thumb.title == "Sem titulo"


# ------------------------------------------------ pagina ampliada (inspetor)
def test_render_page_returns_a_single_page_at_the_asked_width(deck):
    grande = preview.render_page(deck, 1, width=420)
    assert grande.index == 1
    assert abs(grande.width - 420) <= 2
    assert grande.png.startswith(PNG_MAGIC)


def test_render_page_is_bigger_than_the_thumbnail_of_the_same_page(deck):
    pequena = next(iter(preview.render_thumbnails(deck, width=120)))
    grande = preview.render_page(deck, 0, width=420)
    assert grande.width > pequena.width


def test_render_page_carries_the_same_caption_as_the_thumbnail(deck):
    assert preview.render_page(deck, 1, width=300).caption == "Conceito"


def test_render_page_refuses_a_page_outside_the_document(deck):
    import pytest

    with pytest.raises(IndexError):
        preview.render_page(deck, 99)


def test_render_page_releases_the_pdf(deck):
    preview.render_page(deck, 0, width=200)
    deck.unlink()
    assert not deck.exists()


def test_abandoned_thumbnail_generator_releases_the_pdf(deck):
    """Se a montagem da grade falhar no meio, o PDF nao pode ficar travado."""
    thumbs = preview.render_thumbnails(deck, width=80)
    next(thumbs)
    thumbs.close()
    deck.unlink()
    assert not deck.exists()
