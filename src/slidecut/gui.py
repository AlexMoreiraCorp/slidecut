"""Janela do slidecut.

Duas telas:

1. Abrir: escolher o arquivo, arrastando para a janela ou pelo seletor.
2. Folha de contato: todas as paginas em miniatura. A deteccao por cor entra
   como sugestao inicial; quem decide onde cortar e o usuario. A folha se
   reorganiza em capitulos conforme as marcas mudam, entao da para ver os
   arquivos se formando antes de gerar.

O visual vem de theme.py. A conversao e o corte vivem em core.py; aqui so tem
tela.
"""

from __future__ import annotations

import atexit
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__, analyze, convert, core, layout, preview, resources, theme, titles
from . import updates
from .errors import SlidecutError

try:  # arrastar arquivo para a janela; a aplicacao funciona sem isso
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover - depende do ambiente
    DND_FILES = None
    TkinterDnD = None

WINDOW_TITLE = "slidecut"
VERSION_LABEL = f"v{__version__}"
CREDIT = "Desenvolvido por Alex Moreira Productions"
WINDOW_WIDTH, WINDOW_HEIGHT = 1320, 860
"""Tamanho alvo numa tela grande. fit_window_geometry() encolhe isto para caber
em telas menores, ate o piso de MIN_SIZE."""
MIN_SIZE = (1080, 700)
"""A janela cresceu quando a tela de selecao ganhou o painel lateral: no tamanho
antigo, abrir uma pagina de perto espremia a grade a uma coluna."""

THUMBNAIL_WIDTH = 168
CARD_PAD = 10
SCROLL_STEP = 90
"""Pixels por notch do mouse na folha de paginas. Sem um valor fixo, o Windows
rola em fracoes de pixel — a causa do rastro visivel ao usar a roda do mouse."""
EVENTS_PER_TICK = 6
REFLOW_DELAY_MS = 120
"""Reagrupar 145 cartoes a cada clique engasgaria. O cartao clicado responde na
hora; o reagrupamento por capitulo espera o usuario parar de clicar."""

CARD_WIDTH = THUMBNAIL_WIDTH + 34
CARD_EXTRA_HEIGHT = 230
NAME_ROW_HEIGHT = 98
"""Espaco abaixo da miniatura: a marca de corte, o "entra no corte", a legenda e
o campo de nome com a previa — reservados tambem nas paginas sem corte, para a
grade nunca mudar de forma quando uma marca liga ou desliga."""

INSPECTOR_WIDTH = 460
INSPECT_DOCKED_WIDTH = 340
"""Largura do painel lateral, e da pagina dentro dele. A pagina fica menor que o
painel para os botoes de acao caberem sem rolagem na janela minima; dois cliques
pedem o render grande, que aproveita a largura toda."""

CUT_ON_LABEL = "CORTA AQUI"
CUT_OFF_LABEL = "marcar corte aqui"
"""A marca de corte virou um alvo com nome escrito: antes, clicar em qualquer
canto do cartao ligava o corte, e quem ligava sem querer nao achava como
desligar. Sem icone de tesoura — o glifo nao existe na fonte da interface no
Windows e sai desenhado torto; a faixa laranja ja diz o que e."""

DEFAULT_PER_SHEET = 2
"""Padrao pedido: dois slides por folha. Corta as folhas pela metade e o texto
continua legivel impresso."""

LAYOUT_CHOICES = [
    ("1 — uma página por folha (original)", 1),
    ("2 — duas páginas por folha", 2),
    ("3 — três páginas por folha", 3),
    ("4 — quatro páginas por folha", 4),
]

MODE_CHOICES = [
    ("Cortar", "cortar"),
    ("Só converter e organizar", "converter"),
]

TARGET_CHOICES = [
    ("PDF", "pdf"),
    ("Documento do Word (.docx)", "docx"),
]

PRIMARY_TYPES = [
    ("Apresentações, documentos e PDF", "*.pptx *.ppt *.odp *.pps *.ppsx *.docx *.doc *.odt *.pdf"),
    ("Apresentações", "*.pptx *.ppt *.odp *.pps *.ppsx"),
    ("Documentos", "*.docx *.doc *.odt *.rtf"),
    ("PDF", "*.pdf"),
    ("Todos os formatos aceitos", " ".join(f"*{e}" for e in sorted(convert.SUPPORTED_INPUTS))),
    ("Todos os arquivos", "*.*"),
]


# ------------------------------------------------------------------ textos
def conversion_prompt(source: Path, converter_name: str) -> str:
    """Pergunta mostrada antes de converter um arquivo que nao e PDF."""
    return (
        f"{source.name} precisa virar PDF antes de ser cortado.\n\n"
        f"A conversão é feita pelo {converter_name} e não altera o arquivo original.\n\n"
        "Converter agora?"
    )


def no_converter_message(source: Path) -> str:
    return (
        f"{source.name} precisa virar PDF antes de ser cortado, mas este computador "
        "não tem Microsoft Office nem LibreOffice.\n\n"
        "Instale um dos dois, ou abra um arquivo que já seja PDF."
    )


def format_result_summary(result: core.ProcessResult) -> str:
    return f"{len(result.written)} arquivo(s) gravado(s) em:\n{result.outdir}"


def conversion_summary(produced: Path, per_sheet: int) -> str:
    """Mensagem final do modo converter."""
    linha = f"Arquivo gerado:\n{produced.name}"
    if per_sheet != 1:
        linha += f"\n\nAgrupado em {layout.describe(per_sheet)}."
    return linha + f"\n\nPasta: {produced.parent}"


def batch_item_label(index: int, total: int, source: Path) -> str:
    """Rotulo do item corrente do lote, para a barra de progresso e o status."""
    return f"Arquivo {index} de {total}: {source.name}"


def batch_summary(results: list) -> str:
    """Mensagem final do lote: quantos deram certo, quais falharam e por que."""
    ok = [r for r in results if r.ok]
    ruins = [r for r in results if not r.ok]
    linha = f"{len(ok)} de {len(results)} arquivo(s) processados com sucesso."
    if ruins:
        detalhes = "\n".join(f"  • {r.source.name}: {r.error}" for r in ruins)
        linha += f"\n\nFalharam ({len(ruins)}):\n{detalhes}"
    return linha


def selection_summary(selected: int, total: int, excluded: int = 0) -> str:
    base = (
        f"{total} páginas · nenhum corte marcado"
        if selected == 0
        else f"{total} páginas · {selected} arquivo(s) serão gerados"
    )
    if excluded:
        base += f" · {excluded} página(s) fora do corte"
    return base


def filename_preview(
    number: int, title: str, prefix: str = "", suffix: str = "",
    fallback: str = "", numbered: bool = True,
) -> str:
    """Nome exato que o arquivo vai receber, para mostrar embaixo do campo.

    Existe porque o nome final nao e o que o usuario digita: leva o numero do
    capitulo na frente (quando numbered) e o prefixo/sufixo em volta. Sem ver o
    resultado montado, escolher um prefixo vira tentativa e erro.
    """
    escolhido = title.strip() or fallback.strip()
    nome = titles.decorate(escolhido, prefix, suffix)
    return f"{number:02d} - {nome}.pdf" if numbered else f"{nome}.pdf"


def inspector_label(index: int, total: int) -> str:
    return f"Página {index + 1} de {total}"


def colour_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def fit_window_geometry(
    screen_w: int, screen_h: int, target_w: int, target_h: int, min_w: int, min_h: int
) -> str:
    """Geometria "WxH+X+Y" que cabe na tela e fica centralizada.

    O tamanho fixo de antes (1320x860) estourava telas pequenas — um notebook
    de 1366x768 nao sobra espaco para a barra de tarefas. Aqui o tamanho alvo
    encolhe para caber, sem nunca passar do minimo que a tela ainda suporta.
    """
    width = max(min_w, min(target_w, screen_w))
    height = max(min_h, min(target_h, screen_h))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    return f"{width}x{height}+{x}+{y}"


def chapter_ranges(dividers: list[int], page_count: int) -> list[tuple[int, int, int]]:
    """(numero, primeira pagina, ultima pagina) de cada capitulo, base 0.

    Espelha core.build_chapters: paginas antes do primeiro corte formam a
    abertura. Aqui e so para desenhar as faixas na folha.
    """
    if page_count <= 0:
        return []
    starts = sorted(set(dividers))
    if not starts or starts[0] > 0:
        starts.insert(0, 0)
    bounds = starts[1:] + [page_count]
    return [
        (n, s, e - 1) for n, (s, e) in enumerate(zip(starts, bounds), start=1) if e > s
    ]


