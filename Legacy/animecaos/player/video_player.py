import os
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

from animecaos.core.paths import get_bin_path
from animecaos.services.dependency_service import DependencyService


def _build_referer(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


# mpv's human-readable exit message changed across versions:
#   mpv < 0.29 (2018): "Exiting... (End of file)"
#   mpv >= 0.29 (current): "Exiting... (Eof reached)"
# Check both so natural-end detection works regardless of the bundled/system
# mpv version — this is the only signal autoplay uses to advance to the next
# episode, so a stale/incomplete match here silently breaks autoplay.
_EOF_LOG_MARKERS = ("Exiting... (Eof reached)", "Exiting... (End of file)")


def _detect_natural_eof(log: str) -> bool:
    """True only if mpv reported reaching the real end of the video — NOT
    just that the user watched it for a while and then closed the player."""
    return any(marker in log for marker in _EOF_LOG_MARKERS)


def _missing_mpv_message() -> str:
    """Composes an actionable error for a missing mpv, instead of the bare
    'nao esta instalado ou nao esta no PATH' users had no way to act on —
    reported verbatim on Linux as 'Erro ao nao encontrar o MPV instalado'
    with no indication of what to do about it."""
    hint = DependencyService().check("mpv").install_hint
    return f"mpv nao foi encontrado. {hint}"


def _build_mpv_command(url: str) -> list[str]:
    is_local = not url.startswith(("http://", "https://"))
    cmd = [
        get_bin_path("mpv"),
        url,
        "--ontop",
        "--autofit=50%",
        "--geometry=50%:50%",
        "--cursor-autohide=1000",
        "--msg-level=all=warn,cplayer=info,status=info",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        # HLS: always pick the highest-bitrate variant (1080p > 720p > ...).
        "--hls-bitrate=max",
        # Prefer video formats in quality order; avoids accidentally playing
        # a low-quality fallback when the stream has multiple representations.
        "--ytdl-format=bestvideo[height>=1080]+bestaudio/bestvideo[height>=720]+bestaudio/bestvideo+bestaudio/best",
    ]
    if not is_local:
        cmd.append(f"--referrer={_build_referer(url)}")
    return cmd


def build_player_command(url: str, mode: str = "mpv", player_path: str | None = None) -> list[str]:
    """Builds the subprocess argv for the given player mode, without
    launching anything — kept pure/side-effect-free so it's testable on its
    own (unlike the mpv branch's `--log-file`, which needs a real temp file
    and is added by _play_with_mpv() instead, at actual playback time)."""
    if mode == "mpv":
        return _build_mpv_command(url)
    if mode == "custom":
        if not player_path:
            raise ValueError(
                "Nenhum player personalizado configurado — defina o caminho em Configuracoes > Player."
            )
        return [player_path, url]
    if mode == "system":
        if sys.platform == "win32":
            return ["cmd", "/c", "start", "", url]
        if sys.platform == "darwin":
            return ["open", url]
        return ["xdg-open", url]
    raise ValueError(f"Modo de player desconhecido: {mode!r}")


def _play_with_mpv(url: str) -> dict[str, bool]:
    log_fd, log_path = tempfile.mkstemp(suffix=".log", prefix="mpv_")
    os.close(log_fd)

    cmd = _build_mpv_command(url) + [f"--log-file={log_path}"]

    _start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EnvironmentError(_missing_mpv_message()) from exc
    elapsed = time.monotonic() - _start

    if result.returncode != 0 and result.returncode != 4:
        try:
            os.unlink(log_path)
        except OSError:
            pass
        raise RuntimeError(f"mpv encerrou com codigo {result.returncode}.")

    try:
        log = open(log_path, encoding="utf-8", errors="replace").read()
    except OSError:
        log = ""
    finally:
        try:
            os.unlink(log_path)
        except OSError:
            pass

    # Natural EOF: the episode actually played through to its end. This is
    # the only condition that should trigger autoplay to the next episode —
    # closing the player manually must never advance, no matter how long it
    # was open for.
    eof_natural = _detect_natural_eof(log)

    # Watched long enough: player was open >= 30 s (wall-clock), or reached a
    # natural EOF faster than that (short episode/OP). Used only to decide
    # whether to sync progress to AniList — intentionally more lenient than
    # eof_natural since a spurious progress update is low-stakes, unlike
    # autoplay jumping to a episode the user didn't ask for.
    watched = eof_natural or elapsed >= 30.0
    return {"eof": eof_natural, "watched": watched}


def _play_with_system_opener(url: str) -> dict[str, bool]:
    """Hands off to the OS's default handler and returns immediately —
    there's no way to know when (or whether) the user finishes watching, so
    eof/watched are always False. autoplay and AniList progress sync are
    silently unavailable in this mode; the settings screen warns about this
    up front (see settings_view.py)."""
    cmd = build_player_command(url, mode="system")
    try:
        subprocess.Popen(cmd)
    except FileNotFoundError as exc:
        raise EnvironmentError("Nao foi possivel abrir o player padrao do sistema.") from exc
    return {"eof": False, "watched": False}


def _play_with_custom_player(url: str, player_path: str | None) -> dict[str, bool]:
    """Runs the user's chosen player and waits for it to exit. Like the
    system opener, there's no log to read eof from — only the coarse
    elapsed-time heuristic (also used by mpv as a fallback) is available."""
    cmd = build_player_command(url, mode="custom", player_path=player_path)
    _start = time.monotonic()
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except FileNotFoundError as exc:
        raise EnvironmentError(f"Player personalizado nao encontrado: {player_path!r}") from exc
    elapsed = time.monotonic() - _start
    return {"eof": False, "watched": elapsed >= 30.0}


def play_video(
    url: str,
    debug: bool = False,
    mode: str = "mpv",
    player_path: str | None = None,
) -> dict[str, bool]:
    if debug:
        return {"eof": False, "watched": False}

    if not url:
        raise RuntimeError("Caminho de video invalido.")

    is_local = not url.startswith(("http://", "https://"))
    if is_local and not os.path.isfile(url):
        raise RuntimeError(f"Arquivo nao encontrado: {url!r}")

    if mode == "system":
        return _play_with_system_opener(url)
    if mode == "custom":
        return _play_with_custom_player(url, player_path)
    return _play_with_mpv(url)
