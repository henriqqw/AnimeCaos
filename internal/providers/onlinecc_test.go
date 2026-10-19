package providers

import (
	"context"
	"html"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

func TestOnlineCCDetailsUsesExplicitSeasonAndEpisodeNumbers(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`<h1>Jujutsu Kaisen</h1><div class="se-c"><div class="se-q"><span class="se-t">3</span><span class="title">Temporada 3</span></div><div class="se-a"><ul class="episodios"><li><div class="numerando">Ep - 7</div><div class="episodiotitle"><a href="/ep/7">Episodio 7</a></div></li></ul></div></div>`))
	}))
	defer server.Close()
	p := NewOnlineCC(netx.New())
	p.Base = server.URL
	detail, err := p.Details(context.Background(), domain.Anime{ID: "jjk", Provider: p.Name(), URL: server.URL + "/anime/jjk"})
	if err != nil {
		t.Fatal(err)
	}
	if len(detail.Episodes) != 1 {
		t.Fatalf("got %d episodes", len(detail.Episodes))
	}
	if detail.Episodes[0].Season != 3 || detail.Episodes[0].Number != 7 {
		t.Fatalf("unexpected source numbering: %+v", detail.Episodes[0])
	}
}

func TestOnlineCCDoesNotInventSeasonOrEpisodeNumbers(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`<h1>Unknown grouping</h1><ul class="episodios"><li><div class="episodiotitle"><a href="/ep/x">Special</a></div></li></ul>`))
	}))
	defer server.Close()
	p := NewOnlineCC(netx.New())
	p.Base = server.URL
	detail, err := p.Details(context.Background(), domain.Anime{ID: "special", Provider: p.Name(), URL: server.URL + "/anime/special"})
	if err != nil {
		t.Fatal(err)
	}
	if detail.Episodes[0].Season != 0 || detail.Episodes[0].Number != 0 {
		t.Fatalf("parser invented episode identity: %+v", detail.Episodes[0])
	}
}

func TestOnlineCCSearchSupportsCardMarkupVariants(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`<div class="items"><article><div class="data"><h3><a href="/anime/frieren">Sousou no Frieren</a></h3></div><img data-src="/covers/frieren.jpg"></article><div class="item"><a class="series" href="/anime/solo">Solo Leveling</a><img src="/covers/solo.jpg"></div></div><a class="next" href="/page/2">Next</a>`))
	}))
	defer server.Close()
	p := NewOnlineCC(netx.New())
	p.Base = server.URL
	result, err := p.Search(context.Background(), "frieren", 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Items) != 2 || !result.HasNext {
		t.Fatalf("unexpected search: %+v", result)
	}
	if result.Items[0].Cover == "" || result.Items[1].Cover == "" {
		t.Fatalf("cover URLs not resolved: %+v", result.Items)
	}
}

