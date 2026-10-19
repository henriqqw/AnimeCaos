package providers

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"

	"github.com/henriqqw/animecaos/internal/domain"
	"github.com/henriqqw/animecaos/internal/netx"
)

func TestOtakulogiaSearchGroupsAudioVariantsAndHonorsVIPGate(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request struct {
			Operation string         `json:"operationName"`
			Variables map[string]any `json:"variables"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Errorf("decode GraphQL request: %v", err)
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		switch request.Operation {
		case "SearchAnimes":
			_, _ = w.Write([]byte(`{"data":{"searchAnimes":{"total":21,"offset":0,"limit":20,"items":[{"upstreamCid":292,"name":"Naruto","slug":"naruto","nameEn":"NARUTO","synopsis":"Ninja anime","posterUrl":"https://img.example/naruto.jpg","year":2002,"status":"Completo","audioMix":"Misto"}]}}}`))
		case "AnimeCatalogDetail":
			_, _ = w.Write([]byte(`{"data":{"animeCatalogDetail":{"anime":{"upstreamCid":292,"name":"Naruto","slug":"naruto","synopsis":"Ninja anime","posterUrl":"https://img.example/naruto.jpg","audioMix":"Misto"},"seasons":[{"upstreamTid":10,"name":"Temporada 1 | Dublado","audioType":"DUB"},{"upstreamTid":20,"name":"Temporada 1 | Legendado","audioType":"LEG"}],"episodes":[{"upstreamId":101,"title":"T01 EP. 01 - Voltando Para Casa","episodeNumber":52,"upstreamTempId":10,"videoUrl":"https://media.example/dub.mp4","videoType":"server_url","audioType":"DUB"},{"upstreamId":202,"title":"T01 EP. 01 - Return Home","episodeNumber":1,"upstreamTempId":20,"videoUrl":"https://media.example/sub.mp4","videoType":"server_url","audioType":"LEG"}]}}}`))
		case "WatchPlayGate":
			input, _ := request.Variables["upstreamEpisodeId"].(float64)
			_, _ = w.Write([]byte(`{"data":{"requiresVipToWatch":` + strconv.FormatBool(int(input) == 202) + `}}`))
		default:
			t.Errorf("unexpected GraphQL operation %q", request.Operation)
			http.Error(w, "unexpected operation", http.StatusBadRequest)
		}
	}))
	defer server.Close()
	p := NewOtakulogia(netx.New())
	p.Endpoint = server.URL
	p.Base = "https://otakulogia.com"

	search, err := p.Search(context.Background(), "Naruto", 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(search.Items) != 1 || !search.HasNext || search.Items[0].Provider != "otakulogia" || search.Items[0].ID != "292" {
		t.Fatalf("unexpected search: %+v", search)
	}
	detail, err := p.Details(context.Background(), search.Items[0])
	if err != nil {
		t.Fatal(err)
	}
	if len(detail.Episodes) != 1 {
		t.Fatalf("expected one grouped episode, got %+v", detail.Episodes)
	}
	episode := detail.Episodes[0]
	if episode.Season != 1 || episode.Number != 1 || episode.Audio != "dublado & legendado" {
		t.Fatalf("unexpected grouped episode: %+v", episode)
	}
	streams, err := p.Resolve(context.Background(), episode)
	if err != nil {
		t.Fatal(err)
	}
	if len(streams) != 1 || streams[0].URL != "https://media.example/dub.mp4" || streams[0].Audio != "dublado" {
		t.Fatalf("VIP-gated media was returned or free media was lost: %+v", streams)
	}
}

func TestOtakulogiaResolverFailsClosedForMalformedCachedEpisode(t *testing.T) {
	p := NewOtakulogia(netx.New())
	if _, err := p.Resolve(context.Background(), domain.Episode{URL: "not-json"}); err == nil {
		t.Fatal("expected malformed playback payload to fail")
	}
}
