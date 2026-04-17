from __future__ import annotations

import logging
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

import requests

from animecaos.services.config_service import ConfigService

log = logging.getLogger(__name__)

# App credentials from anilist.co/settings/developer
# Redirect URI registered: http://localhost:9742
ANILIST_CLIENT_ID = "39400"
ANILIST_CLIENT_SECRET = "MYACeZXgfgbVbHRCvKfyBBxgHkxOAr1lSMRquoWK"

_ANILIST_API = "https://graphql.anilist.co"
_ANILIST_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"
_OAUTH_PORT = 9742

_LANDING_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AnimeCaos \u2013 Conectado</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#111214;color:#F2F3F5;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
         min-height:100vh;display:flex;align-items:center;justify-content:center}
    .card{text-align:center;padding:52px 48px;
          background:rgba(255,255,255,0.04);
          border:1px solid rgba(255,255,255,0.08);
          border-radius:16px;width:100%;max-width:380px}
    .logo{font-size:26px;font-weight:800;letter-spacing:-0.5px;margin-bottom:36px;
          color:#F2F3F5}
    .logo span{color:#D44242}
    .check{width:68px;height:68px;border-radius:50%;
           background:rgba(61,214,140,0.1);border:2px solid #3DD68C;
           display:flex;align-items:center;justify-content:center;
           margin:0 auto 28px;
           animation:pop .45s cubic-bezier(.34,1.56,.64,1) both}
    @keyframes pop{0%{transform:scale(0);opacity:0}100%{transform:scale(1);opacity:1}}
    .check svg{display:block}
    h2{font-size:21px;font-weight:700;color:#F2F3F5;margin-bottom:10px}
    p{font-size:14px;color:#6B7280;line-height:1.7}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">Anime<span>Caos</span></div>
    <div class="check">
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none"
           stroke="#3DD68C" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    </div>
    <h2>Conta conectada!</h2>
    <p>Pode fechar esta aba e<br>voltar ao AnimeCaos.</p>
  </div>
</body>
</html>"""


class AniListAuthService:
    def __init__(self, config: ConfigService) -> None:
        self._config = config

    def is_authenticated(self) -> bool:
        return bool(self._config.get("anilist_access_token"))

    def get_user(self) -> dict | None:
        if not self.is_authenticated():
            return None
        return {
            "username": self._config.get("anilist_username"),
            "avatar_url": self._config.get("anilist_avatar_url"),
            "user_id": self._config.get("anilist_user_id"),
            "anime_count": self._config.get("anilist_anime_count", 0),
            "episodes_watched": self._config.get("anilist_episodes_watched", 0),
            "minutes_watched": self._config.get("anilist_minutes_watched", 0),
        }

    def login(self) -> bool:
        """Open browser for OAuth2 Authorization Code flow. Blocks until token received or 120s."""
        if not ANILIST_CLIENT_ID:
            return False

        code_holder: list[str] = []
        done = threading.Event()

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                code = qs.get("code", [""])[0]
                body = _LANDING_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if code:
                    code_holder.append(code)
                    done.set()

            def log_message(self, *args): pass

        try:
            server = HTTPServer(("localhost", _OAUTH_PORT), _Handler)
        except OSError:
            return False

        def _serve() -> None:
            server.timeout = 1
            while not done.is_set():
                server.handle_request()
            server.server_close()

        threading.Thread(target=_serve, daemon=True).start()

        redirect_uri = f"http://localhost:{_OAUTH_PORT}"
        webbrowser.open(
            f"https://anilist.co/api/v2/oauth/authorize"
            f"?client_id={ANILIST_CLIENT_ID}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
            f"&response_type=code"
        )
        done.wait(timeout=120)

        if not code_holder:
            return False

        token = self._exchange_code(code_holder[0], redirect_uri)
        if not token:
            return False

        self._config.set("anilist_access_token", token)
        self._fetch_and_save_user(token)
        return True

    def _exchange_code(self, code: str, redirect_uri: str) -> str | None:
        try:
            resp = requests.post(
                _ANILIST_TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": ANILIST_CLIENT_ID,
                    "client_secret": ANILIST_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            return resp.json().get("access_token")
        except Exception:
            return None

    def logout(self) -> None:
        self._config.clear_anilist()

    def fetch_avatar_bytes(self) -> bytes | None:
        url = self._config.get("anilist_avatar_url")
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def _fetch_and_save_user(self, token: str) -> bool:
        query = """query {
          Viewer {
            id name
            avatar { large }
            statistics { anime { count episodesWatched minutesWatched } }
          }
        }"""
        try:
            resp = requests.post(
                _ANILIST_API,
                json={"query": query},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if resp.status_code != 200:
                log.error("AniList Viewer query HTTP %d: %s", resp.status_code, resp.text[:300])
                return False
            body = resp.json()
            if "errors" in body:
                log.error("AniList Viewer query errors: %s", body["errors"])
                return False
            viewer = (body.get("data") or {}).get("Viewer") or {}
            if not viewer:
                log.error("AniList Viewer query returned empty data: %s", body)
                return False

            self._config.set("anilist_user_id", viewer.get("id"))
            self._config.set("anilist_username", viewer.get("name"))
            self._config.set("anilist_avatar_url", (viewer.get("avatar") or {}).get("large"))

            stats = (viewer.get("statistics") or {}).get("anime") or {}
            count = stats.get("count", 0)
            eps = stats.get("episodesWatched", 0)
            mins = stats.get("minutesWatched", 0)

            # statistics can legitimately be 0 on fresh/aggregating accounts.
            # Fall back to MediaListCollection for a direct count.
            if count == 0 and eps == 0:
                user_id = viewer.get("id")
                fallback = self._fetch_list_stats(token, user_id)
                if fallback and fallback.get("count", 0) > 0:
                    count = fallback["count"]
                    eps = fallback["episodesWatched"]
                    mins = fallback.get("minutesWatched", 0)
                    log.debug("AniList: using list fallback — count=%s eps=%s", count, eps)

            # Don't overwrite cached non-zero stats with zeros — AniList aggregates
            # episodesWatched/count asynchronously; a 0 result just means "not ready yet".
            cached_count = self._config.get("anilist_anime_count") or 0
            if count == 0 and eps == 0 and cached_count > 0:
                log.debug("AniList: API returned 0 stats, keeping cached count=%s", cached_count)
                return True

            log.debug("AniList Viewer: %s | count=%s eps=%s min=%s", viewer.get("name"), count, eps, mins)
            self._config.set("anilist_anime_count", count)
            self._config.set("anilist_episodes_watched", eps)
            self._config.set("anilist_minutes_watched", mins)
            return True
        except Exception as exc:
            log.error("AniList _fetch_and_save_user failed: %s", exc)
            return False

    def _fetch_list_stats(self, token: str, user_id: int) -> dict | None:
        """Count anime list entries directly when statistics aggregation returns 0."""
        query = """query ($userId: Int) {
          MediaListCollection(userId: $userId, type: ANIME) {
            lists {
              entries { progress media { duration } }
            }
          }
        }"""
        try:
            resp = requests.post(
                _ANILIST_API,
                json={"query": query, "variables": {"userId": user_id}},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("data") or {}
            collection = data.get("MediaListCollection") or {}
            total_count = 0
            total_eps = 0
            total_mins = 0
            for lst in (collection.get("lists") or []):
                for entry in (lst.get("entries") or []):
                    total_count += 1
                    prog = entry.get("progress") or 0
                    total_eps += prog
                    dur = (entry.get("media") or {}).get("duration") or 0
                    total_mins += prog * dur
            return {"count": total_count, "episodesWatched": total_eps, "minutesWatched": total_mins}
        except Exception as exc:
            log.error("AniList _fetch_list_stats failed: %s", exc)
            return None

    def refresh_user_stats(self) -> bool:
        """Re-fetch and persist live stats from AniList. Call after update_progress."""
        token = self._config.get("anilist_access_token")
        if not token:
            return False
        return self._fetch_and_save_user(token)

    def update_progress(self, media_id: int, episode: int, total_episodes: int) -> bool:
        token = self._config.get("anilist_access_token")
        if not token or not media_id:
            return False
        status = "COMPLETED" if total_episodes > 0 and episode >= total_episodes else "CURRENT"
        mutation = """mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus) {
          SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status) {
            id progress status
          }
        }"""
        try:
            resp = requests.post(
                _ANILIST_API,
                json={"query": mutation, "variables": {
                    "mediaId": media_id, "progress": episode, "status": status,
                }},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code != 200 or "errors" in data:
                log.error("AniList update_progress failed HTTP %d: %s", resp.status_code, data.get("errors"))
                return False
            log.debug("AniList update_progress OK: mediaId=%s ep=%s status=%s", media_id, episode, status)
            return True
        except Exception as exc:
            log.error("AniList update_progress exception: %s", exc)
            return False
