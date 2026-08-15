"""Conversao de qualquer formato suportado para PDF, via LibreOffice headless."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from . import office
from .errors import ConversionError, UnsupportedFormat

ProgressCallback = Callable[[str], None]


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)



SLIDE_FORMATS = {".pptx", ".ppt", ".odp", ".key", ".pps", ".ppsx", ".fodp", ".otp"}
TEXT_FORMATS = {".docx", ".doc", ".odt", ".rtf", ".txt", ".fodt", ".ott", ".pages"}
SHEET_FORMATS = {".xlsx", ".xls", ".ods", ".csv", ".numbers"}
SUPPORTED_INPUTS = {".pdf"} | SLIDE_FORMATS | TEXT_FORMATS | SHEET_FORMATS

CONVERSION_TIMEOUT = 300
"""Decks grandes podem levar minutos; acima disso e travamento."""

SOFFICE_CANDIDATES = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
)


def find_soffice() -> Path | None:
    """Localiza o executavel do LibreOffice no PATH ou nos caminhos usuais."""
    override = os.environ.get("SLIDECUT_SOFFICE")
    if override and Path(override).is_file() and os.access(override, os.X_OK):
        return Path(override)

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)

    for candidate in SOFFICE_CANDIDATES:
        if Path(candidate).exists():
            return Path(candidate)
    return None


def needs_conversion(source: str | Path) -> bool:
    """Diz se o arquivo precisa ser convertido antes do corte."""
    return Path(source).suffix.lower() != ".pdf"


def available_converter(suffix: str) -> str | None:
    """Nome do conversor que daria conta desse formato nesta maquina."""
    if office.is_available(suffix):
        return "Microsoft Office"
    if find_soffice() is not None:
        return "LibreOffice"
    return None


def converter_status(suffix: str = ".pptx") -> tuple[bool, str, str | None]:
    """(tem conversor, frase pronta, aviso) para a tela de abertura.

    O aviso existe porque os dois conversores se completam: ha arquivos que o
    PowerPoint abre e desenha mas se recusa a exportar, e so o LibreOffice da
    conta deles. Ter apenas um dos dois deixa um ponto cego.
    """
    name = available_converter(suffix)
    if name == "Microsoft Office":
        warning = None
        if find_soffice() is None:
            warning = (
                "Sem o LibreOffice instalado, arquivos que o Office recusar não "
                "terão segunda chance."
            )
        return True, "Apresentações serão convertidas pelo Microsoft Office", warning
    if name == "LibreOffice":
        return True, "Apresentações serão convertidas pelo LibreOffice", None
    return False, "Nenhum conversor encontrado — só é possível cortar PDFs", None


def to_pdf(
    source: str | Path,
    workdir: str | Path,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Devolve um PDF equivalente a entrada. PDFs de entrada passam direto.

    Tenta o Microsoft Office primeiro: quando existe na maquina, a renderizacao
    e feita pelo proprio aplicativo que criou o arquivo, entao o resultado e
    fiel e nao exige instalar mais nada. O LibreOffice entra quando o Office
    nao esta disponivel ou falha.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"arquivo nao encontrado: {source}")

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_INPUTS:
        raise UnsupportedFormat(
            f"formato nao suportado: {suffix or '(sem extensao)'}. "
            f"Suportados: {', '.join(sorted(SUPPORTED_INPUTS))}"
        )
    if suffix == ".pdf":
        return source

    if office.is_available(suffix):
        _notify(on_progress, "Convertendo com o Microsoft Office...")
        try:
            return office.to_pdf(source, workdir)
        except ConversionError:
            # O erro cru do COM nao ajuda quem esta olhando a tela, e assusta.
            # Alguns arquivos simplesmente nao sao exportaveis pelo Office
            # (defeito interno do proprio arquivo); o LibreOffice costuma dar
            # conta deles, e a troca de conversor nao muda o resultado do corte.
            _notify(
                on_progress,
                "O Office não conseguiu abrir este arquivo. Usando o LibreOffice.",
            )

    soffice = find_soffice()
    if soffice is None:
        raise ConversionError(
            "nenhum conversor encontrado. Instale o Microsoft Office ou o "
            "LibreOffice, ou aponte SLIDECUT_SOFFICE para o executavel soffice."
        )

    _notify(on_progress, "Convertendo com o LibreOffice...")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    command = [
        str(soffice),
        "--headless",
        "--norestore",
        "--convert-to",
        "pdf",
        "--outdir",
        str(workdir),
        str(source),
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=CONVERSION_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(
            f"LibreOffice passou do tempo limite ({CONVERSION_TIMEOUT}s) convertendo "
            f"{source.name}. Feche instancias abertas do LibreOffice e tente de novo."
        ) from exc

    produced = workdir / f"{source.stem}.pdf"
    if result.returncode != 0 or not produced.is_file():
        detail = (result.stderr or b"").decode(errors="replace").strip()
        raise ConversionError(f"LibreOffice falhou ao converter {source.name}. {detail}".strip())
    return produced
