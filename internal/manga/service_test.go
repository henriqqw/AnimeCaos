package manga

import (
	"archive/zip"
	"context"
	"encoding/json"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestChapterDownloadAndCBZ(t *testing.T) {
	var base string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/at-home/server/chapter":
			json.NewEncoder(w).Encode(map[string]any{"baseUrl": base, "chapter": map[string]any{"hash": "hash", "data": []string{"missing.jpg", "2.png"}, "dataSaver": []string{"1.jpg", "2.jpg"}}})
		case "/data-saver/hash/1.jpg":
			io.WriteString(w, "jpeg-page")
		case "/data/hash/2.png":
			io.WriteString(w, "png-page")
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	base = server.URL
	s := New(netx.New())
	s.Base = base
	s.Gate.Interval = 0
	dir := t.TempDir()
	progress := 0
	path, e := s.Download(context.Background(), domain.Manga{Title: "Mangá / teste"}, domain.Chapter{ID: "chapter", Number: "1", Volume: "1"}, dir, func(n, total int) {
		progress = n
		if total != 2 {
			t.Error("wrong total")
		}
	})
	if e != nil {
		t.Fatal(e)
	}
	if progress != 2 {
		t.Fatal("missing progress")
	}
	z, e := zip.OpenReader(path)
	if e != nil {
		t.Fatal(e)
	}
	defer z.Close()
	if len(z.File) != 2 || filepath.Ext(z.File[1].Name) != ".png" {
		t.Fatal("page types/order lost")
	}
	r, e := z.File[0].Open()
	if e != nil {
		t.Fatal(e)
	}
	b, _ := io.ReadAll(r)
	r.Close()
	if string(b) != "jpeg-page" {
		t.Fatal("CBZ data mismatch")
	}
	entries, _ := os.ReadDir(filepath.Dir(path))
	if len(entries) != 1 {
		t.Fatal("partial files retained")
	}
}
func TestFailedChapterNeverPublished(t *testing.T) {
	var base string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/at-home/server/ch" {
			json.NewEncoder(w).Encode(map[string]any{"baseUrl": base, "chapter": map[string]any{"hash": "hash", "data": []string{"1.jpg"}}})
		} else {
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	base = server.URL
	s := New(netx.New())
	s.Base = base
	s.Gate.Interval = 0
	dir := t.TempDir()
	_, e := s.Download(context.Background(), domain.Manga{Title: "Title"}, domain.Chapter{ID: "ch", Number: "1"}, dir, func(int, int) {})
	if e == nil {
		t.Fatal("missing page accepted")
	}
	filepath.WalkDir(dir, func(path string, d os.DirEntry, e error) error {
		if !d.IsDir() {
			t.Errorf("partial published: %s", path)
		}
		return nil
	})
}
func TestLiveMangaDex(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	s := New(netx.New())
	items, e := s.Search(ctx, "One Piece")
	if e != nil || len(items) == 0 {
		t.Fatalf("search: %v", e)
	}
	chapters, e := s.Chapters(ctx, items[0].ID)
	if e != nil || len(chapters) == 0 {
		t.Fatalf("chapters: %v", e)
	}
	pages, e := s.Pages(ctx, chapters[0].ID)
	if e != nil || len(pages) == 0 {
		t.Fatalf("pages: %v", e)
	}
	var home struct {
		Base    string `json:"baseUrl"`
		Chapter struct {
			Hash  string   `json:"hash"`
			Saver []string `json:"dataSaver"`
		} `json:"chapter"`
	}
	s.get(ctx, "/at-home/server/"+chapters[0].ID, &home)
	if len(home.Chapter.Saver) > 0 {
		r, e := s.Client.Do(ctx, "GET", home.Base+"/data-saver/"+home.Chapter.Hash+"/"+home.Chapter.Saver[0], nil, nil)
		if r != nil {
			r.Body.Close()
		}
		t.Logf("original first page %s; saver result %v", pages[0], e)
	}
	path, e := s.Download(ctx, items[0], chapters[0], t.TempDir(), func(int, int) {})
	if e != nil {
		t.Fatal(e)
	}
	z, e := zip.OpenReader(path)
	if e != nil {
		t.Fatal(e)
	}
	defer z.Close()
	if len(z.File) != len(pages) {
		t.Fatal("missing pages")
	}
	t.Logf("%s: %d chapters, downloaded %d pages into a readable CBZ", items[0].Title, len(chapters), len(z.File))
}
