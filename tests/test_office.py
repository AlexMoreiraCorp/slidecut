from __future__ import annotations

from pathlib import Path

import pytest

from slidecut import office
from slidecut.errors import ConversionError


class FakePresentations:
    def __init__(self, produced: Path):
        self.produced = produced

    def Open(self, path, ReadOnly=True, Untitled=False, WithWindow=False):  # noqa: N803
        return FakeDocument(self.produced)


class FakeDocument:
    def __init__(self, produced: Path):
        self.produced = produced
        self.closed = False

    def SaveAs(self, path, fmt):  # noqa: N802, N803
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"%PDF-1.7\n")

    def Close(self, *args, **kwargs):  # noqa: N802
        self.closed = True


class FakeDocuments:
    def __init__(self, produced: Path):
        self.produced = produced

    def Open(self, path, ReadOnly=True, AddToRecentFiles=False):  # noqa: N803
        return FakeWordDocument(self.produced)


class FakeWordDocument(FakeDocument):
    def SaveAs2(self, path, FileFormat=None):  # noqa: N802, N803
        self.SaveAs(path, FileFormat)


class FakeWordApp:
    def __init__(self, produced: Path):
        self.Documents = FakeDocuments(produced)
        self.quit_called = False
        self.Visible = True
        self.DisplayAlerts = True

    def Quit(self):  # noqa: N802
        self.quit_called = True


class FakeApp:
    def __init__(self, produced: Path):
        self.Presentations = FakePresentations(produced)
        self.quit_called = False
        self.Visible = True
        self.DisplayAlerts = True

    def Quit(self):  # noqa: N802
        self.quit_called = True


def test_can_convert_recognises_slide_and_text_formats():
    assert office.can_convert(".pptx")
    assert office.can_convert(".docx")
    assert office.can_convert(".xlsx")


def test_can_convert_rejects_formats_office_cannot_open():
    assert not office.can_convert(".key")
    assert not office.can_convert(".pages")
    assert not office.can_convert(".pdf")


def test_can_convert_is_case_insensitive():
    assert office.can_convert(".PPTX")


def test_to_pdf_drives_powerpoint_and_returns_the_pdf(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    workdir = tmp_path / "work"
    app = FakeApp(workdir / "aula.pdf")

    monkeypatch.setattr(office, "_dispatch", lambda progid: app)

    produced = office.to_pdf(src, workdir)
    assert produced == workdir / "aula.pdf"
    assert produced.read_bytes().startswith(b"%PDF")
    assert app.quit_called


def test_to_pdf_rejects_a_format_office_cannot_open(tmp_path):
    src = tmp_path / "slides.key"
    src.write_bytes(b"fake")
    with pytest.raises(ConversionError, match="Office"):
        office.to_pdf(src, tmp_path / "work")


def test_to_pdf_reports_a_com_failure_as_conversion_error(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")

    def boom(progid):
        raise OSError("COM nao respondeu")

    monkeypatch.setattr(office, "_dispatch", boom)
    with pytest.raises(ConversionError):
        office.to_pdf(src, tmp_path / "work")


def test_to_pdf_quits_the_app_even_when_saving_fails(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    app = FakeApp(tmp_path / "nunca.pdf")

    def explode(*_args, **_kwargs):
        raise RuntimeError("arquivo corrompido")

    app.Presentations.Open = explode
    monkeypatch.setattr(office, "_dispatch", lambda progid: app)

    with pytest.raises(ConversionError):
        office.to_pdf(src, tmp_path / "work")
    assert app.quit_called


def test_is_available_is_false_when_progid_is_not_registered(monkeypatch):
    monkeypatch.setattr(office, "_progid_registered", lambda progid: False)
    assert not office.is_available(".pptx")


def test_is_available_is_true_when_progid_is_registered(monkeypatch):
    monkeypatch.setattr(office, "_progid_registered", lambda progid: True)
    assert office.is_available(".pptx")


@pytest.mark.real_office
def test_powerpoint_is_registered_on_this_machine():
    """Esta maquina tem Office; garante que a deteccao real funciona."""
    assert office.is_available(".pptx")


def test_an_office_the_user_already_had_open_is_never_quit(tmp_path, monkeypatch):
    """Dar Quit numa instancia do usuario fecharia o trabalho nao salvo dele."""
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    workdir = tmp_path / "work"
    app = FakeApp(workdir / "aula.pdf")

    monkeypatch.setattr(office, "_running_instance", lambda progid: app)
    monkeypatch.setattr(
        office, "_dispatch", lambda progid: pytest.fail("nao devia abrir outra instancia")
    )

    office.to_pdf(src, workdir)
    assert not app.quit_called


def test_an_office_we_started_is_quit(tmp_path, monkeypatch):
    src = tmp_path / "aula.pptx"
    src.write_bytes(b"fake")
    workdir = tmp_path / "work"
    app = FakeApp(workdir / "aula.pdf")

    monkeypatch.setattr(office, "_running_instance", lambda progid: None)
    monkeypatch.setattr(office, "_dispatch", lambda progid: app)

    office.to_pdf(src, workdir)
    assert app.quit_called


def test_visibility_of_a_users_word_is_left_alone(tmp_path, monkeypatch):
    """Esconder a janela de um Word aberto tiraria o documento da frente dele."""
    src = tmp_path / "texto.docx"
    src.write_bytes(b"fake")
    app = FakeWordApp(tmp_path / "work" / "texto.pdf")

    monkeypatch.setattr(office, "_running_instance", lambda progid: app)
    office.to_pdf(src, tmp_path / "work")

    assert app.Visible is True


def test_a_word_we_started_is_kept_hidden(tmp_path, monkeypatch):
    src = tmp_path / "texto.docx"
    src.write_bytes(b"fake")
    app = FakeWordApp(tmp_path / "work" / "texto.pdf")

    monkeypatch.setattr(office, "_running_instance", lambda progid: None)
    monkeypatch.setattr(office, "_dispatch", lambda progid: app)
    office.to_pdf(src, tmp_path / "work")

    assert app.Visible is False
