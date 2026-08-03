import sys
import os
from pathlib import Path


def get_base_path() -> Path:
    """Returns the base path, either the PyInstaller extracted folder or the current script directory."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(os.path.abspath("."))


import shutil

def get_bin_path(binary_name: str) -> str:
    """Returns the path to a bundled binary in the 'bin' folder or installed system locations."""
    base = get_base_path()
    bin_filename = f"{binary_name}.exe" if sys.platform == "win32" and not binary_name.endswith(".exe") else binary_name
    bin_path = base / "bin" / bin_filename

    if bin_path.exists():
        return str(bin_path)

    # Search PATH via shutil.which
    found_in_path = shutil.which(binary_name) or shutil.which(bin_filename)
    if found_in_path:
        return found_in_path

    # Common Windows installation directories for MPV
    if sys.platform == "win32":
        common_paths = [
            Path(r"C:\Program Files\MPV Player") / bin_filename,
            Path(r"C:\Program Files\mpv") / bin_filename,
            Path(r"C:\Program Files (x86)\MPV Player") / bin_filename,
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "mpv" / bin_filename,
            Path(os.environ.get("USERPROFILE", "")) / "mpv" / bin_filename,
        ]
        for p in common_paths:
            if p.exists():
                return str(p)

    return binary_name
