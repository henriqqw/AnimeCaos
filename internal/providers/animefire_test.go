package providers

import (
	"context"
	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"
)

func TestAnimeFireContract(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("v") != "3" {
			t.Error("missing version")
		}
		switch r.URL.Path {
		case "/animes/pesquisar":
			if r.URL.Query().Get("q") != "ação & aventura" {
				t.Error("query encoding")
			}
			w.Write([]byte(`{"data":[{"id":"a","titles":{"BR":"Título","JP":"Title"},"audio":"Dublado & Legendado"}],"meta":{"current_page":1,"last_page":2}}`))
		case "/anime/a":
			w.Write([]byte(`{"data":{"hero":{"id":"a","titles":{"BR":"Título"}},"episodes":[{"id":"second-season","season":2,"number":1},{"id":"first-season","season":1,"number":1}]}}`))
		case "/episode/first-season":
			w.Write([]byte(`{"data":{"id":"first-season","streams":[{"audio":"legendado","url":"https://cdn.test/a.jpg","qualities":["480p","1080p"]},{"audio":"dublado","url":"https://cdn.test/b.jpg"},{"audio":"dublado","url":"https://cdn.test/off.jpg","is_offline":true}]}}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	p := NewAnimeFire(netx.New())
	p.Base = server.URL
	r, e := p.Search(context.Background(), "ação & aventura", 1)
	if e != nil || len(r.Items) != 1 || !r.HasNext {
		t.Fatalf("search: %+v %v", r, e)
	}
	if len(r.Items[0].Titles) != 2 {
		t.Fatal("alternate titles lost")
	}
	d, e := p.Details(context.Background(), r.Items[0])
	if e != nil || len(d.Episodes) != 2 {
		t.Fatalf("details: %+v %v", d, e)
	}
	if d.Episodes[0].ID != "first-season" || d.Episodes[1].Season != 2 {
		t.Fatal("season identity lost")
	}
	streams, e := p.Resolve(context.Background(), d.Episodes[0])
	if e != nil || len(streams) != 2 || streams[0].Kind != "hls" || streams[0].Headers["Referer"] == "" {
		t.Fatalf("streams: %+v %v", streams, e)
	}
}
func TestAnimeFireFailureDoesNotHideDetails(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/anime/a" {
			w.Write([]byte(`{"data":{"hero":{"id":"a"},"episodes":[{"id":"missing","season":1,"number":1}]}}`))
		} else {
			http.NotFound(w, r)
		}
	}))
	defer s.Close()
	p := NewAnimeFire(netx.New())
	p.Base = s.URL
	d, e := p.Details(context.Background(), domain.Anime{ID: "a"})
	if e != nil || len(d.Episodes) != 1 {
		t.Fatal(e)
	}
	if _, e = p.Resolve(context.Background(), d.Episodes[0]); e == nil {
		t.Fatal("expected unavailable stream")
	}
}
func TestAnimeFireCancellationAndRecovery(t *testing.T) {
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("q") == "slow" {
			<-r.Context().Done()
			return
		}
		w.Write([]byte(`{"data":[],"meta":{"last_page":1}}`))
	}))
	defer s.Close()
	p := NewAnimeFire(netx.New())
	p.Base = s.URL
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	if _, e := p.Search(ctx, "slow", 1); e == nil {
		t.Fatal("expected timeout")
	}
	r, e := p.Search(context.Background(), "fast", 1)
	if e != nil || len(r.Items) != 0 {
		t.Fatal(e)
	}
}
func TestLiveAnimeFire(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE") != "1" {
		t.Skip("set ANIMECAOS_LIVE=1 for real source checks")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
	defer cancel()
	p := NewAnimeFire(netx.New())
	r, e := p.Search(ctx, "naruto", 1)
	if e != nil || len(r.Items) == 0 {
		t.Fatalf("search %v", e)
	}
	d, e := p.Details(ctx, r.Items[0])
	if e != nil || len(d.Episodes) == 0 {
		t.Fatalf("details %v", e)
	}
	streams, e := p.Resolve(ctx, d.Episodes[0])
	if e != nil || len(streams) == 0 {
		t.Fatalf("resolve %v", e)
	}
	t.Logf("%s: %d episodes, %d audio streams; playback is validated separately", d.Anime.Title, len(d.Episodes), len(streams))
}
