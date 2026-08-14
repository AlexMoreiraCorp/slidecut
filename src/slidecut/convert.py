"""Conversao de qualquer formato suportado para PDF, via LibreOffice headless."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .errors import ConversionError, UnsupportedFormat

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


def to_pdf(source: str | Path, workdir: str | Path) -> Path:
    """Devolve um PDF equivalente a entrada. PDFs de entrada passam direto."""
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

    soffice = find_soffice()
    if soffice is None:
        raise ConversionError(
            "LibreOffice nao encontrado. Instale-o ou aponte SLIDECUT_SOFFICE "
            "para o executavel soffice."
        )

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
