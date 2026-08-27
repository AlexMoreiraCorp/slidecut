"""Sistema visual da janela: cores, fontes, estilos ttk e o botao arredondado.

A tela e uma mesa de luz: papel cinza-frio, azul-tinta, e as paginas em cima.
Cor aqui nao decora — cada tom quer dizer exatamente um estado, e por isso ha
poucos e sempre os mesmos:

    laranja  CUT     esta pagina abre um capitulo ("corta aqui")
    azul     FOCUS   estou olhando esta pagina de perto
    roxo     MATRIX  esta pagina e o slide matriz, o padrao do corte
    verde    KEEP    esta pagina entra no arquivo gerado
    vermelho DANGER  isto desfaz o que voce marcou

Nenhum botao decorativo usa nenhuma dessas cores fora do seu significado. Um
botao que so navega e branco com borda; o unico laranja da tela e o que gera os
cortes, porque e a acao que o laranja quer dizer.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ------------------------------------------------------------------ cores
INK = "#15243A"
INK_LINE = "#3C5270"
PAPER = "#EEF1F4"
SURFACE = "#FFFFFF"
SURFACE_SUNK = "#F8FAFC"
SLATE = "#5B6B7F"
SLATE_LIGHT = "#8C9BAC"
EDGE = "#D3DAE1"
EDGE_SOFT = "#E7ECF1"

CUT = "#E2711D"
CUT_DARK = "#C55F12"
CUT_SOFT = "#FDF0E4"

# Desfazer marcacoes. Vermelho porque apaga trabalho do usuario, e ele precisa
# ver isso antes de clicar, nao depois.
DANGER = "#D93F3F"
DANGER_DARK = "#B3261E"
DANGER_SOFT = "#FDECEC"

# "Estou olhando esta pagina." Azul de proposito: se fosse um laranja mais claro,
# olhar um slide pareceria te-lo marcado para corte.
FOCUS = "#1C7ED6"
FOCUS_DARK = "#1668B0"
FOCUS_SOFT = "#E7F1FB"

# Slide matriz: a pagina cuja cor define o padrao de corte do documento inteiro.
MATRIX = "#6741D9"
MATRIX_DARK = "#5233B8"
MATRIX_SOFT = "#EFEAFC"

# Entra / nao entra no arquivo gerado.
KEEP = "#2E7D5A"
KEEP_SOFT = "#E6F4EE"
DROP = "#B4BFCB"

GREEN = KEEP
RED = DANGER_DARK

# ----------------------------------------------------------------- fontes
# Segoe UI Variable e a familia do Windows 11: tem corte otico proprio para
# titulo e para texto corrido, o que deixa a tela mais assentada do que usar o
# mesmo desenho em todos os tamanhos. Cai para Segoe UI onde nao existir.
DISPLAY_FAMILIES = (
    "Segoe UI Variable Display", "Segoe UI Semibold", "Bahnschrift", "Segoe UI", "Helvetica",
)
BODY_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Helvetica", "Arial")
MONO_FAMILIES = ("Cascadia Mono", "Consolas", "Courier New")

BUTTON_RADIUS = 9
"""Canto do botao. Redondo o bastante para ser visivel, longe da capsula: a
tela e uma bancada de trabalho, nao um aplicativo de celular."""


def pick_family(candidates: tuple[str, ...], available: set[str]) -> str:
    """Primeira fonte da lista que existe na maquina.

    Nunca devolve vazio: a ultima opcao serve de rede para sistemas enxutos.
    """
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


class Fonts:
    """Fontes ja resolvidas para as familias disponiveis nesta maquina."""

    def __init__(self, root: tk.Misc) -> None:
        available = set(tkfont.families(root))
        display = pick_family(DISPLAY_FAMILIES, available)
        body = pick_family(BODY_FAMILIES, available)
        mono = pick_family(MONO_FAMILIES, available)

        self.brand = tkfont.Font(root=root, family=display, size=13, weight="bold")
        self.section = tkfont.Font(root=root, family=display, size=8, weight="bold")
        self.chapter = tkfont.Font(root=root, family=display, size=9, weight="bold")
        self.button = tkfont.Font(root=root, family=display, size=10, weight="bold")
        self.display = tkfont.Font(root=root, family=display, size=18, weight="bold")
        """Titulo do painel de inspecao — o unico tamanho grande da tela."""

        self.title = tkfont.Font(root=root, family=body, size=15)
        self.subtitle = tkfont.Font(root=root, family=body, size=12)
        self.body = tkfont.Font(root=root, family=body, size=10)
        self.body_bold = tkfont.Font(root=root, family=body, size=10, weight="bold")
        self.small = tkfont.Font(root=root, family=body, size=9)
        self.tiny = tkfont.Font(root=root, family=body, size=8)

        self.number = tkfont.Font(root=root, family=mono, size=8)
        self.code = tkfont.Font(root=root, family=mono, size=9)


# ------------------------------------------------------ botao arredondado
ARC_STEPS = 6
"""Pontos por canto. Seis ja fica liso nesse raio e mantem o desenho barato."""


def rounded_rect_points(
    x0: float, y0: float, x1: float, y1: float, radius: float, steps: int = ARC_STEPS
) -> list[float]:
    """Contorno de um retangulo de cantos redondos, para create_polygon.

    O Tk nao tem canto arredondado nativo: a forma e desenhada ponto a ponto.
    O raio e limitado a metade do lado menor, senao os cantos se cruzariam e a
    figura sairia torta.
    """
    radius = max(0.0, min(radius, abs(x1 - x0) / 2, abs(y1 - y0) / 2))
    corners = (
        (x0 + radius, y0 + radius, 180),
        (x1 - radius, y0 + radius, 270),
        (x1 - radius, y1 - radius, 0),
        (x0 + radius, y1 - radius, 90),
    )
    points: list[float] = []
    for cx, cy, start in corners:
        for step in range(steps + 1):
            angle = math.radians(start + 90 * step / steps)
            points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


BUTTON_KINDS = {
    # (fundo, borda, texto) parado -> (fundo, borda, texto) sob o cursor
    "primary": ((CUT, CUT, SURFACE), (CUT_DARK, CUT_DARK, SURFACE)),
    "danger": ((DANGER_SOFT, DANGER, DANGER_DARK), (DANGER, DANGER, SURFACE)),
    "focus": ((FOCUS_SOFT, FOCUS, FOCUS_DARK), (FOCUS, FOCUS, SURFACE)),
    "matrix": ((MATRIX_SOFT, MATRIX, MATRIX_DARK), (MATRIX, MATRIX, SURFACE)),
    "quiet": ((SURFACE, "#B9C4D0", INK), (SURFACE_SUNK, INK_LINE, INK)),
    "ghost": ((PAPER, PAPER, INK_LINE), (SURFACE, "#B9C4D0", INK)),
}

DISABLED_LOOK = ("#EDF1F5", "#DEE4EA", SLATE_LIGHT)


class RoundedButton(tk.Canvas):
    """Botao de cantos redondos desenhado a mao.

    Existe porque o ttk no Windows nao arredonda canto nenhum: o widget nativo
    e sempre um retangulo duro. Como o botao e desenhado, o fundo do canvas tem
    de ser o mesmo da area onde ele fica — e o que faz o canto parecer vazado em
    vez de recortado num quadrado branco.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command=None,
        kind: str = "quiet",
        fonts: Fonts | None = None,
        background: str = SURFACE,
        min_width: int = 0,
        padx: int = 16,
        pady: int = 9,
    ) -> None:
        self._font = (fonts.button if fonts else tkfont.nametofont("TkDefaultFont"))
        self._text = text
        self._command = command
        self._looks = BUTTON_KINDS.get(kind, BUTTON_KINDS["quiet"])
        self._enabled = True
        self._hovered = False

        width = max(min_width, self._font.measure(text) + padx * 2)
        height = self._font.metrics("linespace") + pady * 2

        super().__init__(
            parent, width=width, height=height, background=background,
            highlightthickness=0, bd=0, takefocus=1, cursor="hand2",
        )
        self._shape = self.create_polygon(
            rounded_rect_points(1, 1, width - 1, height - 1, BUTTON_RADIUS),
            smooth=False, width=1,
        )
        self._label = self.create_text(
            width / 2, height / 2, text=text, font=self._font, anchor="center"
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Return>", lambda _e: self.invoke())
        self.bind("<space>", lambda _e: self.invoke())
        self._repaint()

    # -------------------------------------------------------------- estado
    def _repaint(self) -> None:
        if not self._enabled:
            fill, border, ink = DISABLED_LOOK
        else:
            fill, border, ink = self._looks[1 if self._hovered else 0]
        self.itemconfigure(self._shape, fill=fill, outline=border)
        self.itemconfigure(self._label, fill=ink)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._repaint()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._repaint()

    def _on_press(self, _event=None) -> None:
        if self._enabled:
            self.move(self._label, 0, 1)

    def _on_release(self, _event=None) -> None:
        if not self._enabled:
            return
        self.move(self._label, 0, -1)
        self.invoke()

    def invoke(self) -> None:
        if self._enabled and self._command is not None:
            self._command()

    # ----------------------------------------------- compatibilidade com ttk
    def configure(self, **kwargs):  # type: ignore[override]
        """Aceita text= e state= como um ttk.Button, para as telas nao saberem
        que este botao e desenhado a mao."""
        if "text" in kwargs:
            self._text = kwargs.pop("text")
            self.itemconfigure(self._label, text=self._text)
        if "state" in kwargs:
            self._enabled = kwargs.pop("state") != "disabled"
            self.configure_cursor()
            self._repaint()
        if kwargs:
            return super().configure(**kwargs)
        return None

    config = configure

    def configure_cursor(self) -> None:
        super().configure(cursor="hand2" if self._enabled else "arrow")


def apply(root: tk.Misc, fonts: Fonts) -> ttk.Style:
    """Configura os estilos ttk usados pela janela.

    Usa o tema 'clam' como base porque e o unico dos temas nativos que deixa
    controlar cor de fundo e de borda dos botoes no Windows.
    """
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=PAPER, foreground=INK, font=fonts.body)
    style.configure("Paper.TFrame", background=PAPER)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Sunk.TFrame", background=SURFACE_SUNK)
    style.configure("Ink.TFrame", background=INK)

    for name, bg in (("Paper", PAPER), ("Surface", SURFACE), ("Sunk", SURFACE_SUNK)):
        style.configure(f"{name}.TLabel", background=bg, foreground=INK, font=fonts.body)
        style.configure(f"{name}Muted.TLabel", background=bg, foreground=SLATE, font=fonts.small)
        style.configure(f"{name}Faint.TLabel", background=bg, foreground=SLATE_LIGHT,
                        font=fonts.tiny)
        style.configure(f"{name}Title.TLabel", background=bg, foreground=INK, font=fonts.title)
        style.configure(f"{name}Section.TLabel", background=bg, foreground=CUT,
                        font=fonts.section)

    style.configure("Brand.TLabel", background=INK, foreground=SURFACE, font=fonts.brand)
    style.configure("BrandSub.TLabel", background=INK, foreground="#9EB0C6", font=fonts.body)

    # Botao comum: branco com borda, sem cor de destaque.
    style.configure(
        "Quiet.TButton", background=SURFACE, foreground=INK, bordercolor="#A8B6C5",
        lightcolor=SURFACE, darkcolor=SURFACE, focuscolor=CUT, relief="flat",
        padding=(14, 7), font=fonts.body,
    )
    style.map(
        "Quiet.TButton",
        background=[("pressed", "#E8EDF2"), ("active", SURFACE_SUNK), ("disabled", "#F1F4F7")],
        foreground=[("disabled", SLATE_LIGHT)],
    )

    # Botao principal: o unico preenchido de laranja na aplicacao inteira.
    style.configure(
        "Cut.TButton", background=CUT, foreground=SURFACE, bordercolor=CUT,
        lightcolor=CUT, darkcolor=CUT, focuscolor=SURFACE, relief="flat",
        padding=(20, 10), font=fonts.button,
    )
    style.map(
        "Cut.TButton",
        background=[("pressed", CUT_DARK), ("active", CUT_DARK), ("disabled", "#DEE3E9")],
        foreground=[("disabled", SLATE_LIGHT)],
        bordercolor=[("disabled", "#DEE3E9")],
    )

    # Botao do cabecalho (fundo escuro): contorno claro, sem laranja — laranja
    # e reservado para "cortar aqui" — a troca de modo agora e uma aba, nao um
    # botao no cabecalho escuro (que passava despercebido; feedback real de uso).

    style.configure(
        "TEntry", fieldbackground=SURFACE, bordercolor=EDGE, lightcolor=EDGE,
        darkcolor=EDGE, insertcolor=INK, padding=6,
    )
    style.configure(
        "Name.TEntry", fieldbackground=SURFACE, bordercolor=CUT, lightcolor=CUT,
        darkcolor=CUT, insertcolor=INK, padding=4,
    )

    style.configure(
        "TCheckbutton", background=SURFACE, foreground=SLATE, focuscolor=CUT, font=fonts.body,
    )
    style.map("TCheckbutton", background=[("active", SURFACE)])

    style.configure(
        "Cut.Horizontal.TProgressbar", background=CUT, troughcolor=EDGE_SOFT,
        bordercolor=EDGE_SOFT, lightcolor=CUT, darkcolor=CUT, thickness=4,
    )
    return style
