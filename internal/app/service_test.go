package app

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
	"unicode"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/player"
	"github.com/henriqqw/animecaos/internal/providers"
)

type playbackProvider struct {
	name    string
	detail  domain.Detail
	streams map[string][]domain.Stream
}

type scriptedPlayer struct {
	mu      sync.Mutex
	state   player.State
	starts  []string
	onState func(player.State)
}

func (p *scriptedPlayer) Start(_ context.Context, streamURL, _, _ string, _ float64, session string) error {
	p.mu.Lock()
	p.starts = append(p.starts, streamURL)
	attempt := len(p.starts)
	state := player.State{Session: session, Playing: true}
	if attempt == 1 {
		state.Playing = false
		state.Error = "manifesto falhou antes do avanço"
	} else {
		state.Position = 1
		state.VideoCodec = "h264"
	}
	p.state = state
	callback := p.onState
	p.mu.Unlock()
	if callback != nil {
		callback(state)
	}
	return nil
}
func (p *scriptedPlayer) Stop()                         {}
func (p *scriptedPlayer) Close()                        {}
func (p *scriptedPlayer) State() player.State           { p.mu.Lock(); defer p.mu.Unlock(); return p.state }
func (p *scriptedPlayer) Command(string, float64) error { return nil }

func (p *playbackProvider) Name() string { return p.name }
func (p *playbackProvider) Search(context.Context, string, int) (domain.SearchResult, error) {
	return domain.SearchResult{}, nil
}
func (p *playbackProvider) Details(context.Context, domain.Anime) (domain.Detail, error) {
	return p.detail, nil
}
func (p *playbackProvider) Resolve(_ context.Context, ep domain.Episode) ([]domain.Stream, error) {
	return p.streams[ep.ID], nil
}

func TestResolveFallsBackAfterPrimaryVideoReturns404(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/missing" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "video/mp4")
		w.Write([]byte("video bytes"))
	}))
	defer server.Close()

	primaryEpisode := domain.Episode{ID: "fire-e1", Provider: "animefire", Season: 1, Number: 1}
	alternateEpisode := domain.Episode{ID: "cc-e1", Provider: "animesonlinecc", Season: 1, Number: 1}
	primary := &playbackProvider{name: "animefire", streams: map[string][]domain.Stream{
		primaryEpisode.ID: {{URL: server.URL + "/missing", Kind: "file", Audio: "legendado"}},
	}}
	alternate := &playbackProvider{name: "animesonlinecc", detail: domain.Detail{Episodes: []domain.Episode{alternateEpisode}}, streams: map[string][]domain.Stream{
		alternateEpisode.ID: {{URL: server.URL + "/available", Kind: "file", Audio: "legendado"}},
	}}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{primary, alternate}}, settings: domain.Settings{Audio: "legendado"}}
	anime := domain.Anime{ID: "fire-a", Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc-a", Provider: "animesonlinecc", Title: "Same anime"}}}

	stream, err := s.resolve(context.Background(), anime, primaryEpisode)
	if err != nil {
		t.Fatal(err)
	}
	if stream.URL != server.URL+"/available" {
		t.Fatalf("selected %q; expected alternate stream", stream.URL)
	}
}

