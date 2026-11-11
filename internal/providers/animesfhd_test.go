package providers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

func fhdFixture(t *testing.T, name string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", "animesfhd", name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	if !json.Valid(b) {
		t.Fatalf("invalid JSON or BOM in fixture %s", name)
	}
	return b
}

func fhdServer(t *testing.T, handler http.HandlerFunc) string {
	t.Helper()
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.Header.Get("Referer") != "https://animesfhd.net/" || !strings.Contains(r.Header.Get("User-Agent"), "Mozilla/5.0") {
			t.Errorf("missing GET/browser headers: %s %v", r.Method, r.Header)
		}
		handler(w, r)
	}))
	t.Cleanup(s.Close)
	return s.URL
}

func TestAnimesFHDSearchOneRequest(t *testing.T) {
	for _, tc := range []struct {
		name, query, fixture string
		page, count          int
		hasNext              bool
	}{
		{"query", "  ação & frieren  ", "busca-frieren", 0, 1, false},
		{"popular", "  ", "populares", 2, 5, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			fixture := fhdFixture(t, tc.fixture)
			var calls atomic.Int32
			base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
				calls.Add(1)
				q := r.URL.Query()
				if r.URL.Path != "/api/series" || q.Get("pagination") != "1" || q.Get("per_page") != "24" || q.Get("page") != fmt.Sprint(max(1, tc.page)) || q.Get("q") != strings.TrimSpace(tc.query) {
					t.Errorf("unexpected search request %s", r.URL)
				}
				if strings.TrimSpace(tc.query) == "" && q.Get("sort") != "popular" {
					t.Error("empty search must request popular titles")
				}
				w.Write(fixture)
			})
			p := NewAnimesFHD(netx.New())
			p.Base = base
			result, err := p.Search(context.Background(), tc.query, tc.page)
			if err != nil || len(result.Items) != tc.count || result.HasNext != tc.hasNext || result.Page != max(1, tc.page) || calls.Load() != 1 {
				t.Fatalf("search: %+v, calls=%d, error=%v", result, calls.Load(), err)
			}
			if p.Name() != "animesfhd" || result.Items[0].Provider != p.Name() {
				t.Fatal("unstable provider identity")
			}
			if tc.name == "query" {
				a := result.Items[0]
				if a.ID != "2751618645542326" || a.Title != "Sousou no Frieren" || len(a.Titles) != 3 || a.Year != 2023 || a.EpisodeCount != 38 || a.URL != base+"/serie/"+a.ID || a.Cover == "" || a.Banner == "" || !strings.Contains(a.Audio, "dublado") || !strings.Contains(a.Audio, "legendado") {
					t.Fatalf("metadata lost: %+v", a)
				}
			}
		})
	}
}

func TestAnimesFHDRealDetailsAndSources(t *testing.T) {
	for _, tc := range []struct {
		series, episode, details, sources, format, route string
		count                                            int
	}{
		{"1709160706373932", "22882", "serie-1709160706373932", "episodio-22882", "tv", "/api/v/s6?source=2016384480747057&playlist=.m3u8", 6},
		{"2110072639862535", "1049086484300956", "serie-filme-2110072639862535", "episodio-filme-1049086484300956", "movie", "/api/v/s4?source=2591675809550102&playlist=.m3u8", 1},
	} {
		t.Run(tc.format, func(t *testing.T) {
			details, sources := fhdFixture(t, tc.details), fhdFixture(t, tc.sources)
			base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
				switch r.URL.Path {
				case "/api/series/" + tc.series:
					if r.URL.Query().Get("page") != "1" || r.URL.Query().Get("per_page") != "200" {
						t.Errorf("episode pagination: %s", r.URL)
					}
					w.Write(details)
				case "/api/episodes/" + tc.episode:
					w.Write(sources)
				default:
					t.Errorf("unexpected request %s", r.URL)
					http.NotFound(w, r)
				}
			})
			p := NewAnimesFHD(netx.New())
			p.Base = base
			d, err := p.Details(context.Background(), domain.Anime{ID: tc.series})
			if err != nil || len(d.Episodes) != tc.count || d.Anime.EpisodeCount != tc.count || d.Anime.Format != tc.format {
				t.Fatalf("details: %+v %v", d, err)
			}
			ep := d.Episodes[0]
			if ep.ID != tc.episode || ep.Number != 1 || ep.Season != 1 || ep.Audio != "legendado" || ep.AnimeID != tc.series || ep.URL != base+"/episod/"+tc.episode {
				t.Fatalf("episode identity: %+v", ep)
			}
			streams, err := p.Resolve(context.Background(), ep)
			if err != nil || len(streams) != 1 || streams[0].Kind != "hls" || streams[0].URL != base+tc.route || streams[0].Audio != "legendado" || streams[0].Headers["Referer"] != "https://animesfhd.net/" || streams[0].Headers["User-Agent"] == "" {
				t.Fatalf("streams: %+v %v", streams, err)
			}
		})
	}
}

