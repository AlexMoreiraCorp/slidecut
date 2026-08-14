from __future__ import annotations

from slidecut import cli


def test_split_run_writes_files_and_reports_success(deck, tmp_path, capsys):
    code = cli.main([str(deck), "-o", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert code == 0
    assert (tmp_path / "out" / "01 - Capa.pdf").exists()
    assert "4" in out


def test_list_mode_reports_dividers_without_writing(deck, tmp_path, capsys):
    outdir = tmp_path / "out"
    code = cli.main([str(deck), "--list", "-o", str(outdir)])
    out = capsys.readouterr().out
    assert code == 0
    assert not outdir.exists()
    assert "Conceito" in out


def test_missing_dividers_returns_error_code(deck_no_dividers, tmp_path, capsys):
    code = cli.main([str(deck_no_dividers), "-o", str(tmp_path / "out")])
    assert code == 2
    assert "--color" in capsys.readouterr().err


def test_explicit_color_is_honoured(deck, tmp_path):
    assert cli.main([str(deck), "--color", "#B06E03", "-o", str(tmp_path / "out")]) == 0


def test_invalid_color_returns_error_code(deck, tmp_path, capsys):
    assert cli.main([str(deck), "--color", "roxo", "-o", str(tmp_path / "out")]) == 2
    assert "cor" in capsys.readouterr().err.lower()


def test_missing_input_returns_error_code(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nada.pptx"), "-o", str(tmp_path / "out")]) == 2
    assert capsys.readouterr().err


def test_default_output_dir_is_derived_from_input_name(deck, tmp_path):
    assert cli.main([str(deck)]) == 0
    assert (deck.parent / "deck - cortes").is_dir()


def test_ascii_flag_produces_ascii_filenames(tmp_path, capsys):
    from tests.conftest import ORANGE, WHITE, build_pdf

    src = build_pdf(
        tmp_path / "acentos.pdf",
        [(ORANGE, "Cooperação"), (WHITE, "x"), (ORANGE, "Isonomia"), (WHITE, "y")],
    )
    cli.main([str(src), "--ascii", "-o", str(tmp_path / "out")])
    assert (tmp_path / "out" / "01 - Cooperacao.pdf").exists()


def test_color_that_matches_nothing_returns_error_code(deck, tmp_path, capsys):
    assert cli.main([str(deck), "--color", "#00FF00", "-o", str(tmp_path / "out")]) == 2
    assert "--tolerance" in capsys.readouterr().err


def test_corrupt_pdf_returns_error_code(tmp_path, capsys):
    broken = tmp_path / "quebrado.pdf"
    broken.write_bytes(b"nao sou um pdf")
    assert cli.main([str(broken), "-o", str(tmp_path / "out")]) == 2
    assert "Erro" in capsys.readouterr().err
