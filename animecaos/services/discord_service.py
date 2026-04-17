from __future__ import annotations

import logging
import threading
import time

from animecaos.services.config_service import ConfigService

log = logging.getLogger(__name__)

_APP_ID = "1494706525426421760"


class DiscordService:
    """Wraps pypresence for Discord Rich Presence. Fully optional — silently
    no-ops when Discord is not running or the user has disabled it."""

    def __init__(self, config: ConfigService) -> None:
        self._config = config
        self._rpc = None
        self._connected = False
        self._lock = threading.Lock()
        self._start_ts: int = 0

    # ── public ────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        threading.Thread(target=self._do_connect, daemon=True).start()

    def reconnect(self) -> None:
        threading.Thread(target=self._do_reconnect, daemon=True).start()

    def update(self, anime: str, episode: int, total: int) -> None:
        if not self._should_run():
            return
        threading.Thread(
            target=self._do_update,
            args=(anime, episode, total),
            daemon=True,
        ).start()

    def set_loading(self, anime: str, episode: int) -> None:
        if not self._should_run():
            return
        threading.Thread(
            target=self._do_set_loading,
            args=(anime, episode),
            daemon=True,
        ).start()

    def clear(self) -> None:
        if not self._connected:
            return
        threading.Thread(target=self._do_clear, daemon=True).start()

    def disconnect(self) -> None:
        threading.Thread(target=self._do_disconnect, daemon=True).start()

    # ── private ───────────────────────────────────────────────────

    def _should_run(self) -> bool:
        return self._connected and bool(self._config.get("discord_rp_enabled"))

    def _do_connect(self) -> None:
        if not self._config.get("discord_rp_enabled"):
            return
        with self._lock:
            try:
                from pypresence import Presence  # type: ignore
                rpc = Presence(_APP_ID)
                rpc.connect()
                self._rpc = rpc
                self._connected = True
                log.info("Discord RPC conectado")
            except Exception as exc:
                log.warning("Discord RPC nao disponivel: %s", exc)
                self._connected = False

    def _do_reconnect(self) -> None:
        self._do_disconnect()
        self._do_connect()

    def _do_update(self, anime: str, episode: int, total: int) -> None:
        with self._lock:
            if not self._rpc:
                return
            self._start_ts = int(time.time())
            state = f"Ep {episode}" if total <= 0 else f"Ep {episode} de {total}"
            try:
                self._rpc.update(
                    details=anime,
                    state=state,
                    large_image="logo",
                    large_text="AnimeCaos",
                    start=self._start_ts,
                )
            except Exception as exc:
                log.debug("Discord RPC update falhou: %s", exc)
                self._connected = False
                self._rpc = None

    def _do_set_loading(self, anime: str, episode: int) -> None:
        with self._lock:
            if not self._rpc:
                return
            try:
                self._rpc.update(
                    details=anime,
                    state=f"Carregando Ep {episode}...",
                    large_image="logo",
                    large_text="AnimeCaos",
                )
            except Exception as exc:
                log.debug("Discord RPC set_loading falhou: %s", exc)
                self._connected = False
                self._rpc = None

    def _do_clear(self) -> None:
        with self._lock:
            if not self._rpc:
                return
            try:
                self._rpc.clear()
            except Exception as exc:
                log.debug("Discord RPC clear falhou: %s", exc)

    def _do_disconnect(self) -> None:
        with self._lock:
            if self._rpc:
                try:
                    self._rpc.close()
                except Exception:
                    pass
                self._rpc = None
            self._connected = False
