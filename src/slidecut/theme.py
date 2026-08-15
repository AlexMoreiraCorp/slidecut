"""Sistema visual da janela: cores, fontes e estilos ttk.

A ideia por tras da paleta: laranja quer dizer "corte aqui", e nada mais. Nenhum
botao decorativo, nenhum destaque gratuito usa laranja — assim a interface fala
a mesma lingua do conteudo, ja que o programa procura justamente slides
divisores coloridos. O resto da tela e azul-tinta e papel cinza-frio, como uma
mesa de luz onde se inspecionam paginas.
"""

from __future__ import annotations

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
GREEN = "#2E7D5A"
RED = "#B3261E"

# ----------------------------------------------------------------- fontes
DISPLAY_FAMILIES = ("Bahnschrift", "Segoe UI Semibold", "Segoe UI", "Helvetica")
BODY_FAMILIES = ("Segoe UI", "Helvetica", "Arial")
MONO_FAMILIES = ("Cascadia Mono", "Consolas", "Courier New")


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

        self.title = tkfont.Font(root=root, family=body, size=15)
        self.body = tkfont.Font(root=root, family=body, size=10)
        self.body_bold = tkfont.Font(root=root, family=body, size=10, weight="bold")
        self.small = tkfont.Font(root=root, family=body, size=9)
        self.tiny = tkfont.Font(root=root, family=body, size=8)

        self.number = tkfont.Font(root=root, family=mono, size=8)


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
