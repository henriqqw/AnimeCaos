package downloads

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/store"
)

func TestMangaQueueCancellationKeepsSlotUntilWorkerExits(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	q := New(db, nil, nil, t.TempDir(), 1, func(domain.Download) {})
	started := make(chan string, 4)
	release := make(chan struct{})
	q.SetMangaDownloader(func(ctx context.Context, m domain.Manga, ch domain.Chapter, dir string, p func(int, int)) (string, error) {
		started <- ch.ID
		if ch.ID == "first" {
			<-ctx.Done()
			<-release
			return "", ctx.Err()
		}
		p(1, 1)
		path := filepath.Join(dir, ch.ID+".cbz")
		return path, os.WriteFile(path, []byte("fixture"), 0600)
	})
	defer q.Close()
	m := domain.Manga{ID: "m", Title: "Manga"}
	first, err := q.EnqueueManga(m, domain.Chapter{ID: "first"})
	if err != nil {
		t.Fatal(err)
	}
	select {
	case <-started:
	case <-time.After(time.Second):
		t.Fatal("worker did not start")
	}
	duplicate, err := q.EnqueueManga(m, domain.Chapter{ID: "first"})
	if err != nil || duplicate.ID != first.ID {
		t.Fatal("duplicate queued")
	}
	second, err := q.EnqueueManga(m, domain.Chapter{ID: "second"})
	if err != nil {
		t.Fatal(err)
	}
	q.Cancel(first.ID)
	select {
	case <-started:
		t.Error("cancellation released concurrency slot before worker exit")
	case <-time.After(30 * time.Millisecond):
	}
	close(release)
	select {
	case got := <-started:
		if got != "second" {
			t.Error(got)
		}
	case <-time.After(time.Second):
		t.Fatal("next worker did not start")
	}
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		for _, item := range q.List() {
			if item.ID == second.ID && item.Status == "done" {
				var saved domain.Download
				if e := db.Get("downloads", item.ID, &saved); e != nil {
					t.Fatal(e)
				}
				if saved.Chapter == nil || saved.Chapter.ID != "second" {
					t.Fatal("chapter identity not persisted")
				}
				return
			}
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("chapter did not finish")
}

func TestRestartMarksPendingDownloadsInterrupted(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err = db.Put("downloads", "pending", domain.Download{ID: "pending", Kind: "manga", Status: "downloading", Chapter: &domain.Chapter{ID: "chapter"}}); err != nil {
		t.Fatal(err)
	}
	q := New(db, nil, nil, t.TempDir(), 1, func(domain.Download) {})
	defer q.Close()
	items := q.List()
	if len(items) != 1 || items[0].Status != "interrupted" || items[0].Chapter.ID != "chapter" {
		t.Fatalf("bad recovery: %+v", items)
	}
}
