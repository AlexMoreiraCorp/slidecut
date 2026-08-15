from __future__ import annotations

import pytest

from slidecut import docx as docx_module
from slidecut.errors import ConversionError


def test_to_docx_produces_an_editable_document(deck, tmp_path):
    alvo = docx_module.pdf_to_docx(deck, tmp_path / "saida.docx")
    assert alvo.is_file()
    assert alvo.read_bytes()[:2] == b"PK"  # docx e um zip


def test_to_docx_keeps_the_text(deck, tmp_path):
    from docx import Document

    alvo = docx_module.pdf_to_docx(deck, tmp_path / "texto.docx")
    texto = " ".join(p.text for p in Document(str(alvo)).paragraphs)
    assert "Conceito" in texto


def test_to_docx_creates_the_output_folder(deck, tmp_path):
    alvo = docx_module.pdf_to_docx(deck, tmp_path / "nova" / "pasta" / "x.docx")
    assert alvo.is_file()


def test_to_docx_rejects_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        docx_module.pdf_to_docx(tmp_path / "sumiu.pdf", tmp_path / "x.docx")


def test_to_docx_reports_a_broken_pdf(tmp_path):
    ruim = tmp_path / "quebrado.pdf"
    ruim.write_bytes(b"nao sou pdf")
    with pytest.raises(ConversionError):
        docx_module.pdf_to_docx(ruim, tmp_path / "x.docx")


def test_docx_name_for_derives_from_the_pdf(tmp_path):
    assert docx_module.docx_name_for(tmp_path / "Aula 01.pdf").name == "Aula 01.docx"
