"""Excecoes do slidecut."""

from __future__ import annotations


class SlidecutError(Exception):
    """Erro base da aplicacao."""


class UnsupportedFormat(SlidecutError):
    """Extensao de entrada que o slidecut nao sabe converter."""


class ConversionError(SlidecutError):
    """Falha ao converter o arquivo de entrada para PDF."""


class AnalysisError(SlidecutError):
    """PDF corrompido, protegido por senha ou ilegivel."""
