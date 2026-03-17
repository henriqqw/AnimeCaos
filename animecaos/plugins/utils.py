import logging
import os
import subprocess

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService

from animecaos.core.paths import get_bin_path

log = logging.getLogger(__name__)


def is_firefox_installed_as_snap() -> bool:
    if os.name == "nt":
        return False

    try:
        result = subprocess.run(
            ["snap", "list", "firefox"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_firefox_options() -> webdriver.FirefoxOptions:
    """
    Build shared Firefox options for Selenium, including Cloudflare DNS-over-HTTPS.
    """
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")

    # Force Cloudflare DNS-over-HTTPS to bypass ISP DNS blocks.
    # mode=3 => TRR only (never falls back to native DNS resolver).
    options.set_preference("network.trr.mode", 3)
    options.set_preference("network.trr.uri", "https://1.1.1.1/dns-query")
    options.set_preference("network.trr.bootstrapAddress", "1.1.1.1")

    return options


def validate_player_src(src: str, source_name: str) -> str:
    """Validate a player URL before returning it. Raises RuntimeError if invalid."""
    if not src or src.startswith("javascript:") or src == "about:blank":
        raise RuntimeError(f"URL de player invalida em {source_name}: {src!r}")
    if not src.startswith(("http://", "https://")):
        raise RuntimeError(f"URL de player nao HTTP em {source_name}: {src!r}")
    return src


def make_driver() -> webdriver.Firefox:
    """Create a headless Firefox WebDriver using the best available geckodriver."""
    options = build_firefox_options()
    try:
        if is_firefox_installed_as_snap():
            service = FirefoxService(executable_path="/snap/bin/geckodriver")
            return webdriver.Firefox(options=options, service=service)

        gd_path = get_bin_path("geckodriver")
        if gd_path != "geckodriver":
            service = FirefoxService(executable_path=gd_path)
            return webdriver.Firefox(options=options, service=service)

        return webdriver.Firefox(options=options)
    except WebDriverException as exc:
        raise RuntimeError("Firefox/geckodriver nao encontrado.") from exc
