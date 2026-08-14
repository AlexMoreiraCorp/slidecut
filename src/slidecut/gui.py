"""Interface grafica do slidecut.

Duas telas na mesma janela:

1. Abertura: escolher o arquivo. Se nao for PDF, a conversao e confirmada com o
   usuario antes de rodar o LibreOffice.
2. Selecao: grade com as miniaturas de todas as paginas. A deteccao por cor
   entra so como sugestao inicial; quem decide onde cortar e o usuario, marcando
   e desmarcando paginas. Isso resolve os casos que a cor nao pega (slide so com
   titulo, divisor com foto de fundo, template sem cor chapada).

A logica de conversao e corte fica em core.py; aqui so tem tela.
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

from . import convert, core, preview
from .errors import SlidecutError

INPUT_FILETYPES = [
    ("Todos os suportados", " ".join(f"*{ext}" for ext in sorted(convert.SUPPORTED_INPUTS))),
    ("PDF", "*.pdf"),
    ("Apresentacoes", " ".join(f"*{ext}" for ext in sorted(convert.SLIDE_FORMATS))),
    ("Documentos", " ".join(f"*{ext}" for ext in sorted(convert.TEXT_FORMATS))),
    ("Planilhas", " ".join(f"*{ext}" for ext in sorted(convert.SHEET_FORMATS))),
    ("Todos os arquivos", "*.*"),
]

WINDOW_TITLE = "slidecut"
WINDOW_SIZE = "1000x720"
THUMBNAIL_WIDTH = 170
GRID_COLUMNS = 4
EVENTS_PER_TICK = 6
"""Quantos eventos a janela processa por ciclo. Segura a montagem da grade para
que o loop do Tk continue respondendo enquanto as miniaturas chegam."""

CONVERT_QUESTION = (
    "{name} nao e um PDF.\n\n"
    "Para cortar, o arquivo precisa ser convertido em PDF primeiro "
    "(feito pelo LibreOffice, sem alterar o original).\n\n"
    "Converter agora?"
)


def conversion_prompt(source: Path) -> str:
    """Texto da pergunta de conversao mostrada antes de chamar o LibreOffice."""
    return CONVERT_QUESTION.format(name=source.name)


def format_result_summary(result: core.ProcessResult) -> str:
    """Mensagem final apos gravar os capitulos."""
    return f"{len(result.written)} arquivo(s) gravado(s) em:\n{result.outdir}"


def selection_summary(selected: int, total: int) -> str:
    """Rodape da tela de selecao: quantos cortes e quantos capitulos sairao."""
    if selected == 0:
        return f"{total} paginas. Nenhum corte marcado."
    return f"{total} paginas. {selected} corte(s) marcado(s) - gera {selected} arquivo(s)."


def open_in_file_manager(path: Path) -> None:
    """Abre a pasta de saida no explorador de arquivos do sistema."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606 - caminho gerado pela propria aplicacao
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


class SlidecutApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)

        self.workdir = Path(tempfile.mkdtemp(prefix="slidecut-gui-"))
        # Rede de seguranca: se a janela for fechada de um jeito que nao dispare
        # _on_close (crash, kill), o diretorio temporario ainda some.
        atexit.register(shutil.rmtree, self.workdir, ignore_errors=True)

        self.busy = False
        self._suggested: set[int] = set()
        self.document: core.PreparedDocument | None = None
        self.last_result: core.ProcessResult | None = None
        self.checkbox_vars: dict[int, tk.BooleanVar] = {}
        self.title_vars: dict[int, tk.StringVar] = {}
        self.title_entries: dict[int, ttk.Entry] = {}
        self.thumbnail_images: list[tk.PhotoImage] = []
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_setup_screen()
        self._build_selection_screen()
        self._show_setup()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_events)

    # ------------------------------------------------------------------ telas

    def _build_setup_screen(self) -> None:
        self.setup_frame = ttk.Frame(self.root, padding=16)

        ttk.Label(
            self.setup_frame,
            text="Escolha a apresentacao, o documento ou o PDF que voce quer cortar.",
        ).pack(anchor="w", pady=(0, 12))

        picker = ttk.Frame(self.setup_frame)
        picker.pack(fill="x", pady=4)
        self.pick_input_button = ttk.Button(
            picker, text="Selecionar arquivo...", command=self._pick_input
        )
        self.pick_input_button.pack(side="left")
        self.input_label = ttk.Label(picker, text="Nenhum arquivo selecionado")
        self.input_label.pack(side="left", padx=10)

        outrow = ttk.Frame(self.setup_frame)
        outrow.pack(fill="x", pady=4)
        self.pick_outdir_button = ttk.Button(
            outrow, text="Pasta de saida...", command=self._pick_outdir
        )
        self.pick_outdir_button.pack(side="left")
        self.outdir_var = tk.StringVar()
        ttk.Entry(outrow, textvariable=self.outdir_var).pack(
            side="left", fill="x", expand=True, padx=10
        )

        self.ascii_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.setup_frame, text="Nomes de arquivo sem acento", variable=self.ascii_var
        ).pack(anchor="w", pady=4)

        self.analyse_button = ttk.Button(
            self.setup_frame, text="Abrir paginas para escolher os cortes", command=self._on_analyse
        )
        self.analyse_button.pack(anchor="w", pady=12)

        self.setup_progress = ttk.Progressbar(self.setup_frame, mode="indeterminate")
        self.setup_progress.pack(fill="x", pady=4)

        self.log = tk.Text(self.setup_frame, height=12, state="disabled")
        self.log.pack(fill="both", expand=True, pady=8)

    def _build_selection_screen(self) -> None:
        self.selection_frame = ttk.Frame(self.root, padding=10)

        header = ttk.Frame(self.selection_frame)
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Marque as paginas que comecam um capitulo. Cada marca abre um arquivo novo.",
        ).pack(side="left")
        self.back_button = ttk.Button(header, text="< Voltar", command=self._show_setup)
        self.back_button.pack(side="right")

        tools = ttk.Frame(self.selection_frame)
        tools.pack(fill="x", pady=6)
        ttk.Button(tools, text="Usar sugestao por cor", command=self._apply_suggestion).pack(
            side="left"
        )
        ttk.Button(tools, text="Limpar marcas", command=self._clear_selection).pack(
            side="left", padx=6
        )
        self.summary_label = ttk.Label(tools, text="")
        self.summary_label.pack(side="left", padx=16)

        canvas_wrap = ttk.Frame(self.selection_frame)
        canvas_wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_wrap, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = ttk.Frame(self.selection_frame)
        footer.pack(fill="x", pady=8)
        self.cut_button = ttk.Button(footer, text="Gerar os cortes", command=self._on_cut)
        self.cut_button.pack(side="left")
        self.open_button = ttk.Button(
            footer, text="Abrir pasta", command=self._on_open_outdir, state="disabled"
        )
        self.open_button.pack(side="left", padx=8)
        self.selection_progress = ttk.Progressbar(footer, mode="indeterminate")
        self.selection_progress.pack(side="left", fill="x", expand=True, padx=10)

    def _show_setup(self) -> None:
        self.selection_frame.pack_forget()
        self.setup_frame.pack(fill="both", expand=True)

    def _show_selection(self) -> None:
        self.setup_frame.pack_forget()
        self.selection_frame.pack(fill="both", expand=True)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.selection_frame.winfo_ismapped():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # ----------------------------------------------------------------- acoes

    def _pick_input(self) -> None:
        if self.busy:
            return
        chosen = filedialog.askopenfilename(title="Selecione o arquivo", filetypes=INPUT_FILETYPES)
        if not chosen:
            return
        self.input_path = Path(chosen)
        self.input_label.config(text=self.input_path.name)
        self.outdir_var.set(str(core.default_outdir(self.input_path)))

    def _pick_outdir(self) -> None:
        chosen = filedialog.askdirectory(title="Pasta de saida")
        if chosen:
            self.outdir_var.set(chosen)

    def _on_analyse(self) -> None:
        if self.busy:
            return
        source = getattr(self, "input_path", None)
        if source is None:
            messagebox.showwarning(WINDOW_TITLE, "Selecione um arquivo primeiro.")
            return

        if convert.needs_conversion(source):
            if not messagebox.askyesno(WINDOW_TITLE, conversion_prompt(source)):
                self._log("Conversao cancelada pelo usuario.")
                return

        self._log(f"--- {source.name} ---")
        self._set_busy(self.setup_progress, True)
        threading.Thread(target=self._run_prepare, args=(source,), daemon=True).start()

    def _run_prepare(self, source: Path) -> None:
        """Converte, analisa e ja vai renderizando as miniaturas nesta thread.

        Renderizar aqui (e nao na janela) mantem o Tk respondendo enquanto um
        documento de centenas de paginas e processado.
        """
        try:
            document = core.prepare(
                source,
                workdir=self.workdir,
                on_progress=lambda msg: self._events.put(("log", msg)),
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
        dividers = [index for index, var in self.checkbox_vars.items() if var.get()]
        if not dividers:
            messagebox.showwarning(
                WINDOW_TITLE, "Marque pelo menos uma pagina para comecar um capitulo."
            )
            return

        self.open_button.configure(state="disabled")
        self._set_busy(self.selection_progress, True)
        outdir = self.outdir_var.get() or None
        ascii_only = self.ascii_var.get()
        document = self.document
        custom_titles = {index: self.title_vars[index].get() for index in dividers}

        threading.Thread(
            target=self._run_cut,
            args=(document, dividers, outdir, ascii_only, custom_titles),
            daemon=True,
        ).start()

    def _run_cut(
        self,
        document: core.PreparedDocument,
        dividers: list[int],
        outdir: str | None,
        ascii_only: bool,
        custom_titles: dict[int, str],
    ) -> None:
        try:
            result = core.cut_at(
                document,
                dividers,
                outdir=outdir,
                ascii_only=ascii_only,
                custom_titles=custom_titles,
                on_progress=lambda msg: self._events.put(("log", msg)),
            )
            self._events.put(("cut", result))
        except Exception as exc:  # inclui falha de escrita e permissao negada
            self._events.put(("error", str(exc)))

    def _on_open_outdir(self) -> None:
        if self.last_result is not None:
            open_in_file_manager(self.last_result.outdir)

    # -------------------------------------------------------------- selecao

    def _reset_grid(self) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.checkbox_vars.clear()
        self.title_vars.clear()
        self.title_entries.clear()
        self.thumbnail_images.clear()

    def _add_thumbnail_cell(self, thumb: preview.Thumbnail, suggested: set[int]) -> None:
        """Monta a celula de uma pagina. Chamada uma vez por miniatura recebida."""
        image = tk.PhotoImage(data=thumb.png, master=self.root)
        self.thumbnail_images.append(image)

        cell = ttk.Frame(self.grid_frame, padding=6, relief="groove")
        cell.grid(
            row=thumb.index // GRID_COLUMNS,
            column=thumb.index % GRID_COLUMNS,
            padx=4,
            pady=4,
            sticky="n",
        )
        ttk.Label(cell, image=image).pack()
        ttk.Label(cell, text=f"{thumb.index + 1}. {thumb.caption}", wraplength=THUMBNAIL_WIDTH)\
            .pack(pady=(4, 2))

        index = thumb.index
        checked = tk.BooleanVar(value=index in suggested)
        self.checkbox_vars[index] = checked
        ttk.Checkbutton(cell, text="Cortar aqui", variable=checked).pack()

        title_var = tk.StringVar(value=thumb.title)
        self.title_vars[index] = title_var
        entry = ttk.Entry(cell, textvariable=title_var, width=24)
        entry.pack(pady=(4, 0))
        self.title_entries[index] = entry

        checked.trace_add("write", lambda *_a, i=index: self._on_check_changed(i))
        self._sync_entry_state(index)

    def _on_check_changed(self, index: int) -> None:
        self._sync_entry_state(index)
        self._refresh_summary()

    def _sync_entry_state(self, index: int) -> None:
        """O nome so pode ser editado nas paginas marcadas como inicio de capitulo."""
        marked = self.checkbox_vars[index].get()
        self.title_entries[index].configure(state="normal" if marked else "disabled")

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
        self.summary_label.config(text=selection_summary(selected, len(self.checkbox_vars)))

    # ------------------------------------------------------------- plumbing

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, bar: ttk.Progressbar, busy: bool) -> None:
        """Trava a janela inteira enquanto ha trabalho em andamento.

        Nao basta desabilitar o botao que iniciou o trabalho: sem travar a
        navegacao, o usuario abriria um segundo arquivo por cima, e as duas
        threads escreveriam no mesmo diretorio temporario.
        """
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.analyse_button,
            self.cut_button,
            self.back_button,
            self.pick_input_button,
            self.pick_outdir_button,
        ):
            widget.configure(state=state)
        if busy:
            bar.start(12)
        else:
            bar.stop()

    def _drain_events(self) -> None:
        try:
            for _ in range(EVENTS_PER_TICK):
                kind, payload = self._events.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "prepared":
                    assert isinstance(payload, core.PreparedDocument)
                    self.document = payload
                    self._log(f"{payload.page_count} paginas. Montando as miniaturas...")
                    self._reset_grid()
                    self._suggested = set(payload.suggested_dividers)
                    self._show_selection()
                elif kind == "thumbnail":
                    assert isinstance(payload, preview.Thumbnail)
                    self._add_thumbnail_cell(payload, self._suggested)
                    self._refresh_summary()
                elif kind == "thumbnails_done":
                    self._set_busy(self.setup_progress, False)
                    self._refresh_summary()
                elif kind == "cut":
                    assert isinstance(payload, core.ProcessResult)
                    self.last_result = payload
                    self._set_busy(self.selection_progress, False)
                    self.open_button.configure(state="normal")
                    messagebox.showinfo(WINDOW_TITLE, format_result_summary(payload))
                elif kind == "error":
                    self._set_busy(self.setup_progress, False)
                    self._log(f"Erro: {payload}")
                    messagebox.showerror(WINDOW_TITLE, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(30, self._drain_events)

    def _on_close(self) -> None:
        """Apaga o PDF temporario da conversao antes de fechar."""
        shutil.rmtree(self.workdir, ignore_errors=True)
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    SlidecutApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
