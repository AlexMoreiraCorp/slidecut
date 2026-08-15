from __future__ import annotations

from pathlib import Path

import pytest

from slidecut import convert
from slidecut.errors import ConversionError, UnsupportedFormat


def test_pdf_input_is_returned_untouched(deck, tmp_path):
    assert convert.to_pdf(deck, tmp_path) == deck


def test_unknown_extension_is_rejected(tmp_path):
    src = tmp_path / "arquivo.xyz"
    src.write_text("nada")
    with pytest.raises(UnsupportedFormat):
        convert.to_pdf(src, tmp_path)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        convert.to_pdf(tmp_path / "sumiu.pptx", tmp_path)


def test_office_input_is_converted_via_libreoffice(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    def fake_run(cmd, **kwargs):
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"%PDF-1.4\n")
        return convert.subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))
    monkeypatch.setattr(convert.subprocess, "run", fake_run)

    assert convert.to_pdf(src, tmp_path / "work") == produced


def test_conversion_failure_is_reported(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")

    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))
    monkeypatch.setattr(
        convert.subprocess,
        "run",
        lambda cmd, **kw: convert.subprocess.CompletedProcess(cmd, 1, b"", b"boom"),
    )

    with pytest.raises(ConversionError):
        convert.to_pdf(src, tmp_path / "work")


def test_missing_libreoffice_is_reported(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    monkeypatch.setattr(convert, "find_soffice", lambda: None)
    with pytest.raises(ConversionError, match="LibreOffice"):
        convert.to_pdf(src, tmp_path / "work")


def test_supported_inputs_cover_common_slide_formats():
    for ext in (".pptx", ".ppt", ".odp", ".key", ".docx", ".odt", ".pdf"):
        assert ext in convert.SUPPORTED_INPUTS


def test_find_soffice_prefers_environment_override(tmp_path, monkeypatch):
    fake = tmp_path / "soffice.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv("SLIDECUT_SOFFICE", str(fake))
    assert convert.find_soffice() == fake


def test_find_soffice_ignores_override_that_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("SLIDECUT_SOFFICE", str(tmp_path / "inexistente.exe"))
    monkeypatch.setattr(convert.shutil, "which", lambda name: None)
    monkeypatch.setattr(convert, "SOFFICE_CANDIDATES", ())
    assert convert.find_soffice() is None


def test_find_soffice_uses_path_lookup(monkeypatch):
    monkeypatch.delenv("SLIDECUT_SOFFICE", raising=False)
    monkeypatch.setattr(convert.shutil, "which", lambda name: "/usr/bin/soffice")
    assert convert.find_soffice() == Path("/usr/bin/soffice")


def test_find_soffice_falls_back_to_known_install_paths(tmp_path, monkeypatch):
    fake = tmp_path / "soffice"
    fake.write_bytes(b"")
    monkeypatch.delenv("SLIDECUT_SOFFICE", raising=False)
    monkeypatch.setattr(convert.shutil, "which", lambda name: None)
    monkeypatch.setattr(convert, "SOFFICE_CANDIDATES", (str(fake),))
    assert convert.find_soffice() == fake


def test_libreoffice_is_installed_on_this_machine():
    assert convert.find_soffice() is not None


def test_libreoffice_timeout_is_reported_as_conversion_error(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")

    def hang(cmd, **kwargs):
        raise convert.subprocess.TimeoutExpired(cmd, convert.CONVERSION_TIMEOUT)

    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))
    monkeypatch.setattr(convert.subprocess, "run", hang)

    with pytest.raises(ConversionError, match="tempo"):
        convert.to_pdf(src, tmp_path / "work")


def test_non_executable_override_is_ignored(tmp_path, monkeypatch):
    fake = tmp_path / "soffice.txt"
    fake.write_text("nao sou executavel")
    monkeypatch.setenv("SLIDECUT_SOFFICE", str(fake))
    monkeypatch.setattr(convert.os, "access", lambda path, mode: False)
    monkeypatch.setattr(convert.shutil, "which", lambda name: None)
    monkeypatch.setattr(convert, "SOFFICE_CANDIDATES", ())
    assert convert.find_soffice() is None


