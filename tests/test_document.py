from __future__ import annotations

import pymupdf
import pytest

from slidecut.document import open_pdf
from slidecut.errors import AnalysisError


def test_open_pdf_yields_a_readable_document(deck):
    with open_pdf(deck) as doc:
        assert len(doc) == 7


def test_open_pdf_rejects_a_password_protected_file(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    protected = tmp_path / "trancado.pdf"
    doc.save(
        str(protected),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="segredo",
        owner_pw="segredo",
    )
    doc.close()

    with pytest.raises(AnalysisError, match="senha"):
        with open_pdf(protected):
            pass


def test_open_pdf_rejects_a_missing_file(tmp_path):
    with pytest.raises(AnalysisError):
        with open_pdf(tmp_path / "sumiu.pdf"):
            pass
