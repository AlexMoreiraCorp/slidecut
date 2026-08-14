"""Fluxo completo (converter, detectar cor, cortar), reutilizado por CLI e GUI.

Mantido separado das interfaces para que CLI e GUI cheguem sempre ao mesmo
resultado e so difiram em como mostram o progresso ao usuario.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import analyze, convert, split, titles
from .errors import NoDividerFound

OUTPUT_SUFFIX = " - cortes"

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class ProcessResult:
    """Resultado de um corte: cor achada, capitulos e (se gravado) os arquivos."""

    divider_color_hex: str
    chapters: list[split.Chapter]
    outdir: Path
    written: list[Path] = field(default_factory=list)


def default_outdir(source: Path) -> Path:
    return source.parent / f"{source.stem}{OUTPUT_SUFFIX}"


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


def process(
    source: str | Path,
    outdir: str | Path | None = None,
    color: tuple[int, int, int] | None = None,
    tolerance: float = analyze.DEFAULT_TOLERANCE,
    min_coverage: float = analyze.MIN_COVERAGE,
    ascii_only: bool = False,
    list_only: bool = False,
    on_progress: ProgressCallback | None = None,
) -> ProcessResult:
    """Converte, detecta os divisores e (a menos que list_only) grava os capitulos.

    Levanta SlidecutError (ou subclasse) quando a entrada e invalida, a conversao
    falha ou nenhum divisor e encontrado.
    """
    source = Path(source).expanduser()
    resolved_outdir = Path(outdir).expanduser() if outdir else default_outdir(source)

    with tempfile.TemporaryDirectory(prefix="slidecut-") as workdir:
        _notify(on_progress, f"Convertendo {source.name} para PDF...")
        pdf_path = convert.to_pdf(source, workdir)

        _notify(on_progress, "Analisando cores das paginas...")
        colors = analyze.page_colors(pdf_path)
        target = color or analyze.find_divider_color(colors, tolerance, min_coverage)
        if target is None:
            raise NoDividerFound(
                "nenhuma pagina divisora detectada. Informe a cor com --color "
                "(ex.: --color #B06E03) ou afrouxe a tolerancia."
            )

        dividers = analyze.find_dividers(
            pdf_path, color=target, tolerance=tolerance, min_coverage=min_coverage, colors=colors
        )
        if not dividers:
            raise NoDividerFound(
                f"nenhuma pagina bate com a cor {target}. Ajuste --color ou --tolerance."
            )

        hex_color = "#{:02X}{:02X}{:02X}".format(*target)
        _notify(on_progress, f"Cor divisora: {hex_color} ({len(dividers)} paginas)")

        chapter_titles = titles.page_titles(pdf_path, dividers, ascii_only=ascii_only)
        chapters = split.build_chapters(dividers, len(colors), chapter_titles)
        _notify(on_progress, f"{len(chapters)} capitulos identificados.")

        if list_only:
            return ProcessResult(hex_color, chapters, resolved_outdir, written=[])

        written = split.write_chapters(pdf_path, chapters, resolved_outdir)
        _notify(on_progress, f"{len(written)} arquivos gravados em {resolved_outdir}")

    return ProcessResult(hex_color, chapters, resolved_outdir, written=written)