func TestResolveRanksQualityAcrossSourcesAfterAudioPreference(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write([]byte("video bytes"))
	}))
	defer server.Close()
	primaryEpisode := domain.Episode{ID: "fire-e1", Provider: "animefire", Season: 1, Number: 1}
	alternateEpisode := domain.Episode{ID: "cc-e1", Provider: "animesonlinecc", Season: 1, Number: 1}
	primary := &playbackProvider{name: "animefire", streams: map[string][]domain.Stream{primaryEpisode.ID: {
		{URL: server.URL + "/dub", Audio: "dublado", Qualities: []string{"1080p"}},
		{URL: server.URL + "/sub-low", Audio: "legendado", Qualities: []string{"480p"}},
	}}}
	alternate := &playbackProvider{name: "animesonlinecc", detail: domain.Detail{Episodes: []domain.Episode{alternateEpisode}}, streams: map[string][]domain.Stream{alternateEpisode.ID: {
		{URL: server.URL + "/sub-high", Audio: "legendado", Qualities: []string{"720p"}},
	}}}
	anime := domain.Anime{ID: "fire", Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc", Title: "Same anime"}}}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{primary, alternate}}, settings: domain.Settings{Audio: "legendado"}}
	selected, err := s.resolve(context.Background(), anime, primaryEpisode)
	if err != nil {
		t.Fatal(err)
	}
	if selected.URL != server.URL+"/sub-high" || selected.Source != "animesonlinecc" {
		t.Fatalf("audio preference and global quality ranking selected the wrong stream: %+v", selected)
	}
	s.settings.Audio = ""
	selected, err = s.resolve(context.Background(), anime, primaryEpisode)
	if err != nil {
		t.Fatal(err)
	}
	if selected.URL != server.URL+"/dub" {
		t.Fatalf("without audio preference, max resolution should win: %+v", selected)
	}
}

