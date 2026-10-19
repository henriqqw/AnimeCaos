package store

import (
	"database/sql"
	"encoding/json"
	"github.com/henriqqw/animecaos/internal/domain"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLegacyMigrationIdempotent(t *testing.T) {
	dir := t.TempDir()
	files := map[string]string{"config.json": `{"ui_scale":1.25,"anilist_access_token":"local-test-token","mal_token_expires_at":12345.6}`, "watchlist.json": `["Título antigo"]`, "history.json": `{"Título antigo":[[[["https://old.example/video/12"],"animefire"]],0]}`, "manga_history.json": `{"manga-id":{"title":"Mangá","chapter_id":"ch1","chapter_label":"Cap 2","page":7}}`}
	for name, b := range files {
		if e := os.WriteFile(filepath.Join(dir, name), []byte(b), 0600); e != nil {
			t.Fatal(e)
		}
	}
	s, e := Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	v := s.Defaults()
	if v.UIScale != 1.25 {
		t.Fatal(v)
	}
	history, e := DecodeList[domain.History](s, "history")
	if e != nil || len(history) != 1 || !history[0].NeedsResolve || history[0].Episode.Number != 12 {
		t.Fatalf("%+v %v", history, e)
	}
	if history[0].Episode.ID != "" {
		t.Fatal("legacy index must not become new ID")
	}
	for name := range files {
		if _, e = os.Stat(filepath.Join(dir, "legacy-backup", name)); e != nil {
			t.Fatal(e)
		}
	}
	s.Delete("watchlist", "legacy:Título antigo")
	s.Close()
	s, e = Open(dir)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	items, _ := DecodeList[domain.Anime](s, "watchlist")
	if len(items) != 0 {
		t.Fatal("migration reran and restored removed favorite")
	}
}

func TestLegacyMediaCacheRestoresOldHistoryCovers(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "cache"), 0700); err != nil {
		t.Fatal(err)
	}
	cache, err := sql.Open("sqlite", filepath.Join(dir, "cache", "api_cache.db"))
	if err != nil {
		t.Fatal(err)
	}
	_, err = cache.Exec(`CREATE TABLE entries (key TEXT PRIMARY KEY,namespace TEXT,payload TEXT,created_at REAL,soft_expires_at REAL,hard_expires_at REAL,is_negative INTEGER,hits INTEGER,last_hit_at REAL);
INSERT INTO entries VALUES ('media:bleach: sennen kessen-hen','media','{"id":123,"id_mal":456,"romaji":"Bleach: Sennen Kessen-hen","english":"Bleach: Thousand-Year Blood War","cover_url":"https://images.example/bleach.jpg","score":86,"episodes":13}',1,9999999999,9999999999,0,1,1);`)
	if err != nil {
		t.Fatal(err)
	}
	if err = cache.Close(); err != nil {
		t.Fatal(err)
	}
	legacy := `{"Bleach: Sennen Kessen-hen - Ketsubetsu-tan":[[[["https://old.example/video/1"],"animefire"]],0]}`
	if err = os.WriteFile(filepath.Join(dir, "history.json"), []byte(legacy), 0600); err != nil {
		t.Fatal(err)
	}
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	history, err := DecodeList[domain.History](s, "history")
	if err != nil || len(history) != 1 {
		t.Fatalf("history records=%d err=%v", len(history), err)
	}
	if history[0].Anime.Cover != "https://images.example/bleach.jpg" || len(history[0].Anime.Titles) == 0 {
		t.Fatalf("legacy image metadata was not attached: %+v", history[0].Anime)
	}
	var restored domain.Anime
	if ok, _ := s.CacheGet("metadata:"+strings.ToLower(history[0].Anime.Title), &restored); !ok || restored.Cover == "" {
		t.Fatalf("legacy title lookup was not restored: %+v", restored)
	}
}

func TestLegacyDiscoverCacheUsesExistingCoverFiles(t *testing.T) {
	dir := t.TempDir()
	cover := filepath.Join(dir, "cache", "covers", "one-piece.jpg")
	if err := os.MkdirAll(filepath.Dir(cover), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(cover, []byte("cached-image"), 0600); err != nil {
		t.Fatal(err)
	}
	b, err := json.Marshal(map[string]any{"trending": []any{map[string]any{"title": "One Piece", "cover_path": cover, "anilist_id": 21, "score": 87}}})
	if err != nil {
		t.Fatal(err)
	}
	cachePath := filepath.Join(dir, "cache", "discover_cache.json")
	if err = os.WriteFile(cachePath, b, 0600); err != nil {
		t.Fatal(err)
	}
	items := legacyDiscoverMedia(cachePath, dir)
	anime, ok := items["one piece"]
	if !ok || anime.Cover != cover || anime.AniListID != 21 {
		t.Fatalf("cached discovery cover not recovered: %+v", items)
	}
}

func TestLegacyCacheV2RunsEvenWhenV1WasAlreadyMarked(t *testing.T) {
	dir := t.TempDir()
	s, err := Open(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	if err := s.Put("migration", "python-cache-v1", true); err != nil {
		t.Fatal(err)
	}
	if err := s.Delete("migration", "python-cache-v2"); err != nil {
		t.Fatal(err)
	}
	cover := filepath.Join(dir, "cache", "covers", "old.jpg")
	if err := os.MkdirAll(filepath.Dir(cover), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(cover, []byte("old cover"), 0600); err != nil {
		t.Fatal(err)
	}
	cachePath := filepath.Join(dir, "cache", "discover_cache.json")
	cacheData, err := json.Marshal(map[string]any{"trending": []any{map[string]any{"title": "One Piece", "cover_path": cover, "anilist_id": 21}}})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(cachePath, cacheData, 0600); err != nil {
		t.Fatal(err)
	}
	h := domain.History{Anime: domain.Anime{ID: "old-one-piece", Provider: "legacy", Title: "One Piece"}, NeedsResolve: true}
	if err := s.Put("history", h.Anime.Key(), h); err != nil {
		t.Fatal(err)
	}
	if err := s.ImportLegacy(); err != nil {
		t.Fatal(err)
	}
	var restored domain.History
	if err := s.Get("history", h.Anime.Key(), &restored); err != nil {
		t.Fatal(err)
	}
	if restored.Anime.Cover != cover {
		t.Fatalf("v2 migration did not restore poster after v1 marker: %+v", restored.Anime)
	}
}

func TestMalformedLegacyPreserved(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "history.json")
	os.WriteFile(p, []byte("{invalid"), 0600)
	s, e := Open(dir)
	if e == nil {
		s.Close()
		t.Fatal("expected explicit migration error")
	}
	b, _ := os.ReadFile(p)
	if string(b) != "{invalid" {
		t.Fatal("original modified")
	}
	if _, e := os.Stat(filepath.Join(dir, "legacy-backup", "history.json")); e != nil {
		t.Fatal(e)
	}
}
