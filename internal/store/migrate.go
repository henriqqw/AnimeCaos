package store

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"github.com/henriqqw/animecaos/internal/domain"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

func (s *Store) ImportLegacy() error {
	var done bool
	if s.Get("migration", "python-v1", &done) != nil || !done {
		tx, e := s.DB.Begin()
		if e != nil {
			return e
		}
		defer tx.Rollback()
		migration := *s
		migration.tx = tx
		if e = migration.importLegacy(); e != nil {
			return e
		}
		if e = tx.Commit(); e != nil {
			return e
		}
	}
	// Image/metadata cache is disposable: an unreadable cache must never stop
	// existing installations from launching. Leave the marker unset so a later
	// launch can retry, while preserving every original cache file.
	var cacheDone bool
	if s.Get("migration", "python-cache-v2", &cacheDone) != nil || !cacheDone {
		if s.importLegacyMediaCache() == nil {
			_ = s.Put("migration", "python-cache-v2", true)
		}
	}
	return nil
}

type legacyMedia struct {
	ID          int      `json:"id"`
	MALID       int      `json:"id_mal"`
	Romaji      string   `json:"romaji"`
	English     string   `json:"english"`
	Description string   `json:"description"`
	CoverURL    string   `json:"cover_url"`
	BannerURL   string   `json:"banner_url"`
	Score       *float64 `json:"score"`
	Episodes    *int     `json:"episodes"`
}

func (m legacyMedia) anime() domain.Anime {
	title := strings.TrimSpace(m.Romaji)
	if title == "" {
		title = strings.TrimSpace(m.English)
	}
	a := domain.Anime{ID: strconv.Itoa(m.ID), Provider: "anilist", Title: title, Titles: []string{}, Cover: m.CoverURL, Banner: m.BannerURL, Description: m.Description, AniListID: m.ID, MALID: m.MALID}
	if m.ID > 0 {
		a.URL = "https://anilist.co/anime/" + a.ID
	}
	for _, alias := range []string{m.Romaji, m.English} {
		alias = strings.TrimSpace(alias)
		if alias != "" && !strings.EqualFold(alias, title) {
			a.Titles = append(a.Titles, alias)
		}
	}
	if m.Score != nil {
		a.Score = *m.Score / 10
	}
	if m.Episodes != nil {
		a.EpisodeCount = *m.Episodes
	}
	return a
}