func TestPlaybackRetriesBeforeProgressAndStopsSwitchingAfterProgress(t *testing.T) {
	previousTimeout := playerStartupTimeout
	playerStartupTimeout = 40 * time.Millisecond
	defer func() { playerStartupTimeout = previousTimeout }()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write([]byte("video bytes"))
	}))
	defer server.Close()
	var eventMu sync.Mutex
	transientErrors := 0
	s, err := New(context.Background(), t.TempDir(), func(name string, value any) {
		if name == "player" {
			if event, ok := value.(PlayerEvent); ok && event.State.Error != "" {
				eventMu.Lock()
				transientErrors++
				eventMu.Unlock()
			}
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	primaryEpisode := domain.Episode{ID: "fire-e1", Provider: "animefire", Season: 1, Number: 1}
	alternateEpisode := domain.Episode{ID: "cc-e1", Provider: "animesonlinecc", Season: 1, Number: 1}
	primary := &playbackProvider{name: "animefire", streams: map[string][]domain.Stream{primaryEpisode.ID: {{URL: server.URL + "/high", Audio: "legendado", Qualities: []string{"1080p"}}}}}
	alternate := &playbackProvider{name: "animesonlinecc", detail: domain.Detail{Episodes: []domain.Episode{alternateEpisode}}, streams: map[string][]domain.Stream{alternateEpisode.ID: {
		{URL: server.URL + "/medium", Audio: "legendado", Qualities: []string{"720p"}},
		{URL: server.URL + "/low", Audio: "legendado", Qualities: []string{"480p"}},
	}}}
	s.catalog = &providers.Catalog{Providers: []domain.AnimeProvider{primary, alternate}}
	s.settings.Audio = "legendado"
	s.settings.PlayerMode = "mpv"
	fake := &scriptedPlayer{}
	fake.onState = s.onPlayer
	s.player = fake
	anime := domain.Anime{ID: "fire", Provider: "animefire", Title: "Same anime", Variants: []domain.Anime{{ID: "cc", Provider: "animesonlinecc", Title: "Same anime"}}}
	if err = s.Play("test-play", anime, []domain.Episode{primaryEpisode}, 0, false); err != nil {
		t.Fatal(err)
	}
	deadline := time.After(time.Second)
	for {
		fake.mu.Lock()
		starts := len(fake.starts)
		fake.mu.Unlock()
		if starts >= 2 {
			break
		}
		select {
		case <-deadline:
			t.Fatal("player did not try the next stream after startup failed")
		case <-time.After(10 * time.Millisecond):
		}
	}
	time.Sleep(80 * time.Millisecond)
	fake.mu.Lock()
	defer fake.mu.Unlock()
	if len(fake.starts) != 2 {
		t.Fatalf("source changed after playback position advanced: %d attempts", len(fake.starts))
	}
	eventMu.Lock()
	defer eventMu.Unlock()
	if transientErrors != 0 {
		t.Fatalf("transient startup error was exposed while fallback succeeded: %d", transientErrors)
	}
}

func TestLivePlaybackUsesAvailableVariant(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 to check live stream playback candidates")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	s, err := New(ctx, t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()

	query := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_TITLE"))
	if query == "" {
		query = "Demon Slayer"
	}
	result, err := s.Search("live-playback", query, 1, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) == 0 {
		t.Fatalf("no result for %q", query)
	}
	anime := result.Items[0]
	t.Logf("selected title=%q key=%s AniListID=%d variants=%d", anime.Title, anime.Key(), anime.AniListID, len(anime.Variants))
	detail, err := s.Details("live-playback", anime)
	if err != nil {
		t.Fatal(err)
	}
	if len(detail.Episodes) == 0 {
		t.Fatal("selected title has no episodes")
	}
	t.Logf("detail title=%q key=%s episodes=%d first episode=%q", detail.Anime.Title, detail.Anime.Key(), len(detail.Episodes), detail.Episodes[0].Title)
	var lastErr error
	for i, episode := range detail.Episodes[:min(3, len(detail.Episodes))] {
		streamCtx, streamCancel := context.WithTimeout(ctx, 25*time.Second)
		stream, resolveErr := s.resolve(streamCtx, detail.Anime, episode)
		streamCancel()
		if resolveErr == nil {
			t.Logf("playable episode resolved: title=%q episode=%q input=%s kind=%s", detail.Anime.Title, episode.Title, episode.Key(), stream.Kind)
			return
		}
		t.Logf("candidate %d failed: %v", i+1, resolveErr)
		lastErr = resolveErr
	}
	t.Fatalf("no playable stream found among first episodes: %v", lastErr)
}

func TestLiveMultilingualSearchKeepsCanonicalIdentity(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real multilingual search checks")
	}
	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	queries := []struct{ text, group string }{
		{"Demon Slayer", "demon-slayer"},
		{"鬼滅の刃", "demon-slayer"},
		{"Kimetsu no Yaiba", "demon-slayer"},
		{"Frieren e a Jornada para o Além", "frieren"},
	}
	canonical := map[string]int{}
	for i, query := range queries {
		result, err := s.Search("live-multilingual", query.text, 1, nil)
		if err != nil {
			t.Fatalf("search %q: %v", query.text, err)
		}
		var found int
		for _, anime := range result.Items {
			if anime.AniListID > 0 {
				found = anime.AniListID
				break
			}
		}
		if found == 0 {
			t.Fatalf("search %q produced no canonically matched result", query.text)
		}
		if expected := canonical[query.group]; expected != 0 && found != expected {
			t.Fatalf("query %q resolved to ID %d; expected the same work %d", query.text, found, expected)
		}
		canonical[query.group] = found
		if i == 0 {
			t.Logf("English alias resolved to AniList ID %d", found)
		}
	}
}

func TestLiveSearchAvailabilityTenAnimeSamples(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real search availability samples")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 7*time.Minute)
	defer cancel()
	s, err := New(ctx, t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	titles := []string{"Hunter x Hunter 2011", "Black Clover", "One Punch Man", "Demon Slayer", "Frieren", "Solo Leveling", "Jujutsu Kaisen", "One Piece", "Naruto Shippuden", "Death Note"}
	if onlyTitle := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_TITLE")); onlyTitle != "" {
		titles = []string{onlyTitle}
	}
	for index, title := range titles {
		if ctx.Err() != nil {
			t.Fatalf("live sampling stopped after %d/%d titles: %v", index, len(titles), ctx.Err())
		}
		searchStarted := time.Now()
		result, searchErr := s.Search("live-availability-"+strconv.Itoa(index), title, 1, nil)
		t.Logf("anime=%q search_elapsed=%s", title, time.Since(searchStarted).Round(time.Millisecond))
		if searchErr != nil {
			t.Logf("anime=%q available=false search_error=%q", title, searchErr)
			continue
		}
		if len(result.Warnings) > 0 {
			t.Logf("anime=%q warnings=%q", title, strings.Join(result.Warnings, " | "))
		}
		if len(result.Items) == 0 {
			t.Logf("anime=%q available=false reason=no episode-1 preflight passed", title)
			continue
		}
		metadataMatches, _ := s.metadata.TitleMatches(ctx, title, 0)
		targetID := liveExpectedAniListID(title, metadataMatches)
		metadataTitles := make([]string, 0, len(metadataMatches))
		for _, match := range metadataMatches {
			metadataTitles = append(metadataTitles, fmt.Sprintf("%d:%s", match.AniListID, match.Title))
		}
		t.Logf("anime=%q canonical_target=%d metadata_matches=%s", title, targetID, strings.Join(metadataTitles, ";"))
		if rawExpectedID := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_EXPECTED_ANILIST_ID")); rawExpectedID != "" {
			expectedID, parseErr := strconv.Atoi(rawExpectedID)
			if parseErr != nil || expectedID <= 0 {
				t.Fatalf("invalid ANIMECAOS_LIVE_EXPECTED_ANILIST_ID %q", rawExpectedID)
			}
			targetID = expectedID
		}
		for _, anime := range result.Items {
			availability := anime.Availability
			if availability == nil {
				t.Errorf("anime=%q item=%q escaped without availability metadata", title, anime.Title)
				continue
			}
			t.Logf("anime=%q result=%q key=%s anilist_id=%d variants=%d match_score=%.2f available=true quality=%q max_height=%d sources=%s sample=%q", title, anime.Title, anime.Key(), anime.AniListID, len(anime.Variants), anime.MatchScore, availability.Quality, availability.MaxHeight, strings.Join(availability.SourcesVerified, ","), availability.SampleEpisode)
		}
		if os.Getenv("ANIMECAOS_PLAYER_TEST") == "1" {
			anime, ok := liveExpectedAnime(title, result.Items, targetID)
			if !ok {
				t.Errorf("anime=%q: no available card matched canonical AniList ID %d or the exact title", title, targetID)
				continue
			}
			if err := liveMPVSeekSample(t, s, anime, "live-mpv-"+strconv.Itoa(index), providers.InferSearchIntent(title).Season); err != nil {
				t.Errorf("anime=%q MPV E2E failed: %v", title, err)
			}
		}
	}
}

