"""Fluxo de conversao e corte, reutilizado por CLI e GUI.

Dois modos partem do mesmo lugar:

- automatico (CLI): process() converte, detecta a cor divisora e grava tudo.
- manual (GUI): prepare() converte e devolve uma sugestao de cortes; o usuario
  ajusta a selecao olhando as paginas; cut_at() grava o que ele marcou.

Manter isto fora das interfaces garante que os dois modos cortem igual.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import analyze, convert, docx, layout, split, titles
from .errors import NoDividerFound

OUTPUT_SUFFIX = " - cortes"

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class PreparedDocument:
    """PDF pronto para ser cortado, com a sugestao automatica de divisores.

    O PDF apontado por pdf_path pode ser um arquivo temporario da conversao;
    quem chamou prepare() e dono do workdir e responsavel por apaga-lo.
    """

    source: Path
    pdf_path: Path
    page_count: int
    suggested_dividers: list[int]
    divider_color_hex: str | None


@dataclass(frozen=True)
class ProcessResult:
    """Resultado de um corte: cor usada, capitulos e (se gravado) os arquivos."""

    divider_color_hex: str | None
    chapters: list[split.Chapter]
    outdir: Path
    written: list[Path] = field(default_factory=list)


def default_outdir(source: Path) -> Path:
    return source.parent / f"{source.stem}{OUTPUT_SUFFIX}"


def _notify(on_progress: ProgressCallback | None, message: str) -> None:
    if on_progress is not None:
        on_progress(message)


def prepare(
    source: str | Path,
    workdir: str | Path,
    color: tuple[int, int, int] | None = None,
    tolerance: float = analyze.DEFAULT_TOLERANCE,
    min_coverage: float = analyze.MIN_COVERAGE,
    on_progress: ProgressCallback | None = None,
) -> PreparedDocument:
    """Converte a entrada para PDF e sugere onde cortar.

    Nao levanta erro quando nada e detectado: no modo manual o usuario ainda
    pode marcar os cortes na mao.
    """
    source = Path(source).expanduser()

    _notify(on_progress, f"Preparando {source.name}...")
    pdf_path = convert.to_pdf(source, workdir, on_progress=on_progress)

    _notify(on_progress, "Analisando cores das paginas...")
    colors = analyze.page_colors(pdf_path)
    target = color or analyze.find_divider_color(colors, tolerance, min_coverage)

    if target is None:
        _notify(on_progress, "Nenhuma cor divisora detectada; marque os cortes na mao.")
        return PreparedDocument(source, pdf_path, len(colors), [], None)

    dividers = analyze.find_dividers(
        pdf_path, color=target, tolerance=tolerance, min_coverage=min_coverage, colors=colors
    )
    hex_color = "#{:02X}{:02X}{:02X}".format(*target)
    _notify(on_progress, f"Cor divisora: {hex_color} ({len(dividers)} paginas)")

    return PreparedDocument(source, pdf_path, len(colors), dividers, hex_color)


def normalise_dividers(dividers: list[int], page_count: int) -> list[int]:
    """Ordena, tira repetidos e descarta paginas fora do documento."""
    return sorted({d for d in dividers if 0 <= d < page_count})


def cut_at(
    document: PreparedDocument,
    dividers: list[int],
    outdir: str | Path | None = None,
    ascii_only: bool = False,
    list_only: bool = False,
    custom_titles: dict[int, str] | None = None,
    per_sheet: int = 1,
    on_progress: ProgressCallback | None = None,
) -> ProcessResult:
    """Grava um arquivo por capitulo usando exatamente os cortes informados.

    custom_titles substitui o nome lido da pagina, por indice. Serve para quando
    o corte cai numa pagina de conteudo, cujo texto corrido daria um nome ruim.
    Entradas em branco voltam a usar o texto da pagina.
    """
    clean = normalise_dividers(dividers, document.page_count)
    if not clean:
        raise NoDividerFound("nenhuma pagina de corte selecionada.")

    resolved_outdir = (
        Path(outdir).expanduser() if outdir else default_outdir(document.source)
    )

    chapter_titles = titles.page_titles(document.pdf_path, clean, ascii_only=ascii_only)
    if custom_titles:
        chapter_titles = [
            titles.safe_filename(custom_titles[index], ascii_only)
            if custom_titles.get(index, "").strip()
            else fallback
            for index, fallback in zip(clean, chapter_titles)
        ]
    chapters = split.build_chapters(clean, document.page_count, chapter_titles)
    _notify(on_progress, f"{len(chapters)} capitulos identificados.")

    if list_only:
        return ProcessResult(document.divider_color_hex, chapters, resolved_outdir, written=[])

    written = split.write_chapters(document.pdf_path, chapters, resolved_outdir)

    if per_sheet != 1:
        _notify(on_progress, f"Agrupando em {layout.describe(per_sheet)}...")
        for arquivo in written:
            layout.group_pages(arquivo, arquivo, per_sheet=per_sheet)

    _notify(on_progress, f"{len(written)} arquivos gravados em {resolved_outdir}")
    return ProcessResult(document.divider_color_hex, chapters, resolved_outdir, written=written)


CONVERSION_TARGETS = ("pdf", "docx")
"""Para onde da para converter. Slides->PDF e PDF->Word funcionam bem; o
caminho inverso, PDF->slides, foi testado e o LibreOffice gera um arquivo vazio,
entao nao e oferecido."""


def convert_document(
    source: str | Path,
    outdir: str | Path,
    to: str = "pdf",
    per_sheet: int = 1,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Converte um arquivo inteiro, sem cortar em capitulos.

    E o modo "organizar": pega uma apresentacao, documento ou PDF e devolve um
    unico arquivo no formato pedido, opcionalmente com as paginas agrupadas.
    """
    if to not in CONVERSION_TARGETS:
        raise ValueError(
            f"formato de saida invalido: {to}. Use: {', '.join(CONVERSION_TARGETS)}"
        )

    source = Path(source).expanduser()
    outdir = Path(outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="slidecut-conv-") as workdir:
        _notify(on_progress, f"Preparando {source.name}...")
        pdf_path = convert.to_pdf(source, workdir, on_progress=on_progress)

        if per_sheet != 1:
            _notify(on_progress, f"Agrupando em {layout.describe(per_sheet)}...")
            agrupado = Path(workdir) / "agrupado.pdf"
            pdf_path = layout.group_pages(pdf_path, agrupado, per_sheet=per_sheet)

        if to == "docx":
            _notify(on_progress, "Convertendo em documento do Word...")
            alvo = docx.pdf_to_docx(pdf_path, outdir / f"{source.stem}.docx")
        else:
            alvo = outdir / f"{source.stem}.pdf"
            shutil.copyfile(pdf_path, alvo)

    _notify(on_progress, f"Gravado: {alvo.name}")
    return alvo


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
    """Corte automatico ponta a ponta: converte, detecta a cor e grava.

    Levanta SlidecutError (ou subclasse) quando a entrada e invalida, a
    conversao falha ou nenhum divisor e encontrado.
    """
    source = Path(source).expanduser()
    resolved_outdir = Path(outdir).expanduser() if outdir else default_outdir(source)

    with tempfile.TemporaryDirectory(prefix="slidecut-") as workdir:
        document = prepare(source, workdir, color, tolerance, min_coverage, on_progress)

        if not document.suggested_dividers:
            if color is None:
                raise NoDividerFound(
                    "nenhuma pagina divisora detectada. Informe a cor com --color "
                    "(ex.: --color #B06E03) ou afrouxe a tolerancia."
                )
            raise NoDividerFound(
                f"nenhuma pagina bate com a cor {color}. Ajuste --color ou --tolerance."
            )

        return cut_at(
            document,
            document.suggested_dividers,
            outdir=resolved_outdir,
            ascii_only=ascii_only,
            list_only=list_only,
            on_progress=on_progress,
        )
