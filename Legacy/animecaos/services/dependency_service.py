"""Detects external tools the app depends on (mpv, yt-dlp, geckodriver) and
explains what to do when one is missing.

Before this existed, a missing mpv only surfaced as a bare "Erro: 'mpv' nao
esta instalado ou nao esta no PATH" once the user tried to play something —
no instructions, and on Linux nothing checked Flatpak/Snap install
locations at all. DependencyService lets the UI warn proactively (startup
banner, a settings card) with a platform-appropriate install hint instead.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

from animecaos.core.paths import find_binary

# (name, required). Required deps block core functionality (mpv: nothing
# plays; yt-dlp: nothing downloads). geckodriver is only used by the
# Selenium-based scraping plugins — its absence degrades search for some
# sources but isn't a hard stop, so it's excluded from missing_required().
_DEPENDENCIES: tuple[tuple[str, bool], ...] = (
    ("mpv", True),
    ("yt-dlp", True),
    ("geckodriver", False),
)

_INSTALL_HINTS: dict[str, dict[str, str]] = {
    "mpv": {
        "win32": "Baixe o instalador em https://mpv.io/installation/ ou rode: winget install mpv",
        "linux": "Instale com: sudo apt install mpv   ou   flatpak install flathub io.mpv.Mpv",
        "darwin": "Instale com: brew install mpv",
    },
    "yt-dlp": {
        "win32": "Baixe em https://github.com/yt-dlp/yt-dlp/releases/latest",
        "linux": "Instale com: sudo apt install yt-dlp   ou   pip install -U yt-dlp",
        "darwin": "Instale com: brew install yt-dlp",
    },
    "geckodriver": {
        "win32": "Baixe em https://github.com/mozilla/geckodriver/releases/latest",
        "linux": "Instale com: sudo apt install firefox-geckodriver   ou baixe em https://github.com/mozilla/geckodriver/releases/latest",
        "darwin": "Instale com: brew install geckodriver",
    },
}

_DEFAULT_HINT = "Instale esta dependencia e adicione-a ao PATH do sistema."


@dataclass
class DependencyStatus:
    name: str
    found: bool
    path: str | None
    required: bool
    install_hint: str


class DependencyService:
    def __init__(
        self,
        finder: Callable[[str], str | None] = find_binary,
        platform: str = sys.platform,
    ) -> None:
        self._finder = finder
        self._platform = platform
        self._required = {name for name, required in _DEPENDENCIES if required}

    def check(self, name: str) -> DependencyStatus:
        path = self._finder(name)
        return DependencyStatus(
            name=name,
            found=path is not None,
            path=path,
            required=name in self._required,
            install_hint=self._install_hint(name),
        )

    def check_all(self) -> list[DependencyStatus]:
        return [self.check(name) for name, _required in _DEPENDENCIES]

    def missing_required(self) -> list[DependencyStatus]:
        return [status for status in self.check_all() if status.required and not status.found]

    def _install_hint(self, name: str) -> str:
        hints = _INSTALL_HINTS.get(name, {})
        return hints.get(self._platform, _DEFAULT_HINT)