func liveExpectedAniListID(query string, matches []domain.Anime) int {
	queryKey := liveTitleKey(query)
	bestID, bestEpisodes := 0, -1
	for _, match := range matches {
		for _, title := range match.PrimaryTitles {
			if match.AniListID > 0 && liveTitleKey(title) == queryKey {
				return match.AniListID
			}
			if match.AniListID > 0 && strings.Contains(liveTitleKey(title), queryKey) && match.EpisodeCount > bestEpisodes {
				bestID, bestEpisodes = match.AniListID, match.EpisodeCount
			}
		}
	}
	if bestID > 0 {
		return bestID
	}
	if len(matches) > 0 {
		return matches[0].AniListID
	}
	return 0
}

func liveExpectedAnime(query string, items []domain.Anime, targetID int) (domain.Anime, bool) {
	if targetID > 0 {
		for _, anime := range items {
			if anime.AniListID == targetID {
				return anime, true
			}
		}
	}
	queryKey := liveTitleKey(query)
	for _, anime := range items {
		if liveTitleKey(anime.Title) == queryKey {
			return anime, true
		}
	}
	return domain.Anime{}, false
}

func liveTitleKey(value string) string {
	return strings.Map(func(r rune) rune {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			return unicode.ToLower(r)
		}
		return -1
	}, value)
}