func TestAnimesFHDVersionsAndPagination(t *testing.T) {
	var calls atomic.Int32
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		switch r.URL.Path + "?page=" + r.URL.Query().Get("page") {
		case "/api/series/10?page=1":
			fmt.Fprint(w, `{"series":{"id":10,"title":"Obra","category":"legendado"},"seo":{"season":1},"versions":[{"series_id":10,"season":1,"audio":"legendado"},{"series_id":20,"series_ids":[20,21],"season":2,"audio":"dublado"},{"series_id":20,"season":2,"audio":"dublado"}],"episodes":[{"id":102,"episode_number":2}],"has_more":true,"related":[{"id":999}]}`)
		case "/api/series/10?page=2":
			fmt.Fprint(w, `{"series":{"id":10,"title":"Obra"},"episodes":[{"id":101,"episode_number":1},{"id":102,"episode_number":2}],"has_more":false}`)
		case "/api/series/20?page=1":
			fmt.Fprint(w, `{"series":{"id":20,"title":"Obra T2"},"episodes":[{"id":201,"episode_number":1},{"id":202,"episode_number":1.5},{"id":203,"episode_number":2}],"versions":[{"series_id":999,"season":9}]}`)
		case "/api/episodes/201?page=":
			fmt.Fprint(w, `{"episode":{"id":201,"series_id":21,"episode_number":1},"versions":[{"series_id":21,"series_ids":[20,21],"season":2,"audio":"dublado"}],"sources":[{"url":"/api/v/s6?source=1&playlist=.m3u8","native_video":true,"audio":"dublado"}]}`)
		default:
			t.Errorf("unexpected version request %s", r.URL)
			http.NotFound(w, r)
		}
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	d, err := p.Details(context.Background(), domain.Anime{ID: "10"})
	if err != nil || len(d.Episodes) != 5 || calls.Load() != 3 {
		t.Fatalf("versions: %+v calls=%d error=%v", d, calls.Load(), err)
	}
	for i, id := range []string{"101", "102", "201", "202", "203"} {
		if d.Episodes[i].ID != id {
			t.Fatalf("order or identity lost: %+v", d.Episodes)
		}
	}
	if d.Episodes[2].AnimeID != "20" || d.Episodes[2].Season != 2 || d.Episodes[2].Audio != "dublado" || d.Episodes[3].Number != 1.5 || d.Episodes[4].AnimeID != "20" {
		t.Fatalf("season/audio/number lost: %+v", d.Episodes)
	}
	streams, err := p.Resolve(context.Background(), d.Episodes[2])
	if err != nil || len(streams) != 1 || calls.Load() != 4 {
		t.Fatalf("episode owned by a confirmed copy: %+v %v", streams, err)
	}
}

func TestAnimesFHDAudioVariantsDoNotRepeatEpisodes(t *testing.T) {
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/series/10":
			fmt.Fprint(w, `{"series":{"id":10,"title":"Obra"},"versions":[{"series_id":10,"season":1,"audio":"legendado"},{"series_id":20,"season":1,"audio":"dublado"}],"episodes":[{"id":101,"episode_number":1},{"id":102,"episode_number":2}]}`)
		case "/api/series/20":
			fmt.Fprint(w, `{"series":{"id":20,"title":"Obra Dublado"},"episodes":[{"id":201,"episode_number":1}]}`)
		case "/api/episodes/101":
			fmt.Fprint(w, `{"episode":{"id":101,"series_id":10,"episode_number":1},"versions":[{"series_id":10,"season":1,"part":0,"audio":"legendado","episode_id":101},{"series_id":20,"season":1,"part":0,"audio":"dublado","episode_id":201},{"series_id":30,"season":2,"audio":"dublado","episode_id":301},{"series_id":40,"season":1,"part":2,"audio":"dublado","episode_id":401}],"sources":[{"url":"/leg.m3u8","native_video":true,"audio":"legendado"}]}`)
		case "/api/episodes/201":
			fmt.Fprint(w, `{"episode":{"id":201,"series_id":20,"episode_number":1},"sources":[{"url":"/dub.m3u8","native_video":true,"audio":"dublado"}]}`)
		default:
			t.Errorf("unrelated season/part requested: %s", r.URL)
			http.NotFound(w, r)
		}
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	d, err := p.Details(context.Background(), domain.Anime{ID: "10"})
	if err != nil || len(d.Episodes) != 2 || d.Anime.EpisodeCount != 2 || d.Episodes[0].ID != "101" || d.Episodes[1].ID != "102" {
		t.Fatalf("autoplay would repeat an audio variant: %+v %v", d, err)
	}
	streams, err := p.Resolve(context.Background(), d.Episodes[0])
	if err != nil || len(streams) != 2 || streams[0].Audio != "legendado" || streams[1].Audio != "dublado" {
		t.Fatalf("audio options lost: %+v %v", streams, err)
	}
}

