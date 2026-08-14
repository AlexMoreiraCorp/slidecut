"""Interface de linha de comando do slidecut."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import analyze, convert, split, titles
from .errors import SlidecutError

EXIT_OK = 0
EXIT_ERROR = 2

OUTPUT_SUFFIX = " - cortes"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slidecut",
        description=(
            "Converte apresentacoes e documentos para PDF e corta em capitulos "
            "nas paginas divisoras coloridas."
        ),
    )
    parser.add_argument("input", help="arquivo de entrada (.pptx, .ppt, .odp, .docx, .pdf, ...)")
    parser.add_argument(
        "-o",
        "--out",
        help="pasta de saida (padrao: '<nome do arquivo> - cortes' ao lado da entrada)",
    )
    parser.add_argument(
        "--color",
        help="cor hexadecimal do slide divisor (ex.: #B06E03). Padrao: detectar sozinho",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=analyze.DEFAULT_TOLERANCE,
        help=f"tolerancia de cor, distancia RGB (padrao: {analyze.DEFAULT_TOLERANCE:g})",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=analyze.MIN_COVERAGE,
        help=f"fracao minima da pagina coberta pela cor (padrao: {analyze.MIN_COVERAGE:g})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="so mostra os cortes detectados, sem gravar nada",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="remove acentos dos nomes de arquivo",
    )
    return parser


def default_outdir(source: Path) -> Path:
    return source.parent / f"{source.stem}{OUTPUT_SUFFIX}"


def _report_plan(chapters: list[split.Chapter], divider_color: str) -> None:
    print(f"Cor divisora: {divider_color}")
    print(f"Capitulos detectados: {len(chapters)}\n")
    for number, chapter in enumerate(chapters, start=1):
        pages = f"{chapter.start + 1}-{chapter.end}"
        print(f"  {number:02d}. {chapter.title}  (paginas {pages}, {chapter.page_count})")


def run(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser()
    color = analyze.parse_color(args.color) if args.color else None

    with tempfile.TemporaryDirectory(prefix="slidecut-") as workdir:
        pdf_path = convert.to_pdf(source, workdir)

        colors = analyze.page_colors(pdf_path)
        target = color or analyze.find_divider_color(colors, args.tolerance, args.min_coverage)
        if target is None:
            print(
                "Nenhuma pagina divisora detectada. Informe a cor com --color "
                "(ex.: --color #B06E03) ou afrouxe --tolerance.",
                file=sys.stderr,
            )
            return EXIT_ERROR

        dividers = analyze.find_dividers(
            pdf_path,
            color=target,
            tolerance=args.tolerance,
            min_coverage=args.min_coverage,
            colors=colors,
        )
        if not dividers:
            print(
                f"Nenhuma pagina bate com a cor {target}. Ajuste --color ou --tolerance.",
                file=sys.stderr,
            )
            return EXIT_ERROR

        chapter_titles = titles.page_titles(pdf_path, dividers, ascii_only=args.ascii)
        chapters = split.build_chapters(dividers, len(colors), chapter_titles)
        hex_color = "#{:02X}{:02X}{:02X}".format(*target)

        _report_plan(chapters, hex_color)
        if args.list:
            return EXIT_OK

        outdir = Path(args.out).expanduser() if args.out else default_outdir(source)
        written = split.write_chapters(pdf_path, chapters, outdir)

    print(f"\n{len(written)} arquivos gravados em {outdir}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (SlidecutError, FileNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
