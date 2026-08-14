"""Gera o icone do slidecut.

O desenho conta o que o programa faz: um documento partido em duas partes que
se afastam, cada parte comecando por uma faixa colorida — que e exatamente o
slide divisor que o programa procura.

As partes sao inclinadas em sentidos opostos porque, no tamanho de icone de
taskbar, e a inclinacao que faz o desenho ler como "separou" em vez de
"dois cartoes empilhados". O detalhe interno e minimo pelo mesmo motivo: a
16x16 qualquer linha a mais vira sujeira.

Rodar: python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 512
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

BACKGROUND = (30, 58, 95)
PAGE = (255, 255, 255)
BAND = (233, 143, 26)
TEXT_LINE = (196, 208, 222)
SHADOW = (10, 24, 44, 110)

BG_RADIUS = 112
PIECE_SIZE = (306, 168)
PIECE_RADIUS = 20
BAND_HEIGHT = 52
SUPERSAMPLE = 4
"""Desenha grande e reduz: sem isso as bordas inclinadas ficam serrilhadas."""

# (centro_x, centro_y, angulo) — angulos opostos afastam as partes.
PIECES = [
    (238, 158, 7.0),
    (286, 358, -7.0),
]


def _render_piece() -> Image.Image:
    """Uma parte do documento: pagina branca com faixa colorida no topo."""
    scale = SUPERSAMPLE
    width, height = (PIECE_SIZE[0] * scale, PIECE_SIZE[1] * scale)
    radius = PIECE_RADIUS * scale
    band = BAND_HEIGHT * scale

    piece = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(piece)

    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=BAND)
    draw.rounded_rectangle((0, band, width - 1, height - 1), radius, fill=PAGE)
    # Quadra os cantos de cima do corpo branco, senao a faixa reaparece nos vaos.
    draw.rectangle((0, band, width - 1, band + radius), fill=PAGE)

    margin = 34 * scale
    line_height = 13 * scale
    for row, fraction in enumerate((1.0, 0.62)):
        top = band + (34 * scale) + row * (30 * scale)
        right = margin + (width - 2 * margin) * fraction
        draw.rounded_rectangle(
            (margin, top, right, top + line_height), line_height // 2, fill=TEXT_LINE
        )

    return piece


def build_icon() -> Image.Image:
    scale = SUPERSAMPLE
    size = CANVAS * scale

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle(
        (0, 0, size - 1, size - 1), BG_RADIUS * scale, fill=BACKGROUND
    )

    piece = _render_piece()
    for center_x, center_y, angle in PIECES:
        rotated = piece.rotate(angle, resample=Image.BICUBIC, expand=True)

        shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
        shadow.paste(Image.new("RGBA", rotated.size, SHADOW), mask=rotated)

        top_left = (center_x * scale - rotated.width // 2, center_y * scale - rotated.height // 2)
        image.alpha_composite(shadow, (top_left[0] + 5 * scale, top_left[1] + 7 * scale))
        image.alpha_composite(rotated, top_left)

    return image.resize((CANVAS, CANVAS), Image.LANCZOS)


def main() -> None:
    here = Path(__file__).resolve().parent.parent / "src" / "slidecut" / "assets"
    here.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(here / "icon.png")
    icon.save(here / "icon.ico", sizes=[(s, s) for s in ICO_SIZES])
    print(f"gravado: {here / 'icon.ico'} e {here / 'icon.png'}")


if __name__ == "__main__":
    main()
