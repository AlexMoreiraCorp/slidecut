"""Sobe a janela de verdade e exercita a tela de selecao ponta a ponta.

Os demais testes de janela olham so as funcoes puras, por escolha: nao se testa
o toolkit. Este arquivo cobre o que aquela escolha deixa de fora — a fiacao
entre widgets. Erros como "o botao chama um metodo que nao existe", "a marca
nao repinta o cartao" ou "o painel abre mas nao carrega a pagina" nao aparecem
em nenhum teste de funcao pura, e sao justamente os que quebram o programa na
mao do usuario.

Precisa de uma sessao grafica. Onde nao houver, os testes sao pulados.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from slidecut import gui

from tests.conftest import BLUE, ORANGE, WHITE, build_pdf


@pytest.fixture(scope="module")
def root():
    """Um unico interpretador Tk para o modulo inteiro.

    Criar e destruir um Tk() por teste falha de vez em quando com "Can't find a
    usable tk.tcl": o interpretador anterior ainda esta se desfazendo quando o
    proximo sobe. Como a queixa e do Tk e nao do programa, o teste que caisse
    ali seria ruido puro.
    """
    try:
        window = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - depende do ambiente
        pytest.skip(f"sem sessao grafica: {exc}")

    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def app(root):
    """Janela limpa a cada teste, sobre o mesmo interpretador."""
    for child in root.winfo_children():
        child.destroy()

    application = gui.SlidecutApp(root)
    root.update()
    return application


@pytest.fixture
def deck_ready(app, tmp_path):
    """Baralho de dois tons ja carregado na tela de selecao.

    Azul em tres paginas, laranja em duas: a deteccao automatica escolhe o azul,
    entao da para provar que o slide matriz troca o criterio.
    """
    spec = [
        (BLUE, "Bloco A"),
        (WHITE, "conteudo 1"),
        (ORANGE, "Bloco B"),
        (WHITE, "conteudo 2"),
        (BLUE, "Bloco C"),
        (ORANGE, "Bloco D"),
        (BLUE, "Bloco E"),
    ]
    source = build_pdf(tmp_path / "dois-tons.pdf", spec)

    app._set_input(source)
    app._on_analyse()
    _pump_until(app, lambda: len(app.cards) == len(spec))
    return app


def _is_shown(widget) -> bool:
    """Se o widget esta encaixado na tela.

    winfo_ismapped() nao serve aqui: a janela do teste fica oculta, e nela nada
    conta como "pintado". O que importa e se o widget foi empacotado.
    """
    return bool(widget.winfo_manager())


def _pump_until(app, condition, limit: int = 600) -> None:
    """Roda o laco de eventos ate a condicao valer (o preparo e em thread)."""
    for _ in range(limit):
        app.root.update()
        if condition():
            return
        app.root.after(20)
        app.root.update()
    raise AssertionError("a tela nao chegou ao estado esperado a tempo")


def _marked(app) -> list[int]:
    return sorted(i for i, var in app.checkbox_vars.items() if var.get())


def _excluded(app) -> list[int]:
    return sorted(i for i, var in app.keep_vars.items() if not var.get())


# ------------------------------------------------------------ montagem
def test_the_window_opens_on_the_first_screen(app):
    assert _is_shown(app.open_screen)
    assert not _is_shown(app.sheet_screen)


def test_opening_a_deck_builds_one_card_per_page(deck_ready):
    assert len(deck_ready.cards) == 7
    assert _is_shown(deck_ready.sheet_screen)


def test_every_page_starts_inside_the_cut(deck_ready):
    """A marca de "entra no corte" vem ligada: quem nao mexer corta tudo."""
    assert _excluded(deck_ready) == []


# ---------------------------------------------- marca de corte (itens 4 e 6)
def test_clicking_the_cut_tag_marks_and_unmarks_the_page(deck_ready):
    deck_ready._toggle(3)
    assert 3 in _marked(deck_ready)
    deck_ready._toggle(3)
    assert 3 not in _marked(deck_ready)


def test_the_cut_tag_says_what_it_does_in_each_state(deck_ready):
    tag = deck_ready.cards[3]["cut_tag"]
    assert tag.cget("text") == gui.CUT_OFF_LABEL
    deck_ready._toggle(3)
    assert tag.cget("text") == gui.CUT_ON_LABEL


def test_taking_a_page_out_of_the_cut_leaves_it_in_the_document(deck_ready):
    deck_ready.keep_vars[1].set(False)
    deck_ready.root.update()
    assert _excluded(deck_ready) == [1]
    assert len(deck_ready.cards) == 7, "a pagina continua na folha, so nao entra no corte"
    assert "fora" in deck_ready.summary_label.cget("text").lower()


def test_clearing_marks_undoes_both_the_cuts_and_the_exclusions(deck_ready):
    deck_ready._toggle(3)
    deck_ready.keep_vars[1].set(False)
    deck_ready._clear_selection()
    deck_ready.root.update()
    assert _marked(deck_ready) == []
    assert _excluded(deck_ready) == []


# ------------------------------------------------ painel de inspecao (item 5)
def test_clicking_a_page_opens_it_in_the_side_panel(deck_ready):
    deck_ready._focus_page(2)
    deck_ready.root.update()
    assert _is_shown(deck_ready.inspector)
    assert deck_ready.inspect_title.cget("text") == "Página 3 de 7"


def test_the_panel_reads_the_colour_of_the_page_it_is_showing(deck_ready):
    deck_ready._focus_page(2)
    deck_ready.root.update()
    assert deck_ready.inspect_colour.cget("text").startswith("#")
    assert deck_ready.inspect_swatch.cget("background") == deck_ready.inspect_colour.cget("text")


def test_looking_at_a_page_does_not_mark_it_for_cutting(deck_ready):
    """Separar "ver" de "cortar" e o motivo de o clique ter mudado de funcao."""
    antes = _marked(deck_ready)
    deck_ready._focus_page(1)
    deck_ready.root.update()
    assert _marked(deck_ready) == antes


def test_closing_the_panel_hides_it(deck_ready):
    deck_ready._focus_page(2)
    deck_ready._close_inspector()
    deck_ready.root.update()
    assert not _is_shown(deck_ready.inspector)


def test_the_panel_can_mark_the_cut_of_the_page_it_shows(deck_ready):
    deck_ready._focus_page(3)
    deck_ready._toggle_focused_cut()
    deck_ready.root.update()
    assert 3 in _marked(deck_ready)
    assert "Tirar" in deck_ready.inspect_cut_button._text


def test_the_panel_can_take_its_page_out_of_the_cut(deck_ready):
    deck_ready._focus_page(3)
    deck_ready._toggle_focused_keep()
    deck_ready.root.update()
    assert _excluded(deck_ready) == [3]


# ------------------------------------------------------ slide matriz (item 3)
def test_auto_detection_picks_the_most_repeated_tone(deck_ready):
    assert _marked(deck_ready) == [0, 4, 6], "sem matriz, ganha o azul"


def _apply_matrix(app, page: int) -> None:
    """Escolhe o slide matriz e espera o resultado.

    A operacao roda numa thread desde que passou a mostrar animacao de espera:
    o teste tem de aguardar o resultado voltar pela fila de eventos.
    """
    app._focus_page(page)
    app._use_focused_as_matrix()
    _pump_until(app, lambda: app._matrix_page == page)


def test_choosing_a_matrix_slide_recuts_by_that_slide_tone(deck_ready):
    _apply_matrix(deck_ready, 2)
    assert _marked(deck_ready) == [2, 5], "o laranja da matriz manda no corte"


def test_the_matrix_slide_is_announced_in_the_panel_and_the_status(deck_ready):
    _apply_matrix(deck_ready, 2)
    assert "MATRIZ" in deck_ready.inspect_badge.cget("text")
    assert "matriz" in deck_ready.sheet_status.cget("text").lower()


def test_the_wait_animation_shows_while_the_matrix_is_applied(deck_ready):
    """Operacao demorada precisa avisar que esta acontecendo."""
    deck_ready._focus_page(2)
    deck_ready._use_focused_as_matrix()
    assert _is_shown(deck_ready.wait_overlay.frame), "a animacao aparece durante a espera"

    _pump_until(deck_ready, lambda: deck_ready._matrix_page == 2)
    assert not _is_shown(deck_ready.wait_overlay.frame), "e some quando termina"


def test_asking_for_a_matrix_without_choosing_a_page_does_not_crash(deck_ready, monkeypatch):
    avisos = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a: avisos.append(a))
    deck_ready._close_inspector()
    deck_ready._use_focused_as_matrix()
    assert avisos, "o programa explica que falta escolher a pagina"


def test_clearing_marks_also_forgets_the_matrix_slide(deck_ready):
    _apply_matrix(deck_ready, 2)
    deck_ready._clear_selection()
    deck_ready.root.update()
    assert deck_ready._matrix_page is None


# ------------------------------------------- prefixo, sufixo e nome (1 e 2)
def test_the_card_previews_the_name_the_file_will_get(deck_ready):
    deck_ready._toggle(0) if 0 not in _marked(deck_ready) else None
    deck_ready.root.update()
    previa = deck_ready.cards[0]["name_preview"].cget("text")
    assert previa.endswith(".pdf")
    assert "Bloco A" in previa


def test_numbering_starts_unchecked(app):
    """Pedido explicito: numerar e opcional e comeca desligado."""
    assert app.numbered_var.get() is False


def test_typing_a_prefix_no_longer_flips_the_numbering_choice(deck_ready):
    """O check parou de se mexer sozinho: quem manda e o usuario."""
    deck_ready.numbered_var.set(True)
    deck_ready.prefix_var.set("Aula 02")
    deck_ready.root.update()
    assert deck_ready.numbered_var.get() is True


def test_only_the_focused_card_holds_a_real_text_field(deck_ready):
    """Centenas de campos nativos dentro da grade rolavel deixavam rastro na
    rolagem; so o cartao em foco tem um."""
    for index in range(len(deck_ready.cards)):
        deck_ready._toggle(index) if index not in _marked(deck_ready) else None
    deck_ready._focus_page(0)
    deck_ready.root.update()

    com_campo = [i for i, p in deck_ready.cards.items() if p["entry"] is not None]
    assert com_campo == [0]


def test_typing_a_prefix_updates_every_preview_at_once(deck_ready):
    deck_ready.prefix_var.set("Aula 02")
    deck_ready.suffix_var.set("rev1")
    deck_ready.root.update()
    previa = deck_ready.cards[0]["name_preview"].cget("text")
    assert previa.startswith("Aula 02"), "prefixo digitado desliga a numeracao por padrao"
    assert "rev1.pdf" in previa


def test_editing_the_title_keeps_the_prefix_and_suffix(deck_ready):
    deck_ready.prefix_var.set("Aula 02")
    deck_ready.title_vars[0].set("Meu nome")
    deck_ready.root.update()
    assert deck_ready.cards[0]["name_preview"].cget("text") == "Aula 02 Meu nome.pdf"


def test_the_numbering_checkbox_can_be_forced_back_on_despite_a_prefix(deck_ready):
    """"Somente se o usuario quiser": o padrao muda, mas o controle continua ali."""
    deck_ready.prefix_var.set("Aula 02")
    deck_ready.root.update()
    assert deck_ready.numbered_var.get() is False

    deck_ready.numbered_var.set(True)
    deck_ready._on_numbered_touched()
    deck_ready.root.update()
    assert deck_ready.cards[0]["name_preview"].cget("text").startswith("01 - Aula 02")

    # Depois de tocado a mao, novas teclas no prefixo nao derrubam a escolha.
    deck_ready.suffix_var.set("rev2")
    deck_ready.root.update()
    assert deck_ready.numbered_var.get() is True


def test_emptying_the_title_falls_back_to_the_page_text(deck_ready):
    deck_ready.title_vars[0].set("")
    deck_ready.root.update()
    assert "Bloco A" in deck_ready.cards[0]["name_preview"].cget("text")


# --------------------------------------------------------- navegacao (item 8)
def test_the_back_button_returns_to_the_first_screen(deck_ready):
    deck_ready.back_button.invoke()
    deck_ready.root.update()
    assert _is_shown(deck_ready.open_screen)
    assert not _is_shown(deck_ready.sheet_screen)


def test_the_back_button_points_backwards(deck_ready):
    assert "←" in deck_ready.back_button._text


# ------------------------------------------------- botoes redondos (item 7)
def test_the_clear_button_is_the_red_one(deck_ready):
    fill, _border, _ink = deck_ready.clear_button._looks[0]
    assert fill == gui.theme.DANGER_SOFT
    hover_fill, _b, _i = deck_ready.clear_button._looks[1]
    assert hover_fill == gui.theme.DANGER


def test_the_main_action_is_the_only_orange_button(deck_ready):
    laranjas = [
        botao for botao in (
            deck_ready.cut_button, deck_ready.clear_button, deck_ready.back_button,
            deck_ready.suggest_button, deck_ready.matrix_button, deck_ready.open_button,
        )
        if botao._looks[0][0] == gui.theme.CUT
    ]
    assert laranjas == [deck_ready.cut_button]


def test_a_disabled_button_stops_calling_its_command(deck_ready):
    chamadas = []
    deck_ready.clear_button._command = lambda: chamadas.append(1)
    deck_ready.clear_button.configure(state="disabled")
    deck_ready.clear_button.invoke()
    assert chamadas == []
    deck_ready.clear_button.configure(state="normal")
    deck_ready.clear_button.invoke()
    assert chamadas == [1]


# ------------------------------------------------------------------ lote
# --------------------------------------------- pasta abre ao terminar o corte
def test_finishing_a_cut_opens_the_output_folder(app, monkeypatch, tmp_path):
    """Terminar o corte e sempre seguido de ir ver os arquivos gerados."""
    from slidecut import core

    abertas = []
    monkeypatch.setattr(gui, "open_in_file_manager", lambda p: abertas.append(p))
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *a: None)

    resultado = core.ProcessResult(
        divider_color_hex="#AF6D02", chapters=[], outdir=tmp_path / "saida",
        written=[tmp_path / "saida" / "01 - Capa.pdf"],
    )
    app._events.put(("cut", resultado))
    _pump_until(app, lambda: abertas)

    assert abertas == [tmp_path / "saida"]


# ------------------------------------------------------- aviso de versao
def test_update_notice_stays_hidden_by_default(app):
    assert not _is_shown(app.update_notice)


def test_update_notice_appears_when_a_newer_version_is_found(app):
    from slidecut import updates

    app._show_update_notice(updates.UpdateAvailable(version="9.9.9"))
    app.root.update()
    assert _is_shown(app.update_notice)
    assert "9.9.9" in app.update_notice.cget("text")


def test_clicking_the_update_notice_opens_the_releases_page(app, monkeypatch):
    from slidecut import updates

    abertos = []
    monkeypatch.setattr(gui.webbrowser, "open", lambda url: abertos.append(url))

    app._show_update_notice(updates.UpdateAvailable(version="9.9.9"))
    app._open_update_page()
    assert abertos == [updates.RELEASES_URL]


def test_clicking_the_notice_asks_before_doing_anything(app, monkeypatch):
    """Nada roda sem essa pergunta — nem download, nem navegador."""
    from slidecut import updates

    perguntas = []
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a: perguntas.append(a) or False)
    abertos = []
    monkeypatch.setattr(gui.webbrowser, "open", lambda url: abertos.append(url))

    app._show_update_notice(updates.UpdateAvailable(version="9.9.9"))
    app._on_update_notice_click()

    assert perguntas, "deveria ter perguntado antes de agir"
    assert abertos == [updates.RELEASES_URL], "escolher 'nao' abre o navegador, nao baixa nada"


def test_confirming_the_download_launches_the_installer_and_closes_the_app(
    app, monkeypatch, tmp_path
):
    from slidecut import updates

    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a: True)
    instalador = tmp_path / "slidecut-setup-9.9.9.exe"
    instalador.write_bytes(b"MZ instalador falso")
    monkeypatch.setattr(updates, "download_installer", lambda *a, **kw: instalador)

    lancado = []
    monkeypatch.setattr(gui.subprocess, "Popen", lambda args, **kw: lancado.append(args))
    fechado = []
    monkeypatch.setattr(gui.SlidecutApp, "_on_close", lambda self: fechado.append(True))

    app._show_update_notice(updates.UpdateAvailable(version="9.9.9"))
    app._on_update_notice_click()
    _pump_until(app, lambda: fechado, limit=200)

    assert lancado == [[str(instalador)]]
    assert fechado == [True]


def test_a_failed_download_explains_why_and_lets_the_user_try_again(app, monkeypatch):
    from slidecut import updates

    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *a: True)

    def falha(*_a, **_kw):
        raise updates.UpdateDownloadError("checksum não bateu")

    monkeypatch.setattr(updates, "download_installer", falha)
    erros = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: erros.append(a))

    app._show_update_notice(updates.UpdateAvailable(version="9.9.9"))
    app._on_update_notice_click()
    _pump_until(app, lambda: erros, limit=200)

    assert erros
    assert "checksum" in erros[0][1]
    assert app._updating is False
    assert _is_shown(app.update_notice), "continua ali para o usuario tentar de novo"


def test_the_batch_screen_shares_the_prefix_with_the_single_file_screen(app):
    """Um prefixo escolhido vale para todo arquivo gerado, nao so para uma tela."""
    app._show_batch()
    app.prefix_var.set("Turma A")
    app.root.update()
    app._show_open()
    assert app.prefix_var.get() == "Turma A"
