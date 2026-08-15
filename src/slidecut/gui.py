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
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import convert, core, preview, resources, theme
from .errors import SlidecutError

try:  # arrastar arquivo para a janela; a aplicacao funciona sem isso
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # pragma: no cover - depende do ambiente
    DND_FILES = None
    TkinterDnD = None

WINDOW_TITLE = "slidecut"
WINDOW_SIZE = "1060x740"
MIN_SIZE = (900, 620)

THUMBNAIL_WIDTH = 168
CARD_PAD = 10
EVENTS_PER_TICK = 6
REFLOW_DELAY_MS = 120
"""Reagrupar 145 cartoes a cada clique engasgaria. O cartao clicado responde na
hora; o reagrupamento por capitulo espera o usuario parar de clicar."""

CARD_WIDTH = THUMBNAIL_WIDTH + 34
CARD_EXTRA_HEIGHT = 96
"""Espaco abaixo da miniatura: legenda mais o campo de nome, que fica reservado
tambem nas paginas sem corte para a grade nunca mudar de forma."""

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


def selection_summary(selected: int, total: int) -> str:
    if selected == 0:
        return f"{total} páginas · nenhum corte marcado"
    return f"{total} páginas · {selected} arquivo(s) serão gerados"


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


# ------------------------------------------------------------------ janela
class SlidecutApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
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
        self.checkbox_vars: dict[int, tk.BooleanVar] = {}
        self.title_vars: dict[int, tk.StringVar] = {}
        self.cards: dict[int, dict] = {}
        self.thumbnail_images: list[tk.PhotoImage] = []
        self.chapter_bands: list[ttk.Frame] = []
        self._suggested: set[int] = set()
        self._placement: dict[int, tuple[int, int]] = {}
        self._reflow_job: str | None = None
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_header()
        self._build_open_screen()
        self._build_sheet_screen()
        self._show_open()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(30, self._drain_events)

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
        self.header_file = ttk.Label(bar, text="", style="BrandSub.TLabel")
        self.header_file.pack(side="left", padx=16)

    # -------------------------------------------------------- tela: abrir
    def _build_open_screen(self) -> None:
        self.open_screen = ttk.Frame(self.root, style="Paper.TFrame")

        footer = tk.Frame(self.open_screen, background=theme.SURFACE, height=64)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, background=theme.EDGE, height=1).pack(fill="x")
        self.open_status = ttk.Label(footer, text="", style="SurfaceMuted.TLabel")
        self.open_status.pack(side="left", padx=24)
        self.analyse_button = ttk.Button(
            footer, text="ABRIR PÁGINAS", style="Cut.TButton", command=self._on_analyse)
        self.analyse_button.pack(side="right", padx=24, pady=12)

        outer = ttk.Frame(self.open_screen, style="Paper.TFrame")
        outer.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(outer, background=theme.SURFACE, highlightthickness=1,
                        highlightbackground=theme.EDGE, highlightcolor=theme.EDGE)
        card.pack()
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

        self.drop_label = ttk.Label(self.drop_zone, text="Arraste o arquivo para cá",
                                    style="SunkTitle.TLabel")
        self.drop_label.pack()
        ttk.Label(self.drop_zone, text="pptx · docx · pdf e outros",
                  style="SunkFaint.TLabel").pack(pady=(6, 12))
        self.pick_input_button = ttk.Button(
            self.drop_zone, text="Procurar no computador", style="Quiet.TButton",
            command=self._pick_input,
        )
        self.pick_input_button.pack()

        self.chosen_label = ttk.Label(inner, text="", style="Surface.TLabel")
        self.chosen_label.pack(anchor="w", pady=(14, 0))

        ttk.Label(inner, text="P A S T A   D E   S A Í D A",
                  style="SurfaceSection.TLabel").pack(anchor="w", pady=(18, 6))
        outrow = ttk.Frame(inner, style="Surface.TFrame")
        outrow.pack(fill="x")
        self.outdir_var = tk.StringVar()
        ttk.Entry(outrow, textvariable=self.outdir_var, width=48).pack(
            side="left", fill="x", expand=True)
        self.pick_outdir_button = ttk.Button(
            outrow, text="Escolher...", style="Quiet.TButton", command=self._pick_outdir)
        self.pick_outdir_button.pack(side="left", padx=(10, 0))

        self.ascii_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner, text="Nomes de arquivo sem acento",
                        variable=self.ascii_var).pack(anchor="w", pady=(14, 0))

        tk.Frame(inner, background=theme.EDGE_SOFT, height=1).pack(fill="x", pady=(18, 12))
        status = ttk.Frame(inner, style="Surface.TFrame")
        status.pack(fill="x")
        has_converter, text = convert.converter_status()
        dot = tk.Canvas(status, width=10, height=14, background=theme.SURFACE,
                        highlightthickness=0)
        dot.pack(side="left", pady=(2, 0))
        dot.create_oval(1, 5, 9, 13, fill=theme.GREEN if has_converter else theme.RED,
                        outline="")
        column = ttk.Frame(status, style="Surface.TFrame")
        column.pack(side="left", padx=(8, 0))
        ttk.Label(column, text=text, style="SurfaceMuted.TLabel").pack(anchor="w")
        ttk.Label(
            column,
            text=("Nada mais precisa ser instalado neste computador."
                  if has_converter else "Arquivos que já são PDF continuam funcionando."),
            style="SurfaceFaint.TLabel",
        ).pack(anchor="w")

        self.open_progress = ttk.Progressbar(
            self.open_screen, mode="indeterminate", style="Cut.Horizontal.TProgressbar")

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
        path = parse_dropped_path(event.data)
        if path is None:
            messagebox.showwarning(WINDOW_TITLE, "Não consegui ler o arquivo solto na janela.")
            return
        self._set_input(path)

    # ------------------------------------------------------- tela: folha
    def _build_sheet_screen(self) -> None:
        self.sheet_screen = ttk.Frame(self.root, style="Paper.TFrame")

        toolbar = tk.Frame(self.sheet_screen, background=theme.SURFACE, height=68)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        left = ttk.Frame(toolbar, style="Surface.TFrame")
        left.pack(side="left", padx=24, pady=12)
        ttk.Label(left, text="Marque as páginas onde cada capítulo começa",
                  style="Surface.TLabel").pack(anchor="w")
        ttk.Label(left, text="Cada marca abre um arquivo novo.",
                  style="SurfaceFaint.TLabel").pack(anchor="w")

        self.summary_label = ttk.Label(toolbar, text="", style="SurfaceMuted.TLabel")
        self.summary_label.pack(side="right", padx=24)

        actions = ttk.Frame(toolbar, style="Surface.TFrame")
        actions.pack(side="left", padx=20)
        self.suggest_button = ttk.Button(
            actions, text="Usar sugestão por cor", style="Quiet.TButton",
            command=self._apply_suggestion)
        self.suggest_button.pack(side="left")
        self.clear_button = ttk.Button(
            actions, text="Limpar marcas", style="Quiet.TButton", command=self._clear_selection)
        self.clear_button.pack(side="left", padx=8)
        self.back_button = ttk.Button(
            actions, text="Trocar arquivo", style="Quiet.TButton", command=self._show_open)
        self.back_button.pack(side="left")

        tk.Frame(self.sheet_screen, background=theme.EDGE, height=1).pack(fill="x")

        footer = tk.Frame(self.sheet_screen, background=theme.SURFACE, height=64)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Frame(footer, background=theme.EDGE, height=1).pack(fill="x")
        self.sheet_status = ttk.Label(footer, text="", style="SurfaceMuted.TLabel")
        self.sheet_status.pack(side="left", padx=24)
        self.cut_button = ttk.Button(
            footer, text="GERAR OS CORTES", style="Cut.TButton", command=self._on_cut)
        self.cut_button.pack(side="right", padx=24, pady=12)
        self.open_button = ttk.Button(
            footer, text="Abrir pasta", style="Quiet.TButton",
            command=self._on_open_outdir, state="disabled")
        self.open_button.pack(side="right", pady=12)

        body = ttk.Frame(self.sheet_screen, style="Paper.TFrame")
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, background=theme.PAPER, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
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

        self.sheet_progress = ttk.Progressbar(
            footer, mode="indeterminate", style="Cut.Horizontal.TProgressbar", length=160)

    def _show_open(self) -> None:
        if self.busy:
            return
        self.sheet_screen.pack_forget()
        self.open_screen.pack(fill="both", expand=True)

    def _show_sheet(self) -> None:
        self.open_screen.pack_forget()
        self.sheet_screen.pack(fill="both", expand=True)

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
        threading.Thread(target=self._run_prepare, args=(source,), daemon=True).start()

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
                WINDOW_TITLE, "Marque pelo menos uma página para começar um capítulo.")
            return

        self.open_button.configure(state="disabled")
        self._set_busy(True)
        self.sheet_progress.pack(side="right", padx=16)
        self.sheet_progress.start(12)
        custom_titles = {i: self.title_vars[i].get() for i in dividers}
        threading.Thread(
            target=self._run_cut,
            args=(self.document, dividers, self.outdir_var.get() or None,
                  self.ascii_var.get(), custom_titles),
            daemon=True,
        ).start()

    def _run_cut(self, document, dividers, outdir, ascii_only, custom_titles) -> None:
        try:
            result = core.cut_at(
                document, dividers, outdir=outdir, ascii_only=ascii_only,
                custom_titles=custom_titles,
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
        self.title_vars.clear()
        self.cards.clear()
        self.chapter_bands.clear()
        self._placement.clear()
        self.thumbnail_images.clear()

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
        tk.Label(holder, image=image, background=theme.SURFACE, bd=0).pack()
        number = tk.Label(holder, text=f"{index + 1:03d}", font=self.fonts.number,
                          background=theme.INK, foreground=theme.SURFACE, padx=5, pady=1)
        number.place(x=0, y=0)

        caption = tk.Label(content, text=thumb.caption, font=self.fonts.small,
                           background=theme.SURFACE, foreground=theme.SLATE_LIGHT,
                           wraplength=THUMBNAIL_WIDTH, justify="left", anchor="w")
        caption.pack(fill="x", pady=(10, 0))

        name_row = tk.Frame(content, background=theme.SURFACE, height=44)
        name_row.pack(fill="x", pady=(8, 0))
        name_row.pack_propagate(False)
        name_label = tk.Label(name_row, text="NOME DO ARQUIVO", font=self.fonts.section,
                              background=theme.SURFACE, foreground=theme.CUT, anchor="w")
        title_var = tk.StringVar(value=thumb.title)
        entry = ttk.Entry(name_row, textvariable=title_var, style="Name.TEntry",
                          font=self.fonts.small)

        checked = tk.BooleanVar(value=index in self._suggested)
        self.checkbox_vars[index] = checked
        self.title_vars[index] = title_var
        self.cards[index] = {
            "shell": shell, "body": body, "rail": rail, "number": number,
            "caption": caption, "name_label": name_label, "entry": entry,
        }

        for widget in (body, content, holder, caption):
            widget.bind("<Button-1>", lambda _e, i=index: self._toggle(i))
        holder.winfo_children()[0].bind("<Button-1>", lambda _e, i=index: self._toggle(i))

        checked.trace_add("write", lambda *_a, i=index: self._on_check_changed(i))
        self._paint_card(index)

    def _paint_card(self, index: int) -> None:
        """Marcado muda so a cor, nunca o tamanho: a grade nao pode saltar."""
        parts = self.cards[index]
        marked = self.checkbox_vars[index].get()

        parts["shell"].configure(background=theme.CUT if marked else theme.EDGE)
        parts["rail"].configure(background=theme.CUT if marked else theme.SURFACE)
        parts["number"].configure(background=theme.CUT if marked else theme.INK)
        parts["caption"].configure(foreground=theme.INK if marked else theme.SLATE_LIGHT)

        if marked:
            parts["name_label"].pack(fill="x")
            parts["entry"].pack(fill="x", pady=(2, 0))
        else:
            parts["name_label"].pack_forget()
            parts["entry"].pack_forget()

    def _toggle(self, index: int) -> None:
        var = self.checkbox_vars.get(index)
        if var is not None:
            var.set(not var.get())

    def _on_check_changed(self, index: int) -> None:
        self._paint_card(index)
        self._refresh_summary()
        self._schedule_reflow()

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
        band.number.configure(text=f"C A P Í T U L O  {number:02d}")  # type: ignore[attr-defined]
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
        for var in self.checkbox_vars.values():
            var.set(False)

    def _refresh_summary(self) -> None:
        selected = sum(1 for var in self.checkbox_vars.values() if var.get())
        self.summary_label.configure(text=selection_summary(selected, len(self.checkbox_vars)))

    # ---------------------------------------------------------- plumbing
    def _set_busy(self, busy: bool) -> None:
        """Trava a janela inteira: dois trabalhos gravariam no mesmo temporario."""
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.analyse_button, self.cut_button, self.back_button,
            self.pick_input_button, self.pick_outdir_button,
            self.suggest_button, self.clear_button,
        ):
            widget.configure(state=state)

    def _stop_progress(self) -> None:
        for bar in (self.open_progress, self.sheet_progress):
            bar.stop()
            bar.pack_forget()

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
                elif kind == "cut":
                    self.last_result = payload
                    self._set_busy(False)
                    self._stop_progress()
                    self.open_button.configure(state="normal")
                    messagebox.showinfo(WINDOW_TITLE, format_result_summary(payload))
                elif kind == "error":
                    self._set_busy(False)
                    self._stop_progress()
                    self.open_status.configure(text="")
                    messagebox.showerror(WINDOW_TITLE, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(30, self._drain_events)

    def _on_close(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)
        self.root.destroy()


def apply_window_icon(root: tk.Tk) -> None:
    """Icone na barra de titulo e na barra de tarefas; falhar aqui nao derruba nada."""
    try:
        root.iconbitmap(default=str(resources.icon_path()))
    except (tk.TclError, OSError):
        pass


def make_root() -> tk.Tk:
    """Raiz com suporte a arrastar arquivo quando a biblioteca estiver presente."""
    if TkinterDnD is not None:
        try:
            return TkinterDnD.Tk()
        except Exception:  # pragma: no cover - depende do ambiente
            pass
    return tk.Tk()


def main() -> int:
    root = make_root()
    SlidecutApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
