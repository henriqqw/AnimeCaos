package media

import (
	"context"
	"github.com/henriqqw/animecaos/internal/domain"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestGatewayHLSDisguisedAsJPEG(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Referer") != "https://animefire.one/" {
			t.Error("referer lost")
		}
		switch r.URL.Path {
		case "/master.jpg":
			w.Header().Set("Content-Type", "image/jpeg")
			io.WriteString(w, "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100,RESOLUTION=1280x720\nvariants/video.jpg\n")
		case "/variants/video.jpg":
			io.WriteString(w, "#EXTM3U\n#EXT-X-MAP:URI=\"../init.jpg\"\n#EXT-X-KEY:METHOD=AES-128,URI=\"../key.jpg\"\n#EXTINF:2,\n../segment.jpg\n#EXT-X-ENDLIST\n")
		case "/segment.jpg":
			io.WriteString(w, "segment content")
		default:
			io.WriteString(w, "bytes")
		}
	}))
	defer upstream.Close()
	g, e := NewGateway()
	if e != nil {
		t.Fatal(e)
	}
	defer g.Close()
	u, release := g.Register(domain.Stream{URL: upstream.URL + "/master.jpg", Kind: "hls", Headers: map[string]string{"Referer": "https://animefire.one/"}})
	get := func(u string) string {
		r, e := http.Get(u)
		if e != nil {
			t.Fatal(e)
		}
		defer r.Body.Close()
		b, _ := io.ReadAll(r.Body)
		return string(b)
	}
	master := get(u)
	v := Variants(master, u)
	if len(v) != 1 || !strings.Contains(v[0].URL, "variant.m3u8") {
		t.Fatal(master)
	}
	playlist := get(v[0].URL)
	if strings.Contains(playlist, "../") || !strings.Contains(playlist, "init.mp4") || !strings.Contains(playlist, "key.bin") {
		t.Fatal(playlist)
	}
	for _, line := range strings.Split(playlist, "\n") {
		if strings.HasPrefix(line, "http") && get(line) != "segment content" {
			t.Fatal("segment mismatch")
		}
	}
	g.mu.Lock()
	count := len(g.targets)
	g.mu.Unlock()
	get(u)
	g.mu.Lock()
	if len(g.targets) != count {
		t.Error("duplicate manifest registrations")
	}
	g.mu.Unlock()
	release()
	r, e := http.Get(u)
	if e != nil {
		t.Fatal(e)
	}
	r.Body.Close()
	if r.StatusCode != 404 {
		t.Fatal("released session still accessible")
	}
}
func TestSelectHighestAndFallback(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/master.jpg":
			io.WriteString(w, "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=500,RESOLUTION=852x480\n480.jpg\n#EXT-X-STREAM-INF:BANDWIDTH=1500,RESOLUTION=1920x1080\n1080.jpg\n#EXT-X-STREAM-INF:BANDWIDTH=1000,RESOLUTION=1280x720\n720.jpg\n")
		case "/1080.jpg":
			http.NotFound(w, r)
		default:
			io.WriteString(w, "#EXTM3U\n#EXTINF:1,\nseg.jpg\n")
		}
	}))
	defer s.Close()
	best, e := Best(context.Background(), domain.Stream{URL: s.URL + "/master.jpg", Kind: "hls"})
	if e != nil || !strings.HasSuffix(best.URL, "720.jpg") {
		t.Fatalf("%+v %v", best, e)
	}
}
func TestValidateRejectsHTML(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "<html>error</html>") }))
	defer s.Close()
	if Validate(context.Background(), domain.Stream{URL: s.URL, Kind: "hls"}) == nil {
		t.Fatal("HTML is not HLS")
	}
}

func TestValidatePreservesProviderUserAgent(t *testing.T) {
	const expected = "Mozilla/5.0 ProviderPlayer/1.0"
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("User-Agent"); got != expected {
			t.Errorf("User-Agent = %q, want %q", got, expected)
			http.Error(w, "wrong user agent", http.StatusForbidden)
			return
		}
		w.WriteHeader(http.StatusPartialContent)
		io.WriteString(w, "media")
	}))
	defer s.Close()
	if err := Validate(context.Background(), domain.Stream{URL: s.URL, Kind: "file", Headers: map[string]string{"User-Agent": expected}}); err != nil {
		t.Fatal(err)
	}
}

func TestGatewayPreservesProviderUserAgent(t *testing.T) {
	const expected = "Mozilla/5.0 ProviderPlayer/1.0"
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("User-Agent"); got != expected {
			t.Errorf("User-Agent = %q, want %q", got, expected)
			http.Error(w, "wrong user agent", http.StatusForbidden)
			return
		}
		w.Header().Set("Content-Type", "video/mp4")
		w.WriteHeader(http.StatusPartialContent)
		io.WriteString(w, "media")
	}))
	defer upstream.Close()
	g, err := NewGateway()
	if err != nil {
		t.Fatal(err)
	}
	defer g.Close()
	u, release := g.Register(domain.Stream{URL: upstream.URL, Kind: "file", Headers: map[string]string{"User-Agent": expected}})
	defer release()
	r, err := http.Get(u)
	if err != nil {
		t.Fatal(err)
	}
	r.Body.Close()
	if r.StatusCode != http.StatusPartialContent {
		t.Fatalf("status = %d, want %d", r.StatusCode, http.StatusPartialContent)
	}
}

func TestGatewayDoesNotExposeRedirectToAdvertisingHost(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Location", "https://t.dtscout.com/tracker")
		w.WriteHeader(http.StatusFound)
	}))
	defer upstream.Close()
	g, err := NewGateway()
	if err != nil {
		t.Fatal(err)
	}
	defer g.Close()
	u, release := g.Register(domain.Stream{URL: upstream.URL + "/episode.mp4", Kind: "file"})
	defer release()

	response, err := http.Get(u)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusBadGateway || strings.Contains(response.Header.Get("Location"), "dtscout") {
		t.Fatalf("gateway exposed advertising redirect: status=%d location=%q", response.StatusCode, response.Header.Get("Location"))
	}
}