func TestAnimesFHDDoesNotInferEpisodeIdentity(t *testing.T) {
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, `{"series":{"id":10,"title":"Obra"},"episodes":[{"id":1,"title":"Final"},{"id":2,"episode_number":0}]}`)
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	d, err := p.Details(context.Background(), domain.Anime{ID: "10"})
	if err != nil || len(d.Episodes) != 2 {
		t.Fatalf("details: %+v %v", d, err)
	}
	for _, ep := range d.Episodes {
		if ep.Number != 0 || ep.Season != 0 || ep.Audio != "" {
			t.Fatalf("invented episode metadata: %+v", ep)
		}
	}
}

func TestAnimesFHDRejectsOverlappingParts(t *testing.T) {
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/series/10" {
			fmt.Fprint(w, `{"series":{"id":10,"title":"Obra"},"versions":[{"series_id":10,"season":1,"part":1},{"series_id":20,"season":1,"part":2}],"episodes":[{"id":101,"episode_number":1}]}`)
		} else {
			fmt.Fprint(w, `{"series":{"id":20,"title":"Obra Parte 2"},"episodes":[{"id":201,"episode_number":1}]}`)
		}
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	_, err := p.Details(context.Background(), domain.Anime{ID: "10"})
	if err == nil || !strings.Contains(err.Error(), "partes") {
		t.Fatalf("overlapping parts must not become the same episode: %v", err)
	}
}

func TestAnimesFHDAlternateAudioFailureKeepsPrimary(t *testing.T) {
	for _, alternate := range []string{
		`{"episode":{"id":201,"series_id":20,"episode_number":2},"sources":[{"url":"/wrong.m3u8","native_video":true}]}`,
		`{"episode":{"id":201,"series_id":99,"episode_number":1},"sources":[{"url":"/wrong.m3u8","native_video":true}]}`,
		`{"episode":{"id":999,"series_id":20,"episode_number":1},"sources":[{"url":"/wrong.m3u8","native_video":true}]}`,
		`unavailable`,
	} {
		t.Run(alternate, func(t *testing.T) {
			base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/api/episodes/101" {
					fmt.Fprint(w, `{"episode":{"id":101,"series_id":10,"episode_number":1},"versions":[{"series_id":10,"season":1,"audio":"legendado","episode_id":101},{"series_id":20,"season":1,"audio":"dublado","episode_id":201}],"sources":[{"url":"/leg.m3u8","native_video":true}]}`)
				} else if alternate == "unavailable" {
					http.NotFound(w, r)
				} else {
					fmt.Fprint(w, alternate)
				}
			})
			p := NewAnimesFHD(netx.New())
			p.Base = base
			streams, err := p.Resolve(context.Background(), domain.Episode{ID: "101", AnimeID: "10", Number: 1})
			if err != nil || len(streams) != 1 || streams[0].Audio != "legendado" || streams[0].URL != base+"/leg.m3u8" {
				t.Fatalf("wrong alternate accepted or primary hidden: %+v %v", streams, err)
			}
		})
	}
}