// importLegacyMediaCache moves the Python AniList metadata records into the
// Go cache and enriches imported history/watchlist entries. Python stored
// image files by MD5(URL); app.Image still knows that layout, so retaining the
// source URL makes those already-downloaded covers immediately available.
func (s *Store) importLegacyMediaCache() error {
	path := filepath.Join(s.Dir, "cache", "api_cache.db")
	media := map[string]domain.Anime{}
	if _, err := os.Stat(path); err == nil {
		dsnPath := filepath.ToSlash(path)
		if runtime.GOOS == "windows" && len(dsnPath) > 1 && dsnPath[1] == ':' {
			dsnPath = "/" + dsnPath
		}
		uri := (&url.URL{Scheme: "file", Path: dsnPath}).String() + "?mode=ro"
		legacyDB, err := sql.Open("sqlite", uri)
		if err != nil {
			return err
		}
		rows, err := legacyDB.Query(`SELECT key,payload FROM entries WHERE namespace='media' AND payload IS NOT NULL AND is_negative=0`)
		if err != nil {
			legacyDB.Close()
			return err
		}
		for rows.Next() {
			var key string
			var payload []byte
			if err = rows.Scan(&key, &payload); err != nil {
				rows.Close()
				legacyDB.Close()
				return err
			}
			var record legacyMedia
			if json.Unmarshal(payload, &record) != nil || record.ID <= 0 || record.CoverURL == "" {
				continue
			}
			key = strings.TrimPrefix(key, "media:")
			media[key] = record.anime()
		}
		if err = rows.Err(); err != nil {
			rows.Close()
			legacyDB.Close()
			return err
		}
		if err = rows.Close(); err != nil {
			legacyDB.Close()
			return err
		}
		if err = legacyDB.Close(); err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	for key, anime := range legacyDiscoverMedia(filepath.Join(s.Dir, "cache", "discover_cache.json"), s.Dir) {
		if _, exists := media[key]; !exists {
			media[key] = anime
		}
	}
	if len(media) == 0 {
		return nil
	}
	var err error
	for _, bucket := range []string{"history", "watchlist"} {
		values, listErr := s.List(bucket)
		if listErr != nil {
			return listErr
		}
		for _, value := range values {
			if bucket == "history" {
				var h domain.History
				if json.Unmarshal(value, &h) != nil || h.Anime.Title == "" {
					continue
				}
				legacy, ok := media[legacyMediaKey(h.Anime.Title)]
				if !ok {
					continue
				}
				if h.Anime.Cover == "" {
					h.Anime.Cover = legacy.Cover
				}
				aliases := append([]string{legacy.Title}, legacy.Titles...)
				h.Anime.Titles = appendUnique(h.Anime.Titles, aliases...)
				if err = s.Put("history", h.Anime.Key(), h); err != nil {
					return err
				}
				cacheLegacyLookup(s, h.Anime.Title, legacy)
			} else {
				var a domain.Anime
				if json.Unmarshal(value, &a) != nil || a.Title == "" {
					continue
				}
				legacy, ok := media[legacyMediaKey(a.Title)]
				if !ok {
					continue
				}
				if a.Cover == "" {
					a.Cover = legacy.Cover
				}
				aliases := append([]string{legacy.Title}, legacy.Titles...)
				a.Titles = appendUnique(a.Titles, aliases...)
				if err = s.Put("watchlist", a.Key(), a); err != nil {
					return err
				}
				cacheLegacyLookup(s, a.Title, legacy)
			}
		}
	}
	return nil
}

func legacyDiscoverMedia(path, dataDir string) map[string]domain.Anime {
	type item struct {
		Title     string `json:"title"`
		CoverPath string `json:"cover_path"`
		AniListID int    `json:"anilist_id"`
		BannerURL string `json:"banner_url"`
		Score     int    `json:"score"`
		Episodes  int    `json:"episodes"`
	}
	var cached struct {
		Trending []item `json:"trending"`
		Seasonal []item `json:"seasonal"`
	}
	b, err := os.ReadFile(path)
	if err != nil || json.Unmarshal(b, &cached) != nil {
		return nil
	}
	out := map[string]domain.Anime{}
	for _, candidate := range append(cached.Trending, cached.Seasonal...) {
		if candidate.Title == "" || candidate.AniListID <= 0 || candidate.CoverPath == "" {
			continue
		}
		cover, err := filepath.Abs(candidate.CoverPath)
		if err != nil {
			continue
		}
		rel, err := filepath.Rel(dataDir, cover)
		if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
			continue
		}
		if info, err := os.Stat(cover); err != nil || !info.Mode().IsRegular() {
			continue
		}
		id := strconv.Itoa(candidate.AniListID)
		out[legacyMediaKey(candidate.Title)] = domain.Anime{ID: id, Provider: "anilist", Title: candidate.Title, Cover: cover, Banner: candidate.BannerURL, Score: float64(candidate.Score) / 10, EpisodeCount: candidate.Episodes, AniListID: candidate.AniListID, URL: "https://anilist.co/anime/" + id}
	}
	return out
}

func legacyMediaKey(title string) string {
	title = strings.ReplaceAll(title, "(Dublado)", "")
	title = strings.ReplaceAll(title, "(Legendado)", "")
	title = strings.TrimSpace(title)
	if i := strings.Index(title, " - "); i >= 0 {
		title = strings.TrimSpace(title[:i])
	}
	return strings.ToLower(title)
}

func appendUnique(values []string, candidates ...string) []string {
	seen := map[string]bool{}
	for _, value := range values {
		seen[strings.ToLower(strings.TrimSpace(value))] = true
	}
	for _, value := range candidates {
		value = strings.TrimSpace(value)
		key := strings.ToLower(value)
		if value != "" && !seen[key] {
			values = append(values, value)
			seen[key] = true
		}
	}
	return values
}

