"""Interface de linha de comando do slidecut."""

from __future__ import annotations

import argparse
import sys

from . import analyze, core
from .errors import SlidecutError

EXIT_OK = 0
EXIT_ERROR = 2


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


def _report_plan(result: core.ProcessResult) -> None:
    print(f"Cor divisora: {result.divider_color_hex}")
    print(f"Capitulos detectados: {len(result.chapters)}\n")
    for number, chapter in enumerate(result.chapters, start=1):
        pages = f"{chapter.start + 1}-{chapter.end}"
        print(f"  {number:02d}. {chapter.title}  (paginas {pages}, {chapter.page_count})")


def run(args: argparse.Namespace) -> int:
    color = analyze.parse_color(args.color) if args.color else None

    try:
        result = core.process(
            args.input,
            outdir=args.out,
            color=color,
            tolerance=args.tolerance,
            min_coverage=args.min_coverage,
            ascii_only=args.ascii,
            list_only=args.list,
        )
    except SlidecutError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return EXIT_ERROR

    _report_plan(result)
    if not args.list:
        print(f"\n{len(result.written)} arquivos gravados em {result.outdir}")
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
