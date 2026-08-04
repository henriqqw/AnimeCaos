import os
import subprocess
import tempfile
import time
from urllib.parse import urlparse

from animecaos.core.paths import get_bin_path


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


def play_video(url: str, debug: bool = False) -> dict[str, bool]:
    if debug:
        return {"eof": False, "watched": False}

    if not url:
        raise RuntimeError("Caminho de video invalido.")

    is_local = not url.startswith(("http://", "https://"))
    if is_local and not os.path.isfile(url):
        raise RuntimeError(f"Arquivo nao encontrado: {url!r}")

    log_fd, log_path = tempfile.mkstemp(suffix=".log", prefix="mpv_")
    os.close(log_fd)

    cmd = [
        get_bin_path("mpv"),
        url,
        "--ontop",
        "--autofit=50%",
        "--geometry=50%:50%",
        "--cursor-autohide=1000",
        f"--log-file={log_path}",
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

    _start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EnvironmentError("Erro: 'mpv' nao esta instalado ou nao esta no PATH.") from exc
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
