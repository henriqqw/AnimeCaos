"""
Sugestao de usuario: fechamento automatico da tela/overlay de Downloads
quando tudo termina. Integra DownloadQueueService.all_finished com o
QTimer de auto-fechar da MainWindow, usando o mesmo _FakeDownloadWorker
controlavel de tests/test_download_queue.py para nao depender de yt-dlp
real nem de timing de subprocess.
"""
from __future__ import annotations

from PySide6.QtCore import QThreadPool

from animecaos.services.downloads_service import DownloadsService
from animecaos.services.download_queue_service import DownloadQueueService
from tests.test_download_queue import _FakeDownloadWorker, _make_resolver


def _make_window_with_queue(main_window_factory, tmp_path, max_concurrent=1):
    _FakeDownloadWorker.instances.clear()
    downloads_service = DownloadsService(download_dir=tmp_path)
    queue = DownloadQueueService(
        resolver=_make_resolver(),
        downloads_service=downloads_service,
        thread_pool=QThreadPool.globalInstance(),
        max_concurrent=max_concurrent,
        download_worker_factory=_FakeDownloadWorker,
    )
    window = main_window_factory(download_queue_service=queue)
    window._downloads_service = downloads_service
    return window


def _release_worker(qtbot, index: int) -> None:
    """Waits for the fake worker at `index` to actually exist (resolving
    happens on a background thread, so it may not be there the instant the
    overlay becomes visible) before releasing it."""
    qtbot.waitUntil(lambda: len(_FakeDownloadWorker.instances) > index, timeout=2000)
    _FakeDownloadWorker.instances[index].release.set()


def _drain_queue_until_done(window, qtbot) -> None:
    """Repeatedly releases every fake worker seen so far — including ones
    that only get created once an earlier item finishes and the next is
    promoted — until the overlay reaches the DONE state."""
    def _tick():
        for w in _FakeDownloadWorker.instances:
            w.release.set()
        assert window._download_overlay._state == window._download_overlay._ST_DONE

    qtbot.waitUntil(_tick, timeout=3000)


def test_auto_fechar_ligado_esconde_o_overlay_apos_o_atraso(main_window_factory, tmp_path, qtbot):
    window = _make_window_with_queue(main_window_factory, tmp_path)
    window._config_service.set("downloads_auto_close", True)
    window._config_service.set("downloads_auto_close_delay_ms", 50)

    window._download_queue.enqueue("Naruto", 0)
    qtbot.waitUntil(lambda: window._download_overlay.isVisible(), timeout=2000)

    _release_worker(qtbot, 0)
    qtbot.waitUntil(lambda: window._download_overlay._state == window._download_overlay._ST_DONE, timeout=2000)

    qtbot.waitUntil(lambda: window._download_overlay.isVisible() is False, timeout=2000)


def test_auto_fechar_desligado_mantem_o_overlay_no_estado_done(main_window_factory, tmp_path, qtbot):
    window = _make_window_with_queue(main_window_factory, tmp_path)
    window._config_service.set("downloads_auto_close", False)

    window._download_queue.enqueue("Naruto", 0)
    qtbot.waitUntil(lambda: window._download_overlay.isVisible(), timeout=2000)

    _release_worker(qtbot, 0)
    qtbot.waitUntil(lambda: window._download_overlay._state == window._download_overlay._ST_DONE, timeout=2000)

    qtbot.wait(200)
    assert window._download_overlay.isVisible() is True


def test_novo_item_durante_o_atraso_cancela_o_auto_fechamento(main_window_factory, tmp_path, qtbot):
    window = _make_window_with_queue(main_window_factory, tmp_path, max_concurrent=1)
    window._config_service.set("downloads_auto_close", True)
    window._config_service.set("downloads_auto_close_delay_ms", 300)

    window._download_queue.enqueue("Naruto", 0)
    qtbot.waitUntil(lambda: window._download_overlay.isVisible(), timeout=2000)
    _release_worker(qtbot, 0)
    qtbot.waitUntil(lambda: window._download_auto_close_timer.isActive(), timeout=2000)

    # Um novo download entra na fila durante a janela de auto-fechamento.
    window._download_queue.enqueue("One Piece", 0)

    assert window._download_auto_close_timer.isActive() is False
    assert window._download_overlay.isVisible() is True

    _release_worker(qtbot, 1)
    qtbot.waitUntil(lambda: window._download_overlay._state == window._download_overlay._ST_DONE, timeout=2000)


def test_overlay_reflete_o_agregado_da_fila_nao_o_primeiro_item(main_window_factory, tmp_path, qtbot):
    window = _make_window_with_queue(main_window_factory, tmp_path, max_concurrent=2)

    window._download_queue.enqueue_many("One Piece", [0, 1, 2])

    def _two_active():
        assert len(window._download_queue.active) == 2

    qtbot.waitUntil(_two_active, timeout=2000)
    qtbot.waitUntil(lambda: "2" in window._download_overlay._anime_name, timeout=2000)
    assert "1 na fila" in window._download_overlay._episode_label

    _drain_queue_until_done(window, qtbot)
