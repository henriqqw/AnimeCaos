from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import requests

BASE_URL = "https://api.mangadex.org"
CDN_URL = "https://uploads.mangadex.org"

_sess = requests.Session()
_sess.headers["User-Agent"] = "AnimeCaos/1.0"


def _cache_dir() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA", "")
        base = Path(appdata) / "AnimeCaos" if appdata else Path.home() / "AppData" / "Roaming" / "AnimeCaos"
    else:
        base = Path.home() / ".local" / "state" / "AnimeCaos"
    return base / "manga_cache"


class MangaService:
    def __init__(self) -> None:
        self._cache = _cache_dir()
        self._cache.mkdir(parents=True, exist_ok=True)

    # ── Search ───────────────────────────────────────────────────

    def search_manga(self, query: str) -> list[dict]:
        for lang in ("pt-br", None):
            params: dict = {
                "title": query,
                "limit": 20,
                "includes[]": "cover_art",
                "contentRating[]": ["safe", "suggestive"],
                "order[relevance]": "desc",
            }
            if lang:
                params["availableTranslatedLanguage[]"] = lang
            try:
                r = _sess.get(f"{BASE_URL}/manga", params=params, timeout=12)
                r.raise_for_status()
                items = r.json().get("data", [])
            except Exception:
                continue
            if items:
                return [self._parse_manga(m) for m in items]
        return []

    def _parse_manga(self, item: dict) -> dict:
        attrs = item.get("attributes", {})
        mid = item.get("id", "")
        titles = attrs.get("title", {})
        title = (
            titles.get("pt-br")
            or titles.get("pt")
            or titles.get("en")
            or next(iter(titles.values()), mid)
        )
        descs = attrs.get("description", {})
        desc = descs.get("pt-br") or descs.get("pt") or descs.get("en") or ""
        cover_url: Optional[str] = None
        for rel in item.get("relationships", []):
            if rel.get("type") == "cover_art":
                fname = (rel.get("attributes") or {}).get("fileName", "")
                if fname:
                    cover_url = f"{CDN_URL}/covers/{mid}/{fname}.256.jpg"
                break
        available_langs: list[str] = attrs.get("availableTranslatedLanguages") or []
        has_ptbr = "pt-br" in available_langs or "pt" in available_langs
        return {
            "id": mid,
            "title": title,
            "description": desc,
            "cover_url": cover_url,
            "status": attrs.get("status", ""),
            "available_langs": available_langs,
            "has_ptbr": has_ptbr,
        }

    # ── Chapters ─────────────────────────────────────────────────

    def has_chapters(self, manga_id: str) -> bool:
        """Quick check: does this manga have any hosted chapters at all?"""
        try:
            r = _sess.get(
                f"{BASE_URL}/manga/{manga_id}/feed",
                params={
                    "limit": 1,
                    "contentRating[]": ["safe", "suggestive", "erotica"],
                },
                timeout=8,
            )
            r.raise_for_status()
            return r.json().get("total", 0) > 0
        except Exception:
            return True  # assume available on network error

    def fetch_chapters(self, manga_id: str) -> list[dict]:
        for lang in ("pt-br", "en", "es-la", "es"):
            chapters = self._fetch_chapters_lang(manga_id, lang)
            if chapters:
                return chapters
        return []

    def _fetch_chapters_lang(self, manga_id: str, lang: str) -> list[dict]:
        all_data: list[dict] = []
        offset = 0
        while True:
            try:
                r = _sess.get(
                    f"{BASE_URL}/manga/{manga_id}/feed",
                    params={
                        "translatedLanguage[]": lang,
                        "order[volume]": "asc",
                        "order[chapter]": "asc",
                        "limit": 500,
                        "offset": offset,
                        "contentRating[]": ["safe", "suggestive"],
                    },
                    timeout=12,
                )
                r.raise_for_status()
                payload = r.json()
            except Exception:
                break
            batch = payload.get("data", [])
            if not batch:
                break
            all_data.extend(batch)
            total = payload.get("total", 0)
            offset += 500
            if offset >= total:
                break
            time.sleep(0.25)

        seen: set[str] = set()
        result: list[dict] = []
        for item in all_data:
            attrs = item.get("attributes", {})
            num = attrs.get("chapter") or "?"
            if num in seen:
                continue
            seen.add(num)
            vol = attrs.get("volume") or ""
            title = attrs.get("title") or ""
            parts = []
            if vol:
                parts.append(f"Vol.{vol}")
            parts.append(f"Cap.{num}")
            if title:
                parts.append(f"— {title}")
            result.append({
                "id": item.get("id", ""),
                "chapter_num": num,
                "volume": vol,
                "title": title,
                "label": " ".join(parts),
                "pages": attrs.get("pages", 0),
            })
        return result

    # ── Pages ────────────────────────────────────────────────────

    def fetch_chapter_pages(self, chapter_id: str) -> list[str]:
        try:
            r = _sess.get(f"{BASE_URL}/at-home/server/{chapter_id}", timeout=12)
            r.raise_for_status()
            p = r.json()
        except Exception:
            return []
        base = p.get("baseUrl", "")
        ch = p.get("chapter", {})
        h = ch.get("hash", "")
        return [f"{base}/data/{h}/{f}" for f in ch.get("data", [])]

    # ── Cover / image download ───────────────────────────────────

    def download_cover(self, manga_id: str, cover_url: str) -> Optional[str]:
        if not cover_url:
            return None
        ext = cover_url.rsplit(".", 1)[-1] if "." in cover_url else "jpg"
        path = self._cache / f"cover_{manga_id}.{ext}"
        if path.exists():
            return str(path)
        try:
            r = _sess.get(cover_url, timeout=12)
            r.raise_for_status()
            path.write_bytes(r.content)
            return str(path)
        except Exception:
            return None

    def download_page(self, url: str) -> Optional[bytes]:
        try:
            r = _sess.get(url, timeout=20)
            r.raise_for_status()
            return r.content
        except Exception:
            return None
