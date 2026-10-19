package providers

import (
	"context"
	"html"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

func TestSushiSearchDetailsAndResolve(t *testing.T) {
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/search/Naruto":
			_, _ = w.Write([]byte(`<div class="list-item"><a class="list-title" href="/anime/naruto">Naruto Shippuden (Dublado)</a><img data-src="/cover.jpg"></div><div class="pagination"><a class="next" href="/search/Naruto/2">Next</a></div>`))
		case r.Method == http.MethodGet && r.URL.Path == "/anime/naruto":
			_, _ = w.Write([]byte(`<h1>Naruto Shippuden</h1><button data-bs-target="#season-1">Temporada 1</button><div class="tab-pane" id="season-1"><a class="epx-card" href="/anime/naruto-1-season-1-episode"><span>Continuar</span><span>1º Episódio</span><span class="epx-title">Voltando Para Casa</span></a></div>`))
		case r.Method == http.MethodGet && r.URL.Path == "/anime/naruto-1-season-1-episode":
			_, _ = w.Write([]byte(`<button class="btn-service selected" data-id="71" data-player-name="Dublado"></button>`))
		case r.Method == http.MethodPost && r.URL.Path == "/ajax/embed":
			if err := r.ParseForm(); err != nil || r.Form.Get("id") != "71" {
				http.Error(w, "bad embed request", http.StatusBadRequest)
				return
			}
			response := `<iframe srcdoc="` + html.EscapeString(`<script>var playerEmbed="https://cdn.example.test/episode/index.m3u8";</script>`) + `"></iframe>`
			_, _ = w.Write([]byte(response))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	p := NewSushiAnimes(netx.New())
	p.Base = server.URL

	search, err := p.Search(context.Background(), "Naruto", 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(search.Items) != 1 || !search.HasNext || search.Items[0].Cover != server.URL+"/cover.jpg" {
		t.Fatalf("unexpected search result: %+v", search)
	}
	detail, err := p.Details(context.Background(), search.Items[0])
	if err != nil {
		t.Fatal(err)
	}
	if len(detail.Episodes) != 1 || detail.Episodes[0].Season != 1 || detail.Episodes[0].Number != 1 || detail.Episodes[0].Title != "Voltando Para Casa" {
		t.Fatalf("unexpected details: %+v", detail.Episodes)
	}
	streams, err := p.Resolve(context.Background(), detail.Episodes[0])
	if err != nil {
		t.Fatal(err)
	}
	if len(streams) != 1 || streams[0].URL != "https://cdn.example.test/episode/index.m3u8" || streams[0].Kind != "hls" || streams[0].Audio != "dublado" {
		t.Fatalf("unexpected streams: %+v", streams)
	}
}

func TestSushiResolveFallsBackToScopedEmbeddedPlayer(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/episode/one":
			_, _ = w.Write([]byte(`<div class="player-container"><iframe src="/embed/one"></iframe></div>`))
		case "/embed/one":
			w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
			_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-ENDLIST\n"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	p := NewSushiAnimes(netx.New())
	p.Base = server.URL
	streams, err := p.Resolve(context.Background(), domain.Episode{ID: "episode-one", URL: server.URL + "/episode/one", Audio: "legendado"})
	if err != nil {
		t.Fatal(err)
	}
	if len(streams) != 1 || streams[0].Kind != "hls" || streams[0].Audio != "legendado" {
		t.Fatalf("unexpected embedded-player fallback: %+v", streams)
	}
}

func TestSushiRejectsNonHTTPMediaAndMalformedEpisodeURL(t *testing.T) {
	p := NewSushiAnimes(netx.New())
	if got := scrapedHTTPURL(p.Base, "javascript:alert(1)"); got != "" {
		t.Fatalf("accepted non-HTTP player URL %q", got)
	}
	if match := sushiEpisodePathRE.FindStringSubmatch("/anime/naruto-1-season-x-episode"); len(match) != 0 {
		t.Fatalf("accepted malformed episode URL: %v", match)
	}
	if strings.TrimSpace(sushiEpisodeLabelRE.ReplaceAllString("Continuar 1º Episódio Voltando Para Casa", "")) != "Voltando Para Casa" {
		t.Fatal("episode label cleanup changed")
	}
}
