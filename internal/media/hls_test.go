package media

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/henriqqw/animecaos/internal/domain"
)

func TestBestExplainsMissingManifestAsRemote404(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	}))
	defer server.Close()

	_, err := Best(context.Background(), domain.Stream{URL: server.URL + "/i/signed-path/h.jpg", Kind: "hls"})
	if err == nil || !strings.Contains(err.Error(), "servidor de vídeo não encontrou o arquivo deste episódio (HTTP 404)") {
		t.Fatalf("expected a clear remote 404 error, got %v", err)
	}
}

func TestBestDoesNotFollowRedirectToAdvertisingHost(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Location", "https://t.dtscout.com/tracker")
		w.WriteHeader(http.StatusFound)
	}))
	defer server.Close()

	_, err := Best(context.Background(), domain.Stream{URL: server.URL + "/master.m3u8", Kind: "hls"})
	if err == nil || !strings.Contains(err.Error(), "HTTP 302") {
		t.Fatalf("advertising redirect should remain an unavailable 302, got %v", err)
	}
}

func TestVariantsDropsAdvertisingHosts(t *testing.T) {
	manifest := "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000,RESOLUTION=1920x1080\nhttps://doubleclick.net/ad.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=1000,RESOLUTION=1280x720\nhttps://cdn.example/720.m3u8\n"
	variants := Variants(manifest, "https://video.example/master.m3u8")
	if len(variants) != 1 || variants[0].URL != "https://cdn.example/720.m3u8" {
		t.Fatalf("unexpected HLS variants after ad filtering: %+v", variants)
	}
}