func TestOnlineCCResolveReturnsAudioPlayerOptions(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/ep/1":
			w.Write([]byte(`<nav class="player"><ul class="options"><li><ul class="idTabs sourceslist"><li><a href="#option-1">Dublado</a></li><li><a href="#option-2">Legendado</a></li></ul></li></ul></nav><div id="option-1"><iframe src="/dub"></iframe></div><div id="option-2"><iframe src="/sub"></iframe></div>`))
		case "/dub", "/sub":
			w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
			w.Write([]byte("#EXTM3U\n#EXT-X-ENDLIST\n"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	p := NewOnlineCC(netx.New())
	p.Base = server.URL
	streams, err := p.Resolve(context.Background(), domain.Episode{ID: "ep1", URL: server.URL + "/ep/1"})
	if err != nil {
		t.Fatal(err)
	}
	if len(streams) != 2 || streams[0].Audio != "dublado" || streams[1].Audio != "legendado" {
		t.Fatalf("audio options not preserved: %+v", streams)
	}
}

func TestOnlineCCResolveHonorsIframeNoReferrerPolicy(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/ep/1":
			_, _ = w.Write([]byte(`<ul class="sourceslist"><li><a href="#option-1">Legendado</a></li></ul><div id="option-1"><iframe src="/embed" referrerpolicy="no-referrer"></iframe></div>`))
		case "/embed":
			if got := r.Header.Get("Referer"); got != "" {
				t.Errorf("no-referrer iframe sent Referer %q", got)
			}
			w.Header().Set("Content-Type", "application/vnd.apple.mpegurl")
			_, _ = w.Write([]byte("#EXTM3U\n#EXT-X-ENDLIST\n"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	p := NewOnlineCC(netx.New())
	p.Base = server.URL
	streams, err := p.Resolve(context.Background(), domain.Episode{ID: "ep1", URL: server.URL + "/ep/1"})
	if err != nil {
		t.Fatal(err)
	}
	if len(streams) != 1 || streams[0].Kind != "hls" {
		t.Fatalf("unexpected no-referrer stream result: %+v", streams)
	}
}

func TestAnidriveEmbedUsesBrowserFetchMetadata(t *testing.T) {
	got := playerRequestHeaders("https://anidrive.click/token/example", "https://animesonline.io/17864/")
	if got["Referer"] != "https://animesonline.io/17864/" ||
		got["User-Agent"] != anidriveBrowserUA ||
		got["Accept"] == "" ||
		got["Sec-Fetch-Dest"] != "iframe" ||
		got["Sec-Fetch-Mode"] != "navigate" ||
		got["Sec-Fetch-Site"] != "cross-site" {
		t.Fatalf("Anidrive request metadata = %#v", got)
	}
	if unrelated := playerRequestHeaders("https://player.example/embed", "https://animesonline.io/17864/"); len(unrelated) != 1 {
		t.Fatalf("unrelated player received browser metadata: %#v", unrelated)
	}
}

func TestAnidriveMediaURLIsRecognizedFromEmbedReferer(t *testing.T) {
	got := anidriveMediaHeaders("https://cdn.videocdn.example/video.mp4", "https://anidrive.click/embed/1")
	if got["User-Agent"] != anidriveBrowserUA || got["Referer"] != "https://anidrive.click/embed/1" {
		t.Fatalf("Anidrive media headers = %#v", got)
	}
	unrelated := anidriveMediaHeaders("https://video.example/video.mp4", "https://anime.example/episode/1")
	if len(unrelated) != 1 || unrelated["User-Agent"] != "" {
		t.Fatalf("unrelated media received browser metadata: %#v", unrelated)
	}
}

func TestOnlineCCSkipsStaticAssetsExtractedFromPlayerScripts(t *testing.T) {
	for _, raw := range []string{
		"https://player.example/loading.gif",
		"https://player.example/poster.webp",
		"https://player.example/player.css",
		"https://player.example/player.js",
	} {
		if !isStaticPlayerAsset(raw) {
			t.Errorf("static player asset was retained as a media candidate: %s", raw)
		}
	}
	for _, raw := range []string{
		"https://video.example/stream.m3u8",
		"https://video.example/stream.mp4",
		"https://video.example/token/abc123",
	} {
		if isStaticPlayerAsset(raw) {
			t.Errorf("media candidate was filtered as a static asset: %s", raw)
		}
	}
}

func TestLiveAnidrivePlayerPage(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("defina ANIMECAOS_LIVE=1 para consultar o player público")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	client := netx.New()
	episodeURL := "https://animesonline.io/17864/"
	r, err := client.Do(ctx, http.MethodGet, episodeURL, nil, map[string]string{
		"User-Agent": anidriveBrowserUA,
		"Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	})
	if err != nil {
		t.Fatal(err)
	}
	page, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	r.Body.Close()
	if err != nil {
		t.Fatal(err)
	}
	match := regexp.MustCompile(`(?i)(?:src|data-src)=["']([^"']*anidrive[^"']*)`).FindSubmatch(page)
	if len(match) < 2 {
		t.Fatal("episódio público não contém iframe Anidrive")
	}
	embedURL := strings.ReplaceAll(html.UnescapeString(string(match[1])), `\/`, `/`)
	r, err = client.Do(ctx, http.MethodGet, embedURL, nil, playerRequestHeaders(embedURL, episodeURL))
	if err != nil {
		t.Fatalf("página do iframe Anidrive: %v", err)
	}
	defer r.Body.Close()
	player, err := io.ReadAll(io.LimitReader(r.Body, 8<<20))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(player), `id="video_player"`) || !strings.Contains(strings.ToLower(string(player)), "jwplayer") {
		t.Fatalf("Anidrive não retornou o documento do player (HTTP %d, %s)", r.StatusCode, r.Header.Get("Content-Type"))
	}
}