func liveMPVSeekSample(t *testing.T, s *Service, anime domain.Anime, operationID string, requestedSeason int) error {
	detail, err := s.Details(operationID+"-details", anime)
	if err != nil {
		return fmt.Errorf("details: %w", err)
	}
	episode, ok := firstEpisodeForSeason(detail.Episodes, requestedSeason)
	if !ok {
		return fmt.Errorf("details did not contain one explicit episode 1 for season %d", requestedSeason)
	}
	index := -1
	for i, candidate := range detail.Episodes {
		if candidate.Key() == episode.Key() {
			index = i
			break
		}
	}
	if index < 0 {
		return fmt.Errorf("episode 1 was not in the playback list")
	}
	if err := s.Play(operationID, detail.Anime, detail.Episodes, index, false); err != nil {
		return err
	}
	defer func() { _ = s.PlayerCommand("stop", 0) }()
	deadline := time.NewTimer(45 * time.Second)
	defer deadline.Stop()
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	var playing player.State
	for {
		playing = s.player.State()
		if playing.Error != "" && !playing.Playing && playing.Position < 0.5 {
			// The startup monitor may still have another validated candidate.
			s.mu.Lock()
			remaining := s.current.FallbackRemaining
			s.mu.Unlock()
			if remaining == 0 {
				return fmt.Errorf("MPV startup: %s", playing.Error)
			}
		}
		if playing.Position > 0.5 && playing.VideoCodec != "" && playing.AudioCodec != "" && playing.Width > 0 && playing.Height > 0 {
			break
		}
		select {
		case <-deadline.C:
			return fmt.Errorf("MPV did not report decoded video/audio and dimensions: %+v", playing)
		case <-ticker.C:
		}
	}
	s.mu.Lock()
	selected := s.current
	s.mu.Unlock()
	target := playing.Position + 3
	if playing.Duration > 0 && target > playing.Duration-1 {
		target = playing.Duration / 2
	}
	if err := s.PlayerCommand("seek", target); err != nil {
		return fmt.Errorf("seek command: %w", err)
	}
	for {
		state := s.player.State()
		if state.Error != "" {
			return fmt.Errorf("MPV after seek: %s", state.Error)
		}
		if state.Position >= target+0.5 {
			t.Logf("MPV sample anime=%q source=%s height=%dp codecs=%s/%s dimensions=%dx%d seek=%.1fs position=%.1fs", anime.Title, selected.Source, selected.Height, state.VideoCodec, state.AudioCodec, state.Width, state.Height, target, state.Position)
			return nil
		}
		select {
		case <-deadline.C:
			return fmt.Errorf("MPV position did not advance after seek to %.1f: %+v", target, state)
		case <-ticker.C:
		}
	}
}

