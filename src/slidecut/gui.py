"""Interface grafica do slidecut: escolher arquivo, cortar, ver o resultado.

A logica de negocio vive em core.process(); esta janela so coleta as opcoes,
chama core.process() numa thread separada (pra nao travar a janela) e mostra
o progresso e o resultado.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import analyze, convert, core
from .errors import SlidecutError

INPUT_FILETYPES = [
    ("Todos os suportados", " ".join(f"*{ext}" for ext in sorted(convert.SUPPORTED_INPUTS))),
    ("PDF", "*.pdf"),
    ("Apresentacoes", " ".join(f"*{ext}" for ext in sorted(convert.SLIDE_FORMATS))),
    ("Documentos", " ".join(f"*{ext}" for ext in sorted(convert.TEXT_FORMATS))),
    ("Planilhas", " ".join(f"*{ext}" for ext in sorted(convert.SHEET_FORMATS))),
    ("Todos os arquivos", "*.*"),
]

WINDOW_TITLE = "slidecut - cortar apresentacao por slide divisor"
WINDOW_SIZE = "640x480"


def format_result_summary(result: core.ProcessResult, list_only: bool) -> str:
    """Mensagem final mostrada ao usuario apos o corte (ou a previa)."""
    if list_only:
        return f"{len(result.chapters)} capitulos detectados (nada foi gravado)."
    return f"{len(result.written)} arquivo(s) gravado(s) em:\n{result.outdir}"


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

        self.input_path: Path | None = None
        self.last_result: core.ProcessResult | None = None
        self.last_list_only = False
        self._events: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_widgets()
        self.root.after(100, self._drain_events)

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        file_frame = ttk.Frame(self.root)
        file_frame.pack(fill="x", **pad)
        ttk.Button(file_frame, text="Selecionar arquivo...", command=self._pick_input).pack(
            side="left"
        )
        self.input_label = ttk.Label(file_frame, text="Nenhum arquivo selecionado")
        self.input_label.pack(side="left", padx=10)

        out_frame = ttk.Frame(self.root)
        out_frame.pack(fill="x", **pad)
        ttk.Button(out_frame, text="Pasta de saida...", command=self._pick_outdir).pack(
            side="left"
        )
        self.outdir_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.outdir_var).pack(
            side="left", fill="x", expand=True, padx=10
        )

        options = ttk.Frame(self.root)
        options.pack(fill="x", **pad)
        self.color_var = tk.StringVar()
        ttk.Label(options, text="Cor do divisor (opcional, ex.: #B06E03):").pack(side="left")
        ttk.Entry(options, textvariable=self.color_var, width=12).pack(side="left", padx=6)
        self.ascii_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="Nomes sem acento", variable=self.ascii_var).pack(
            side="left", padx=12
        )

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        self.preview_button = ttk.Button(actions, text="Pre-visualizar", command=self._on_preview)
        self.preview_button.pack(side="left")
        self.run_button = ttk.Button(actions, text="Cortar", command=self._on_run)
        self.run_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(
            actions, text="Abrir pasta", command=self._on_open_outdir, state="disabled"
        )
        self.open_button.pack(side="left")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", **pad)

        self.log = tk.Text(self.root, height=16, state="disabled")
        self.log.pack(fill="both", expand=True, **pad)

    def _pick_input(self) -> None:
        chosen = filedialog.askopenfilename(title="Selecione o arquivo", filetypes=INPUT_FILETYPES)
        if not chosen:
            return
        self.input_path = Path(chosen)
        self.input_label.config(text=self.input_path.name)
        if not self.outdir_var.get():
            self.outdir_var.set(str(core.default_outdir(self.input_path)))

    def _pick_outdir(self) -> None:
        chosen = filedialog.askdirectory(title="Pasta de saida")
        if chosen:
            self.outdir_var.set(chosen)

    def _on_open_outdir(self) -> None:
        if self.last_result is not None:
            open_in_file_manager(self.last_result.outdir)

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.run_button.configure(state=state)
        self.preview_button.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _on_preview(self) -> None:
        self._start_job(list_only=True)

    def _on_run(self) -> None:
        self._start_job(list_only=False)

    def _start_job(self, list_only: bool) -> None:
        if self.input_path is None:
            messagebox.showwarning(WINDOW_TITLE, "Selecione um arquivo primeiro.")
            return

        try:
            color = analyze.parse_color(self.color_var.get()) if self.color_var.get() else None
        except ValueError as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))
            return

        self.open_button.configure(state="disabled")
        self.last_result = None
        self.last_list_only = list_only
        self._log(f"--- {'Previa' if list_only else 'Corte'}: {self.input_path.name} ---")
        self._set_busy(True)

        outdir = self.outdir_var.get() or None
        ascii_only = self.ascii_var.get()
        input_path = self.input_path

        thread = threading.Thread(
            target=self._run_job,
            args=(input_path, outdir, color, ascii_only, list_only),
            daemon=True,
        )
        thread.start()

    def _run_job(
        self,
        input_path: Path,
        outdir: str | None,
        color: tuple[int, int, int] | None,
        ascii_only: bool,
        list_only: bool,
    ) -> None:
        try:
            result = core.process(
                input_path,
                outdir=outdir,
                color=color,
                ascii_only=ascii_only,
                list_only=list_only,
                on_progress=lambda msg: self._events.put(("log", msg)),
            )
            self._events.put(("done", result))
        except SlidecutError as exc:
            self._events.put(("error", str(exc)))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "done":
                    result = payload
                    assert isinstance(result, core.ProcessResult)
                    self.last_result = result
                    self._log(format_result_summary(result, self.last_list_only))
                    self._set_busy(False)
                    if not self.last_list_only:
                        self.open_button.configure(state="normal")
                elif kind == "error":
                    self._log(f"Erro: {payload}")
                    self._set_busy(False)
                    messagebox.showerror(WINDOW_TITLE, str(payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._drain_events)


def main() -> int:
    root = tk.Tk()
    SlidecutApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
