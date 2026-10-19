"""
Fase 2 (TDD): make_driver() must bound Selenium's page load time. Today no
code path calls driver.set_page_load_timeout(...), so a hung site (matching
the ReadTimeoutError/retry pattern seen against animesonlinecc.to) can block
driver.get() for Selenium's default timeout (minutes, or effectively
unbounded on some geckodriver builds) while the caller is holding
AnimeService._rep_lock — freezing play/search/download for everyone.
"""
from __future__ import annotations

import pytest

from animecaos.plugins import driver_pool


class _FakeDriver:
    def __init__(self, *args, **kwargs) -> None:
        self.page_load_timeout_calls: list[float] = []

    def set_page_load_timeout(self, seconds: float) -> None:
        self.page_load_timeout_calls.append(seconds)


@pytest.fixture
def fake_firefox(monkeypatch):
    created: list[_FakeDriver] = []

    def _factory(*args, **kwargs):
        driver = _FakeDriver(*args, **kwargs)
        created.append(driver)
        return driver

    monkeypatch.setattr(driver_pool.webdriver, "Firefox", _factory)
    monkeypatch.setattr(driver_pool, "is_firefox_installed_as_snap", lambda: False)
    monkeypatch.setattr(driver_pool, "get_bin_path", lambda name: name)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(driver_pool.os.path, "isfile", lambda path: False)
    return created


def test_make_driver_sets_a_bounded_page_load_timeout(fake_firefox):
    driver = driver_pool.make_driver()

    assert driver.page_load_timeout_calls, "make_driver() never called set_page_load_timeout()"
    timeout = driver.page_load_timeout_calls[-1]
    assert 0 < timeout <= 30, f"page load timeout {timeout}s is not tightly bounded"
