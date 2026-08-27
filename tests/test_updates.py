from __future__ import annotations

import pytest

from slidecut import updates


# ------------------------------------------------------ leitura da versao
def test_parse_version_reads_the_tag_out_of_the_release_url():
    url = "https://github.com/AlexMoreiraCorp/slidecut/releases/tag/v0.10.6"
    assert updates.parse_version(url) == "0.10.6"


def test_parse_version_accepts_a_tag_without_the_v_prefix():
    assert updates.parse_version("https://x/releases/tag/1.2.3") == "1.2.3"


def test_parse_version_returns_none_when_there_is_no_tag_in_the_url():
    assert updates.parse_version("https://github.com/x/y/releases") is None


def test_the_version_source_has_no_request_quota():
    """A API do GitHub limita 60 consultas por hora por IP. Num time atras do
    mesmo IP corporativo isso estoura, e ai ninguem mais recebe aviso nenhum.
    A pagina de releases nao tem essa cota — e continua sendo o release, entao
    so anuncia versao que ja tem instalador publicado."""
    assert "api.github.com" not in updates.VERSION_URL
    assert "raw.githubusercontent" not in updates.VERSION_URL
    assert updates.VERSION_URL == updates.RELEASES_URL


# ------------------------------------------------------- comparar versoes
def test_is_newer_detects_a_higher_patch():
    assert updates.is_newer("0.10.3", "0.10.4") is True


def test_is_newer_detects_a_higher_minor_even_with_lower_patch():
    assert updates.is_newer("0.10.9", "0.11.0") is True


def test_is_newer_is_false_for_the_same_version():
    assert updates.is_newer("0.10.3", "0.10.3") is False


def test_is_newer_is_false_when_remote_is_older():
    assert updates.is_newer("0.10.3", "0.9.9") is False


def test_is_newer_tolerates_a_leading_v():
    assert updates.is_newer("0.10.3", "v0.10.4") is True


def test_is_newer_treats_garbage_as_not_newer():
    """Uma resposta inesperada nao pode acender um alarme falso de atualizacao."""
    assert updates.is_newer("0.10.3", "isso nao e versao nenhuma") is False


# -------------------------------------------------- verificacao ponta a ponta
def test_check_for_update_reports_a_newer_version_available():
    resultado = updates.check_for_update("0.10.3", fetch=lambda url: "https://x/releases/tag/v0.10.4")
    assert resultado is not None
    assert resultado.version == "0.10.4"
    assert resultado.url == updates.RELEASES_URL


def test_check_for_update_is_none_when_already_up_to_date():
    resultado = updates.check_for_update("0.10.4", fetch=lambda url: "https://x/releases/tag/v0.10.4")
    assert resultado is None


def test_check_for_update_is_none_when_the_network_fails():
    """Sem internet, ou GitHub fora do ar: o app segue normal, sem travar nem avisar errado."""
    def falha(_url):
        raise OSError("sem rede")

    assert updates.check_for_update("0.10.3", fetch=falha) is None


def test_check_for_update_is_none_when_the_response_is_unparseable():
    resultado = updates.check_for_update("0.10.3", fetch=lambda url: "https://github.com/x/y/releases")
    assert resultado is None


def test_check_for_update_never_raises_even_on_a_surprising_error():
    def explode(_url):
        raise ValueError("qualquer coisa inesperada")

    assert updates.check_for_update("0.10.3", fetch=explode) is None


# --------------------------------------------------------- baixar e instalar
def test_installer_url_follows_the_release_asset_convention():
    assert updates.installer_url("0.10.5") == (
        "https://github.com/AlexMoreiraCorp/slidecut/releases/download/"
        "v0.10.5/slidecut-setup-0.10.5.exe"
    )


def test_checksum_url_points_to_the_sidecar_file():
    assert updates.checksum_url("0.10.5") == (
        "https://github.com/AlexMoreiraCorp/slidecut/releases/download/"
        "v0.10.5/slidecut-setup-0.10.5.exe.sha256"
    )


def test_verify_sha256_accepts_matching_bytes():
    dados = b"conteudo qualquer"
    import hashlib

    digest = hashlib.sha256(dados).hexdigest()
    assert updates.verify_sha256(dados, digest) is True


def test_verify_sha256_rejects_a_mismatch():
    assert updates.verify_sha256(b"conteudo qualquer", "0" * 64) is False


def test_verify_sha256_ignores_case_and_surrounding_whitespace():
    """O arquivo .sha256 costuma vir como 'HASH  nome-do-arquivo\\n'."""
    import hashlib

    dados = b"conteudo qualquer"
    digest = hashlib.sha256(dados).hexdigest().upper()
    assert updates.verify_sha256(dados, f"  {digest}  arquivo.exe\n") is True


def test_download_installer_writes_the_verified_file(tmp_path):
    import hashlib

    conteudo = b"MZ" + b"instalador falso" * 10
    digest = hashlib.sha256(conteudo).hexdigest()

    def fetch_bytes(url):
        if url.endswith(".sha256"):
            return digest.encode()
        return conteudo

    destino = updates.download_installer("0.10.5", tmp_path, fetch_bytes=fetch_bytes)
    assert destino.name == "slidecut-setup-0.10.5.exe"
    assert destino.read_bytes() == conteudo


def test_download_installer_refuses_a_file_that_fails_the_checksum(tmp_path):
    def fetch_bytes(url):
        if url.endswith(".sha256"):
            return b"0" * 64
        return b"MZ conteudo adulterado"

    with pytest.raises(updates.UpdateDownloadError, match="[Ii]ntegridade"):
        updates.download_installer("0.10.5", tmp_path, fetch_bytes=fetch_bytes)
    assert not (tmp_path / "slidecut-setup-0.10.5.exe").exists()


def test_download_installer_wraps_a_network_failure(tmp_path):
    def fetch_bytes(_url):
        raise OSError("sem rede")

    with pytest.raises(updates.UpdateDownloadError):
        updates.download_installer("0.10.5", tmp_path, fetch_bytes=fetch_bytes)


def test_download_installer_never_leaves_a_partial_file_behind(tmp_path):
    """Se a verificacao falhar, nao pode sobrar um .exe incompleto ou adulterado
    no disco esperando alguem clicar nele sem saber."""
    def fetch_bytes(url):
        if url.endswith(".sha256"):
            return b"0" * 64
        return b"lixo"

    with pytest.raises(updates.UpdateDownloadError):
        updates.download_installer("0.10.5", tmp_path, fetch_bytes=fetch_bytes)
    assert list(tmp_path.iterdir()) == []
