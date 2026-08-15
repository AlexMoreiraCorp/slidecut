"""Conversao de PDF em documento do Word (.docx).

Usa a biblioteca pdf2docx e nao a automacao do Word. O Word ate abre PDF e
converte, mas em automacao sem janela ele trava esperando uma confirmacao que
nunca aparece — testado, e nao ha combinacao de DisplayAlerts/ConfirmConversions
que resolva de forma confiavel. A biblioteca faz o trabalho em segundos, sem
depender do Office estar instalado.

O texto sai editavel e pesquisavel; o resultado e bom para reaproveitar
conteudo, nao para reproduzir o desenho do slide fielmente.
"""

from __future__ import annotations

from pathlib import Path

from .errors import ConversionError


def docx_name_for(pdf_path: str | Path) -> Path:
    """Caminho .docx correspondente a um PDF, na mesma pasta."""
    pdf_path = Path(pdf_path)
    return pdf_path.with_suffix(".docx")


def pdf_to_docx(source: str | Path, target: str | Path) -> Path:
    """Converte o PDF em .docx e devolve o caminho gerado."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"arquivo nao encontrado: {source}")

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        from pdf2docx import Converter
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise ConversionError(
            "a conversao para Word precisa da biblioteca pdf2docx, que nao esta instalada."
        ) from exc

    converter = None
    try:
        converter = Converter(str(source))
        converter.convert(str(target))
    except Exception as exc:
        raise ConversionError(f"nao foi possivel converter {source.name} em Word: {exc}") from exc
    finally:
        if converter is not None:
            try:
                converter.close()
            except Exception:
                pass

    if not target.is_file():
        raise ConversionError(f"a conversao de {source.name} em Word nao gerou arquivo")
    return target
