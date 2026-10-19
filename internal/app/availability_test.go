package app

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/providers"
)

type availabilityFixtureProvider struct {
	name      string
	detail    domain.Detail
	streams   map[string][]domain.Stream
	delay     time.Duration
	mu        sync.Mutex
	calls     int
	active    int
	maxActive int
	block     bool
}

func (p *availabilityFixtureProvider) Name() string { return p.name }
func (p *availabilityFixtureProvider) Search(context.Context, string, int) (domain.SearchResult, error) {
	return domain.SearchResult{}, nil
}
func (p *availabilityFixtureProvider) Details(ctx context.Context, _ domain.Anime) (domain.Detail, error) {
	p.mu.Lock()
	p.calls++
	p.active++
	if p.active > p.maxActive {
		p.maxActive = p.active
	}
	p.mu.Unlock()
	defer func() { p.mu.Lock(); p.active--; p.mu.Unlock() }()
	if p.block {
		<-ctx.Done()
		return domain.Detail{}, ctx.Err()
	}
	if p.delay > 0 {
		select {
		case <-time.After(p.delay):
		case <-ctx.Done():
			return domain.Detail{}, ctx.Err()
		}
	}
	return p.detail, nil
}
func (p *availabilityFixtureProvider) Resolve(_ context.Context, ep domain.Episode) ([]domain.Stream, error) {
	return p.streams[ep.ID], nil
}

func TestSearchAvailabilityFiltersAndProgressivelyUpdatesOneCard(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write([]byte("video"))
	}))
	defer server.Close()
	main := domain.Anime{ID: "a1", Provider: "animefire", Title: "Same title", AniListID: 80}
	alt := domain.Anime{ID: "b1", Provider: "onlinecc", Title: "Same title"}
	main.Variants = []domain.Anime{alt}
	first := &availabilityFixtureProvider{name: "animefire", detail: domain.Detail{Episodes: []domain.Episode{{ID: "a-e1", Provider: "animefire", Season: 1, Number: 1}}}, streams: map[string][]domain.Stream{"a-e1": {{URL: server.URL + "/low", Qualities: []string{"480p"}}}}}
	second := &availabilityFixtureProvider{name: "onlinecc", delay: 80 * time.Millisecond, detail: domain.Detail{Episodes: []domain.Episode{{ID: "b-e1", Provider: "onlinecc", Season: 1, Number: 1}}}, streams: map[string][]domain.Stream{"b-e1": {{URL: server.URL + "/high", Qualities: []string{"1080p"}}}}}
	var searchItemEvents int
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{first, second}}, emit: func(name string, _ any) {
		if name == "search-item" {
			searchItemEvents++
		}
	}, availabilityCache: map[string]availabilityCacheEntry{}}
	result := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{main}})
	if len(result.Items) != 1 {
		t.Fatalf("expected one available card, got %d", len(result.Items))
	}
	availability := result.Items[0].Availability
	if availability == nil || availability.MaxHeight != 1080 || availability.Quality != "Até 1080p" || len(availability.SourcesVerified) != 2 {
		t.Fatalf("availability summary did not aggregate both sources: %+v", availability)
	}
	if searchItemEvents != 0 {
		t.Fatalf("search cards must be returned as one verified batch, got %d progressive events", searchItemEvents)
	}
	encoded, err := json.Marshal(availability)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "http://") || strings.Contains(string(encoded), "https://") {
		t.Fatalf("availability summary must not retain stream URLs: %s", encoded)
	}
	first.mu.Lock()
	firstCalls := first.calls
	first.mu.Unlock()
	second.mu.Lock()
	secondCalls := second.calls
	second.mu.Unlock()
	cached := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{main}})
	if len(cached.Items) != 1 || cached.Items[0].Availability.MaxHeight != 1080 {
		t.Fatalf("positive availability cache lost summary: %+v", cached.Items)
	}
	first.mu.Lock()
	defer first.mu.Unlock()
	second.mu.Lock()
	defer second.mu.Unlock()
	if first.calls != firstCalls || second.calls != secondCalls {
		t.Fatal("positive availability cache unexpectedly re-resolved sources")
	}
}

