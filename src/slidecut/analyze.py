"""Deteccao das paginas divisoras a partir da cor dominante de cada pagina.

A ideia: um slide divisor e uma pagina de fundo chapado numa cor forte, e essa
mesma cor se repete ao longo do deck. Paginas de conteudo tem fundo claro e
neutro. Entao procuramos o agrupamento de cores saturadas que mais se repete.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .document import open_pdf

RGB = tuple[int, int, int]

RENDER_SCALE = 0.15
"""Escala de render. Baixa de proposito: so precisamos da cor, nao do detalhe."""

SAMPLE_STEP = 2
"""Amostragem de pixels. Passo 2 ja e preciso o bastante e corta o custo em 4x."""

QUANTIZE_BITS = 4
"""Agrupa canais em blocos de 16 para tolerar gradientes e ruido de compressao."""

DEFAULT_TOLERANCE = 45
"""Distancia euclidiana RGB maxima entre duas paginas da mesma cor divisora."""

MIN_COVERAGE = 0.45
"""Fracao minima da pagina ocupada pela cor dominante."""

MIN_SATURATION = 0.20
MAX_LUMINANCE = 225
DARK_LUMINANCE = 90
MIN_RECURRENCE = 2
"""Uma cor so vira divisora se aparecer em pelo menos duas paginas."""

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class PageColor:
    """Cor dominante de uma pagina e quanto dela essa cor ocupa."""

    index: int
    rgb: RGB
    coverage: float


def parse_color(value: str) -> RGB:
    """Converte '#B06E03' ou 'b06e03' em (176, 110, 3)."""
    match = _HEX_RE.match(value.strip())
    if not match:
        raise ValueError(f"cor invalida: {value!r} (use hexadecimal, ex.: #B06E03)")
    digits = match.group(1)
    return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def saturation(rgb: RGB) -> float:
    """Saturacao HSV: 0 para cinzas, 1 para cores puras."""
    high, low = max(rgb), min(rgb)
    return 0.0 if high == 0 else (high - low) / high


def luminance(rgb: RGB) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def distance(a: RGB, b: RGB) -> float:
    return math.dist(a, b)


def is_divider_candidate(rgb: RGB, coverage: float, min_coverage: float = MIN_COVERAGE) -> bool:
    """Uma pagina so e candidata se for chapada e nao for um fundo claro neutro."""
    if coverage < min_coverage:
        return False
    lum = luminance(rgb)
    if lum <= DARK_LUMINANCE:
        return True
    return saturation(rgb) >= MIN_SATURATION and lum <= MAX_LUMINANCE


def dominant_color(pixmap: pymupdf.Pixmap) -> tuple[RGB, float]:
    """Cor mais frequente do pixmap (quantizada) e a fracao de pixels que ela cobre."""
    samples = pixmap.samples
    channels = pixmap.n
    width, height = pixmap.width, pixmap.height

    buckets: dict[tuple[int, int, int], list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    total = 0
    for y in range(0, height, SAMPLE_STEP):
        row = y * width * channels
        for x in range(0, width, SAMPLE_STEP):
            offset = row + x * channels
            r, g, b = samples[offset], samples[offset + 1], samples[offset + 2]
            bucket = buckets[(r >> QUANTIZE_BITS, g >> QUANTIZE_BITS, b >> QUANTIZE_BITS)]
            bucket[0] += 1
            bucket[1] += r
            bucket[2] += g
            bucket[3] += b
            total += 1

    if not total:
        return (255, 255, 255), 0.0

    count, sum_r, sum_g, sum_b = max(buckets.values(), key=lambda acc: acc[0])
    mean = (round(sum_r / count), round(sum_g / count), round(sum_b / count))
    return mean, count / total


def page_colors(pdf_path: str | Path, scale: float = RENDER_SCALE) -> list[PageColor]:
    """Cor dominante de cada pagina do PDF, na ordem."""
    matrix = pymupdf.Matrix(scale, scale)
    colors: list[PageColor] = []
    with open_pdf(pdf_path) as doc:
        for index, page in enumerate(doc):
            pixmap = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)
            rgb, coverage = dominant_color(pixmap)
            colors.append(PageColor(index=index, rgb=rgb, coverage=coverage))
    return colors


def page_color(pdf_path: str | Path, index: int, scale: float = RENDER_SCALE) -> RGB:
    """Cor dominante de uma unica pagina — a base do "slide matriz".

    Em vez de deixar o programa adivinhar qual tom separa os capitulos, o
    usuario aponta um slide que ele sabe ser divisor e o corte passa a seguir a
    cor daquele slide. Resolve o deck com mais de um tom forte, onde a contagem
    automatica escolheria o grupo errado.
    """
    matrix = pymupdf.Matrix(scale, scale)
    with open_pdf(pdf_path) as doc:
        if not 0 <= index < doc.page_count:
            raise IndexError(f"pagina {index} fora do documento ({doc.page_count} paginas)")
        pixmap = doc[index].get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)
        rgb, _coverage = dominant_color(pixmap)
    return rgb


def find_divider_color(
    colors: list[PageColor],
    tolerance: float = DEFAULT_TOLERANCE,
    min_coverage: float = MIN_COVERAGE,
) -> RGB | None:
    """Escolhe a cor divisora: o grupo de cores fortes que mais se repete."""
    candidates = [c for c in colors if is_divider_candidate(c.rgb, c.coverage, min_coverage)]
    if not candidates:
        return None

    # Ligacao simples: basta estar perto de UM membro. Comparar so com o primeiro
    # membro quebraria um tom que varia aos poucos ao longo do deck em dois grupos.
    clusters: list[list[PageColor]] = []
    for candidate in candidates:
        for cluster in clusters:
            if any(distance(candidate.rgb, member.rgb) <= tolerance for member in cluster):
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])

    eligible = [c for c in clusters if len(c) >= MIN_RECURRENCE]
    if not eligible:
        return None

    best = max(eligible, key=lambda cluster: (len(cluster), saturation(cluster[0].rgb)))
    size = len(best)
    return (
        round(sum(c.rgb[0] for c in best) / size),
        round(sum(c.rgb[1] for c in best) / size),
        round(sum(c.rgb[2] for c in best) / size),
    )


def find_dividers(
    pdf_path: str | Path,
    color: RGB | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    min_coverage: float = MIN_COVERAGE,
    colors: list[PageColor] | None = None,
) -> list[int]:
    """Indices (base 0) das paginas divisoras. Lista vazia se nada for detectado."""
    if colors is None:
        colors = page_colors(pdf_path)

    target = color if color is not None else find_divider_color(colors, tolerance, min_coverage)
    if target is None:
        return []

    return [
        c.index
        for c in colors
        if c.coverage >= min_coverage and distance(c.rgb, target) <= tolerance
    ]
