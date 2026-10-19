package app

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/player"
	"github.com/henriqqw/animecaos/internal/store"
)

type historyTestPlayer struct {
	path     string
	position float64
}

func (p *historyTestPlayer) Start(_ context.Context, path, _, _ string, position float64, _ string) error {
	p.path = path
	p.position = position
	return nil
}
func (*historyTestPlayer) Stop()                         {}
func (*historyTestPlayer) Close()                        {}
func (*historyTestPlayer) State() player.State           { return player.State{} }
func (*historyTestPlayer) Command(string, float64) error { return nil }

func TestHistoryMergesDownloadedPlaybackAndResumesOffline(t *testing.T) {
	dataDir := t.TempDir()
	downloadsDir := filepath.Join(t.TempDir(), "downloads")
	videoPath := filepath.Join(downloadsDir, "HUNTER × HUNTER (2011)", "HUNTER × HUNTER (2011) - S01E1-legendado.mp4")
	if err := os.MkdirAll(filepath.Dir(videoPath), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(videoPath, []byte("video"), 0600); err != nil {
		t.Fatal(err)
	}

	anime := domain.Anime{ID: "144", Provider: "otakulogia", Title: "HUNTER × HUNTER (2011)", AniListID: 11061}
	episode := domain.Episode{ID: "episode-1", AnimeID: anime.ID, Provider: anime.Provider, Title: "Episódio 1", Season: 1, Number: 1, URL: "https://example.test/episode-1"}
	download := domain.Download{ID: "download-1", Anime: anime, Episode: episode, Kind: "anime", Status: "done", Path: videoPath}
	localAnime := domain.Anime{ID: videoPath, Provider: "local", Title: anime.Title}
	localEpisode := domain.Episode{ID: videoPath, AnimeID: videoPath, Provider: "local", Title: filepath.Base(videoPath), Number: 1, URL: videoPath}
	database, err := store.Open(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Put("downloads", download.ID, download); err != nil {
		t.Fatal(err)
	}
	if err := database.Put("history", anime.Key(), domain.History{Anime: anime, Episode: episode, Position: 300, Updated: 100}); err != nil {
		t.Fatal(err)
	}
	if err := database.Put("history", localAnime.Key(), domain.History{Anime: localAnime, Episode: localEpisode, Position: 8, Updated: 200}); err != nil {
		t.Fatal(err)
	}
	if err := database.Close(); err != nil {
		t.Fatal(err)
	}

	service, err := New(context.Background(), dataDir, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer service.Close()
	service.mu.Lock()
	service.settings.DownloadsDir = downloadsDir
	service.mu.Unlock()

	history, err := service.History()
	if err != nil {
		t.Fatal(err)
	}
	if len(history) != 1 {
		t.Fatalf("offline and online playback appeared as %d history entries", len(history))
	}
	if history[0].Anime.Key() != anime.Key() || history[0].Episode.Provider != "local" || history[0].Episode.Season != 1 || history[0].Position != 8 {
		t.Fatalf("newer offline history was not merged into the downloaded anime identity: %+v", history[0])
	}
	if err := service.db.Get("history", localAnime.Key(), &domain.History{}); err == nil {
		t.Fatal("duplicate local history key was not removed")
	}

	capture := &historyTestPlayer{}
	service.player = capture
	if err := service.Resume("resume", anime.Key()); err != nil {
		t.Fatal(err)
	}
	if capture.path != videoPath || capture.position != 8 {
		t.Fatalf("offline resume opened %q at %v; want %q at 8", capture.path, capture.position, videoPath)
	}
	service.onPlayer(player.State{Session: service.current.ID, Playing: true, Position: 14})
	history, err = service.History()
	if err != nil || len(history) != 1 || history[0].Anime.Key() != anime.Key() || history[0].Position != 14 {
		t.Fatalf("offline playback did not keep one canonical history entry: %+v, %v", history, err)
	}
}