func TestSearchAvailabilityHidesUnplayableAndCachesNegative(t *testing.T) {
	server := httptest.NewServer(http.NotFoundHandler())
	defer server.Close()
	anime := domain.Anime{ID: "a1", Provider: "animefire", Title: "Unavailable"}
	provider := &availabilityFixtureProvider{name: "animefire", detail: domain.Detail{Episodes: []domain.Episode{{ID: "e1", Provider: "animefire", Season: 1, Number: 1}}}, streams: map[string][]domain.Stream{"e1": {{URL: server.URL + "/404"}}}}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{provider}}, emit: func(string, any) {}, availabilityCache: map[string]availabilityCacheEntry{}}
	result := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}})
	if len(result.Items) != 0 {
		t.Fatalf("unplayable title appeared in search: %+v", result.Items)
	}
	provider.mu.Lock()
	calls := provider.calls
	provider.mu.Unlock()
	_ = s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}})
	provider.mu.Lock()
	defer provider.mu.Unlock()
	if provider.calls != calls {
		t.Fatal("negative cache did not avoid an immediate duplicate check")
	}
}

func TestFirstEpisodeRequiresExplicitUniqueEpisodeOne(t *testing.T) {
	if _, ok := firstEpisode([]domain.Episode{{ID: "e1", Number: 1.5}, {ID: "e2", Number: 2}}); ok {
		t.Fatal("must not infer episode 1 from list position")
	}
	if _, ok := firstEpisode([]domain.Episode{{ID: "a", Season: 1, Number: 1}, {ID: "b", Season: 1, Number: 1}}); ok {
		t.Fatal("ambiguous episode 1 must remain unavailable")
	}
	if got, ok := firstEpisode([]domain.Episode{{ID: "special", Season: 0, Number: 1}, {ID: "episode", Season: 1, Number: 1}, {ID: "season-2", Season: 2, Number: 1}}); !ok || got.ID != "episode" {
		t.Fatalf("expected explicit season 1 episode 1, got %+v (%t)", got, ok)
	}
}

func TestFirstEpisodeUsesRequestedSeason(t *testing.T) {
	episodes := []domain.Episode{
		{ID: "season-1-e1", Season: 1, Number: 1},
		{ID: "season-2-e1", Season: 2, Number: 1},
	}
	if got, ok := firstEpisodeForSeason(episodes, 2); !ok || got.ID != "season-2-e1" {
		t.Fatalf("requested season 2 preflight selected %+v (%t)", got, ok)
	}
	if _, ok := firstEpisodeForSeason(episodes, 3); ok {
		t.Fatal("must not fall back to another season when the requested season is absent")
	}
	if got := sampleEpisodeLabel(2); got != "T2 E1" {
		t.Fatalf("season-specific badge sample=%q, want T2 E1", got)
	}
}

func TestSearchAvailabilityPreflightsAndCachesTheRequestedSeason(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write([]byte("video"))
	}))
	defer server.Close()
	anime := domain.Anime{ID: "series", Provider: "animesonlinecc", Title: "Tensei Shitara Ken Deshita", SearchGroupID: 159042}
	provider := &availabilityFixtureProvider{
		name: "animesonlinecc",
		detail: domain.Detail{Episodes: []domain.Episode{
			{ID: "s1e1", Provider: "animesonlinecc", Season: 1, Number: 1},
			{ID: "s2e1", Provider: "animesonlinecc", Season: 2, Number: 1},
		}},
		streams: map[string][]domain.Stream{
			"s1e1": {{URL: "http://127.0.0.1:1/not-the-requested-season"}},
			"s2e1": {{URL: server.URL + "/s2e1", Qualities: []string{"720p"}}},
		},
	}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{provider}}, emit: func(string, any) {}, availabilityCache: map[string]availabilityCacheEntry{}}
	result := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}}, 2)
	if len(result.Items) != 1 || result.Items[0].Availability == nil || result.Items[0].Availability.SampleEpisode != "T2 E1" {
		t.Fatalf("season 2 should be independently preflighted and labeled: %+v", result.Items)
	}
	if result.Items[0].AniListID != 159042 || result.Items[0].SearchGroupID != 0 {
		t.Fatalf("requested canonical identity should be promoted only after preflight: %+v", result.Items[0])
	}
	if got := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}}, 3); len(got.Items) != 0 {
		t.Fatalf("missing season 3 must not reuse season 2 availability: %+v", got.Items)
	}
	provider.mu.Lock()
	calls := provider.calls
	provider.mu.Unlock()
	second := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}}, 2)
	if len(second.Items) != 1 || second.Items[0].Availability.SampleEpisode != "T2 E1" {
		t.Fatalf("season 2 positive cache was lost: %+v", second.Items)
	}
	provider.mu.Lock()
	defer provider.mu.Unlock()
	if provider.calls != calls {
		t.Fatal("season 2 cache was invalidated by a season 3 lookup")
	}
}

