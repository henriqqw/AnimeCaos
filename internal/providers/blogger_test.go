package providers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/media"
	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/player"
)

func bloggerFixture() string {
	payload, _ := json.Marshal([]any{1, nil, []any{
		[]any{"https://video.example/low.mp4?x=1&y=2", []int{18}},
		[]any{"https://video.example/high.mp4", []int{37}},
	}})
	batch, _ := json.Marshal([]any{[]any{"wrb.fr", "WcwnYd", string(payload)}})
	return ")]}'\n\n" + fmt.Sprint(len(batch)) + "\n" + string(batch)
}

func TestBloggerRPC(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Query().Get("rpcids") != "WcwnYd" {
			t.Error("wrong RPC request")
		}
		r.ParseForm()
		var batch [][][]json.RawMessage
		if e := json.Unmarshal([]byte(r.Form.Get("f.req")), &batch); e != nil {
			t.Error(e)
		}
		var request string
		json.Unmarshal(batch[0][0][1], &request)
		if request != `["public-token",null,false]` {
			t.Errorf("wrong payload: %s", request)
		}
		fmt.Fprint(w, bloggerFixture())
	}))
	defer srv.Close()
	p := NewOnlineCC(netx.New())
	streams, e := p.resolveBlogger(context.Background(), srv.URL+"/video.g?token=public-token")
	if e != nil {
		t.Fatal(e)
	}
	if len(streams) != 2 || streams[0].Qualities[0] != "1080p" || streams[1].URL != "https://video.example/low.mp4?x=1&y=2" {
		t.Fatalf("bad streams: %+v", streams)
	}
	if _, e := parseBlogger([]byte("<html>unavailable</html>"), srv.URL); e == nil {
		t.Fatal("accepted HTML")
	}
	emptyPayload, _ := json.Marshal([]any{1, nil, []any{}})
	emptyBatch, _ := json.Marshal([]any{[]any{"wrb.fr", "WcwnYd", string(emptyPayload)}})
	if _, e := parseBlogger(emptyBatch, srv.URL); e == nil || !strings.Contains(e.Error(), "status=1, formatos=0") {
		t.Fatalf("empty Blogger response should report absence of renditions without exposing URLs: %v", e)
	}
	nullPayloadBatch, _ := json.Marshal([]any{[]any{"wrb.fr", "WcwnYd", nil}})
	if _, e := parseBlogger(nullPayloadBatch, srv.URL); e == nil || !strings.Contains(e.Error(), "payload=null") {
		t.Fatalf("null Blogger response should be distinguished from an unknown payload format: %v", e)
	}
}

func TestLiveOnlineCC(t *testing.T) {
	if os.Getenv("ANIMECAOS_LIVE_TEST") != "1" {
		t.Skip("live source test is opt-in")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	p := NewOnlineCC(netx.New())
	streams, e := p.Resolve(ctx, domain.Episode{URL: "https://animesonlinecc.to/episodio/naruto-classico-episodio-1/"})
	if e != nil {
		t.Fatal(e)
	}
	if e = media.Validate(ctx, streams[0]); e != nil {
		t.Fatal(e)
	}
	t.Logf("resolved and read media bytes: %s %v", streams[0].Kind, streams[0].Qualities)
}

func TestLiveOnlineCCPlayback(t *testing.T) {
	if os.Getenv("ANIMECAOS_PLAYER_TEST") != "1" || os.Getenv("ANIMECAOS_LIVE_TEST") != "1" {
		t.Skip("live player test is opt-in")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	p := NewOnlineCC(netx.New())
	streams, e := p.Resolve(ctx, domain.Episode{URL: "https://animesonlinecc.to/episodio/naruto-classico-episodio-1/"})
	if e != nil {
		t.Fatal(e)
	}
	g, e := media.NewGateway()
	if e != nil {
		t.Fatal(e)
	}
	defer g.Close()
	u, release := g.Register(streams[0])
	defer release()
	events := make(chan player.State, 512)
	c := player.New(func(s player.State) {
		select {
		case events <- s:
		default:
		}
	})
	defer c.Close()
	if e = c.Start(ctx, u, "mpv", "", 0, "onlinecc"); e != nil {
		t.Fatal(e)
	}
	seeked := false
	for {
		select {
		case <-ctx.Done():
			t.Fatal(ctx.Err())
		case state := <-events:
			if !seeked && state.Position > 1 && state.Duration > 10 && state.AudioCodec != "" && state.VideoCodec != "" {
				if e = c.Command("seek", state.Duration-2); e != nil {
					t.Fatal(e)
				}
				seeked = true
			}
			if !state.Playing {
				if state.Error != "" || !state.EOF || !seeked {
					t.Fatalf("playback failed: %+v", state)
				}
				t.Logf("decoded %s / %s, %.2fs, seek and natural EOF", state.VideoCodec, state.AudioCodec, state.Duration)
				return
			}
		}
	}
}
