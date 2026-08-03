from __future__ import annotations

import re
import threading

from PySide6.QtCore import QObject, Signal

from animecaos.services.anime_service import AnimeService
from animecaos.services.anilist_service import AniListService


class LoaderWorker(QObject):
    """Runs AniList + spotlight loading in a background thread, emits progress signals."""
    status_changed = Signal(str)
    progress_changed = Signal(float)
    load_finished = Signal(object)  # emits dict with preloaded data

    def __init__(self, anilist_service: AniListService, anime_service: AnimeService) -> None:
        super().__init__()
        self._anilist = anilist_service
        self._anime = anime_service

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _card_available(self, card: dict) -> bool:
        """Quick existence check for a card — no is_playable, just title lookup."""
        title = card.get("title", "")
        if not title:
            return False
        query = re.split(r":\s+", title, maxsplit=1)[0].strip()
        if query == query.upper() and len(query) > 1:
            query = query.title()
        if len(query) >= 3 and self._anime.quick_search_exists(query):
            return True
        words = title.split()
        if len(words) > 3:
            short = " ".join(words[:3])
            if short.lower() != query.lower() and self._anime.quick_search_exists(short):
                return True
        return False

    def _filter_section(self, cards: list[dict], target: int, base_progress: float, progress_range: float) -> list[dict]:
        valid: list[dict] = []
        for i, card in enumerate(cards):
            if len(valid) >= target:
                break
            frac = base_progress + progress_range * (i / max(len(cards), 1))
            self.progress_changed.emit(frac)
            try:
                if self._card_available(card):
                    valid.append(card)
            except Exception:
                pass
        return valid

    def _run(self) -> None:
        try:
            # Step 1: plugins
            self.status_changed.emit("Inicializando plugins...")
            self.progress_changed.emit(0.05)
            self._anime.ensure_plugins_loaded()

            # Step 2: fetch AniList data
            self.status_changed.emit("Buscando animes populares...")
            self.progress_changed.emit(0.10)
            trending_raw = self._anilist.fetch_trending(per_page=25)
            self.progress_changed.emit(0.18)
            self.status_changed.emit("Buscando temporada atual...")
            seasonal_raw = self._anilist.fetch_seasonal(per_page=25)
            self.progress_changed.emit(0.25)

            # Step 3: filter trending to 10 available
            self.status_changed.emit("Verificando disponibilidade dos animes em alta...")
            trending = self._filter_section(trending_raw, 10, 0.25, 0.30)
            self.progress_changed.emit(0.55)

            # Step 4: filter seasonal to 10 available
            self.status_changed.emit("Verificando disponibilidade da temporada...")
            seasonal = self._filter_section(seasonal_raw, 10, 0.55, 0.25)
            self.progress_changed.emit(0.80)

            # Step 5: find spotlight
            self.status_changed.emit("Selecionando destaque da temporada...")
            spotlight = None
            for i, candidate in enumerate(trending[:6]):
                try:
                    if self._card_available(candidate):
                        spotlight = self._anilist.fetch_spotlight_extras(candidate)
                        spotlight["_rank"] = i + 1
                        break
                except Exception:
                    pass
            self.progress_changed.emit(0.95)

            self.status_changed.emit("Preparando interface...")
            self.load_finished.emit({
                "trending": trending,
                "seasonal": seasonal,
                "spotlight": spotlight,
            })
        except Exception as exc:
            self.status_changed.emit("Pronto!")
            self.load_finished.emit({
                "trending": [],
                "seasonal": [],
                "spotlight": None,
                "_error": str(exc),
            })
