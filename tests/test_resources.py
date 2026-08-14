from __future__ import annotations

from slidecut import resources


def test_icon_ships_with_the_package():
    icon = resources.icon_path()
    assert icon.is_file()
    assert icon.suffix == ".ico"


def test_icon_lives_inside_the_package_so_it_survives_freezing():
    """Empacotado com PyInstaller, o icone tem de acompanhar o modulo."""
    icon = resources.icon_path()
    package_dir = resources.PACKAGE_DIR
    assert package_dir in icon.parents


def test_icon_file_is_a_real_ico():
    header = resources.icon_path().read_bytes()[:4]
    assert header == b"\x00\x00\x01\x00"