def test_needs_conversion_is_false_for_pdf(tmp_path):
    assert not convert.needs_conversion(tmp_path / "ja.pdf")
    assert not convert.needs_conversion(tmp_path / "MAIUSCULO.PDF")


def test_needs_conversion_is_true_for_slides_and_documents(tmp_path):
    assert convert.needs_conversion(tmp_path / "aula.pptx")
    assert convert.needs_conversion(tmp_path / "texto.docx")


def test_office_is_preferred_when_available(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: True)
    monkeypatch.setattr(convert.office, "to_pdf", lambda s, w: produced)
    monkeypatch.setattr(
        convert, "find_soffice", lambda: pytest.fail("nao devia chamar o LibreOffice")
    )

    assert convert.to_pdf(src, tmp_path / "work") == produced


def test_libreoffice_takes_over_when_office_is_missing(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: False)
    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))

    def fake_run(cmd, **kwargs):
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"%PDF-1.4\n")
        return convert.subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(convert.subprocess, "run", fake_run)
    assert convert.to_pdf(src, tmp_path / "work") == produced


def test_libreoffice_takes_over_when_office_fails(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    def office_boom(source, workdir):
        raise ConversionError("PowerPoint travou")

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: True)
    monkeypatch.setattr(convert.office, "to_pdf", office_boom)
    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))

    def fake_run(cmd, **kwargs):
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"%PDF-1.4\n")
        return convert.subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(convert.subprocess, "run", fake_run)
    assert convert.to_pdf(src, tmp_path / "work") == produced


def test_error_mentions_both_converters_when_neither_exists(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: False)
    monkeypatch.setattr(convert, "find_soffice", lambda: None)

    with pytest.raises(ConversionError) as excinfo:
        convert.to_pdf(src, tmp_path / "work")
    assert "Office" in str(excinfo.value)
    assert "LibreOffice" in str(excinfo.value)


def test_a_converter_is_reported_through_the_progress_callback(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: True)
    monkeypatch.setattr(convert.office, "to_pdf", lambda s, w: produced)

    messages = []
    convert.to_pdf(src, tmp_path / "work", on_progress=messages.append)
    assert any("Office" in m for m in messages)


def test_the_fallback_message_stays_readable_instead_of_dumping_the_com_error(
    tmp_path, monkeypatch
):
    """O erro cru do COM assusta e nao ajuda quem esta olhando a tela."""
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    produced = tmp_path / "work" / "aula.pdf"

    def office_boom(source, workdir):
        raise ConversionError(
            "o Office falhou ao converter aula.pptx: (-2147352567, 'Exceção.', "
            "(0, 'Microsoft PowerPoint', 'Presentation.SaveAs : Ocorreu um erro', '', 0, -1))"
        )

    monkeypatch.setattr(convert.office, "is_available", lambda suffix: True)
    monkeypatch.setattr(convert.office, "to_pdf", office_boom)
    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))

    def fake_run(cmd, **kwargs):
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"%PDF-1.4\n")
        return convert.subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(convert.subprocess, "run", fake_run)

    messages = []
    convert.to_pdf(src, tmp_path / "work", on_progress=messages.append)
    joined = " ".join(messages)
    assert "LibreOffice" in joined
    assert "-2147352567" not in joined
    assert "SaveAs" not in joined


def test_converter_status_names_office_when_present(monkeypatch):
    monkeypatch.setattr(convert.office, "is_available", lambda suffix: True)
    ok, texto = convert.converter_status(".pptx")
    assert ok and "Microsoft Office" in texto


def test_converter_status_names_libreoffice_as_the_fallback(monkeypatch):
    monkeypatch.setattr(convert.office, "is_available", lambda suffix: False)
    monkeypatch.setattr(convert, "find_soffice", lambda: Path("soffice"))
    ok, texto = convert.converter_status(".pptx")
    assert ok and "LibreOffice" in texto


def test_converter_status_warns_when_nothing_can_convert(monkeypatch):
    monkeypatch.setattr(convert.office, "is_available", lambda suffix: False)
    monkeypatch.setattr(convert, "find_soffice", lambda: None)
    ok, texto = convert.converter_status(".pptx")
    assert not ok and "PDF" in texto
