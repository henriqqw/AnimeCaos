"""
Sugestao de usuario: agrupar os episodios baixados em uma subpasta por
anime, em vez de todos soltos direto em Downloads/AnimeCaos/.

Downloads feitos antes desta mudanca ficam soltos na raiz — migrate_to_
subfolders() os move para dentro da subpasta correta, uma unica vez
(chamada pela MainWindow ao abrir a tela de Downloads), de forma idempotente
e sem nunca sobrescrever um arquivo ja existente no destino.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from animecaos.services.downloads_service import DownloadsService, sanitize_anime_filename


def _make_video(path: Path, size: int = 2048) -> None:
    path.write_bytes(b"0" * size)


def test_anime_dir_sanitiza_igual_ao_nome_de_arquivo(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    assert service.anime_dir("One Piece (Dublado)") == tmp_path / sanitize_anime_filename("One Piece (Dublado)")


def test_download_novo_grava_dentro_da_subpasta_do_anime(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    service.write_metadata("Naruto", cover_path="/covers/naruto.jpg")

    sidecar = service.anime_dir("Naruto") / "Naruto.meta.json"
    assert sidecar.exists()


def test_scan_encontra_episodios_dentro_de_subpastas(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    anime_dir = service.anime_dir("Naruto")
    anime_dir.mkdir(parents=True)
    _make_video(anime_dir / "Naruto - EP1.mp4")

    entries = service.scan()
    assert len(entries) == 1
    assert entries[0].anime == "Naruto"
    assert entries[0].episode_num == 1


def test_scan_ainda_encontra_arquivos_soltos_na_raiz_para_compatibilidade(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    _make_video(tmp_path / "One Piece - EP1.mp4")

    entries = service.scan()
    assert len(entries) == 1
    assert entries[0].anime == "One Piece"


def test_migrate_move_arquivo_e_sidecar_e_devolve_1(tmp_path):
    _make_video(tmp_path / "One Piece - EP1.mp4")
    (tmp_path / "One Piece.meta.json").write_text('{"anime": "One Piece", "cover_path": null}', encoding="utf-8")

    service = DownloadsService(download_dir=tmp_path)
    moved = service.migrate_to_subfolders()

    assert moved == 1
    assert (tmp_path / "One Piece" / "One Piece - EP1.mp4").exists()
    assert (tmp_path / "One Piece" / "One Piece.meta.json").exists()
    assert not (tmp_path / "One Piece - EP1.mp4").exists()


def test_migrate_e_idempotente(tmp_path):
    _make_video(tmp_path / "One Piece - EP1.mp4")
    service = DownloadsService(download_dir=tmp_path)

    first = service.migrate_to_subfolders()
    second = service.migrate_to_subfolders()

    assert first == 1
    assert second == 0


def test_migrate_nao_sobrescreve_arquivo_ja_existente_no_destino(tmp_path):
    anime_dir = tmp_path / "One Piece"
    anime_dir.mkdir()
    _make_video(anime_dir / "One Piece - EP1.mp4", size=999)  # ja existe, arquivo "real"
    _make_video(tmp_path / "One Piece - EP1.mp4", size=1)  # solto na raiz, nao deve sobrescrever

    service = DownloadsService(download_dir=tmp_path)
    service.migrate_to_subfolders()

    # O arquivo de destino continua o "real" (999 bytes) — nao foi
    # sobrescrito pelo duplicado solto na raiz.
    assert (anime_dir / "One Piece - EP1.mp4").stat().st_size == 999
    # O duplicado solto continua no lugar (migracao pulou, nao apagou).
    assert (tmp_path / "One Piece - EP1.mp4").exists()


def test_delete_do_ultimo_episodio_remove_a_pasta_vazia(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    service.write_metadata("Naruto")
    anime_dir = service.anime_dir("Naruto")
    video = anime_dir / "Naruto - EP1.mp4"
    _make_video(video)

    entries = service.scan()
    assert len(entries) == 1

    assert service.delete(entries[0]) is True
    assert not anime_dir.exists()


def test_delete_nao_remove_a_pasta_se_ainda_ha_outros_episodios(tmp_path):
    service = DownloadsService(download_dir=tmp_path)
    anime_dir = service.anime_dir("Naruto")
    anime_dir.mkdir(parents=True)
    _make_video(anime_dir / "Naruto - EP1.mp4")
    _make_video(anime_dir / "Naruto - EP2.mp4")

    entries = service.scan()
    to_delete = next(e for e in entries if e.episode_num == 1)
    service.delete(to_delete)

    assert anime_dir.exists()
    assert (anime_dir / "Naruto - EP2.mp4").exists()


# ── integracao com MainWindow ──────────────────────────────────────


class _InertDownloadWorker(QRunnable):
    """Captures the out_template it would have downloaded to, without
    touching the network or spawning yt-dlp — used only to verify the queue
    points DownloadWorker at the right (per-anime subfolder) path."""

    captured: list[tuple[str, str]] = []

    def __init__(self, url: str, out_template: str) -> None:
        super().__init__()
        self.signals = _InertSignals()
        _InertDownloadWorker.captured.append((url, out_template))

    def cancel(self) -> None:
        pass

    def run(self) -> None:
        pass


class _InertSignals(QObject):
    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()


def test_download_via_fila_grava_dentro_da_subpasta_do_anime(main_window_factory, tmp_path, qtbot):
    window = main_window_factory()
    window._downloads_service = DownloadsService(download_dir=tmp_path)
    # A fila (self._download_queue) capturou uma referencia ao DownloadsService
    # original na construcao da MainWindow — precisa apontar pra mesma
    # instancia trocada acima, senao o download continuaria indo pro
    # diretorio real de Downloads do usuario. A factory tambem e trocada por
    # uma versao inerte, so pra capturar o out_template sem rodar yt-dlp de
    # verdade.
    window._download_queue._downloads_service = window._downloads_service
    window._download_queue._download_worker_factory = _InertDownloadWorker
    _InertDownloadWorker.captured.clear()

    window._detail_view.set_anime("Naruto")
    window._current_anime = "Naruto"
    window._on_episode_download_clicked(0)

    qtbot.waitUntil(lambda: bool(_InertDownloadWorker.captured), timeout=2000)
    _url, out_template = _InertDownloadWorker.captured[0]
    expected_dir = window._downloads_service.anime_dir("Naruto")
    assert out_template.startswith(str(expected_dir))
