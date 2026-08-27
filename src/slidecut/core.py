"""Fluxo de conversao e corte, reutilizado por CLI e GUI.

Dois modos partem do mesmo lugar:

- automatico (CLI): process() converte, detecta a cor divisora e grava tudo.
- manual (GUI): prepare() converte e devolve uma sugestao de cortes; o usuario
  ajusta a selecao olhando as paginas; cut_at() grava o que ele marcou.

Manter isto fora das interfaces garante que os dois modos cortem igual.
"""

from __future__ import annotations

import contextlib
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import analyze, convert, docx, layout, split, titles
from . import document as document_module
from .errors import NoDividerFound, SlidecutError

OUTPUT_SUFFIX = " - cortes"

ProgressCallback = Callable[[str], None]
BatchItemCallback = Callable[[int, int, Path], None]
"""Chamado no inicio de cada item do lote: (indice base 1, total, arquivo).

Canal separado do texto livre de ProgressCallback de proposito: a barra de
progresso do lote nao pode depender de recortar um numero de dentro de uma
mensagem qualquer, que quebraria se o texto dessa mensagem mudasse."""


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


def _notify_item(on_item: BatchItemCallback | None, index: int, total: int, source: Path) -> None:
    if on_item is not None:
        on_item(index, total, source)


def prepare(
    source: str | Path,
    workdir: str | Path,
    color: tuple[int, int, int] | None = None,
    tolerance: float = analyze.DEFAULT_TOLERANCE,
    min_coverage: float = analyze.MIN_COVERAGE,
    on_progress: ProgressCallback | None = None,
    matrix_page: int | None = None,
) -> PreparedDocument:
    """Converte a entrada para PDF e sugere onde cortar.

    matrix_page aponta um slide que o usuario reconhece como divisor: a cor dele
    vira o padrao do corte, no lugar do palpite automatico. Serve para o deck com
    mais de um tom forte, onde "o que mais se repete" nao e o tom certo.

    Nao levanta erro quando nada e detectado: no modo manual o usuario ainda
    pode marcar os cortes na mao.
    """
    source = Path(source).expanduser()

    _notify(on_progress, f"Preparando {source.name}...")
    pdf_path = convert.to_pdf(source, workdir, on_progress=on_progress)

    _notify(on_progress, "Analisando cores das paginas...")
    colors = analyze.page_colors(pdf_path)

    if color is None and matrix_page is not None:
        color = analyze.page_color(pdf_path, matrix_page)
        _notify(on_progress, f"Usando a pagina {matrix_page + 1} como slide matriz.")

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
    prefix: str = "",
    suffix: str = "",
    excluded_pages: set[int] | frozenset[int] | None = None,
    numbered: bool = True,
) -> ProcessResult:
    """Grava um arquivo por capitulo usando exatamente os cortes informados.

    custom_titles substitui o nome lido da pagina, por indice. Serve para quando
    o corte cai numa pagina de conteudo, cujo texto corrido daria um nome ruim.
    Entradas em branco voltam a usar o texto da pagina.

    prefix e suffix envolvem todos os nomes gerados, inclusive os que o usuario
    digitou: quem escolheu um prefixo quer ele em todo o lote, e nao teria por
    que redigita-lo capitulo a capitulo.

    excluded_pages sao paginas que ficam de fora dos arquivos gerados. O arquivo
    de origem nao e tocado — a pagina continua la, so nao entra no corte.
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
    if prefix.strip() or suffix.strip():
        chapter_titles = [
            titles.decorate(name, prefix, suffix, ascii_only) for name in chapter_titles
        ]

    chapters = split.build_chapters(
        clean, document.page_count, chapter_titles, excluded=excluded_pages
    )
    if not chapters:
        raise NoDividerFound(
            "todas as paginas foram desmarcadas; nao sobrou nada para gravar."
        )
    _notify(on_progress, f"{len(chapters)} capitulos identificados.")

    if list_only:
        return ProcessResult(document.divider_color_hex, chapters, resolved_outdir, written=[])

    written = split.write_chapters(document.pdf_path, chapters, resolved_outdir, numbered=numbered)

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

        # PDF de entrada passa direto por convert.to_pdf, sem abrir o arquivo.
        # Um PDF corrompido so seria pego na hora de escrever a saida (ou nunca,
        # no caminho to="pdf" com per_sheet=1, que so copia bytes). Confere aqui
        # para o erro aparecer sempre no mesmo lugar, nao depender do caminho.
        with document_module.open_pdf(pdf_path):
            pass

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


@dataclass(frozen=True)
class BatchItemResult:
    """Resultado de um arquivo dentro de um lote: sucesso ou erro, nunca os dois."""

    source: Path
    ok: bool
    output: Path | None = None
    written: list[Path] = field(default_factory=list)
    error: str | None = None


def process_batch(
    sources: list[str | Path],
    outdir: str | Path,
    color: tuple[int, int, int] | None = None,
    tolerance: float = analyze.DEFAULT_TOLERANCE,
    min_coverage: float = analyze.MIN_COVERAGE,
    ascii_only: bool = False,
    per_sheet: int = 1,
    on_progress: ProgressCallback | None = None,
    on_item: BatchItemCallback | None = None,
    prefix: str = "",
    suffix: str = "",
    numbered: bool = True,
) -> list[BatchItemResult]:
    """Corta varios arquivos de uma vez, cada um na sua propria subpasta.

    Um arquivo com problema (sem divisor, corrompido, formato invalido) nao
    interrompe o lote: fica registrado como erro e os demais continuam.

    on_progress traz o texto solto de cada etapa (o mesmo canal que
    prepare()/cut_at() usam por dentro). on_item e um canal a parte, so para o
    indice do lote (index, total, source) — nao deriva desse texto, entao a
    barra de progresso nao depende de nenhum formato de mensagem.
    """
    outdir = Path(outdir).expanduser()
    results: list[BatchItemResult] = []
    total = len(sources)

    for index, raw_source in enumerate(sources, start=1):
        # Tudo dentro do try, inclusive normalizar o caminho e avisar o
        # progresso: um item com um caminho invalido nao pode derrubar os
        # demais, que e a garantia central deste laco.
        try:
            source = Path(raw_source).expanduser()
            _notify_item(on_item, index, total, source)
            _notify(on_progress, f"Processando {source.name}...")
            result = process(
                source,
                outdir=outdir / source.stem,
                color=color,
                tolerance=tolerance,
                min_coverage=min_coverage,
                ascii_only=ascii_only,
                per_sheet=per_sheet,
                on_progress=on_progress,
                prefix=prefix,
                suffix=suffix,
                numbered=numbered,
            )
            results.append(BatchItemResult(source, ok=True, written=result.written))
        except Exception as exc:
            source = Path(str(raw_source))
            with contextlib.suppress(Exception):
                _notify(on_progress, f"{source.name}: falhou ({exc})")
            results.append(BatchItemResult(source, ok=False, error=str(exc)))

    return results


def convert_batch(
    sources: list[str | Path],
    outdir: str | Path,
    to: str = "pdf",
    per_sheet: int = 1,
    on_progress: ProgressCallback | None = None,
    on_item: BatchItemCallback | None = None,
) -> list[BatchItemResult]:
    """Converte varios arquivos de uma vez para o mesmo formato de saida.

    Todos vao para a mesma pasta, sem subpasta por arquivo. Duas entradas com o
    mesmo nome (pastas diferentes, ou so a extensao diferente) gerariam o mesmo
    arquivo de saida; a segunda e recusada em vez de sobrescrever a primeira em
    silencio.
    """
    outdir = Path(outdir).expanduser()
    results: list[BatchItemResult] = []
    used_names: set[str] = set()
    total = len(sources)

    for index, raw_source in enumerate(sources, start=1):
        try:
            source = Path(raw_source).expanduser()
            _notify_item(on_item, index, total, source)
            _notify(on_progress, f"Processando {source.name}...")

            expected_name = f"{source.stem}.docx" if to == "docx" else f"{source.stem}.pdf"
            if expected_name in used_names:
                raise SlidecutError(
                    f"{expected_name} ja foi gerado por outro arquivo do lote; "
                    "renomeie um dos dois para evitar que um sobrescreva o outro."
                )

            produced = convert_document(
                source, outdir, to=to, per_sheet=per_sheet, on_progress=on_progress
            )
            used_names.add(expected_name)
            results.append(BatchItemResult(source, ok=True, output=produced))
        except Exception as exc:
            source = Path(str(raw_source))
            with contextlib.suppress(Exception):
                _notify(on_progress, f"{source.name}: falhou ({exc})")
            results.append(BatchItemResult(source, ok=False, error=str(exc)))

    return results


def process(
    source: str | Path,
    outdir: str | Path | None = None,
    color: tuple[int, int, int] | None = None,
    tolerance: float = analyze.DEFAULT_TOLERANCE,
    min_coverage: float = analyze.MIN_COVERAGE,
    ascii_only: bool = False,
    list_only: bool = False,
    per_sheet: int = 1,
    on_progress: ProgressCallback | None = None,
    prefix: str = "",
    suffix: str = "",
    numbered: bool = True,
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
            per_sheet=per_sheet,
            on_progress=on_progress,
            prefix=prefix,
            suffix=suffix,
            numbered=numbered,
        )
