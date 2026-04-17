import contextlib
import logging
import os
import shutil
import socket
import subprocess
import threading
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService

from animecaos.core.paths import get_bin_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Driver pool — one persistent geckodriver session per plugin.
# Eliminates the 5–10s Firefox cold-start on every play/search request.
# ---------------------------------------------------------------------------
_driver_pool: dict[str, webdriver.Remote] = {}
_pool_locks: dict[str, threading.Lock] = {}
_pool_meta_lock = threading.Lock()


def _get_plugin_lock(plugin_name: str) -> threading.Lock:
    with _pool_meta_lock:
        if plugin_name not in _pool_locks:
            _pool_locks[plugin_name] = threading.Lock()
        return _pool_locks[plugin_name]


def _is_driver_alive(driver: webdriver.Remote) -> bool:
    try:
        driver.execute_script("return 1")
        return True
    except Exception:
        return False


@contextlib.contextmanager
def driver_session(plugin_name: str):
    """Context manager that yields a reusable WebDriver for the given plugin.

    Acquires a per-plugin lock (so two calls for the same plugin queue rather
    than spawn two Firefox processes), performs a health check, recreates if
    stale, and releases the lock without quitting the driver on exit.
    """
    lock = _get_plugin_lock(plugin_name)
    lock.acquire()
    try:
        with _pool_meta_lock:
            driver = _driver_pool.get(plugin_name)

        if driver is None or not _is_driver_alive(driver):
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            driver = make_driver()
            with _pool_meta_lock:
                _driver_pool[plugin_name] = driver

        yield driver
    except WebDriverException:
        with _pool_meta_lock:
            _driver_pool.pop(plugin_name, None)
        raise
    finally:
        lock.release()


def shutdown_driver_pool() -> None:
    """Quit all pooled drivers. Call once at app exit."""
    with _pool_meta_lock:
        drivers = list(_driver_pool.values())
        _driver_pool.clear()
    for driver in drivers:
        try:
            driver.quit()
        except Exception:
            pass

_gd_host_lock = threading.Lock()
_gd_host_path: str | None = None


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
    # mode=2 => TRR first, falls back to native DNS if DoH bootstrap is slow.
    options.set_preference("network.trr.mode", 2)
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


# ---------------------------------------------------------------------------
# Flatpak support: geckodriver must run on the host (outside the sandbox) so
# it can launch Firefox natively. Inside the sandbox, geckodriver can't find
# the host Firefox binary and the cross-sandbox Marionette IPC fails.
# Strategy: copy the bundled geckodriver to /tmp (shared with host via
# --filesystem=/tmp) and start it on the host via flatpak-spawn. Selenium
# connects to it as a RemoteWebDriver over localhost (shared network namespace
# via --share=network).
# ---------------------------------------------------------------------------

def _get_host_geckodriver_path() -> str:
    """Copy the bundled geckodriver to /tmp once so the host can execute it."""
    global _gd_host_path
    if _gd_host_path:
        return _gd_host_path
    with _gd_host_lock:
        if _gd_host_path:
            return _gd_host_path
        src = "/app/bin/geckodriver"
        if not os.path.isfile(src):
            raise RuntimeError(f"geckodriver nao encontrado em {src}.")
        dst = "/tmp/animecaos-geckodriver"
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        _gd_host_path = dst
    return _gd_host_path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _FlatpakDriver(webdriver.Remote):
    """RemoteWebDriver wrapper that shuts down the host geckodriver process on quit()."""

    def __init__(self, port: int, options: webdriver.FirefoxOptions, gd_proc: subprocess.Popen):
        super().__init__(command_executor=f"http://localhost:{port}", options=options)
        self._gd_proc = gd_proc

    def quit(self):
        try:
            super().quit()
        finally:
            try:
                self._gd_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._gd_proc.kill()


def _make_flatpak_driver(options: webdriver.FirefoxOptions) -> "_FlatpakDriver":
    gd_path = _get_host_geckodriver_path()
    port = _free_port()

    proc = subprocess.Popen(
        ["flatpak-spawn", "--host", gd_path, f"--port={port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Poll until geckodriver is accepting connections (up to 15 s).
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                break
        except OSError:
            time.sleep(0.3)
    else:
        proc.terminate()
        raise RuntimeError("Timeout aguardando geckodriver iniciar no host.")

    return _FlatpakDriver(port, options, proc)


def make_driver() -> webdriver.Remote:
    """Create a headless Firefox WebDriver using the best available geckodriver."""
    options = build_firefox_options()

    # In Flatpak, run geckodriver on the host so it can find and launch the host
    # Firefox directly — avoids cross-sandbox Marionette IPC failures.
    # Detection: env var (set by runtime) OR presence of the bundled binary.
    if os.environ.get("FLATPAK_ID") or os.path.isfile("/app/bin/geckodriver"):
        return _make_flatpak_driver(options)

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
