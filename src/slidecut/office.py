"""Conversao para PDF usando o Microsoft Office instalado, via automacao COM.

E o caminho preferido quando o Office existe na maquina: a renderizacao e feita
pelo proprio PowerPoint/Word/Excel, entao a fidelidade visual e exata — fontes,
layouts e elementos graficos saem como o autor viu. Tambem dispensa instalar o
LibreOffice, que sao uns 350 MB.

So funciona no Windows e so com o Office instalado; convert.py cai para o
LibreOffice quando isso nao vale.
"""

from __future__ import annotations

import contextlib
import gc
from pathlib import Path
from typing import Iterator

from .errors import ConversionError

POWERPOINT = "PowerPoint.Application"
WORD = "Word.Application"
EXCEL = "Excel.Application"

POWERPOINT_FORMATS = {".pptx", ".ppt", ".pps", ".ppsx", ".odp"}
WORD_FORMATS = {".docx", ".doc", ".odt", ".rtf", ".txt"}
EXCEL_FORMATS = {".xlsx", ".xls", ".ods", ".csv"}
"""Formatos Apple (.key, .pages, .numbers) ficam de fora: o Office nao os abre."""

PROGID_BY_SUFFIX = {
    **{suffix: POWERPOINT for suffix in POWERPOINT_FORMATS},
    **{suffix: WORD for suffix in WORD_FORMATS},
    **{suffix: EXCEL for suffix in EXCEL_FORMATS},
}

PPT_SAVE_AS_PDF = 32
WORD_FORMAT_PDF = 17
EXCEL_TYPE_PDF = 0


def can_convert(suffix: str) -> bool:
    """Diz se algum aplicativo do Office abre esse formato."""
    return suffix.lower() in PROGID_BY_SUFFIX


def _progid_registered(progid: str) -> bool:
    """Consulta o registro do Windows sem abrir o aplicativo.

    Chamar Dispatch so para testar disponibilidade abriria o Office inteiro.
    """
    try:
        import winreg
    except ImportError:  # fora do Windows
        return False

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid):
            return True
    except OSError:
        return False


def is_available(suffix: str) -> bool:
    """Diz se o Office desta maquina consegue converter esse formato."""
    progid = PROGID_BY_SUFFIX.get(suffix.lower())
    return progid is not None and _progid_registered(progid)


def _dispatch(progid: str):
    """Abre o aplicativo do Office. Isolado para os testes substituirem."""
    import win32com.client

    return win32com.client.DispatchEx(progid)


def _running_instance(progid: str):
    """Devolve a instancia do Office que o usuario ja tem aberta, ou None.

    O PowerPoint e de instancia unica: nao adianta pedir uma copia separada,
    qualquer conexao cai na mesma. Precisamos saber disso para nunca encerrar
    um aplicativo que ja estava aberto — seria fechar o trabalho do usuario.
    """
    try:
        import win32com.client
    except ImportError:
        return None

    try:
        return win32com.client.GetActiveObject(progid)
    except Exception:
        return None


@contextlib.contextmanager
def _com_initialised() -> Iterator[None]:
    """COM precisa ser inicializado em cada thread que o usa.

    A janela converte numa thread de trabalho; sem isto, o Dispatch falha ali.
    """
    try:
        import pythoncom
    except ImportError:
        yield
        return

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        # Os objetos COM do pywin32 caem em ciclos de referencia, entao o
        # contador sozinho nao os libera a tempo. Encerrar o COM com algum
        # deles ainda vivo derruba o processo com RPC_E_DISCONNECTED.
        gc.collect()
        pythoncom.CoUninitialize()


def _export_powerpoint(app, source: Path, target: Path, owns_app: bool) -> None:
    presentation = app.Presentations.Open(
        str(source), ReadOnly=True, Untitled=False, WithWindow=False
    )
    try:
        presentation.SaveAs(str(target), PPT_SAVE_AS_PDF)
    finally:
        presentation.Close()
        del presentation


def _export_word(app, source: Path, target: Path, owns_app: bool) -> None:
    if owns_app:
        # Mexer nisso numa instancia do usuario esconderia a janela dele.
        app.Visible = False
        app.DisplayAlerts = False
    document = app.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)
    try:
        document.SaveAs2(str(target), FileFormat=WORD_FORMAT_PDF)
    finally:
        document.Close(SaveChanges=0)
        del document


def _export_excel(app, source: Path, target: Path, owns_app: bool) -> None:
    if owns_app:
        app.Visible = False
        app.DisplayAlerts = False
    workbook = app.Workbooks.Open(str(source), ReadOnly=True, UpdateLinks=0)
    try:
        workbook.ExportAsFixedFormat(EXCEL_TYPE_PDF, str(target))
    finally:
        workbook.Close(SaveChanges=False)
        del workbook


EXPORTERS = {
    POWERPOINT: _export_powerpoint,
    WORD: _export_word,
    EXCEL: _export_excel,
}


def to_pdf(source: str | Path, workdir: str | Path) -> Path:
    """Converte usando o Office e devolve o PDF gerado.

    Levanta ConversionError se o formato nao for do Office ou se a automacao
    falhar — convert.py trata isso caindo para o LibreOffice.
    """
    source = Path(source)
    progid = PROGID_BY_SUFFIX.get(source.suffix.lower())
    if progid is None:
        raise ConversionError(f"o Office nao abre arquivos {source.suffix}")

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    target = workdir / f"{source.stem}.pdf"

    # Guarda so o texto do erro, nunca o objeto da excecao: o traceback dela
    # segura os quadros de pilha que referenciam o objeto COM, e ai o
    # CoUninitialize derruba o processo com RPC_E_DISCONNECTED.
    failure: str | None = None

    with _com_initialised():
        app = None
        owns_app = False
        try:
            app = _running_instance(progid)
            owns_app = app is None
            if app is None:
                app = _dispatch(progid)
            EXPORTERS[progid](app, source.resolve(), target, owns_app)
        except Exception as exc:
            failure = str(exc)
        finally:
            # So encerra o aplicativo se fomos nos que o abrimos. O PowerPoint
            # e de instancia unica: dar Quit numa instancia do usuario fecharia
            # a apresentacao dele, com o que nao estivesse salvo.
            if app is not None and owns_app:
                with contextlib.suppress(Exception):
                    app.Quit()
            # Solta a ultima referencia antes de encerrar o COM desta thread.
            app = None

    if failure is not None:
        raise ConversionError(f"o Office falhou ao converter {source.name}: {failure}")
    if not target.is_file():
        raise ConversionError(f"o Office nao gerou o PDF de {source.name}")
    return target
