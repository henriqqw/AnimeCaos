package providers

import (
	"context"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
)

// TestLiveProviderPlayerAdAudit checks each registered anime source against a
// real episode. It is opt-in because public catalogs and media hosts change.
func TestLiveProviderPlayerAdAudit(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 to audit the public provider player flows")
	}
	providers := []domain.AnimeProvider{
		NewAnimeFire(netx.New()),
		NewSushiAnimes(netx.New()),
		NewOnlineCC(netx.New()),
		NewOtakulogia(netx.New()),
	}
	providerFilter := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_PROVIDER"))
	query := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_QUERY"))
	if query == "" {
		query = "Hunter x Hunter"
	}
	expected := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_EXPECTED"))
	if expected == "" {
		expected = normalized(query)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 6*time.Minute)
	defer cancel()
	for _, provider := range providers {
		provider := provider
		t.Run(provider.Name(), func(t *testing.T) {
			if providerFilter != "" && !strings.EqualFold(provider.Name(), providerFilter) {
				t.Skip("filtered by ANIMECAOS_LIVE_PROVIDER")
			}
			sourceCtx, sourceCancel := context.WithTimeout(ctx, time.Minute)
			defer sourceCancel()
			result, err := provider.Search(sourceCtx, query, 1)
			if err != nil {
				t.Logf("search unavailable: %v", err)
				return
			}
			var selected domain.Anime
			var firstMatch domain.Anime
			var matchedTitles []string
			for _, candidate := range result.Items {
				if liveResultMatches(candidate, expected, []string{query}) {
					matchedTitles = append(matchedTitles, candidate.Title)
					if firstMatch.ID == "" {
						firstMatch = candidate
					}
					if !strings.Contains(normalized(candidate.Title), "filme") && !strings.Contains(normalized(candidate.Title), "film") {
						selected = candidate
						break
					}
				}
			}
			if selected.ID == "" {
				selected = firstMatch
			}
			if selected.ID == "" {
				t.Logf("search returned %d item(s), no Hunter x Hunter match", len(result.Items))
				return
			}
			t.Logf("catalog matched %q; relevant results=%q", selected.Title, matchedTitles)
			detail, err := provider.Details(sourceCtx, selected)
			if err != nil {
				t.Logf("details unavailable: %v", err)
				return
			}
			if len(detail.Episodes) == 0 {
				t.Log("details returned no episodes")
				return
			}
			episode := detail.Episodes[0]
			for _, candidate := range detail.Episodes {
				if candidate.Number == 1 && (candidate.Season == 0 || candidate.Season == 1) {
					episode = candidate
					break
				}
			}
			t.Logf("player sample: season=%d episode=%g title=%q", episode.Season, episode.Number, episode.Title)
			if provider.Name() == "animesonlinecc" {
				browserCtx, browserCancel := context.WithTimeout(sourceCtx, 15*time.Second)
				candidates, browserErr := renderedPlayerURLs(browserCtx, episode.URL)
				if browserErr != nil {
					t.Logf("direct rendered-page audit: %v", browserErr)
				} else {
					hosts := make([]string, 0, len(candidates))
					for _, candidate := range candidates {
						if parsed, parseErr := url.Parse(candidate.URL); parseErr == nil {
							hosts = append(hosts, parsed.Hostname())
						}
					}
					t.Logf("direct rendered-page audit: %d player candidate(s), hosts=%v", len(candidates), hosts)
				}
				browserCancel()
			}
			streams, err := provider.Resolve(sourceCtx, episode)
			if err != nil {
				t.Logf("player resolution failed closed: %v", err)
				return
			}
			var lastErr error
			for _, stream := range streams {
				parsed, parseErr := url.Parse(stream.URL)
				if parseErr != nil {
					lastErr = parseErr
					continue
				}
				mediaCtx, mediaCancel := context.WithTimeout(sourceCtx, 12*time.Second)
				var mediaErr error
				if stream.Kind == "hls" {
					_, mediaErr = media.Best(mediaCtx, stream)
				} else {
					mediaErr = media.Validate(mediaCtx, stream)
				}
				mediaCancel()
				if mediaErr == nil {
					t.Logf("playable candidate: kind=%s host=%s audio=%s", stream.Kind, parsed.Hostname(), stream.Audio)
					return
				}
				lastErr = mediaErr
				t.Logf("candidate rejected: kind=%s host=%s reason=%v", stream.Kind, parsed.Hostname(), mediaErr)
			}
			if lastErr == nil {
				lastErr = err
			}
			t.Logf("no candidate passed media validation: %v", lastErr)
		})
		if ctx.Err() != nil {
			t.Fatalf("audit time budget expired after source %q: %v", provider.Name(), ctx.Err())
		}
	}
}