def open_in_file_manager(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606 - caminho gerado pela propria aplicacao
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def parse_dropped_path(payload: str) -> Path | None:
    """Extrai o caminho do texto que o Windows entrega ao soltar um arquivo.

    Caminhos com espaco vem entre chaves; soltar varios arquivos entrega todos,
    e o primeiro basta.
    """
    payload = payload.strip()
    if not payload:
        return None
    if payload.startswith("{"):
        payload = payload[1:].split("}", 1)[0]
    else:
        payload = payload.split(" ")[0]
    candidate = Path(payload)
    return candidate if candidate.exists() else None


def parse_dropped_paths(payload: str) -> list[Path]:
    """Extrai todos os caminhos do texto que o Windows entrega ao soltar arquivos.

    O TkDND devolve uma lista no formato do Tcl: caminhos com espaco vem entre
    chaves, os demais soltos, tudo separado por espaco. Entradas que nao
    existem mais no disco sao descartadas.
    """
    paths: list[Path] = []
    rest = payload.strip()
    while rest:
        if rest.startswith("{"):
            token, _, rest = rest[1:].partition("}")
            rest = rest.strip()
        else:
            token, _, rest = rest.partition(" ")
            rest = rest.strip()
        if not token:
            continue
        candidate = Path(token)
        if candidate.exists():
            paths.append(candidate)
    return paths


def most_common_extension(paths: list[Path]) -> str:
    """Extensao (minuscula) que mais aparece na lista. Empate: a primeira vista."""
    counts: dict[str, int] = {}
    order: list[str] = []
    for path in paths:
        ext = path.suffix.lower()
        if ext not in counts:
            counts[ext] = 0
            order.append(ext)
        counts[ext] += 1
    return max(order, key=lambda ext: counts[ext])


def has_mixed_formats(paths: list[Path]) -> bool:
    """Diz se a lista tem mais de uma extensao (comparacao sem diferenciar caixa)."""
    return len({p.suffix.lower() for p in paths}) > 1


def filter_by_extension(paths: list[Path], extension: str) -> list[Path]:
    """So os arquivos cuja extensao bate com a informada, preservando a ordem."""
    return [p for p in paths if p.suffix.lower() == extension.lower()]


def batch_confirm_prompt(count: int) -> str:
    return (
        f"Você soltou {count} arquivos.\n\n"
        "Deseja processá-los em lote, todos de uma vez?\n\n"
        "Se preferir, clique em Não para usar apenas o primeiro arquivo."
    )


def mixed_formats_prompt(extensions: set[str]) -> str:
    lista = ", ".join(sorted(extensions))
    return (
        f"Os arquivos soltos têm formatos diferentes ({lista}).\n\n"
        "Deseja processar todos mesmo assim?\n\n"
        "Se preferir, clique em Não para manter apenas os arquivos do formato "
        "mais comum entre eles."
    )


# ------------------------------------------------------------------ janela
class SlidecutApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{WINDOW_TITLE} {VERSION_LABEL}")
        self.root.update_idletasks()
        self.root.geometry(fit_window_geometry(
            root.winfo_screenwidth(), root.winfo_screenheight(),
            WINDOW_WIDTH, WINDOW_HEIGHT, *MIN_SIZE,
        ))
        self.root.minsize(*MIN_SIZE)
        self.root.configure(background=theme.PAPER)
        apply_window_icon(root)

        self.fonts = theme.Fonts(root)
        theme.apply(root, self.fonts)

        self.workdir = Path(tempfile.mkdtemp(prefix="slidecut-gui-"))
        atexit.register(shutil.rmtree, self.workdir, ignore_errors=True)

        self.busy = False
        self.input_path: Path | None = None
        self.document: core.PreparedDocument | None = None
        self.last_result: core.ProcessResult | None = None
        self.last_output_dir: Path | None = None
        self.checkbox_vars: dict[int, tk.BooleanVar] = {}
        """Por pagina: esta pagina abre um capitulo? (a marca de corte)"""
        self.keep_vars: dict[int, tk.BooleanVar] = {}
        """Por pagina: esta pagina entra no arquivo gerado? Vem marcada; quem
        desmarca tira a pagina do corte sem tirar do documento de origem."""
        self.title_vars: dict[int, tk.StringVar] = {}
        self.cards: dict[int, dict] = {}
        self.thumbnail_images: list[tk.PhotoImage] = []
        self.chapter_bands: list[ttk.Frame] = []
        self._suggested: set[int] = set()
        self._placement: dict[int, tuple[int, int]] = {}
        self._reflow_job: str | None = None
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._focused: int | None = None
        """Pagina aberta no painel de inspecao — "estou olhando esta"."""
        self._matrix_page: int | None = None
        self._inspect_image: tk.PhotoImage | None = None
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.numbered_var = tk.BooleanVar(value=False)
        """Comeca desmarcado por pedido explicito: numerar e opcional, o
        usuario liga quando quiser."""

        self._build_header()
        self._build_credit_strip()
        self._build_open_screen()
        self._build_sheet_screen()
        self._build_batch_screen()
        self._show_open()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(30, self._drain_events)
        self._check_for_update()

    # ------------------------------------------------------------- chrome
    def _build_header(self) -> None:
        bar = tk.Frame(self.root, background=theme.INK, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        mark = tk.Canvas(bar, width=30, height=32, background=theme.INK,
                         highlightthickness=0, bd=0)
        mark.pack(side="left", padx=(18, 10))
        mark.create_rectangle(1, 6, 19, 13, fill=theme.CUT, outline="")
        mark.create_rectangle(1, 12, 19, 18, fill="#DCE3EA", outline="")
        mark.create_rectangle(8, 16, 26, 23, fill=theme.CUT, outline="")
        mark.create_rectangle(8, 22, 26, 28, fill="#DCE3EA", outline="")

        ttk.Label(bar, text="SLIDECUT", style="Brand.TLabel").pack(side="left")
        tk.Label(bar, text=VERSION_LABEL, font=self.fonts.tiny, background=theme.INK,
                foreground=theme.CUT, padx=0).pack(side="left", padx=(6, 0), pady=(6, 0))
        self.header_file = ttk.Label(bar, text="", style="BrandSub.TLabel")
        self.header_file.pack(side="left", padx=16)

        # Aviso de atualizacao: escondido ate a checagem em segundo plano
        # confirmar que existe uma versao mais nova. Clicavel — abre a pagina
        # de downloads no navegador; o programa nunca baixa nem instala nada
        # sozinho.
        self.update_notice = tk.Label(
            bar, text="", font=self.fonts.small, background=theme.INK,
            foreground=theme.CUT, cursor="hand2",
        )
        self.update_notice.bind("<Button-1>", lambda _e: self._on_update_notice_click())


    def _build_credit_strip(self) -> None:
        """Faixa fina e discreta no rodape, visivel em qualquer tela."""
        strip = tk.Frame(self.root, background=theme.PAPER, height=22)
        strip.pack(side="bottom", fill="x")
        strip.pack_propagate(False)
        tk.Label(strip, text=CREDIT, background=theme.PAPER, foreground=theme.SLATE_LIGHT,
                font=self.fonts.tiny).pack(side="right", padx=12)

    def _build_mode_tabs(self, parent: tk.Widget, active: str) -> None:
        """Abas 'Um arquivo' / 'Vários arquivos de uma vez', no topo do cartão.

        Existia so um link discreto no rodape da tela e um botao pequeno no
        cabecalho escuro — ambos passavam despercebidos (feedback real de uso).
        Aba e o padrao que ninguem deixa de notar: e a primeira coisa vista ao
        abrir a tela, nao um extra que precisa ser descoberto.
        """
        tabs = tk.Frame(parent, background=theme.SURFACE)
        tabs.pack(fill="x")
        self._make_tab(tabs, "Um arquivo", active == "single", self._show_open)
        self._make_tab(tabs, "Vários arquivos de uma vez", active == "batch", self._show_batch)

    def _make_tab(self, parent: tk.Widget, text: str, is_active: bool, command) -> None:
        fill = theme.SURFACE if is_active else theme.SURFACE_SUNK
        fg = theme.INK if is_active else theme.SLATE
        font = self.fonts.body_bold if is_active else self.fonts.body

        outer = tk.Frame(parent, background=fill, cursor="hand2")
        outer.pack(side="left", fill="both", expand=True)
        label = tk.Label(outer, text=text, background=fill, foreground=fg, font=font, pady=13)
        label.pack(fill="both", expand=True)
        # Sublinha na cor do topo (INK), nao dourado: dourado e reservado para
        # "cortar aqui" em algum lugar do fluxo, e escolher a aba nao e um corte.
        tk.Frame(outer, background=theme.INK if is_active else fill, height=3).pack(
            fill="x", side="bottom")

        for widget in (outer, label):
            widget.bind("<Button-1>", lambda _e: command())

    # -------------------------------------------------------- tela: abrir
    def _build_open_screen(self) -> None:
        self.open_screen = ttk.Frame(self.root, style="Paper.TFrame")

        footer = tk.Frame(self.open_screen, background=theme.SURFACE, height=68)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, background=theme.EDGE, height=1).pack(fill="x")
        self.open_status = ttk.Label(footer, text="", style="SurfaceMuted.TLabel")
        self.open_status.pack(side="left", padx=24)
        self.analyse_button = theme.RoundedButton(
            footer, "ABRIR PÁGINAS", command=self._on_analyse,
            kind="primary", fonts=self.fonts, background=theme.SURFACE, min_width=190)
        self.analyse_button.pack(side="right", padx=24, pady=13)

        outer = ttk.Frame(self.open_screen, style="Paper.TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(outer, background=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.EDGE, highlightcolor=theme.EDGE)
        card.pack()

        self._build_mode_tabs(card, active="single")

        inner = ttk.Frame(card, style="Surface.TFrame", padding=(36, 30, 36, 26))
        inner.pack()

        ttk.Label(inner, text="A B R I R   A R Q U I V O",
                  style="SurfaceSection.TLabel").pack(anchor="w")
        ttk.Label(inner, text="Escolha a apresentação, o documento",
                  style="SurfaceTitle.TLabel").pack(anchor="w", pady=(10, 0))
        ttk.Label(inner, text="ou o PDF que você quer cortar.",
                  style="SurfaceTitle.TLabel").pack(anchor="w")

        self.drop_zone = tk.Frame(inner, background=theme.SURFACE_SUNK,
                                  highlightthickness=1, highlightbackground="#C4CED9")
        self.drop_zone.pack(fill="x", pady=(20, 0), ipady=22)

        icon = tk.Canvas(self.drop_zone, width=54, height=44,
                         background=theme.SURFACE_SUNK, highlightthickness=0)
        icon.pack(pady=(4, 8))
        icon.create_rectangle(2, 4, 32, 14, fill="#C4D0DC", outline="")
        icon.create_rectangle(2, 12, 32, 20, fill="#E9EEF3", outline="")
        icon.create_rectangle(14, 20, 44, 30, fill=theme.CUT, outline="")
        icon.create_rectangle(14, 28, 44, 38, fill="#F2F6FA", outline="")

        self.drop_label = ttk.Label(self.drop_zone, text="Arraste o(s) arquivo(s) para cá",
                                    style="SunkTitle.TLabel")
        self.drop_label.pack()
        ttk.Label(self.drop_zone, text="pptx · docx · pdf e outros",
                  style="SunkFaint.TLabel").pack(pady=(6, 12))
        self.pick_input_button = theme.RoundedButton(
            self.drop_zone, "Procurar no computador", command=self._pick_input,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE_SUNK,
        )
        self.pick_input_button.pack()

        self.chosen_label = ttk.Label(inner, text="", style="SurfaceChosen.TLabel")
        self.chosen_label.pack(anchor="w", pady=(14, 0))

        ttk.Label(inner, text="P A S T A   D E   S A Í D A",
                  style="SurfaceSection.TLabel").pack(anchor="w", pady=(18, 6))
        outrow = ttk.Frame(inner, style="Surface.TFrame")
        outrow.pack(fill="x")
        self.outdir_var = tk.StringVar()
        ttk.Entry(outrow, textvariable=self.outdir_var, width=48).pack(
            side="left", fill="x", expand=True)
        self.pick_outdir_button = theme.RoundedButton(
            outrow, "Escolher...", command=self._pick_outdir,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE)
        self.pick_outdir_button.pack(side="left", padx=(10, 0))

        self.ascii_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner, text="Nomes de arquivo sem acento",
                        variable=self.ascii_var).pack(anchor="w", pady=(14, 0))

        # --- o que fazer com o arquivo ---
        ttk.Label(inner, text="O   Q U E   F A Z E R",
                  style="SurfaceSection.TLabel").pack(anchor="w", pady=(20, 6))
        self.mode_var = tk.StringVar(value="cortar")
        for rotulo, valor in MODE_CHOICES:
            ttk.Radiobutton(inner, text=rotulo, value=valor, variable=self.mode_var,
                            command=self._on_mode_changed).pack(anchor="w")

        # Formato de saida: so faz sentido no modo converter.
        self.target_row = ttk.Frame(inner, style="Surface.TFrame")
        self.target_var = tk.StringVar(value="pdf")
        ttk.Label(self.target_row, text="Converter para:",
                  style="SurfaceMuted.TLabel").pack(side="left", padx=(20, 8))
        ttk.Combobox(
            self.target_row, state="readonly", width=26,
            values=[rotulo for rotulo, _ in TARGET_CHOICES],
            textvariable=tk.StringVar(value=TARGET_CHOICES[0][0]),
        ).pack(side="left")
        self.target_row.children["!combobox"].bind(
            "<<ComboboxSelected>>", self._on_target_changed)
        self.target_combo = self.target_row.children["!combobox"]

        ttk.Label(inner, text="P Á G I N A S   P O R   F O L H A",
                  style="SurfaceSection.TLabel").pack(anchor="w", pady=(18, 6))
        self.per_sheet_var = tk.IntVar(value=DEFAULT_PER_SHEET)
        self.layout_combo = ttk.Combobox(
            inner, state="readonly", width=34,
            values=[rotulo for rotulo, _ in LAYOUT_CHOICES],
        )
        self.layout_combo.current(
            [valor for _, valor in LAYOUT_CHOICES].index(DEFAULT_PER_SHEET))
        self.layout_combo.pack(anchor="w")
        self.layout_combo.bind("<<ComboboxSelected>>", self._on_layout_changed)
        ttk.Label(
            inner,
            text="Agrupar reduz as folhas para impressão; o tamanho do arquivo muda pouco.",
            style="SurfaceFaint.TLabel", wraplength=440, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self.open_progress = ttk.Progressbar(
            self.open_screen, mode="indeterminate", style="Cut.Horizontal.TProgressbar")

        self._on_mode_changed()
        self._enable_drop_target()

    def _enable_drop_target(self) -> None:
        if DND_FILES is None or not hasattr(self.root, "drop_target_register"):
            self.drop_label.configure(text="Escolha o arquivo abaixo")
            return
        for widget in (self.drop_zone, self.drop_label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.dnd_bind("<<DragEnter>>", lambda _e: self._highlight_drop(True))
            widget.dnd_bind("<<DragLeave>>", lambda _e: self._highlight_drop(False))

    def _highlight_drop(self, active: bool) -> None:
        self.drop_zone.configure(
            background=theme.CUT_SOFT if active else theme.SURFACE_SUNK,
            highlightbackground=theme.CUT if active else "#C4CED9",
        )

    def _on_drop(self, event) -> None:
        self._highlight_drop(False)
        if self.busy:
            return

        paths = parse_dropped_paths(event.data)
        if not paths:
            messagebox.showwarning(WINDOW_TITLE, "Não consegui ler o(s) arquivo(s) solto(s) na janela.")
            return

        if len(paths) == 1:
            self._set_input(paths[0])
            return

        if not messagebox.askyesno(WINDOW_TITLE, batch_confirm_prompt(len(paths))):
            self._set_input(paths[0])
            return

        if has_mixed_formats(paths):
            if not messagebox.askyesno(WINDOW_TITLE, mixed_formats_prompt(
                {p.suffix.lower() for p in paths}
            )):
                paths = filter_by_extension(paths, most_common_extension(paths))

        self._show_batch()
        self._batch_set_files(paths)

    def _batch_set_files(self, paths: list[Path]) -> None:
        """Substitui a lista do lote pelos arquivos informados."""
        self._batch_files = []
        self.batch_listbox.delete(0, "end")
        for path in paths:
            if path not in self._batch_files:
                self._batch_files.append(path)
                self.batch_listbox.insert("end", path.name)
        self.batch_status.configure(text=f"{len(self._batch_files)} arquivo(s) na lista")

    # ------------------------------------------------------- tela: folha
    def _build_sheet_screen(self) -> None:
        self.sheet_screen = ttk.Frame(self.root, style="Paper.TFrame")

        self._build_sheet_toolbar()
        tk.Frame(self.sheet_screen, background=theme.EDGE, height=1).pack(fill="x")
        self._build_sheet_footer()

        body = ttk.Frame(self.sheet_screen, style="Paper.TFrame")
        body.pack(fill="both", expand=True)

        self._build_inspector(body)

        grid_area = ttk.Frame(body, style="Paper.TFrame")
        grid_area.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(
            grid_area, background=theme.PAPER, highlightthickness=0, bd=0,
            yscrollincrement=SCROLL_STEP,
        )
        # Sem yscrollincrement, o Windows rola em passos minusculos e mal
        # alinhados: cada notch do mouse dispara varios blits parciais em
        # pixels fracionados (pior ainda com a janela DPI-aware, onde a escala
        # nao e um numero inteiro), e o resultado e o rastro visivel ao rolar.
        # Um passo fixo em pixels inteiros faz o Windows mover um bloco so.
        scrollbar = ttk.Scrollbar(grid_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = ttk.Frame(self.canvas, style="Paper.TFrame", padding=(20, 16))
        self.sheet_window = self.canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.wait_overlay = theme.WaitOverlay(self.sheet_screen, self.fonts)

    def _build_sheet_toolbar(self) -> None:
        """Duas faixas: o que fazer com as marcas, e como nomear o que sai."""
        toolbar = tk.Frame(self.sheet_screen, background=theme.SURFACE)
        toolbar.pack(fill="x")

        row = tk.Frame(toolbar, background=theme.SURFACE)
        row.pack(fill="x", padx=24, pady=(14, 8))

        left = tk.Frame(row, background=theme.SURFACE)
        left.pack(side="left")
        ttk.Label(left, text="Marque onde cada corte começa",
                  style="Surface.TLabel").pack(anchor="w")
        ttk.Label(left, text="Clique numa página para vê-la de perto. Dois cliques abrem maior.",
                  style="SurfaceFaint.TLabel").pack(anchor="w")

        # As acoes vao a direita e o resumo desce para a faixa de baixo: quando
        # os dois dividiam esta linha, o botao de limpar ficava cortado nas
        # janelas mais estreitas.
        actions = tk.Frame(row, background=theme.SURFACE)
        actions.pack(side="right")
        self.suggest_button = theme.RoundedButton(
            actions, "Marcar pela cor", command=self._apply_suggestion,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE)
        self.suggest_button.pack(side="left")
        self.matrix_button = theme.RoundedButton(
            actions, "Slide matriz", command=self._use_focused_as_matrix,
            kind="matrix", fonts=self.fonts, background=theme.SURFACE)
        self.matrix_button.pack(side="left", padx=8)
        self.clear_button = theme.RoundedButton(
            actions, "✕  Limpar marcações", command=self._clear_selection,
            kind="danger", fonts=self.fonts, background=theme.SURFACE)
        self.clear_button.pack(side="left")

        naming = tk.Frame(toolbar, background=theme.SURFACE_SUNK)
        naming.pack(fill="x")
        tk.Frame(naming, background=theme.EDGE_SOFT, height=1).pack(fill="x")
        inner = tk.Frame(naming, background=theme.SURFACE_SUNK)
        inner.pack(fill="x", padx=24, pady=10)

        ttk.Label(inner, text="N O M E   D O S   A R Q U I V O S",
                  style="SunkSection.TLabel").pack(side="left", padx=(0, 14))
        ttk.Label(inner, text="Antes:", style="SunkMuted.TLabel").pack(side="left")
        ttk.Entry(inner, textvariable=self.prefix_var, width=16).pack(side="left", padx=(6, 14))
        ttk.Label(inner, text="Depois:", style="SunkMuted.TLabel").pack(side="left")
        ttk.Entry(inner, textvariable=self.suffix_var, width=16).pack(side="left", padx=(6, 0))

        # selectcolor era igual ao fundo: a caixinha marcada ficava invisivel,
        # e o texto cinza-claro sumia perto dos rotulos em negrito ao lado —
        # motivo do usuario nao perceber que a opcao existia.
        self.numbered_check = tk.Checkbutton(
            inner, text="numerar (01, 02...)", variable=self.numbered_var,
            font=self.fonts.body_bold, background=theme.SURFACE_SUNK,
            activebackground=theme.SURFACE_SUNK, foreground=theme.INK,
            activeforeground=theme.INK, selectcolor=theme.SURFACE,
            bd=0, highlightthickness=0, cursor="hand2",
            command=self._on_numbered_touched,
        )
        self.numbered_check.pack(side="left", padx=(18, 0))

        self.summary_label = ttk.Label(inner, text="", style="SunkMuted.TLabel")
        self.summary_label.pack(side="right")

        for var in (self.prefix_var, self.suffix_var):
            var.trace_add("write", lambda *_a: self._on_naming_changed())

    def _build_inspector(self, parent: tk.Widget) -> None:
        """Painel lateral com a pagina aberta em tamanho grande.

        E um painel encaixado, nao uma janela: o pedido foi ver de perto sem
        sair da tela, e uma caixa flutuante taparia justamente a grade que o
        usuario esta comparando. Aqui a pagina grande fica lado a lado com as
        miniaturas, que e o que a tarefa pede — comparar tons.
        """
        self.inspector = tk.Frame(parent, background=theme.SURFACE, width=INSPECTOR_WIDTH)
        self.inspector.pack_propagate(False)

        tk.Frame(self.inspector, background=theme.EDGE, width=1).pack(side="left", fill="y")
        inner = tk.Frame(self.inspector, background=theme.SURFACE)
        inner.pack(fill="both", expand=True, padx=20, pady=16)

        head = tk.Frame(inner, background=theme.SURFACE)
        head.pack(fill="x")
        self.inspect_title = tk.Label(
            head, text="", font=self.fonts.display, background=theme.SURFACE,
            foreground=theme.INK, anchor="w")
        self.inspect_title.pack(side="left")
        tk.Label(head, text="✕", font=self.fonts.body_bold, background=theme.SURFACE,
                 foreground=theme.SLATE_LIGHT, cursor="hand2", padx=6
                 ).pack(side="right")
        head.winfo_children()[-1].bind("<Button-1>", lambda _e: self._close_inspector())

        self.inspect_caption = tk.Label(
            inner, text="", font=self.fonts.small, background=theme.SURFACE,
            foreground=theme.SLATE, wraplength=INSPECTOR_WIDTH - 60, justify="left", anchor="w")
        self.inspect_caption.pack(fill="x", pady=(2, 12))

        frame = tk.Frame(inner, background=theme.EDGE)
        frame.pack()
        self.inspect_image_label = tk.Label(frame, background=theme.SURFACE_SUNK, bd=0)
        self.inspect_image_label.pack(padx=1, pady=1)

        # A cor lida da pagina e o que decide o corte automatico. Mostrar o
        # quadradinho ao lado do hexadecimal deixa a conta do programa visivel:
        # da para comparar dois slides sem adivinhar por que um virou divisor.
        swatch_row = tk.Frame(inner, background=theme.SURFACE)
        swatch_row.pack(fill="x", pady=(14, 0))
        self.inspect_swatch = tk.Frame(swatch_row, width=26, height=26,
                                       background=theme.EDGE_SOFT,
                                       highlightthickness=1, highlightbackground=theme.EDGE)
        self.inspect_swatch.pack(side="left")
        self.inspect_swatch.pack_propagate(False)
        column = tk.Frame(swatch_row, background=theme.SURFACE)
        column.pack(side="left", padx=(10, 0))
        self.inspect_colour = tk.Label(column, text="", font=self.fonts.code,
                                       background=theme.SURFACE, foreground=theme.INK, anchor="w")
        self.inspect_colour.pack(anchor="w")
        tk.Label(column, text="cor dominante desta página", font=self.fonts.tiny,
                 background=theme.SURFACE, foreground=theme.SLATE_LIGHT, anchor="w").pack(anchor="w")

        self.inspect_badge = tk.Label(inner, text="", font=self.fonts.section,
                                      background=theme.SURFACE, foreground=theme.MATRIX_DARK,
                                      anchor="w")
        self.inspect_badge.pack(fill="x", pady=(10, 0))

        actions = tk.Frame(inner, background=theme.SURFACE)
        actions.pack(fill="x", pady=(14, 0))
        self.inspect_cut_button = theme.RoundedButton(
            actions, "Marcar corte aqui", command=self._toggle_focused_cut,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE,
            min_width=INSPECTOR_WIDTH - 60)
        self.inspect_cut_button.pack(fill="x")
        self.inspect_keep_button = theme.RoundedButton(
            actions, "Tirar do corte", command=self._toggle_focused_keep,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE,
            min_width=INSPECTOR_WIDTH - 60)
        self.inspect_keep_button.pack(fill="x", pady=(8, 0))
        self.inspect_matrix_button = theme.RoundedButton(
            actions, "Usar como slide matriz", command=self._use_focused_as_matrix,
            kind="matrix", fonts=self.fonts, background=theme.SURFACE,
            min_width=INSPECTOR_WIDTH - 60)
        self.inspect_matrix_button.pack(fill="x", pady=(8, 0))

    def _build_sheet_footer(self) -> None:
        footer = tk.Frame(self.sheet_screen, background=theme.SURFACE, height=68)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, background=theme.EDGE, height=1).pack(fill="x")

        self.back_button = theme.RoundedButton(
            footer, "←  Voltar ao início", command=self._show_open,
            kind="ghost", fonts=self.fonts, background=theme.SURFACE)
        self.back_button.pack(side="left", padx=24, pady=13)

        self.sheet_status = ttk.Label(footer, text="", style="SurfaceMuted.TLabel")
        self.sheet_status.pack(side="left")

        self.cut_button = theme.RoundedButton(
            footer, "GERAR OS CORTES", command=self._on_cut,
            kind="primary", fonts=self.fonts, background=theme.SURFACE, min_width=190)
        self.cut_button.pack(side="right", padx=24, pady=13)
        self.open_button = theme.RoundedButton(
            footer, "Abrir pasta", command=self._on_open_outdir,
            kind="quiet", fonts=self.fonts, background=theme.SURFACE)
        self.open_button.configure(state="disabled")
        self.open_button.pack(side="right", pady=13)

        self.sheet_progress = ttk.Progressbar(
            footer, mode="indeterminate", style="Cut.Horizontal.TProgressbar", length=160)

    # -------------------------------------------------------- tela: lote
    def _build_batch_screen(self) -> None:
        self.batch_screen = ttk.Frame(self.root, style="Paper.TFrame")

        self._build_mode_tabs(self.batch_screen, active="batch")

        header = ttk.Frame(self.batch_screen, style="Paper.TFrame", padding=(24, 18, 24, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Vários arquivos de uma vez", style="PaperTitle.TLabel"
                 ).pack(anchor="w")
        ttk.Label(
            header,
            text="Cada arquivo é processado sozinho: um problema num deles não para o resto.",
            style="PaperFaint.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        top = tk.Frame(self.batch_screen, background=theme.PAPER)
        top.pack(fill="x", padx=24, pady=8)
        theme.RoundedButton(top, "+  Adicionar arquivos", command=self._batch_add_files,
                            kind="quiet", fonts=self.fonts, background=theme.PAPER
                            ).pack(side="left")
        theme.RoundedButton(top, "Remover selecionado(s)", command=self._batch_remove_selected,
                            kind="danger", fonts=self.fonts, background=theme.PAPER
                            ).pack(side="left", padx=8)
        theme.RoundedButton(top, "Limpar lista", command=self._batch_clear,
                            kind="ghost", fonts=self.fonts, background=theme.PAPER
                            ).pack(side="left")

        naming = tk.Frame(self.batch_screen, background=theme.PAPER)
        naming.pack(fill="x", padx=24, pady=(2, 6))
        ttk.Label(naming, text="Antes do nome:", style="PaperMuted.TLabel").pack(side="left")
        ttk.Entry(naming, textvariable=self.prefix_var, width=16).pack(side="left", padx=(6, 14))
        ttk.Label(naming, text="Depois:", style="PaperMuted.TLabel").pack(side="left")
        ttk.Entry(naming, textvariable=self.suffix_var, width=16).pack(side="left", padx=(6, 0))
        tk.Checkbutton(
            naming, text="numerar (01, 02...)", variable=self.numbered_var,
            font=self.fonts.body_bold, background=theme.PAPER, activebackground=theme.PAPER,
            foreground=theme.INK, activeforeground=theme.INK, selectcolor=theme.SURFACE,
            bd=0, highlightthickness=0, cursor="hand2", command=self._on_numbered_touched,
        ).pack(side="left", padx=(18, 0))

        self.batch_mode_var = tk.StringVar(value="cortar")
        modes = ttk.Frame(self.batch_screen, style="Paper.TFrame", padding=(24, 4))
        modes.pack(fill="x")
        ttk.Radiobutton(modes, text="Cortar cada arquivo",
                        value="cortar", variable=self.batch_mode_var,
                        command=self._on_batch_mode_changed).pack(side="left")
        ttk.Radiobutton(modes, text="Só converter para PDF",
                        value="converter", variable=self.batch_mode_var,
                        command=self._on_batch_mode_changed).pack(side="left", padx=16)

        self.batch_layout_row = ttk.Frame(self.batch_screen, style="Paper.TFrame",
                                          padding=(24, 4))
        ttk.Label(self.batch_layout_row, text="Páginas por folha:",
                 style="PaperMuted.TLabel").pack(side="left", padx=(0, 8))
        self.batch_layout_combo = ttk.Combobox(
            self.batch_layout_row, state="readonly", width=30,
            values=[rotulo for rotulo, _ in LAYOUT_CHOICES],
        )
        self.batch_layout_combo.current(
            [valor for _, valor in LAYOUT_CHOICES].index(DEFAULT_PER_SHEET))
        self.batch_layout_combo.pack(side="left")

        listwrap = tk.Frame(self.batch_screen, background=theme.SURFACE,
                            highlightthickness=1, highlightbackground=theme.EDGE)
        listwrap.pack(fill="both", expand=True, padx=24, pady=12)
        self.batch_listbox = tk.Listbox(
            listwrap, background=theme.SURFACE, foreground=theme.INK,
            selectbackground=theme.INK_LINE, selectforeground=theme.SURFACE,
            borderwidth=0, highlightthickness=0, font=self.fonts.body, activestyle="none",
            selectmode="extended",
        )
        self.batch_listbox.pack(fill="both", expand=True, padx=1, pady=1)
        self.batch_listbox.bind("<Delete>", lambda _e: self._batch_remove_selected())
        self.batch_listbox.bind("<<ListboxSelect>>", lambda _e: self._batch_update_status())

        footer = tk.Frame(self.batch_screen, background=theme.SURFACE, height=68)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, background=theme.EDGE, height=1).pack(fill="x")
        theme.RoundedButton(footer, "←  Voltar ao início", command=self._show_open,
                            kind="ghost", fonts=self.fonts, background=theme.SURFACE
                            ).pack(side="left", padx=24, pady=13)
        self.batch_status = ttk.Label(footer, text="", style="SurfaceMuted.TLabel")
        self.batch_status.pack(side="left", padx=(0, 24))
        self.batch_run_button = theme.RoundedButton(
            footer, "PROCESSAR TODOS", command=self._on_batch_run,
            kind="primary", fonts=self.fonts, background=theme.SURFACE, min_width=190)
        self.batch_run_button.pack(side="right", padx=24, pady=13)
        self.batch_progress = ttk.Progressbar(
            footer, mode="determinate", style="Cut.Horizontal.TProgressbar", length=200)

        self._batch_files: list[Path] = []
        self._on_batch_mode_changed()

    def _on_batch_mode_changed(self) -> None:
        if self.batch_mode_var.get() == "converter":
            self.batch_layout_row.pack(fill="x")
        else:
            self.batch_layout_row.pack_forget()

    def _batch_add_files(self) -> None:
        if self.busy:
            return
        chosen = filedialog.askopenfilenames(title="Selecione os arquivos",
                                             filetypes=PRIMARY_TYPES)
        for path in chosen:
            candidate = Path(path)
            if candidate not in self._batch_files:
                self._batch_files.append(candidate)
                self.batch_listbox.insert("end", candidate.name)
        self.batch_status.configure(text=f"{len(self._batch_files)} arquivo(s) na lista")

    def _batch_clear(self) -> None:
        self._batch_files.clear()
        self.batch_listbox.delete(0, "end")
        self.batch_status.configure(text="")

    def _batch_remove_selected(self) -> None:
        """Tira da lista os arquivos marcados, sem mexer nos demais."""
        selected = self.batch_listbox.curselection()
        if not selected:
            return
        for index in sorted(selected, reverse=True):
            self.batch_listbox.delete(index)
            del self._batch_files[index]
        self._batch_update_status()

    def _batch_update_status(self) -> None:
        """Mostra quantos arquivos estao selecionados, alem do total na lista."""
        total = len(self._batch_files)
        selected = len(self.batch_listbox.curselection())
        if selected:
            self.batch_status.configure(
                text=f"{selected} de {total} arquivo(s) selecionado(s)")
        else:
            self.batch_status.configure(text=f"{total} arquivo(s) na lista")

    def _on_batch_run(self) -> None:
        if self.busy or not self._batch_files:
            if not self._batch_files:
                messagebox.showwarning(WINDOW_TITLE, "Adicione ao menos um arquivo.")
            return

        outdir = filedialog.askdirectory(title="Pasta de saída para o lote")
        if not outdir:
            return

        mode = self.batch_mode_var.get()
        per_sheet = LAYOUT_CHOICES[self.batch_layout_combo.current()][1]
        files = list(self._batch_files)

        self._set_busy(True)
        self.batch_progress.configure(maximum=len(files), value=0)
        self.batch_progress.pack(side="right", padx=16)
        threading.Thread(
            target=self._run_batch,
            args=(files, outdir, mode, per_sheet,
                  self.prefix_var.get(), self.suffix_var.get(), self.numbered_var.get()),
            daemon=True,
        ).start()

    def _run_batch(self, files: list[Path], outdir: str, mode: str, per_sheet: int,
                   prefix: str = "", suffix: str = "", numbered: bool = True) -> None:
        def progress(msg: str) -> None:
            self._events.put(("batch_status", msg))

        def item(index: int, total: int, source: Path) -> None:
            # Canal estruturado, separado do texto de `progress`: a barra nao
            # depende de recortar numero nenhum de dentro de uma mensagem.
            self._events.put(("batch_item", (index, total, source)))

        try:
            if mode == "converter":
                results = core.convert_batch(files, outdir, to="pdf", per_sheet=per_sheet,
                                             on_progress=progress, on_item=item)
            else:
                results = core.process_batch(files, outdir, per_sheet=per_sheet,
                                             on_progress=progress, on_item=item,
                                             prefix=prefix, suffix=suffix, numbered=numbered)
            self._events.put(("batch_done", results))
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _hide_all_screens(self) -> None:
        for screen in (self.open_screen, self.sheet_screen, self.batch_screen):
            screen.pack_forget()

    def _show_open(self) -> None:
        if self.busy:
            return
        self._hide_all_screens()
        self.open_screen.pack(fill="both", expand=True)

    def _show_sheet(self) -> None:
        self._hide_all_screens()
        self.sheet_screen.pack(fill="both", expand=True)

    def _show_batch(self) -> None:
        if self.busy:
            return
        self._hide_all_screens()
        self.batch_screen.pack(fill="both", expand=True)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.sheet_screen.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ------------------------------------------------------------- acoes
    def _set_input(self, path: Path) -> None:
        self.input_path = path
        self.chosen_label.configure(text=f"Selecionado: {path.name}")
        self.header_file.configure(text=path.name)
        self.outdir_var.set(str(core.default_outdir(path)))

    def _pick_input(self) -> None:
        if self.busy:
            return
        chosen = filedialog.askopenfilename(title="Selecione o arquivo", filetypes=PRIMARY_TYPES)
        if chosen:
            self._set_input(Path(chosen))

    def _on_mode_changed(self) -> None:
        """No modo converter aparece o formato de saida; no corte, nao ha escolha."""
        if self.mode_var.get() == "converter":
            self.target_row.pack(anchor="w", pady=(6, 0))
            self.analyse_button.configure(text="CONVERTER")
        else:
            self.target_row.pack_forget()
            self.analyse_button.configure(text="ABRIR PÁGINAS")

    def _on_target_changed(self, _event=None) -> None:
        rotulo = self.target_combo.get()
        for texto, valor in TARGET_CHOICES:
            if texto == rotulo:
                self.target_var.set(valor)
                break

    def _on_layout_changed(self, _event=None) -> None:
        self.per_sheet_var.set(LAYOUT_CHOICES[self.layout_combo.current()][1])

    def _pick_outdir(self) -> None:
        if self.busy:
            return
        chosen = filedialog.askdirectory(title="Pasta de saída")
        if chosen:
            self.outdir_var.set(chosen)

    def _on_analyse(self) -> None:
        if self.busy:
            return
        source = self.input_path
        if source is None:
            messagebox.showwarning(WINDOW_TITLE, "Escolha um arquivo primeiro.")
            return

        if convert.needs_conversion(source):
            converter_name = convert.available_converter(source.suffix)
            if converter_name is None:
                messagebox.showerror(WINDOW_TITLE, no_converter_message(source))
                return
            if not messagebox.askyesno(
                WINDOW_TITLE, conversion_prompt(source, converter_name)
            ):
                self.open_status.configure(text="Conversão cancelada.")
                return

        self.open_status.configure(text="Preparando o arquivo...")
        self._set_busy(True)
        self.open_progress.pack(side="bottom", fill="x")
        self.open_progress.start(12)

        if self.mode_var.get() == "converter":
            threading.Thread(
                target=self._run_convert,
                args=(source, self.outdir_var.get() or str(core.default_outdir(source)),
                      self.target_var.get(), self.per_sheet_var.get()),
                daemon=True,
            ).start()
            return

        threading.Thread(target=self._run_prepare, args=(source,), daemon=True).start()

    def _run_convert(self, source: Path, outdir: str, to: str, per_sheet: int) -> None:
        try:
            produced = core.convert_document(
                source, outdir, to=to, per_sheet=per_sheet,
                on_progress=lambda msg: self._events.put(("status", msg)),
            )
            self._events.put(("converted", (produced, per_sheet)))
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _run_prepare(self, source: Path) -> None:
        try:
            document = core.prepare(
                source, workdir=self.workdir,
                on_progress=lambda msg: self._events.put(("status", msg)),
            )
            self._events.put(("prepared", document))

            thumbnails = preview.render_thumbnails(document.pdf_path, width=THUMBNAIL_WIDTH)
            try:
                for thumb in thumbnails:
                    self._events.put(("thumbnail", thumb))
            finally:
                thumbnails.close()
            self._events.put(("thumbnails_done", document))
        except Exception as exc:  # inclui erros de disco e de leitura fora do dominio
            self._events.put(("error", str(exc)))

    def _on_cut(self) -> None:
        if self.busy or self.document is None:
            return
        dividers = [i for i, var in self.checkbox_vars.items() if var.get()]
        if not dividers:
            messagebox.showwarning(
                WINDOW_TITLE, "Marque pelo menos uma página para começar um corte.")
            return

        excluded = {i for i, var in self.keep_vars.items() if not var.get()}
        if excluded and len(excluded) == len(self.cards):
            messagebox.showwarning(
                WINDOW_TITLE,
                "Todas as páginas estão fora do corte. Marque pelo menos uma "
                "para haver o que gravar.",
            )
            return

        self.open_button.configure(state="disabled")
        self._set_busy(True)
        self.sheet_progress.pack(side="right", padx=16)
        self.sheet_progress.start(12)
        self.wait_overlay.show("Gerando os cortes...")
        custom_titles = {i: self.title_vars[i].get() for i in dividers}
        threading.Thread(
            target=self._run_cut,
            args=(self.document, dividers, self.outdir_var.get() or None,
                  self.ascii_var.get(), custom_titles, self.per_sheet_var.get(),
                  self.prefix_var.get(), self.suffix_var.get(), excluded,
                  self.numbered_var.get()),
            daemon=True,
        ).start()

    def _run_cut(self, document, dividers, outdir, ascii_only, custom_titles,
                 per_sheet=1, prefix="", suffix="", excluded=None, numbered=True) -> None:
        try:
            result = core.cut_at(
                document, dividers, outdir=outdir, ascii_only=ascii_only,
                custom_titles=custom_titles, per_sheet=per_sheet,
                prefix=prefix, suffix=suffix, excluded_pages=excluded, numbered=numbered,
                on_progress=lambda msg: self._events.put(("status", msg)),
            )
            self._events.put(("cut", result))
        except Exception as exc:  # inclui falha de escrita e permissao negada
            self._events.put(("error", str(exc)))

    def _on_open_outdir(self) -> None:
        if self.last_result is not None:
            open_in_file_manager(self.last_result.outdir)

    # ------------------------------------------------------ folha: cartoes
    def _reset_sheet(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.checkbox_vars.clear()
        self.keep_vars.clear()
        self.title_vars.clear()
        self.cards.clear()
        self.chapter_bands.clear()
        self._placement.clear()
        self.thumbnail_images.clear()
        self._matrix_page = None
        self._focused = None
        self._inspect_image = None
        self.inspector.pack_forget()

    def _add_card(self, thumb: preview.Thumbnail) -> None:
        index = thumb.index
        image = tk.PhotoImage(data=thumb.png, master=self.root)
        self.thumbnail_images.append(image)

        # Tamanho travado de proposito. Os cartoes ja tem altura igual nos dois
        # estados; dizer isso ao Tk faz o rearranjo parar de recalcular o
        # tamanho de cada filho — numa folha de 145 paginas essa e a diferenca
        # entre meio segundo de travamento e nenhum.
        shell = tk.Frame(self.grid_frame, background=theme.EDGE,
                         width=CARD_WIDTH, height=image.height() + CARD_EXTRA_HEIGHT)
        shell.pack_propagate(False)
        shell.grid_propagate(False)
        body = tk.Frame(shell, background=theme.SURFACE)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        rail = tk.Frame(body, background=theme.SURFACE, width=4)
        rail.pack(side="left", fill="y")

        content = tk.Frame(body, background=theme.SURFACE, padx=12, pady=12)
        content.pack(side="left", fill="both", expand=True)

        holder = tk.Frame(content, background=theme.SURFACE)
        holder.pack()
        thumb_label = tk.Label(holder, image=image, background=theme.SURFACE, bd=0)
        thumb_label.pack()
        number = tk.Label(holder, text=f"{index + 1:03d}", font=self.fonts.number,
                          background=theme.INK, foreground=theme.SURFACE, padx=5, pady=1)
        number.place(x=0, y=0)

        # Marca de corte com nome escrito, no lugar do clique-em-qualquer-lugar
        # que existia antes: quem ligou por engano nao adivinhava como desligar.
        cut_tag = tk.Label(content, text=CUT_OFF_LABEL, font=self.fonts.section,
                           background=theme.SURFACE_SUNK, foreground=theme.SLATE,
                           cursor="hand2", pady=5)
        cut_tag.pack(fill="x", pady=(10, 0))

        keep = tk.BooleanVar(value=True)
        keep_box = tk.Checkbutton(
            content, text="entra no corte", variable=keep, font=self.fonts.tiny,
            background=theme.SURFACE, activebackground=theme.SURFACE,
            foreground=theme.KEEP, activeforeground=theme.KEEP, selectcolor=theme.SURFACE,
            bd=0, highlightthickness=0, padx=0, cursor="hand2", anchor="w",
        )
        keep_box.pack(anchor="w", pady=(6, 0))

        caption = tk.Label(content, text=thumb.caption, font=self.fonts.small,
                           background=theme.SURFACE, foreground=theme.SLATE_LIGHT,
                           wraplength=THUMBNAIL_WIDTH, justify="left", anchor="w")
        caption.pack(fill="x", pady=(6, 0))

        name_row = tk.Frame(content, background=theme.SURFACE, height=NAME_ROW_HEIGHT)
        name_row.pack(fill="x", pady=(6, 0))
        name_row.pack_propagate(False)
        name_label = tk.Label(name_row, text="NOME DO ARQUIVO", font=self.fonts.section,
                              background=theme.SURFACE, foreground=theme.CUT, anchor="w")
        title_var = tk.StringVar(value=thumb.title)
        # O nome aparece como rotulo; o campo editavel so e criado no cartao em
        # foco (ver _mount_entry). Um ttk.Entry e um controle nativo do Windows,
        # e centenas deles dentro do canvas rolavel arrastam fantasmas na tela
        # e deixam a rolagem pesada — num documento com 360 cortes marcados eram
        # 360 controles nativos sendo movidos a cada notch do mouse.
        name_value = tk.Label(name_row, text=thumb.title, font=self.fonts.small,
                              background=theme.SURFACE_SUNK, foreground=theme.INK,
                              anchor="w", padx=4, cursor="hand2")
        name_preview = tk.Label(name_row, text="", font=self.fonts.tiny,
                                background=theme.SURFACE, foreground=theme.SLATE_LIGHT,
                                anchor="w", wraplength=THUMBNAIL_WIDTH, justify="left")

        checked = tk.BooleanVar(value=index in self._suggested)
        self.checkbox_vars[index] = checked
        self.keep_vars[index] = keep
        self.title_vars[index] = title_var
        self.cards[index] = {
            "shell": shell, "body": body, "rail": rail, "number": number,
            "caption": caption, "name_label": name_label, "entry": None,
            "name_row": name_row, "name_value": name_value,
            "cut_tag": cut_tag, "keep_box": keep_box, "thumb": thumb_label,
            "name_preview": name_preview, "fallback": thumb.title,
        }
        name_value.bind("<Button-1>", lambda _e, i=index: self._focus_page(i))
        title_var.trace_add("write", lambda *_a, i=index, v=name_value: v.configure(
            text=self.title_vars[i].get()))

        # Um clique abre a pagina no painel; dois cliques renderizam maior. A
        # marca de corte tem controle proprio, entao clicar para olhar nunca
        # mexe no que vai ser gerado.
        for widget in (body, content, holder, caption, thumb_label, number):
            widget.bind("<Button-1>", lambda _e, i=index: self._focus_page(i))
            widget.bind("<Double-Button-1>", lambda _e, i=index: self._focus_page(i, big=True))
        cut_tag.bind("<Button-1>", lambda _e, i=index: self._toggle(i))

        checked.trace_add("write", lambda *_a, i=index: self._on_check_changed(i))
        keep.trace_add("write", lambda *_a, i=index: self._on_keep_changed(i))
        title_var.trace_add("write", lambda *_a, i=index: self._refresh_name_preview(i))
        self._paint_card(index)

    def _paint_card(self, index: int) -> None:
        """Marcado muda so a cor, nunca o tamanho: a grade nao pode saltar."""
        parts = self.cards[index]
        marked = self.checkbox_vars[index].get()
        kept = self.keep_vars[index].get()
        focused = self._focused == index
        is_matrix = self._matrix_page == index

        if focused:
            border = theme.FOCUS
        elif is_matrix:
            border = theme.MATRIX
        elif marked:
            border = theme.CUT
        else:
            border = theme.EDGE
        parts["shell"].configure(background=border)

        parts["rail"].configure(background=theme.CUT if marked else theme.SURFACE)
        parts["number"].configure(
            background=theme.CUT if marked else (theme.DROP if not kept else theme.INK))
        parts["caption"].configure(
            foreground=theme.INK if marked else (theme.DROP if not kept else theme.SLATE_LIGHT))

        parts["cut_tag"].configure(
            text=CUT_ON_LABEL if marked else CUT_OFF_LABEL,
            background=theme.CUT if marked else theme.SURFACE_SUNK,
            foreground=theme.SURFACE if marked else theme.SLATE,
        )
        parts["keep_box"].configure(
            text="entra no corte" if kept else "fora do corte",
            foreground=theme.KEEP if kept else theme.DANGER_DARK,
            activeforeground=theme.KEEP if kept else theme.DANGER_DARK,
        )

        if marked:
            parts["name_label"].pack(fill="x")
            if focused:
                self._mount_entry(index)
            else:
                self._unmount_entry(index)
                parts["name_value"].pack(fill="x", pady=(2, 0))
            parts["name_preview"].pack(fill="x")
            self._refresh_name_preview(index)
        else:
            self._unmount_entry(index)
            parts["name_label"].pack_forget()
            parts["name_value"].pack_forget()
            parts["name_preview"].pack_forget()

    def _mount_entry(self, index: int) -> None:
        """Cria o campo editavel neste cartao — so o cartao em foco tem um.

        Um ttk.Entry e um controle nativo do Windows. Centenas deles vivendo
        dentro do canvas rolavel e o que deixava a rolagem cheia de fantasmas.
        """
        parts = self.cards[index]
        parts["name_value"].pack_forget()
        if parts["entry"] is None:
            parts["entry"] = ttk.Entry(
                parts["name_row"], textvariable=self.title_vars[index],
                style="Name.TEntry", font=self.fonts.small)
        parts["entry"].pack(fill="x", pady=(2, 0))

    def _unmount_entry(self, index: int) -> None:
        parts = self.cards[index]
        if parts["entry"] is not None:
            parts["entry"].destroy()
            parts["entry"] = None

    def _refresh_name_preview(self, index: int) -> None:
        parts = self.cards.get(index)
        if parts is None or not self.checkbox_vars[index].get():
            return
        marks = sorted(i for i, v in self.checkbox_vars.items() if v.get())
        number = marks.index(index) + 1 if index in marks else 1
        if marks and marks[0] > 0:
            number += 1  # a abertura ocupa o numero 1
        parts["name_preview"].configure(text=filename_preview(
            number, self.title_vars[index].get(),
            self.prefix_var.get(), self.suffix_var.get(), parts["fallback"],
            numbered=self.numbered_var.get(),
        ))

    def _refresh_name_previews(self) -> None:
        for index in list(self.cards):
            self._refresh_name_preview(index)

    def _on_numbered_touched(self) -> None:
        self._refresh_name_previews()

    def _on_naming_changed(self) -> None:
        """Prefixo/sufixo mudou: so atualiza a previa. Numerar fica como o
        usuario deixou — nao se mexe mais sozinho."""
        self._refresh_name_previews()

    def _toggle(self, index: int) -> None:
        var = self.checkbox_vars.get(index)
        if var is not None:
            var.set(not var.get())

    def _on_check_changed(self, index: int) -> None:
        self._paint_card(index)
        self._refresh_summary()
        self._refresh_name_previews()
        self._schedule_reflow()
        if self._focused == index:
            self._refresh_inspector_actions()

    def _on_keep_changed(self, index: int) -> None:
        self._paint_card(index)
        self._refresh_summary()
        if self._focused == index:
            self._refresh_inspector_actions()

    # -------------------------------------------------- painel de inspecao
    def _focus_page(self, index: int, big: bool = False) -> None:
        """Abre a pagina no painel lateral. Dois cliques pedem o render maior."""
        if self.document is None or index not in self.cards:
            return

        previous, self._focused = self._focused, index
        if previous is not None and previous in self.cards:
            self._paint_card(previous)
        self._paint_card(index)

        # winfo_manager() e nao winfo_ismapped(): a pergunta e "ja esta
        # encaixado?", nao "ja esta pintado?" — a segunda responde nao enquanto
        # a janela nao terminou de aparecer, e o painel abriria duas vezes.
        if not self.inspector.winfo_manager():
            self.inspector.pack(side="right", fill="y")
            # A grade perdeu largura: sem recontar as colunas, os cartoes ficam
            # escondidos atras do painel em vez de reencaixarem.
            self._schedule_reflow()

        width = preview.INSPECT_WIDTH if big else INSPECT_DOCKED_WIDTH
        try:
            page = preview.render_page(self.document.pdf_path, index, width=width)
            rgb = analyze.page_color(self.document.pdf_path, index)
        except (OSError, IndexError, SlidecutError):
            # Pagina que nao renderiza nao pode derrubar a tela inteira: a
            # grade continua utilizavel e o usuario segue marcando cortes.
            self.inspect_caption.configure(text="Não consegui abrir esta página de perto.")
            return

        self._inspect_image = tk.PhotoImage(data=page.png, master=self.root)
        self.inspect_image_label.configure(image=self._inspect_image)
        self.inspect_title.configure(text=inspector_label(index, len(self.cards)))
        self.inspect_caption.configure(text=page.caption)
        self.inspect_swatch.configure(background=colour_hex(rgb))
        self.inspect_colour.configure(text=colour_hex(rgb))
        self._refresh_inspector_actions()

    def _refresh_inspector_actions(self) -> None:
        index = self._focused
        if index is None:
            return
        marked = self.checkbox_vars[index].get()
        kept = self.keep_vars[index].get()

        self.inspect_cut_button.configure(
            text="Tirar a marca de corte" if marked else "Marcar corte aqui")
        self.inspect_keep_button.configure(
            text="Trazer de volta para o corte" if not kept else "Tirar esta página do corte")
        self.inspect_badge.configure(
            text="SLIDE MATRIZ — a cor desta página define o corte"
            if self._matrix_page == index else ""
        )

    def _close_inspector(self) -> None:
        previous, self._focused = self._focused, None
        self.inspector.pack_forget()
        if previous is not None and previous in self.cards:
            self._paint_card(previous)
        self._schedule_reflow()

    def _toggle_focused_cut(self) -> None:
        if self._focused is not None:
            self._toggle(self._focused)

    def _toggle_focused_keep(self) -> None:
        if self._focused is None:
            return
        var = self.keep_vars[self._focused]
        var.set(not var.get())

    def _use_focused_as_matrix(self) -> None:
        """Reaplica a deteccao usando a cor da pagina aberta no painel.

        As marcas anteriores sao substituidas: escolher uma matriz e dizer "o
        padrao e este", e manter marcas do palpite antigo misturaria dois
        criterios sem o usuario perceber.
        """
        if self.document is None:
            return
        if self._focused is None:
            messagebox.showinfo(
                WINDOW_TITLE,
                "Clique primeiro na página que serve de modelo — a que tem a cor "
                "que separa os cortes. Depois use este botão.",
            )
            return

        index = self._focused
        self.wait_overlay.show("Aplicando o slide matriz...")
        threading.Thread(target=self._run_matrix, args=(index,), daemon=True).start()

    def _run_matrix(self, index: int) -> None:
        """A leitura da cor sai da thread da janela: mesmo reaproveitando as
        cores ja calculadas, renderizar a pagina escolhida leva um instante, e
        a janela nao pode congelar nesse meio tempo."""
        try:
            rgb = analyze.page_color(self.document.pdf_path, index)
            # colors=self.document.colors reaproveita o que prepare() ja
            # calculou. Sem isso, find_dividers renderiza o PDF inteiro de novo
            # do zero, pagina por pagina — foi o que travou o PC do usuario.
            encontrados = analyze.find_dividers(
                self.document.pdf_path, color=rgb, colors=self.document.colors)
        except (OSError, IndexError, SlidecutError) as exc:
            self._events.put(("matrix_failed", str(exc)))
            return
        self._events.put(("matrix_done", (index, rgb, encontrados)))

    def _apply_matrix_result(self, index: int, rgb, encontrados) -> None:
        self.wait_overlay.hide()
        self._matrix_page = index
        alvo = set(encontrados) or {index}
        for page, var in self.checkbox_vars.items():
            var.set(page in alvo)

        for page in list(self.cards):
            self._paint_card(page)
        self._refresh_inspector_actions()
        self.sheet_status.configure(
            text=f"Slide matriz: página {index + 1} ({colour_hex(rgb)}) · "
                 f"{len(alvo)} corte(s) marcado(s)"
        )

    def _schedule_reflow(self) -> None:
        if self._reflow_job is not None:
            self.root.after_cancel(self._reflow_job)
        self._reflow_job = self.root.after(REFLOW_DELAY_MS, self._reflow)

    def _columns(self) -> int:
        width = max(self.canvas.winfo_width(), MIN_SIZE[0])
        card_width = CARD_WIDTH + CARD_PAD * 2
        return max(1, (width - 40) // card_width)

    def _reflow(self) -> None:
        """Reagrupa a folha em capitulos: cada corte abre uma faixa nova.

        Numa folha de 145 paginas, reposicionar tudo de uma vez segura a janela
        por mais de meio segundo. Entao o trabalho e planejado de uma vez (custo
        desprezivel) e aplicado em blocos, um pedaco por ciclo do Tk: a folha se
        reorganiza a vista e a janela nunca trava.
        """
        self._reflow_job = None
        if not self.cards:
            return

        dividers = {i for i, var in self.checkbox_vars.items() if var.get()}
        ranges = chapter_ranges(sorted(dividers), len(self.cards))
        columns = self._columns()

        moves: list[tuple[int, int, int]] = []
        row = 0
        for slot, (number, first, last) in enumerate(ranges):
            title = self.title_vars[first].get() if first in dividers else "Abertura"
            band = self._band(slot)
            self._fill_band(band, number, title, last - first + 1)
            if band.grid_info().get("row") != row:
                band.grid(row=row, column=0, columnspan=columns, sticky="ew", pady=(14, 8))
            row += 1

            for offset, index in enumerate(range(first, last + 1)):
                position = (row + offset // columns, offset % columns)
                if self._placement.get(index) != position:
                    moves.append((index, *position))
            row += (last - first) // columns + 1

        for extra in self.chapter_bands[len(ranges):]:
            extra.grid_remove()

        self._apply_moves(moves)

    def _apply_moves(self, moves: list[tuple[int, int, int]]) -> None:
        for index, row, column in moves:
            self.cards[index]["shell"].grid(
                row=row, column=column, padx=CARD_PAD, pady=CARD_PAD, sticky="n")
            self._placement[index] = (row, column)

    def _band(self, slot: int) -> ttk.Frame:
        """Faixa de capitulo do pool, criando so quando o pool acaba."""
        while slot >= len(self.chapter_bands):
            band = ttk.Frame(self.grid_frame, style="Paper.TFrame")
            tk.Frame(band, background="#CED6DE", height=1).pack(fill="x")
            tk.Frame(band, background=theme.CUT, height=2, width=46).place(x=0, y=0)

            row = ttk.Frame(band, style="Paper.TFrame")
            row.pack(fill="x", pady=(8, 0))
            band.number = ttk.Label(row, text="", style="PaperSection.TLabel")  # type: ignore[attr-defined]
            band.number.pack(side="left")  # type: ignore[attr-defined]
            band.title = ttk.Label(row, text="", font=self.fonts.body_bold,  # type: ignore[attr-defined]
                                   background=theme.PAPER, foreground=theme.INK)
            band.title.pack(side="left", padx=14)  # type: ignore[attr-defined]
            band.count = ttk.Label(row, text="", style="PaperMuted.TLabel")  # type: ignore[attr-defined]
            band.count.pack(side="right")  # type: ignore[attr-defined]
            self.chapter_bands.append(band)
        return self.chapter_bands[slot]

    @staticmethod
    def _fill_band(band: ttk.Frame, number: int, title: str, pages: int) -> None:
        band.number.configure(text=f"C O R T E  {number:02d}")  # type: ignore[attr-defined]
        band.title.configure(text=title)  # type: ignore[attr-defined]
        band.count.configure(text=f"{pages} página(s)")  # type: ignore[attr-defined]
        if not band.winfo_ismapped():
            band.grid()

    def _apply_suggestion(self) -> None:
        if self.document is None:
            return
        suggested = set(self.document.suggested_dividers)
        for index, var in self.checkbox_vars.items():
            var.set(index in suggested)

    def _clear_selection(self) -> None:
        """Tira tudo: marcas de corte, paginas fora do corte e o slide matriz.

        Um botao chamado "limpar marcacoes" que deixasse metade das marcas de pe
        seria pior do que nao existir — a saida tem de voltar ao estado inicial.
        """
        self._matrix_page = None
        for var in self.checkbox_vars.values():
            var.set(False)
        for var in self.keep_vars.values():
            var.set(True)
        for index in list(self.cards):
            self._paint_card(index)
        self._refresh_inspector_actions()
        self.sheet_status.configure(text="Marcações apagadas.")

    def _refresh_summary(self) -> None:
        selected = sum(1 for var in self.checkbox_vars.values() if var.get())
        excluded = sum(1 for var in self.keep_vars.values() if not var.get())
        self.summary_label.configure(
            text=selection_summary(selected, len(self.checkbox_vars), excluded))

    # ---------------------------------------------------------- plumbing
    def _set_busy(self, busy: bool) -> None:
        """Trava a janela inteira: dois trabalhos gravariam no mesmo temporario."""
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.analyse_button, self.cut_button, self.back_button,
            self.pick_input_button, self.pick_outdir_button,
            self.suggest_button, self.clear_button, self.batch_run_button,
            self.matrix_button, self.inspect_cut_button, self.inspect_keep_button,
            self.inspect_matrix_button,
        ):
            widget.configure(state=state)

    def _stop_progress(self) -> None:
        for bar in (self.open_progress, self.sheet_progress):
            bar.stop()
            bar.pack_forget()
        self.wait_overlay.hide()

    def _drain_events(self) -> None:
        try:
            for _ in range(EVENTS_PER_TICK):
                kind, payload = self._events.get_nowait()
                if kind == "status":
                    self.open_status.configure(text=str(payload))
                    self.sheet_status.configure(text=str(payload))
                elif kind == "prepared":
                    self.document = payload
                    self._suggested = set(payload.suggested_dividers)
                    self._reset_sheet()
                    self._show_sheet()
                elif kind == "thumbnail":
                    self._add_card(payload)
                    self._refresh_summary()
                elif kind == "thumbnails_done":
                    self._set_busy(False)
                    self._stop_progress()
                    self._reflow()
                    self._refresh_summary()
                    self.sheet_status.configure(text="")
                elif kind == "batch_item":
                    # Unico responsavel por mover a barra: indice estruturado,
                    # nunca derivado de texto.
                    index, total, source = payload
                    self.batch_progress.configure(maximum=total, value=index - 1)
                    self.batch_status.configure(text=batch_item_label(index, total, source))
                elif kind == "batch_status":
                    self.batch_status.configure(text=str(payload))
                elif kind == "batch_done":
                    self._set_busy(False)
                    self.batch_progress.pack_forget()
                    self.batch_progress.configure(value=len(payload))
                    self.batch_status.configure(text=batch_summary(payload))
                    messagebox.showinfo(WINDOW_TITLE, batch_summary(payload))
                elif kind == "converted":
                    produced, per_sheet = payload
                    self._set_busy(False)
                    self._stop_progress()
                    self.open_status.configure(text=f"Gravado: {produced.name}")
                    self.last_output_dir = produced.parent
                    messagebox.showinfo(
                        WINDOW_TITLE, conversion_summary(produced, per_sheet))
                    open_in_file_manager(produced.parent)
                elif kind == "cut":
                    self.last_result = payload
                    self._set_busy(False)
                    self._stop_progress()
                    self.open_button.configure(state="normal")
                    messagebox.showinfo(WINDOW_TITLE, format_result_summary(payload))
                    # Abre a pasta sozinho, como o modo converter ja fazia:
                    # terminar o corte e sempre seguido de ir ver os arquivos.
                    open_in_file_manager(payload.outdir)
                elif kind == "matrix_done":
                    self._apply_matrix_result(*payload)
                elif kind == "matrix_failed":
                    self.wait_overlay.hide()
                    messagebox.showerror(
                        WINDOW_TITLE, f"Não consegui ler a cor desta página.\n\n{payload}")
                elif kind == "update":
                    self._show_update_notice(payload)
                elif kind == "update_ready":
                    self._launch_installer(payload)
                elif kind == "update_failed":
                    self._updating = False
                    self.update_notice.configure(
                        text=f"Nova versão disponível: v{self._update_version} →",
                        cursor="hand2")
                    messagebox.showerror(
                        WINDOW_TITLE,
                        f"Não consegui atualizar automaticamente.\n\n{payload}\n\n"
                        "Você pode baixar manualmente pelo navegador.",
                    )
                elif kind == "error":
                    self._set_busy(False)
                    self._stop_progress()
                    self.open_status.configure(text="")
                    messagebox.showerror(WINDOW_TITLE, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(30, self._drain_events)

    # ------------------------------------------------------- atualizacao
    def _check_for_update(self) -> None:
        """Dispara a checagem numa thread — nunca pode travar a abertura do app."""
        threading.Thread(target=self._run_check_for_update, daemon=True).start()

    def _run_check_for_update(self) -> None:
        result = updates.check_for_update(__version__)
        if result is not None:
            self._events.put(("update", result))

    def _show_update_notice(self, result: "updates.UpdateAvailable") -> None:
        self._update_version = result.version
        self._update_url = result.url
        self._updating = False
        self.update_notice.configure(text=f"Nova versão disponível: v{result.version} →")
        self.update_notice.pack(side="left", padx=(4, 0))

    def _open_update_page(self) -> None:
        webbrowser.open(getattr(self, "_update_url", updates.RELEASES_URL))

    def _on_update_notice_click(self) -> None:
        """Pergunta como o usuario quer atualizar — nada roda sem essa confirmacao."""
        version = getattr(self, "_update_version", None)
        if version is None or getattr(self, "_updating", False):
            return

        if messagebox.askyesno(
            WINDOW_TITLE,
            f"Baixar e instalar a versão v{version} agora?\n\n"
            "O aplicativo vai fechar para concluir a instalação. Escolha "
            "\"Não\" para abrir a página de download no navegador em vez disso.",
        ):
            self._start_update_download(version)
        else:
            self._open_update_page()

    def _start_update_download(self, version: str) -> None:
        self._updating = True
        self.update_notice.configure(text=f"Baixando v{version}...", cursor="watch")
        threading.Thread(target=self._run_download_update, args=(version,), daemon=True).start()

    def _run_download_update(self, version: str) -> None:
        try:
            # Pasta propria, fora do workdir de trabalho: o workdir e apagado
            # ao fechar a janela, e o instalador continua lendo o proprio
            # .exe enquanto roda — nunca guardar ali algo que precisa
            # sobreviver ao fechamento do app.
            dest = Path(tempfile.gettempdir()) / "slidecut-update"
            installer = updates.download_installer(version, dest)
            self._events.put(("update_ready", installer))
        except updates.UpdateDownloadError as exc:
            self._events.put(("update_failed", str(exc)))

    def _launch_installer(self, installer_path: Path) -> None:
        try:
            subprocess.Popen([str(installer_path)], close_fds=True)
        except OSError as exc:
            self._updating = False
            self.update_notice.configure(
                text=f"Nova versão disponível: v{self._update_version} →", cursor="hand2")
            messagebox.showerror(
                WINDOW_TITLE,
                f"Baixei o instalador mas não consegui abrir automaticamente.\n\n{exc}\n\n"
                f"Abra manualmente: {installer_path}",
            )
            return
        self._on_close()

    def _on_close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)
        self.root.destroy()


def apply_window_icon(root: tk.Tk) -> None:
    """Icone na barra de titulo e na barra de tarefas; falhar aqui nao derruba nada."""
    try:
        root.iconbitmap(default=str(resources.icon_path()))
    except (tk.TclError, OSError):
        pass


def _enable_dpi_awareness() -> None:
    """Declara ao Windows que o app desenha na resolucao real do monitor.

    Sem isso, o Windows trata o programa como se ele so soubesse desenhar a
    96 DPI e esbagaca (bitmap-stretch) a janela inteira para bater com a
    escala configurada — 125%, 150% etc. E exatamente o "parece de baixa
    resolucao": o problema nao e o desenho, e o Windows escalando o resultado
    depois de pronto. Precisa rodar antes de qualquer janela existir.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _apply_dpi_scaling(root: tk.Tk) -> None:
    """Ajusta a escala do Tk para bater com a DPI real, depois da janela criada.

    Com o processo ja marcado como DPI-aware, o Windows entrega a DPI real do
    monitor; sem repassar isso ao Tk, ele so assume 96 e o texto sai borrado
    de novo em qualquer tela acima de 100%.
    """
    try:
        dpi = root.winfo_fpixels("1i")
        if dpi > 0:
            root.tk.call("tk", "scaling", dpi / 72.0)
    except tk.TclError:  # pragma: no cover - depende do ambiente
        pass


def make_root() -> tk.Tk:
    """Raiz com suporte a arrastar arquivo quando a biblioteca estiver presente."""
    _enable_dpi_awareness()
    if TkinterDnD is not None:
        try:
            root = TkinterDnD.Tk()
        except Exception:  # pragma: no cover - depende do ambiente
            root = tk.Tk()
    else:
        root = tk.Tk()
    _apply_dpi_scaling(root)
    return root


def main() -> int:
    root = make_root()
    SlidecutApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