func cacheLegacyLookup(s *Store, title string, anime domain.Anime) {
	key := "metadata:" + strings.ToLower(title)
	var current domain.Anime
	if ok, stale := s.CacheGet(key, &current); ok && !stale && current.Cover != "" {
		return
	}
	_ = s.CachePut(key, anime, 365*24*time.Hour, 10*365*24*time.Hour)
}
func (s *Store) importLegacy() error {
	read := func(name string, out any) error {
		b, e := os.ReadFile(filepath.Join(s.Dir, name))
		if os.IsNotExist(e) {
			legacy := filepath.Join(filepath.Dir(s.Dir), "animecaos", name)
			b, e = os.ReadFile(legacy)
		}
		if os.IsNotExist(e) {
			return nil
		}
		if e != nil {
			return e
		}
		if e = s.BackupFile(name); e != nil {
			return e
		}
		if e = json.Unmarshal(b, out); e != nil {
			return fmt.Errorf("arquivo legado %s inválido: %w; original preservado", name, e)
		}
		return nil
	}
	var config map[string]json.RawMessage
	if e := read("config.json", &config); e != nil {
		return e
	}
	for k, v := range config {
		if e := s.Put("legacy_config", k, v); e != nil {
			return e
		}
	}
	var watch []string
	if e := read("watchlist.json", &watch); e != nil {
		return e
	}
	for _, title := range watch {
		a := domain.Anime{ID: title, Provider: "legacy", Title: title}
		if e := s.Put("watchlist", a.Key(), a); e != nil {
			return e
		}
	}
	var history map[string][]json.RawMessage
	if e := read("history.json", &history); e != nil {
		return e
	}
	epRE := regexp.MustCompile(`/([0-9]+(?:\.[0-9]+)?)/?$`)
	for title, v := range history {
		if len(v) != 2 {
			continue
		}
		var index int
		if json.Unmarshal(v[1], &index) != nil || index < 0 {
			continue
		}
		h := domain.History{Anime: domain.Anime{ID: title, Provider: "legacy", Title: title}, LegacyIndex: index, NeedsResolve: true}
		var sources [][]json.RawMessage
		if json.Unmarshal(v[0], &sources) == nil {
			for _, source := range sources {
				if len(source) != 2 {
					continue
				}
				var urls []string
				var provider string
				json.Unmarshal(source[0], &urls)
				json.Unmarshal(source[1], &provider)
				if index >= len(urls) {
					continue
				}
				u := urls[index]
				m := epRE.FindStringSubmatch(u)
				h.Episode = domain.Episode{Provider: provider, URL: u}
				if len(m) > 1 {
					h.Episode.Number, _ = strconv.ParseFloat(m[1], 64)
				}
				break
			}
		}
		if e := s.Put("history", h.Anime.Key(), h); e != nil {
			return e
		}
	}
	var mangas map[string]struct {
		Title     string `json:"title"`
		ChapterID string `json:"chapter_id"`
		Label     string `json:"chapter_label"`
		Page      int    `json:"page"`
		Cover     string `json:"cover_path"`
	}
	if e := read("manga_history.json", &mangas); e != nil {
		return e
	}
	for id, m := range mangas {
		p := domain.MangaProgress{Manga: domain.Manga{ID: id, Title: m.Title, Cover: m.Cover}, Chapter: domain.Chapter{ID: m.ChapterID, Title: m.Label}, Page: m.Page}
		if e := s.Put("manga_history", id, p); e != nil {
			return e
		}
	}
	// Existing accounts remain local; never expose tokens through the UI settings DTO.
	for _, p := range []string{"anilist", "mal"} {
		var token string
		if b := config[p+"_access_token"]; b != nil {
			json.Unmarshal(b, &token)
		}
		if token != "" {
			record := map[string]any{"accessToken": token}
			var refresh string
			json.Unmarshal(config[p+"_refresh_token"], &refresh)
			record["refreshToken"] = refresh
			var expiry float64
			json.Unmarshal(config[p+"_token_expires_at"], &expiry)
			record["expiresAt"] = int64(expiry)
			if e := s.Put("auth", p, record); e != nil {
				return e
			}
		}
	}
	return s.Put("migration", "python-v1", true)
}
func (s *Store) Defaults() domain.Settings {
	h, _ := os.UserHomeDir()
	v := domain.Settings{UIScale: 1, Theme: "system", PlayerMode: "mpv", DownloadsDir: filepath.Join(h, "Downloads", "AnimeCaos"), Concurrent: 2, AutoClose: true, AutoCloseMS: 3000, Autoplay: true, Audio: "legendado", Width: 1280, Height: 820}
	if s.Get("settings", "app", &v) == nil {
		if v.Theme != "light" && v.Theme != "dark" && v.Theme != "system" {
			v.Theme = "system"
		}
		return v
	}
	for k, d := range map[string]any{"ui_scale": &v.UIScale, "player_mode": &v.PlayerMode, "player_path": &v.PlayerPath, "downloads_dir": &v.DownloadsDir, "downloads_max_concurrent": &v.Concurrent, "downloads_auto_close": &v.AutoClose, "downloads_auto_close_delay_ms": &v.AutoCloseMS, "discord_rp_enabled": &v.Discord} {
		_ = s.Get("legacy_config", k, d)
	}
	if v.Concurrent < 1 || v.Concurrent > 5 {
		v.Concurrent = 2
	}
	if v.UIScale < 1 || v.UIScale > 1.5 {
		v.UIScale = 1
	}
	v.PlayerMode = strings.ToLower(v.PlayerMode)
	return v
}