func TestSearchAvailabilityLimitsChecksPerProviderToTwo(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "video/mp4")
		_, _ = w.Write([]byte("video"))
	}))
	defer server.Close()
	anime := domain.Anime{ID: "a0", Provider: "animefire", Title: "Same title"}
	for i := 1; i < 7; i++ {
		anime.Variants = append(anime.Variants, domain.Anime{ID: fmt.Sprintf("a%d", i), Provider: "animefire", Title: "Same title"})
	}
	provider := &availabilityFixtureProvider{name: "animefire", delay: 40 * time.Millisecond, detail: domain.Detail{Episodes: []domain.Episode{{ID: "e1", Provider: "animefire", Season: 1, Number: 1}}}, streams: map[string][]domain.Stream{"e1": {{URL: server.URL + "/media"}}}}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{provider}}, emit: func(string, any) {}, availabilityCache: map[string]availabilityCacheEntry{}}
	result := s.verifySearchAvailability(context.Background(), domain.SearchResult{Items: []domain.Anime{anime}})
	if len(result.Items) != 1 {
		t.Fatalf("expected one checked anime: %+v", result.Items)
	}
	provider.mu.Lock()
	defer provider.mu.Unlock()
	if provider.maxActive > 2 || provider.maxActive < 2 {
		t.Fatalf("provider concurrency was %d; want exactly two overlapping checks", provider.maxActive)
	}
}

func TestSearchAvailabilityCancellationEmitsNoUnverifiedCards(t *testing.T) {
	provider := &availabilityFixtureProvider{name: "animefire", block: true, detail: domain.Detail{Episodes: []domain.Episode{{ID: "e1", Provider: "animefire", Season: 1, Number: 1}}}}
	var events int
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{provider}}, emit: func(name string, _ any) {
		if name == "search-item" {
			events++
		}
	}, availabilityCache: map[string]availabilityCacheEntry{}}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan domain.SearchResult, 1)
	go func() {
		done <- s.verifySearchAvailability(ctx, domain.SearchResult{Items: []domain.Anime{{ID: "a1", Provider: "animefire", Title: "Pending"}}})
	}()
	deadline := time.After(time.Second)
	for {
		provider.mu.Lock()
		calls := provider.calls
		provider.mu.Unlock()
		if calls > 0 {
			break
		}
		select {
		case <-deadline:
			t.Fatal("availability preflight did not start")
		case <-time.After(10 * time.Millisecond):
		}
	}
	cancel()
	select {
	case result := <-done:
		if len(result.Items) != 0 || events != 0 {
			t.Fatalf("cancelled preflight published unverified content: items=%d events=%d", len(result.Items), events)
		}
	case <-time.After(time.Second):
		t.Fatal("availability checks did not stop after cancellation")
	}
}

