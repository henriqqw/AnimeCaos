"""
Tres sugestoes dos usuarios sao o mesmo problema arquitetural: hoje existe
UM _active_download_worker em MainWindow e um segundo download e
simplesmente recusado ("Ja existe um download em andamento"). DownloadQueueService
substitui isso por uma fila real: downloads simultaneos (ate max_concurrent),
download em lote (enqueue_many) e downloads em segundo plano (a fila continua
rodando independente do que a UI mostra).

O resolver (equivalente a AnimeService.resolve_player_url) e injetado para
que os testes rodem contra um fake, sem rede nem Selenium — e o download em
si tambem usa uma factory injetavel no lugar do DownloadWorker real (que
chama yt-dlp de verdade), para os testes controlarem exatamente quando cada
item "termina" sem depender de timing de subprocess real.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from animecaos.services.downloads_service import DownloadsService
from animecaos.services.download_queue_service import DownloadQueueService


class _FakeWorkerSignals(QObject):
    progress = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()


class _FakeDownloadWorker(QRunnable):
    """Stand-in for the real DownloadWorker (which shells out to yt-dlp) —
    tests hold it open with an Event and decide exactly when/how it
    finishes, instead of depending on real subprocess timing."""

    instances: list["_FakeDownloadWorker"] = []

    def __init__(self, url: str, out_template: str) -> None:
        super().__init__()
        self.url = url
        self.out_template = out_template
        self.signals = _FakeWorkerSignals()
        self.cancelled = False
        self.release = threading.Event()
        self.outcome = "succeeded"  # or "failed"
        self.error_text = "erro simulado"
        _FakeDownloadWorker.instances.append(self)

    def cancel(self) -> None:
        self.cancelled = True
        self.release.set()

    def run(self) -> None:
        self.release.wait(timeout=5)
        if self.cancelled:
            self.signals.failed.emit("Download cancelado.")
        elif self.outcome == "succeeded":
            self.signals.succeeded.emit(self.out_template)
        else:
            self.signals.failed.emit(self.error_text)
        self.signals.finished.emit()


def _make_resolver(fail_for: set[tuple[str, int]] | None = None):
    fail_for = fail_for or set()
    calls: list[tuple[str, int]] = []

    def resolver(anime: str, episode_index: int) -> str:
        calls.append((anime, episode_index))
        if (anime, episode_index) in fail_for:
            raise RuntimeError("falha ao resolver")
        return f"https://example.com/{anime}/{episode_index}.mp4"

    resolver.calls = calls
    return resolver


def _make_queue(tmp_path, max_concurrent=2, resolver=None):
    _FakeDownloadWorker.instances.clear()
    resolver = resolver or _make_resolver()
    downloads_service = DownloadsService(download_dir=tmp_path)
    thread_pool = QThreadPool.globalInstance()
    return DownloadQueueService(
        resolver=resolver,
        downloads_service=downloads_service,
        thread_pool=thread_pool,
        max_concurrent=max_concurrent,
        download_worker_factory=_FakeDownloadWorker,
    )


def _release_all(workers: list[_FakeDownloadWorker]) -> None:
    for w in workers:
        w.release.set()
    # Drain the shared QThreadPool before the test returns — otherwise a
    # worker still finishing on a background thread can emit through its
    # QObject signals after the test's local references (and pytest-qt's
    # own per-test cleanup) have let them get garbage-collected, which
    # surfaces as a noisy (but harmless) "Signal source has been deleted".
    QThreadPool.globalInstance().waitForDone(2000)


# ── enqueue / item_added ────────────────────────────────────────────


def test_enqueue_emite_item_added_com_status_queued_ou_ja_iniciado(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    received = []
    queue.item_added.connect(received.append)

    item = queue.enqueue("Naruto", 0)

    assert received == [item]
    # Com uma vaga livre, o item enfileirado imediatamente comeca a resolver.
    qtbot.waitUntil(lambda: item.status in ("resolving", "downloading"), timeout=2000)

    _release_all(_FakeDownloadWorker.instances)


# ── concorrencia ─────────────────────────────────────────────────────


def test_max_concurrent_limita_downloads_simultaneos(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=2)
    items = queue.enqueue_many("One Piece", [0, 1, 2, 3, 4])

    def _two_downloading():
        assert sum(1 for i in items if i.status == "downloading") == 2

    qtbot.waitUntil(_two_downloading, timeout=2000)
    assert sum(1 for i in items if i.status == "queued") == 3

    _release_all(_FakeDownloadWorker.instances)


def test_terminar_um_item_promove_o_proximo_da_fila(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0, 1])

    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)
    assert items[1].status == "queued"

    _FakeDownloadWorker.instances[0].release.set()

    qtbot.waitUntil(lambda: items[0].status == "done", timeout=2000)
    qtbot.waitUntil(lambda: items[1].status == "downloading", timeout=2000)

    _release_all(_FakeDownloadWorker.instances)


def test_set_max_concurrent_promove_itens_pendentes_imediatamente(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0, 1, 2])

    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)
    assert items[1].status == "queued"
    assert items[2].status == "queued"

    queue.set_max_concurrent(3)

    qtbot.waitUntil(lambda: items[1].status == "downloading", timeout=2000)
    qtbot.waitUntil(lambda: items[2].status == "downloading", timeout=2000)

    _release_all(_FakeDownloadWorker.instances)


# ── cancelamento ─────────────────────────────────────────────────────


def test_cancel_de_item_ainda_em_fila_nunca_inicia_um_worker(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0, 1])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    assert queue.cancel(items[1].id) is True
    assert items[1].status == "cancelled"

    # Nenhum worker chegou a ser criado para o item 1 (so o item 0 esta na lista).
    assert len(_FakeDownloadWorker.instances) == 1

    _release_all(_FakeDownloadWorker.instances)


def test_cancel_de_item_em_download_chama_worker_cancel(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    assert queue.cancel(items[0].id) is True
    assert _FakeDownloadWorker.instances[0].cancelled is True
    assert items[0].status == "cancelled"

    QThreadPool.globalInstance().waitForDone(2000)


def test_cancel_all_esvazia_a_fila_e_nao_deixa_worker_orfao(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=2)
    items = queue.enqueue_many("One Piece", [0, 1, 2, 3])
    qtbot.waitUntil(lambda: sum(1 for i in items if i.status == "downloading") == 2, timeout=2000)

    queue.cancel_all()

    assert queue.active == []
    assert queue.pending == []
    assert all(i.status == "cancelled" for i in items)
    for w in _FakeDownloadWorker.instances:
        assert w.cancelled is True

    QThreadPool.globalInstance().waitForDone(2000)


# ── falhas ───────────────────────────────────────────────────────────


def test_falha_na_resolucao_marca_failed_e_nao_trava_a_fila(qtbot, tmp_path):
    resolver = _make_resolver(fail_for={("Naruto", 0)})
    queue = _make_queue(tmp_path, max_concurrent=1, resolver=resolver)
    items = queue.enqueue_many("Naruto", [0, 1])

    qtbot.waitUntil(lambda: items[0].status == "failed", timeout=2000)
    assert items[0].error

    qtbot.waitUntil(lambda: items[1].status == "downloading", timeout=2000)

    _release_all(_FakeDownloadWorker.instances)


def test_download_com_falha_tambem_libera_a_fila(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0, 1])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    _FakeDownloadWorker.instances[0].outcome = "failed"
    _FakeDownloadWorker.instances[0].release.set()

    qtbot.waitUntil(lambda: items[0].status == "failed", timeout=2000)
    qtbot.waitUntil(lambda: items[1].status == "downloading", timeout=2000)

    _release_all(_FakeDownloadWorker.instances)


# ── all_finished ─────────────────────────────────────────────────────


def test_all_finished_emite_uma_unica_vez_quando_a_fila_esvazia(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=2)
    received = []
    queue.all_finished.connect(lambda: received.append(1))

    items = queue.enqueue_many("One Piece", [0, 1, 2])
    qtbot.waitUntil(lambda: sum(1 for i in items if i.status == "downloading") == 2, timeout=2000)

    # Termina os dois ativos; o terceiro entao comeca e tambem termina.
    _FakeDownloadWorker.instances[0].release.set()
    _FakeDownloadWorker.instances[1].release.set()
    qtbot.waitUntil(lambda: items[2].status == "downloading", timeout=2000)
    _FakeDownloadWorker.instances[2].release.set()

    qtbot.waitUntil(lambda: all(i.status == "done" for i in items), timeout=2000)
    qtbot.waitUntil(lambda: len(received) >= 1, timeout=2000)

    assert received == [1]


# ── parsing de progresso do yt-dlp ───────────────────────────────────


def test_parse_progress_line_extrai_percentual_velocidade_e_eta():
    from animecaos.services.download_queue_service import _parse_progress_line

    line = "[download]  45.2% of   123.45MiB at    1.23MiB/s ETA 00:12"
    parsed = _parse_progress_line(line)

    assert parsed["percent"] == 45.2
    assert parsed["speed"] == "1.23MiB/s"
    assert parsed["eta"] == "00:12"


def test_parse_progress_line_sem_percentual_devolve_dict_vazio():
    from animecaos.services.download_queue_service import _parse_progress_line

    assert _parse_progress_line("Merging formats into output.mp4") == {}


# ── prevencao de downloads duplicados ────────────────────────────────


def test_find_active_or_queued_encontra_item_ainda_na_fila(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0, 1])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    found = queue.find_active_or_queued("One Piece", 1)  # ainda "queued"
    assert found is items[1]

    _release_all(_FakeDownloadWorker.instances)


def test_find_active_or_queued_encontra_item_baixando(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    found = queue.find_active_or_queued("One Piece", 0)
    assert found is items[0]

    _release_all(_FakeDownloadWorker.instances)


def test_find_active_or_queued_ignora_itens_concluidos_ou_cancelados(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=1)
    items = queue.enqueue_many("One Piece", [0])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)
    _FakeDownloadWorker.instances[0].release.set()
    qtbot.waitUntil(lambda: items[0].status == "done", timeout=2000)

    assert queue.find_active_or_queued("One Piece", 0) is None


def test_find_active_or_queued_nao_confunde_animes_ou_episodios_diferentes(qtbot, tmp_path):
    queue = _make_queue(tmp_path, max_concurrent=2)
    items = queue.enqueue_many("One Piece", [0, 1])
    qtbot.waitUntil(lambda: items[0].status == "downloading", timeout=2000)

    assert queue.find_active_or_queued("Naruto", 0) is None
    assert queue.find_active_or_queued("One Piece", 5) is None

    _release_all(_FakeDownloadWorker.instances)


def test_find_active_or_queued_sem_nada_na_fila_devolve_none(tmp_path):
    queue = _make_queue(tmp_path)
    assert queue.find_active_or_queued("One Piece", 0) is None
