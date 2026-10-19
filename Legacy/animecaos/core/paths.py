import sys
import os
from pathlib import Path


APP_NAME = "AnimeCaos"


def user_data_dir(app_name: str = APP_NAME) -> Path:
    """Returns the per-user writable data directory (config, watchlist,
    history, caches). This body used to be copy-pasted as `_watchlist_dir` /
    `_history_dir` / `_cache_dir` across four service modules; it lives here
    now so there is a single definition of where user data goes.

    Note this is APPDATA (Roaming) on Windows, not LOCALAPPDATA — kept as-is
    to stay compatible with every existing install's data location.
    """
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    return Path.home() / ".local" / "state" / app_name


def cache_dir(app_name: str = APP_NAME) -> Path:
    """Returns the cache subdirectory under user_data_dir(), creating it.

    Everything in here is disposable: deleting it must only cost the user
    re-fetching, never real data. The API response cache (api_cache.db) and
    downloaded cover art both live here.
    """
    path = user_data_dir(app_name) / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_base_path() -> Path:
    """Returns the base path, either the PyInstaller extracted folder or the
    repo root when running from source.

    Resolved from this module's own location, NOT the current working
    directory: a .desktop launcher, systemd unit, or Start Menu shortcut can
    start the process with an arbitrary cwd, and os.path.abspath(".") would
    silently point at the wrong place in that case.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent.parent


def resolve_icon_path(filename: str = "icon.png") -> str:
    """Returns the app icon path, preferring assets/icons/ (higher-res
    source art) and falling back to the public/ copy bundled by PyInstaller.
    Used both for QApplication.setWindowIcon() and MainWindow's own icon so
    there's a single place that knows where the icon actually lives."""
    base = get_base_path()
    assets_path = base / "assets" / "icons" / filename
    if assets_path.exists():
        return str(assets_path)
    return str(base / "public" / filename)


import shutil


def find_binary(binary_name: str) -> str | None:
    """Locates a binary (bundled 'bin' folder -> PATH -> common per-platform
    install locations) and, unlike get_bin_path() below, actually
    distinguishes "found" from "not found" by returning None instead of the
    bare name. That distinction is what lets DependencyService tell the user
    a dependency is missing *before* a subprocess call fails with a bare
    FileNotFoundError."""
    base = get_base_path()
    bin_filename = f"{binary_name}.exe" if sys.platform == "win32" and not binary_name.endswith(".exe") else binary_name
    bin_path = base / "bin" / bin_filename

    if bin_path.exists():
        return str(bin_path)

    # Search PATH via shutil.which
    found_in_path = shutil.which(binary_name) or shutil.which(bin_filename)
    if found_in_path:
        return found_in_path

    if sys.platform == "win32":
        common_paths = [
            Path(r"C:\Program Files\MPV Player") / bin_filename,
            Path(r"C:\Program Files\mpv") / bin_filename,
            Path(r"C:\Program Files (x86)\MPV Player") / bin_filename,
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "mpv" / bin_filename,
            Path(os.environ.get("USERPROFILE", "")) / "mpv" / bin_filename,
        ]
    else:
        # Linux/macOS: cover the common package-manager, Flatpak and Snap
        # install locations that shutil.which() alone can miss (e.g. Flatpak
        # exports live under a path most shells don't have on PATH).
        common_paths = [
            Path("/usr/bin") / binary_name,
            Path("/usr/local/bin") / binary_name,
            Path.home() / ".local" / "bin" / binary_name,
            Path("/snap/bin") / binary_name,
        ]
        if binary_name == "mpv":
            common_paths.append(Path("/var/lib/flatpak/exports/bin/io.mpv.Mpv"))
            common_paths.append(Path.home() / ".local/share/flatpak/exports/bin/io.mpv.Mpv")

    for p in common_paths:
        if p.exists():
            return str(p)

    return None


def get_bin_path(binary_name: str) -> str:
    """Returns the path to a bundled/installed binary, or the bare name if
    it can't be found — existing callers (DownloadWorker, video_player, ...)
    pass that straight to subprocess, which then raises FileNotFoundError
    the same way it always has. Use find_binary() directly when you need to
    know whether the binary was actually found."""
    return find_binary(binary_name) or binary_name
