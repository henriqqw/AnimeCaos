package providers

import (
	"context"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
)

func TestLiveCatalogSearchAndEpisodeGroups(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real catalog checks")
	}
	checks := []struct {
		label, expected string
		queries         []string
	}{
		{"Demon Slayer", "kimetsu", []string{"Demon Slayer", "Kimetsu no Yaiba"}},
		{"Frieren", "frieren", []string{"Sousou no Frieren", "Frieren: Beyond Journey's End"}},
		{"Solo Leveling", "solo leveling", []string{"Solo Leveling", "Ore dake Level Up na Ken"}},
		{"Jujutsu Kaisen", "jujutsu kaisen", []string{"Jujutsu Kaisen"}},
		{"One Piece", "one piece", []string{"One Piece"}},
		{"Hunter x Hunter", "hunter x hunter", []string{"Hunter x Hunter"}},
		{"Naruto", "naruto", []string{"Naruto Shippuden", "Naruto"}},
		{"Death Note", "death note", []string{"Death Note"}},
		{"Boruto", "boruto", []string{"Boruto: Naruto Next Generations", "Boruto"}},
		{"Chainsaw Man", "chainsaw man", []string{"Chainsaw Man"}},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Minute)
	defer cancel()
	client := netx.New()
	providers := []domain.AnimeProvider{NewAnimeFire(client), NewOnlineCC(client)}
	if only := strings.TrimSpace(os.Getenv("ANIMECAOS_LIVE_TITLE")); only != "" {
		filtered := checks[:0]
		for _, check := range checks {
			if strings.EqualFold(check.label, only) {
				filtered = append(filtered, check)
			}
		}
		checks = filtered
		if len(checks) == 0 {
			t.Fatalf("unknown live title %q", only)
		}
	}
	for _, check := range checks {
		check := check
		for _, provider := range providers {
			provider := provider
			t.Run(check.label+"/"+provider.Name(), func(t *testing.T) {
				var selected domain.Anime
				for _, query := range check.queries {
					result, err := provider.Search(ctx, query, 1)
					if err != nil {
						t.Logf("query %q failed: %v", query, err)
						continue
					}
					for _, item := range result.Items {
						if liveResultMatches(item, check.expected, check.queries) {
							selected = item
							break
						}
					}
					if selected.ID != "" {
						break
					}
				}
				if selected.ID == "" {
					t.Fatalf("no relevant result found for %s", check.label)
				}
				detail, err := provider.Details(ctx, selected)
				if err != nil {
					t.Fatal(err)
				}
				if len(detail.Episodes) == 0 {
					t.Fatal("details had no episodes")
				}
				if provider.Name() == "animesonlinecc" {
					browserCtx, browserCancel := context.WithTimeout(ctx, 35*time.Second)
					rendered, browserErr := renderedPlayerURLs(browserCtx, detail.Episodes[0].URL)
					checked := false
					if browserErr != nil {
						t.Logf("headless browser could not read rendered player on live episode page: %v", browserErr)
					} else {
						t.Logf("headless browser rendered %d player source(s) on the live episode page", len(rendered))
						for _, raw := range rendered {
							playerURL := scrapedHTTPURL(detail.Episodes[0].URL, raw.URL)
							if playerURL == "" {
								continue
							}
							referer := playerReferer(detail.Episodes[0].URL, playerURL, raw.ReferrerPolicy, detail.Episodes[0].URL)
							streams, resolveErr := NewOnlineCC(client).resolvePage(browserCtx, playerURL, referer, 0)
							if resolveErr != nil {
								t.Logf("rendered player candidate did not resolve: %v", resolveErr)
								continue
							}
							for _, stream := range streams {
								if stream.Kind == "hls" {
									_, resolveErr = media.Best(browserCtx, stream)
								} else {
									resolveErr = media.Validate(browserCtx, stream)
								}
								if resolveErr == nil {
									t.Logf("rendered player candidate returned accessible %s media", stream.Kind)
									checked = true
									break
								}
							}
							if checked {
								break
							}
						}
					}
					if len(rendered) > 0 && !checked {
						t.Log("headless browser sources did not yield an accessible media stream")
					}
					browserCancel()
				}
				// A URL from the catalog is only a candidate. Read its HLS manifest
				// (or validate a direct file) before calling the episode playable.
				resolvedURL, playable := false, false
				var lastMediaErr error
				for _, i := range mediaProbeIndexes(len(detail.Episodes)) {
					streamCtx, streamCancel := context.WithTimeout(ctx, 25*time.Second)
					streams, resolveErr := provider.Resolve(streamCtx, detail.Episodes[i])
					if resolveErr != nil {
						t.Logf("episode %v URL resolution failed: %v", detail.Episodes[i].Number, resolveErr)
						lastMediaErr = resolveErr
						streamCancel()
						continue
					}
					for _, stream := range streams {
						if strings.TrimSpace(stream.URL) == "" {
							continue
						}
						resolvedURL = true
						var checkErr error
						if stream.Kind == "hls" {
							_, checkErr = media.Best(streamCtx, stream)
						} else {
							checkErr = media.Validate(streamCtx, stream)
						}
						if checkErr != nil {
							t.Logf("episode %v URL returned but media check failed: %v", detail.Episodes[i].Number, checkErr)
							lastMediaErr = checkErr
							continue
						}
						t.Logf("playable episode found: number=%v kind=%s audio=%s", detail.Episodes[i].Number, stream.Kind, stream.Audio)
						playable = true
						break
					}
					streamCancel()
					if playable {
						break
					}
				}
				if !resolvedURL {
					t.Errorf("no media URL found in %d sampled entries", len(mediaProbeIndexes(len(detail.Episodes))))
				} else if !playable {
					t.Errorf("provider returned URLs, but none of %d sampled episodes had accessible media: %v", len(mediaProbeIndexes(len(detail.Episodes))), lastMediaErr)
				}
				seasons, ids, audio := map[int]bool{}, map[string]bool{}, map[string]bool{}
				for _, episode := range detail.Episodes {
					if episode.ID == "" {
						t.Fatal("episode without stable ID")
					}
					if ids[episode.ID] {
						t.Fatalf("duplicate episode ID %q", episode.ID)
					}
					ids[episode.ID] = true
					if episode.Season > 0 {
						seasons[episode.Season] = true
					}
					if episode.Audio != "" {
						audio[episode.Audio] = true
					}
				}
				t.Logf("%s: %d episodes, %d explicit seasons, audio labels=%v", selected.Title, len(detail.Episodes), len(seasons), audio)
			})
		}
	}
}

func liveResultMatches(item domain.Anime, expected string, queries []string) bool {
	wanted := append([]string{expected}, queries...)
	titles := append([]string{item.Title}, item.Titles...)
	for _, title := range titles {
		got := normalized(title)
		for _, candidate := range wanted {
			want := normalized(candidate)
			if want != "" && (got == want || strings.HasPrefix(got, want)) {
				return true
			}
		}
	}
	return false
}

// mediaProbeIndexes checks the first few episodes plus the middle and latest
// entries. Some sources temporarily keep only recent media online.
func mediaProbeIndexes(count int) []int {
	if count <= 0 {
		return nil
	}
	seen := map[int]bool{}
	indexes := make([]int, 0, min(count, 7))
	appendIndex := func(i int) {
		if i >= 0 && i < count && !seen[i] {
			seen[i] = true
			indexes = append(indexes, i)
		}
	}
	for i := 0; i < min(5, count); i++ {
		appendIndex(i)
	}
	appendIndex(count / 2)
	appendIndex(count - 1)
	return indexes
}
