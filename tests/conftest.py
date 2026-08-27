"""Fixtures compartilhadas: geram PDFs sinteticos com paginas divisoras coloridas."""

from __future__ import annotations

import pymupdf
import pytest

from slidecut import office


@pytest.fixture(autouse=True)
def isolate_office(request, monkeypatch):
    """Impede que um teste abra o Microsoft Office de verdade sem querer.

    A conversao pelo Office e escolhida sozinha quando a maquina tem Office,
    entao qualquer teste de conversao acabaria disparando o PowerPoint — lento,
    e o resultado passaria a depender da maquina. Testes que precisam do Office
    real levam a marca `real_office`.
    """
    if "real_office" in request.keywords:
        return

    monkeypatch.setattr(office, "_progid_registered", lambda progid: False)

    def _refuse(progid):
        raise AssertionError(f"o teste tentou abrir o Office de verdade ({progid})")

    monkeypatch.setattr(office, "_dispatch", _refuse)

ORANGE = (0.69, 0.43, 0.01)
WHITE = (1.0, 1.0, 1.0)
PAGE_SIZE = (720, 405)


def _add_page(doc, fill, text=""):
    page = doc.new_page(width=PAGE_SIZE[0], height=PAGE_SIZE[1])
    page.draw_rect(page.rect, color=fill, fill=fill)
    if text:
        color = WHITE if sum(fill) < 1.8 else (0.0, 0.0, 0.0)
        page.insert_textbox(
            pymupdf.Rect(60, 140, 660, 320),
            text,
            fontsize=28,
            color=color,
            align=pymupdf.TEXT_ALIGN_CENTER,
        )
    return page


def build_pdf(path, spec):
    """spec: lista de (fill_rgb_0_1, texto). Grava e devolve o caminho."""
    doc = pymupdf.open()
    for fill, text in spec:
        _add_page(doc, fill, text)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def deck(tmp_path):
    """Baralho tipico: divisores laranja separando paginas de conteudo claras."""
    spec = [
        (ORANGE, "Capa\nProf. Fulano"),
        (ORANGE, "Conceito\nProf. Fulano"),
        (WHITE, "conteudo 1"),
        (WHITE, "conteudo 2"),
        (ORANGE, "Fontes\nProf. Fulano"),
        (WHITE, "conteudo 3"),
        (ORANGE, "Encerramento\nProf. Fulano"),
    ]
    return build_pdf(tmp_path / "deck.pdf", spec)


BLUE = (0.12, 0.29, 0.65)


@pytest.fixture
def deck_two_divider_colors(tmp_path):
    """Dois tons divisores no mesmo baralho: azul em tres paginas, laranja em duas.

    A deteccao automatica escolhe o azul, por ser o que mais se repete. Serve
    para provar que o slide matriz manda mais que a contagem.
    """
    spec = [
        (BLUE, "Bloco A"),
        (WHITE, "conteudo 1"),
        (ORANGE, "Bloco B"),
        (WHITE, "conteudo 2"),
        (BLUE, "Bloco C"),
        (WHITE, "conteudo 3"),
        (ORANGE, "Bloco D"),
        (BLUE, "Bloco E"),
    ]
    return build_pdf(tmp_path / "dois-tons.pdf", spec)


@pytest.fixture
def deck_no_dividers(tmp_path):
    spec = [(WHITE, f"pagina {i}") for i in range(4)]
    return build_pdf(tmp_path / "plain.pdf", spec)