func TestAnimesFHDNativeFilteringAndRedirects(t *testing.T) {
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/episodes/1":
			fmt.Fprint(w, `{"episode":{"id":1,"series_id":10},"sources":[{"url":"/embed","kind":"embed","native_video":true},{"url":"/not-native","kind":"file"},{"url":"javascript:alert(1)","native_video":true},{"url":"/hls","media_kind":"s6","native_video":true,"audio":"legendado"},{"url":"/hls","media_kind":"s6","native_video":true,"audio":"legendado"},{"url":"/api/v/s5?source=1","native_video":true,"audio":"dublado"},{"url":"/api/v/s5?source=2","native_video":true,"audio":"legendado"},{"url":"/dead","native_video":true}]}`)
		case "/api/v/s5":
			http.Redirect(w, r, "/media/"+r.URL.Query().Get("source"), http.StatusTemporaryRedirect)
		case "/media/1":
			if r.Header.Get("Range") == "" {
				t.Error("media probe must use Range")
			}
			w.Header().Set("Content-Type", "video/mp4")
			fmt.Fprint(w, "\x00\x00\x00\x18ftypisom")
		case "/media/2":
			w.Header().Set("Content-Type", "application/octet-stream")
			fmt.Fprint(w, "#EXTM3U\n#EXTINF:10,\nsegment.ts\n")
		case "/dead":
			http.NotFound(w, r)
		default:
			t.Errorf("embed, known HLS or invalid URL fetched: %s", r.URL)
			http.NotFound(w, r)
		}
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	streams, err := p.Resolve(context.Background(), domain.Episode{ID: "1", AnimeID: "10"})
	if err != nil || len(streams) != 3 || streams[0].Kind != "hls" || streams[1].Kind != "file" || streams[2].Kind != "hls" || streams[1].Audio != "dublado" || streams[1].URL != base+"/api/v/s5?source=1" {
		t.Fatalf("native streams/redirects: %+v %v", streams, err)
	}
}

func TestAnimesFHDFailures(t *testing.T) {
	for _, tc := range []struct {
		name, operation, body string
		status                int
	}{
		{"http search", "search", `{}`, 403},
		{"invalid JSON", "search", `<html>error</html>`, 200},
		{"missing search envelope", "search", `{}`, 200},
		{"missing series", "details", `{}`, 200},
		{"wrong series", "details", `{"series":{"id":11,"title":"Outra"}}`, 200},
		{"stalled pagination", "details", `{"series":{"id":10,"title":"Obra"},"episodes":[{"id":1,"episode_number":1}],"has_more":true}`, 200},
		{"wrong episode", "resolve", `{"episode":{"id":2},"sources":[]}`, 200},
		{"wrong parent", "resolve", `{"episode":{"id":1,"series_id":11},"sources":[]}`, 200},
		{"missing owner", "resolve", `{"episode":{"id":1},"versions":[{"series_ids":[10]}],"sources":[{"url":"/video.m3u8","native_video":true}]}`, 200},
		{"unavailable", "resolve", `{"episode":{"id":1,"series_id":10},"sources":[{"kind":"embed","url":"/embed","native_video":true}]}`, 200},
	} {
		t.Run(tc.name, func(t *testing.T) {
			base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(tc.status)
				fmt.Fprint(w, tc.body)
			})
			p := NewAnimesFHD(netx.New())
			p.Base = base
			var err error
			switch tc.operation {
			case "search":
				_, err = p.Search(context.Background(), "test", 1)
			case "details":
				_, err = p.Details(context.Background(), domain.Anime{ID: "10"})
			case "resolve":
				_, err = p.Resolve(context.Background(), domain.Episode{ID: "1", AnimeID: "10"})
			}
			if err == nil {
				t.Fatal("expected source error")
			}
		})
	}
}

func TestAnimesFHDCancellationAndRecovery(t *testing.T) {
	base := fhdServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("q") == "fast" {
			fmt.Fprint(w, `{"series":[],"has_more":false}`)
			return
		}
		<-r.Context().Done()
	})
	p := NewAnimesFHD(netx.New())
	p.Base = base
	for _, operation := range []string{"search", "details", "resolve"} {
		t.Run(operation, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
			defer cancel()
			var err error
			switch operation {
			case "search":
				_, err = p.Search(ctx, "slow", 1)
			case "details":
				_, err = p.Details(ctx, domain.Anime{ID: "10"})
			case "resolve":
				_, err = p.Resolve(ctx, domain.Episode{ID: "1"})
			}
			if !errors.Is(err, context.DeadlineExceeded) {
				t.Fatalf("cancellation not propagated: %v", err)
			}
		})
	}
	r, err := p.Search(context.Background(), "fast", 1)
	if err != nil || len(r.Items) != 0 || r.HasNext {
		t.Fatalf("recovery: %+v %v", r, err)
	}
}

func TestLiveAnimesFHD(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real source checks")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	p := NewAnimesFHD(netx.New())
	r, err := p.Search(ctx, "frieren", 1)
	if err != nil || len(r.Items) == 0 {
		t.Fatalf("search: %v", err)
	}
	d, err := p.Details(ctx, r.Items[0])
	if err != nil || len(d.Episodes) == 0 {
		t.Fatalf("details: %v", err)
	}
	streams, err := p.Resolve(ctx, d.Episodes[0])
	if err != nil || len(streams) == 0 {
		t.Fatalf("resolve: %v", err)
	}
	t.Logf("%d episodes, %d native streams; playback requires separate validation", len(d.Episodes), len(streams))
}
