package providers

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSecurityChallengeMarkersAreRejected(t *testing.T) {
	if !securityChallenge(`<title>Performing security verification</title><div class="cf-chl-widget"></div>`) {
		t.Fatal("security-verification pages must not be treated as player content")
	}
	if securityChallenge(`<h1>Episode player</h1><video src="https://video.example/episode.mp4"></video>`) {
		t.Fatal("normal player content was classified as a security challenge")
	}
}

func TestRenderedPlayerURLsFindsIframeCreatedByJavaScript(t *testing.T) {
	if _, err := findBrowser(); err != nil {
		t.Skip(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(`<!doctype html><html><body><script>
document.body.insertAdjacentHTML('beforeend', '<iframe src="https://tags.crwdcntrl.net/tracker"></iframe><div class="player-container"></div>');
setTimeout(() => {
  const frame = document.createElement('iframe');
  frame.src = '/embed/episode-1';
  document.querySelector('.player-container').appendChild(frame);
}, 300);
</script></body></html>`))
	}))
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	urls, err := renderedPlayerURLs(ctx, server.URL)
	if err != nil {
		t.Fatal(err)
	}
	if len(urls) != 1 || !strings.HasSuffix(urls[0].URL, "/embed/episode-1") {
		t.Fatalf("unexpected rendered player URLs: %v", urls)
	}
}

func TestRenderedPlayerURLsRejectsProtectorInsteadOfOpeningItsLink(t *testing.T) {
	if _, err := findBrowser(); err != nil {
		t.Skip(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(`<!doctype html><html><body>
			<iframe src="https://t.dtscout.com/tracker"></iframe>
			<div class="player-container"><div class="div-mypopads-protector-iframe">
				<a class="mypopads_protector_link" target="_blank" href="https://ads.example/protector">continue</a>
			</div></div>
		</body></html>`))
	}))
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	_, err := renderedPlayerURLs(ctx, server.URL)
	if err == nil || !strings.Contains(err.Error(), "intersticial de anúncio") {
		t.Fatalf("protector must not be returned as a player candidate: %v", err)
	}
}

func TestRenderedPlayerURLsReadsJWPlayerAndStartsMuted(t *testing.T) {
	if _, err := findBrowser(); err != nil {
		t.Skip(err)
	}
	t.Run("configured source", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write([]byte(`<!doctype html><html><body><div id="video_player"></div><script>
window.jwplayer = () => ({getPlaylistItem: () => ({sources: [{file: 'https://video.example/episode.m3u8'}]})});
</script></body></html>`))
		}))
		defer server.Close()
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		urls, err := renderedPlayerURLs(ctx, server.URL)
		if err != nil {
			t.Fatal(err)
		}
		if len(urls) != 1 || urls[0].URL != "https://video.example/episode.m3u8" {
			t.Fatalf("JWPlayer config URL not returned: %v", urls)
		}
	})
	t.Run("muted playback exposes video", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write([]byte(`<!doctype html><html><body><div id="video_player"></div><script>
window.jwplayer = () => ({getPlaylistItem: () => ({}), setMute: () => {}, play: () => { const v = document.createElement('video'); v.src = 'https://video.example/episode.mp4'; document.querySelector('#video_player').appendChild(v); }});
</script></body></html>`))
		}))
		defer server.Close()
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		urls, err := renderedPlayerURLs(ctx, server.URL)
		if err != nil {
			t.Fatal(err)
		}
		if len(urls) != 1 || urls[0].URL != "https://video.example/episode.mp4" {
			t.Fatalf("muted JWPlayer playback URL not returned: %v", urls)
		}
	})
}

func TestRenderedPlayerURLsStartsScopedHTML5VideoMuted(t *testing.T) {
	if _, err := findBrowser(); err != nil {
		t.Skip(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write([]byte(`<!doctype html><html><body><div class="player-container"><video id="episode"></video></div><script>
HTMLMediaElement.prototype.play = function() { this.src = 'https://video.example/episode.mp4'; return Promise.resolve(); };
</script></body></html>`))
	}))
	defer server.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	urls, err := renderedPlayerURLs(ctx, server.URL)
	if err != nil {
		t.Fatal(err)
	}
	if len(urls) != 1 || urls[0].URL != "https://video.example/episode.mp4" {
		t.Fatalf("scoped HTML5 playback URL not returned: %v", urls)
	}
}
