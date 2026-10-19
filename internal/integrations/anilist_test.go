package integrations

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/store"
)

func TestMetadataCoalescesAndPreservesPartial404(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		var body struct {
			Variables map[string]string `json:"variables"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
		}
		data := map[string]any{}
		for k, title := range body.Variables {
			data["a"+k[1:]] = map[string]any{"id": 1, "title": map[string]string{"romaji": title}}
		}
		w.WriteHeader(404) // AniList can return partial data together with a missing alias.
		json.NewEncoder(w).Encode(map[string]any{"data": data, "errors": []any{map[string]string{"message": "Not Found"}}})
	}))
	defer server.Close()
	m := NewMetadata(netx.New(), db)
	m.URL = server.URL
	m.Gate.Interval = 0
	defer m.Close()
	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			title := fmt.Sprintf("Anime %d", i)
			a, err := m.Lookup(context.Background(), title)
			if err != nil || a.Title != title {
				t.Errorf("lookup %s: %+v %v", title, a, err)
			}
		}()
	}
	close(start)
	wg.Wait()
	if n := requests.Load(); n != 2 {
		t.Fatalf("20 titles used %d requests instead of 2", n)
	}
	if _, err = m.Lookup(context.Background(), "Anime 0"); err != nil {
		t.Fatal(err)
	}
	if requests.Load() != 2 {
		t.Fatal("cache hit made another request")
	}
}

func TestCancelledMetadataDoesNotSpendRequest(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests.Add(1) }))
	defer server.Close()
	m := NewMetadata(netx.New(), db)
	m.URL = server.URL
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err = m.Lookup(ctx, "Cancelled"); err != context.Canceled {
		t.Fatal(err)
	}
	m.Close()
	if requests.Load() != 0 {
		t.Fatal("cancelled metadata hit network")
	}
}

func TestTitleMatchesIncludesNativeAndSynonymAliases(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request struct {
			Query     string         `json:"query"`
			Variables map[string]any `json:"variables"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Error(err)
		}
		if request.Variables["q0"] != "Demon Slayer" {
			t.Errorf("wrong search variable: %#v", request.Variables)
		}
		if !strings.Contains(request.Query, "native") || !strings.Contains(request.Query, "synonyms") {
			t.Error("query omitted multilingual aliases")
		}
		json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"r0": map[string]any{"media": []any{map[string]any{
			"id": 101, "idMal": 101, "title": map[string]string{"romaji": "Kimetsu no Yaiba", "english": "Demon Slayer", "native": "鬼滅の刃"}, "synonyms": []string{"Blade of Demon Destruction"},
		}}}}})
	}))
	defer server.Close()
	m := NewMetadata(netx.New(), nil)
	m.URL = server.URL
	m.Gate.Interval = 0
	defer m.Close()
	items, err := m.TitleMatches(context.Background(), "Demon Slayer", 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 || items[0].AniListID != 101 {
		t.Fatalf("unexpected canonical result: %+v", items)
	}
	for _, title := range []string{"Kimetsu no Yaiba", "Demon Slayer", "鬼滅の刃", "Blade of Demon Destruction"} {
		found := false
		for _, value := range append([]string{items[0].Title}, items[0].Titles...) {
			if value == title {
				found = true
			}
		}
		if !found {
			t.Errorf("missing alias %q in %+v", title, items[0].Titles)
		}
	}
	if contains := strings.Contains(strings.Join(items[0].PrimaryTitles, "|"), "Blade of Demon Destruction"); contains {
		t.Fatal("AniList synonym was classified as a primary title")
	}
}

func TestTitleMatchesBatchUsesOneRequestAndCachesQueries(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		var request struct {
			Variables map[string]string `json:"variables"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Error(err)
		}
		data := map[string]any{}
		for variable, title := range request.Variables {
			id := 101
			if title == "Anime B" {
				id = 202
			}
			data["r"+strings.TrimPrefix(variable, "q")] = map[string]any{"media": []any{
				map[string]any{"id": id, "title": map[string]string{"romaji": title}},
			}}
		}
		json.NewEncoder(w).Encode(map[string]any{"data": data})
	}))
	defer server.Close()

	m := NewMetadata(netx.New(), db)
	m.URL = server.URL
	m.Gate.Interval = 0
	defer m.Close()

	queries := []string{"Anime A", "Anime B", " anime a "}
	got, err := m.TitleMatchesBatch(context.Background(), queries)
	if err != nil {
		t.Fatal(err)
	}
	if len(got["Anime A"]) != 1 || len(got["Anime B"]) != 1 || len(got["anime a"]) != 1 {
		t.Fatalf("batch omitted a result or a duplicate query spelling: %+v", got)
	}
	if got["Anime A"][0].AniListID != 101 || got["Anime B"][0].AniListID != 202 {
		t.Fatalf("batch mapped AniList responses to the wrong query: %+v", got)
	}
	if requests.Load() != 1 {
		t.Fatalf("batch used %d requests; want one", requests.Load())
	}
	if matches, err := m.TitleMatches(context.Background(), "Anime A", 0); err != nil || len(matches) != 1 || matches[0].AniListID != 101 {
		t.Fatalf("single lookup did not reuse batch cache: %+v %v", matches, err)
	}
	if requests.Load() != 1 {
		t.Fatalf("cached lookup made another request: %d", requests.Load())
	}
}
