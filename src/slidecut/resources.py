"""Arquivos que acompanham o codigo (hoje, o icone).

O icone mora dentro do pacote, e nao numa pasta assets na raiz do projeto, para
que o mesmo caminho valha nos dois modos: rodando do fonte e dentro do
executavel do PyInstaller — ali o pacote e desempacotado com a mesma estrutura,
entao Path(__file__).parent continua apontando para o lugar certo.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"


def icon_path() -> Path:
    """Caminho do icone da aplicacao (.ico)."""
    return ASSETS_DIR / "icon.ico"