func TestSearchAvailabilityKeepsVerifiedCardsWhenPageDeadlineExpires(t *testing.T) {
	mediaRequested := make(chan struct{}, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case mediaRequested <- struct{}{}:
		default:
		}
		w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
		if r.URL.Path == "/master.m3u8" {
			_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1800000,RESOLUTION=1280x720\nmedia.m3u8\n"))
			return
		}
		_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nsegment.ts\n#EXT-X-ENDLIST\n"))
	}))
	defer server.Close()

	stalled := &availabilityFixtureProvider{name: "animefire", block: true}
	available := &availabilityFixtureProvider{
		name:    "onlinecc",
		detail:  domain.Detail{Episodes: []domain.Episode{{ID: "available-e1", Provider: "onlinecc", Season: 1, Number: 1}}},
		streams: map[string][]domain.Stream{"available-e1": {{URL: server.URL + "/master.m3u8", Kind: "hls"}}},
	}
	s := &Service{
		catalog:           &providers.Catalog{Providers: []domain.AnimeProvider{stalled, available}},
		availabilityCache: map[string]availabilityCacheEntry{},
	}

	ctx, cancel := context.WithTimeout(context.Background(), 300*time.Millisecond)
	defer cancel()
	result := make(chan domain.SearchResult, 1)
	go func() {
		result <- s.verifySearchAvailability(ctx, domain.SearchResult{Items: []domain.Anime{
			{ID: "slow", Provider: "animefire", Title: "Slow title"},
			{ID: "available", Provider: "onlinecc", Title: "Available title"},
		}})
	}()

	select {
	case <-mediaRequested:
	case <-time.After(time.Second):
		t.Fatal("the available source did not reach media validation")
	}
	select {
	case got := <-result:
		if len(got.Items) != 1 || got.Items[0].Title != "Available title" {
			t.Fatalf("deadline should retain only the already verified card: %+v", got.Items)
		}
		if got.Items[0].Availability == nil || got.Items[0].Availability.MaxHeight != 720 {
			t.Fatalf("verified availability summary was lost at the deadline: %+v", got.Items[0].Availability)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("availability checks did not stop after the page deadline")
	}
}

func TestSearchAvailabilityDoesNotLetOneProviderStarveOthers(t *testing.T) {
	mediaRequested := make(chan struct{}, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case mediaRequested <- struct{}{}:
		default:
		}
		w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
		if r.URL.Path == "/master.m3u8" {
			_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1800000,RESOLUTION=1280x720\nmedia.m3u8\n"))
			return
		}
		_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nsegment.ts\n#EXT-X-ENDLIST\n"))
	}))
	defer server.Close()

	stalled := &availabilityFixtureProvider{name: "animefire", block: true}
	available := &availabilityFixtureProvider{
		name:    "onlinecc",
		detail:  domain.Detail{Episodes: []domain.Episode{{ID: "available-e1", Provider: "onlinecc", Season: 1, Number: 1}}},
		streams: map[string][]domain.Stream{"available-e1": {{URL: server.URL + "/master.m3u8", Kind: "hls"}}},
	}
	items := make([]domain.Anime, 0, 7)
	for i := 0; i < 6; i++ {
		items = append(items, domain.Anime{ID: fmt.Sprintf("slow-%d", i), Provider: "animefire", Title: fmt.Sprintf("Slow title %d", i)})
	}
	items = append(items, domain.Anime{ID: "available", Provider: "onlinecc", Title: "Available title"})
	s := &Service{
		catalog:           &providers.Catalog{Providers: []domain.AnimeProvider{stalled, available}},
		availabilityCache: map[string]availabilityCacheEntry{},
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	result := make(chan domain.SearchResult, 1)
	go func() { result <- s.verifySearchAvailability(ctx, domain.SearchResult{Items: items}) }()

	select {
	case <-mediaRequested:
		// Let HLS validation finish before cancelling the stalled AnimeFire jobs.
		time.Sleep(50 * time.Millisecond)
		cancel()
	case <-time.After(250 * time.Millisecond):
		cancel()
		t.Fatal("six queued jobs from one provider starved the available source")
	}
	select {
	case got := <-result:
		if len(got.Items) != 1 || got.Items[0].Title != "Available title" {
			t.Fatalf("fair scheduling should preserve the available source result: %+v", got.Items)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled source checks did not return promptly")
	}
}

func TestAvailabilitySourceTimeoutStopsAStalledProvider(t *testing.T) {
	previousTimeout := availabilitySourceTimeout
	availabilitySourceTimeout = 40 * time.Millisecond
	defer func() { availabilitySourceTimeout = previousTimeout }()
	provider := &availabilityFixtureProvider{name: "animefire", block: true}
	s := &Service{catalog: &providers.Catalog{Providers: []domain.AnimeProvider{provider}}}
	started := time.Now()
	if _, valid := s.verifySource(context.Background(), domain.Anime{ID: "a1", Provider: "animefire"}, 0); valid {
		t.Fatal("a stalled provider was considered valid")
	}
	if elapsed := time.Since(started); elapsed > time.Second {
		t.Fatalf("source timeout was not enforced: %s", elapsed)
	}
}
