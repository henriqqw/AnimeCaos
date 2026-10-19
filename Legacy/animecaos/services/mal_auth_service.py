from __future__ import annotations

import logging
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

import requests

from animecaos.services.rate_limiter import Priority, mal_limiter
from animecaos.services.config_service import ConfigService

log = logging.getLogger(__name__)

# App credentials from myanimelist.net/apiconfig
# Redirect URI registered: http://localhost:9743/
MAL_CLIENT_ID = ""

_MAL_API = "https://api.myanimelist.net/v2"
_MAL_AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
_MAL_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
_OAUTH_PORT = 9743
_TOKEN_REFRESH_MARGIN_SECONDS = 120

_LANDING_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>AnimeCaos – Conectado</title>
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


class MALAuthService:
    def __init__(self, config: ConfigService) -> None:
        self._config = config

    def is_authenticated(self) -> bool:
        return bool(self._config.get("mal_access_token"))

    def get_user(self) -> dict | None:
        if not self.is_authenticated():
            return None
        return {
            "username": self._config.get("mal_username"),
            "avatar_url": self._config.get("mal_avatar_url"),
            "user_id": self._config.get("mal_user_id"),
            "anime_count": self._config.get("mal_anime_count", 0),
            "episodes_watched": self._config.get("mal_episodes_watched", 0),
            "minutes_watched": self._config.get("mal_minutes_watched", 0),
        }

    def login(self) -> bool:
        """Open browser for OAuth2 Authorization Code + PKCE flow. Blocks until token received or 120s."""
        if not MAL_CLIENT_ID:
            return False

        code_verifier = secrets.token_urlsafe(96)[:128]
        state = secrets.token_urlsafe(16)

        code_holder: list[str] = []
        done = threading.Event()

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                code = qs.get("code", [""])[0]
                returned_state = qs.get("state", [""])[0]
                body = _LANDING_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if code and returned_state == state:
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

        redirect_uri = f"http://localhost:{_OAUTH_PORT}/"
        webbrowser.open(
            f"{_MAL_AUTHORIZE_URL}"
            f"?response_type=code"
            f"&client_id={MAL_CLIENT_ID}"
            f"&code_challenge={quote(code_verifier, safe='')}"
            f"&code_challenge_method=plain"
            f"&state={state}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
        )
        done.wait(timeout=120)

        if not code_holder:
            return False

        token = self._exchange_code(code_holder[0], code_verifier, redirect_uri)
        if not token:
            return False

        self._save_token(token)
        self._fetch_and_save_user()
        return True

    def _exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> dict | None:
        try:
            resp = requests.post(
                _MAL_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": MAL_CLIENT_ID,
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                if resp.status_code == 429:
                    mal_limiter.note_rate_limited(resp.headers)
                log.error("MAL token exchange HTTP %d: %s", resp.status_code, resp.text[:300])
                return None
            return resp.json()
        except Exception as exc:
            log.error("MAL token exchange failed: %s", exc)
            return None

    def _save_token(self, token: dict) -> None:
        self._config.set("mal_access_token", token.get("access_token"))
        self._config.set("mal_refresh_token", token.get("refresh_token"))
        expires_in = token.get("expires_in") or 0
        self._config.set("mal_token_expires_at", time.time() + expires_in)

    def _ensure_fresh_token(self) -> str | None:
        """Refresh the access token if it's expired or about to expire. Returns
        a usable access token, or None if there's no session / refresh failed."""
        token = self._config.get("mal_access_token")
        if not token:
            return None
        expires_at = self._config.get("mal_token_expires_at") or 0
        if time.time() < expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return token

        refresh_token = self._config.get("mal_refresh_token")
        if not refresh_token:
            return token  # let the caller's request fail naturally
        try:
            resp = requests.post(
                _MAL_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": MAL_CLIENT_ID,
                    "refresh_token": refresh_token,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                if resp.status_code == 429:
                    mal_limiter.note_rate_limited(resp.headers)
                log.error("MAL token refresh HTTP %d: %s", resp.status_code, resp.text[:300])
                return token
            new_token = resp.json()
            self._save_token(new_token)
            return new_token.get("access_token")
        except Exception as exc:
            log.error("MAL token refresh failed: %s", exc)
            return token

    def logout(self) -> None:
        self._config.clear_mal()

    def fetch_avatar_bytes(self) -> bytes | None:
        url = self._config.get("mal_avatar_url")
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    def _fetch_and_save_user(self) -> bool:
        token = self._ensure_fresh_token()
        if not token:
            return False
        try:
            mal_limiter.acquire(Priority.FOREGROUND)
            resp = requests.get(
                f"{_MAL_API}/users/@me",
                params={"fields": "anime_statistics,picture"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-MAL-CLIENT-ID": MAL_CLIENT_ID,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                if resp.status_code == 429:
                    mal_limiter.note_rate_limited(resp.headers)
                log.error("MAL @me query HTTP %d: %s", resp.status_code, resp.text[:300])
                return False
            user = resp.json()
            if not user:
                log.error("MAL @me query returned empty data")
                return False

            self._config.set("mal_user_id", user.get("id"))
            self._config.set("mal_username", user.get("name"))
            self._config.set("mal_avatar_url", user.get("picture"))

            stats = user.get("anime_statistics") or {}
            count = stats.get("num_items", 0)
            eps = stats.get("num_episodes", 0)
            mins = round((stats.get("num_days_watched") or 0) * 1440)

            log.debug("MAL @me: %s | count=%s eps=%s min=%s", user.get("name"), count, eps, mins)
            self._config.set("mal_anime_count", count)
            self._config.set("mal_episodes_watched", eps)
            self._config.set("mal_minutes_watched", mins)
            return True
        except Exception as exc:
            log.error("MAL _fetch_and_save_user failed: %s", exc)
            return False

    def refresh_user_stats(self) -> bool:
        """Re-fetch and persist live stats from MAL. Call after update_progress."""
        if not self.is_authenticated():
            return False
        return self._fetch_and_save_user()

    def update_progress(self, mal_id: int, episode: int, total_episodes: int) -> bool:
        if not mal_id:
            return False
        token = self._ensure_fresh_token()
        if not token:
            return False
        status = "completed" if total_episodes > 0 and episode >= total_episodes else "watching"
        try:
            mal_limiter.acquire(Priority.FOREGROUND)
            resp = requests.patch(
                f"{_MAL_API}/anime/{mal_id}/my_list_status",
                data={"status": status, "num_watched_episodes": episode},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-MAL-CLIENT-ID": MAL_CLIENT_ID,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                if resp.status_code == 429:
                    mal_limiter.note_rate_limited(resp.headers)
                log.error("MAL update_progress failed HTTP %d: %s", resp.status_code, resp.text[:300])
                return False
            log.debug("MAL update_progress OK: mal_id=%s ep=%s status=%s", mal_id, episode, status)
            return True
        except Exception as exc:
            log.error("MAL update_progress exception: %s", exc)
            return False
