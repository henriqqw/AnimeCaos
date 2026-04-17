import os
import subprocess
import tempfile
import time
from urllib.parse import urlparse

from animecaos.core.paths import get_bin_path


def _build_referer(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def play_video(url: str, debug: bool = False) -> dict[str, bool]:
    if debug:
        return {"eof": False}

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

    # Natural EOF: user let the episode finish (or skipped to the end).
    eof_natural = "Exiting... (End of file)" in log

    # Watched long enough: player was open >= 30 s (wall-clock).
    # MPV only stays alive while the video is open, so wall-clock ≈ watch time.
    # 30 s is enough to confirm intentional viewing without being too strict.
    watched = eof_natural or elapsed >= 30.0
    return {"eof": watched}