func TestLiveAnidriveMPVE2E(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" || os.Getenv("ANIMECAOS_PLAYER_TEST") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 and ANIMECAOS_PLAYER_TEST=1 for the Anidrive-to-MPV check")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	s, err := New(ctx, t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	provider, err := s.catalog.Provider("animesonlinecc")
	if err != nil {
		t.Fatal(err)
	}
	s.catalog.Providers = []domain.AnimeProvider{provider}
	const episodeURL = "https://animesonline.io/17864/"
	anime := domain.Anime{ID: "live-anidrive-17864", Provider: "animesonlinecc", Title: "Anidrive live player sample"}
	episode := domain.Episode{ID: "live-anidrive-17864-e1", AnimeID: anime.ID, Provider: anime.Provider, Title: "Anidrive live player sample", Season: 1, Number: 1, URL: episodeURL}
	if err := s.Play("live-anidrive-e2e", anime, []domain.Episode{episode}, 0, false); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = s.PlayerCommand("stop", 0) }()
	deadline := time.NewTimer(75 * time.Second)
	defer deadline.Stop()
	ticker := time.NewTicker(150 * time.Millisecond)
	defer ticker.Stop()
	var state player.State
	for {
		state = s.player.State()
		if state.Position > 0.5 && state.VideoCodec != "" && state.AudioCodec != "" && state.Width > 0 && state.Height > 0 {
			break
		}
		if state.EOF {
			s.mu.Lock()
			selected := s.current
			s.mu.Unlock()
			t.Fatalf("Anidrive stream reached EOF without decoded audio/video: selected source=%s height=%dp bandwidth=%d state=%+v", selected.Source, selected.Height, selected.Bandwidth, state)
		}
		if state.Error != "" && !state.Playing && state.Position < 0.5 {
			s.mu.Lock()
			remaining := s.current.FallbackRemaining
			s.mu.Unlock()
			if remaining == 0 {
				t.Fatalf("Anidrive MPV startup failed: %s", state.Error)
			}
		}
		select {
		case <-deadline.C:
			t.Fatalf("Anidrive MPV did not report decoded audio/video and dimensions: %+v", state)
		case <-ticker.C:
		}
	}
	s.mu.Lock()
	selected := s.current
	s.mu.Unlock()
	t.Logf("Anidrive MPV selected source=%s height=%dp bandwidth=%d", selected.Source, selected.Height, selected.Bandwidth)
	target := state.Position + 3
	if state.Duration > 0 && target > state.Duration-1 {
		target = state.Duration / 2
	}
	if err := s.PlayerCommand("seek", target); err != nil {
		t.Fatal(err)
	}
	for {
		state = s.player.State()
		if state.EOF {
			t.Fatalf("Anidrive stream reached EOF before seek completed: selected source=%s height=%dp state=%+v", selected.Source, selected.Height, state)
		}
		if state.Error != "" {
			t.Fatalf("Anidrive MPV failed after seek: %s", state.Error)
		}
		if state.Position >= target+0.5 {
			t.Logf("Anidrive MPV sample source=%s height=%dp codecs=%s/%s dimensions=%dx%d seek=%.1fs position=%.1fs", selected.Source, selected.Height, state.VideoCodec, state.AudioCodec, state.Width, state.Height, target, state.Position)
			return
		}
		select {
		case <-deadline.C:
			t.Fatalf("Anidrive MPV did not advance after seek: target=%.1f state=%+v", target, state)
		case <-ticker.C:
		}
	}
}

func TestLiveLegacyHistoryCovers(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real legacy poster lookup checks")
	}
	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	titles := []string{
		"Bleach: Sennen Kessen-hen - Ketsubetsu-tan",
		"Bleach: Sennen Kessen-hen - Soukoku-tan",
		"Clevatess II: Majuu no Ou to Itsuwari no Yuusha Denshou",
		"Dogulwang",
		"Grand Blue Season 3",
		"Hunter x Hunter (2011) (Dublado)",
		"Jujutsu Kaisen 2nd Season",
		"Koukaku Kidoutai Arise: Ghost in the Shell - Border:1 Ghost Pain",
		"Mushoku Tensei II: Isekai Ittara Honki Dasu (Dublado)",
		"Naruto Clássico Dublado",
		"One Piece (Dublado)",
		"Yomi no Tsugai",
		"Yuu☆Yuu☆Hakusho",
	}
	missing := []string{}
	for _, title := range titles {
		anime, err := s.Preview("live-legacy-cover", title, 0)
		if err != nil || anime.Cover == "" {
			missing = append(missing, title)
		}
	}
	if len(missing) > 0 {
		t.Fatalf("legacy posters missing for %d/%d titles: %v", len(missing), len(titles), missing)
	}
}

func TestOperationCancellationDoesNotCancelReplacement(t *testing.T) {
	s, e := New(context.Background(), t.TempDir(), nil)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	first, end1 := s.operation("search", time.Minute)
	second, end2 := s.operation("search", time.Minute)
	defer end2()
	if first.Err() == nil {
		t.Fatal("first operation not cancelled")
	}
	end1()
	if second.Err() != nil {
		t.Fatal("old completion cancelled new operation")
	}
	s.Cancel("search")
	if second.Err() == nil {
		t.Fatal("replacement not cancelled")
	}
}

func TestAutoplayCannotReplaceANewerSelection(t *testing.T) {
	s, e := New(context.Background(), t.TempDir(), nil)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	s.settings.Autoplay = true
	s.playRequest = 1
	p := playback{ID: "previous", Request: 1}
	s.current = p
	if !s.canAutoplay(p) {
		t.Fatal("current playback should allow autoplay")
	}
	s.playRequest++ // A newer request may still be resolving its stream.
	if s.canAutoplay(p) {
		t.Fatal("old EOF replaced a newer request")
	}
	s.playRequest = 1
	s.current.ID = "new-session"
	if s.canAutoplay(p) {
		t.Fatal("old session allowed autoplay")
	}
}

func TestFavoriteDoesNotPersistSearchAvailabilitySummary(t *testing.T) {
	s, err := New(context.Background(), t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	anime := domain.Anime{ID: "saved", Provider: "animefire", Title: "Saved anime", Availability: &domain.PlaybackAvailability{MaxHeight: 1080, Quality: "Até 1080p", SourcesVerified: []string{"animefire"}, SampleEpisode: "E1"}}
	if err := s.Favorite(anime, true); err != nil {
		t.Fatal(err)
	}
	library, err := s.Library()
	if err != nil {
		t.Fatal(err)
	}
	if len(library) != 1 || library[0].Availability != nil {
		t.Fatalf("ephemeral search availability leaked to the library: %+v", library)
	}
}

func TestOfflinePlayerEventsArePersisted(t *testing.T) {
	events := []PlayerEvent{}
	s, e := New(context.Background(), t.TempDir(), func(name string, v any) {
		if name == "player" {
			events = append(events, v.(PlayerEvent))
		}
	})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	a := domain.Anime{ID: "local-file", Provider: "local", Title: "Downloaded anime"}
	ep := domain.Episode{ID: "local-file", Provider: "local", Number: 3}
	s.current = playback{ID: "offline", Anime: a, Episodes: []domain.Episode{ep}, Local: true}
	s.onPlayer(player.State{Session: "offline", Playing: true, Position: 90, Duration: 1200})
	s.onPlayer(player.State{Session: "offline", Position: 95, Duration: 1200})
	if len(events) != 2 || events[1].State.Position != 95 {
		t.Fatalf("offline controls did not get state: %+v", events)
	}
	var history domain.History
	if e = s.db.Get("history", a.Key(), &history); e != nil || history.Position != 95 {
		t.Fatalf("offline resume lost: %+v %v", history, e)
	}
	s.onPlayer(player.State{Session: "old-session", Position: 100})
	if len(events) != 2 {
		t.Fatal("old session affected current player")
	}
}

func TestStoppingPlayerClearsThePublishedSession(t *testing.T) {
	events := []any{}
	s, err := New(context.Background(), t.TempDir(), func(name string, value any) {
		if name == "player" {
			events = append(events, value)
		}
	})
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	released := false
	s.current = playback{
		ID:       "session-to-close",
		Episodes: []domain.Episode{{ID: "ep1", Provider: "animefire"}},
		Release:  func() { released = true },
	}

	if err := s.PlayerCommand("stop", 0); err != nil {
		t.Fatal(err)
	}
	if s.current.ID != "" {
		t.Fatalf("stopped session remains current: %+v", s.current)
	}
	if !released {
		t.Fatal("stopping did not release the active media session")
	}
	if len(events) == 0 || events[len(events)-1] != nil {
		t.Fatalf("stop should publish a clear player event, got %#v", events)
	}
}
