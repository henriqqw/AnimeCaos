package integrations

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/store"
)

func TestSyncUpdatesMALListAtWatchThreshold(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method == http.MethodGet {
			if r.URL.Path != "/v2/anime/21" || r.URL.Query().Get("fields") != "my_list_status" {
				t.Errorf("unexpected progress lookup: %s %s", r.Method, r.URL.String())
			}
			json.NewEncoder(w).Encode(map[string]any{"my_list_status": map[string]any{"status": "watching", "num_episodes_watched": 6}})
			return
		}
		if r.Method != http.MethodPatch || r.URL.Path != "/v2/anime/21/my_list_status" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer access-token" {
			t.Errorf("authorization header = %q", got)
		}
		if got := r.Header.Get("X-MAL-CLIENT-ID"); got != "public-client" {
			t.Errorf("client id header = %q", got)
		}
		body, _ := io.ReadAll(r.Body)
		form, err := url.ParseQuery(string(body))
		if err != nil {
			t.Errorf("invalid form body: %v", err)
		}
		if form.Get("num_watched_episodes") != "7" || form.Get("status") != "watching" {
			t.Errorf("unexpected watching update: %v", form)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "mal", Token{Access: "access-token"}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	accounts := NewAccounts(db, meta)
	accounts.Client.HTTP = server.Client()
	accounts.MALAPIBase = server.URL + "/v2/"
	accounts.MALGate.Interval = 0

	if err := accounts.Sync(context.Background(), "mal", "public-client", 21, 7, 24); err != nil {
		t.Fatal(err)
	}
	if requests != 2 {
		t.Fatalf("got %d requests, want a progress lookup and update", requests)
	}
}

func TestSyncMarksAniListCompleteOnlyAtFinalEpisode(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != http.MethodPost || r.URL.Path != "/graphql" {
			t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer ani-token" {
			t.Errorf("authorization header = %q", got)
		}
		var body struct {
			Query     string         `json:"query"`
			Variables map[string]any `json:"variables"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Errorf("decode GraphQL request: %v", err)
		}
		if strings.Contains(body.Query, "SaveMediaListEntry") {
			if body.Variables["id"] != float64(11061) || body.Variables["ep"] != float64(148) || body.Variables["status"] != "COMPLETED" {
				t.Errorf("unexpected final-episode update: %+v", body)
			}
			json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"SaveMediaListEntry": map[string]any{"id": 1, "progress": 148}}})
			return
		}
		if !strings.Contains(body.Query, "mediaListEntry") || body.Variables["id"] != float64(11061) {
			t.Errorf("unexpected current-progress query: %+v", body)
		}
		json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"Media": map[string]any{"mediaListEntry": map[string]any{"progress": 147, "status": "CURRENT"}}}})
	}))
	defer server.Close()

	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "anilist", Token{Access: "ani-token"}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	meta.URL = server.URL + "/graphql"
	meta.Gate.Interval = 0
	defer meta.Close()
	accounts := NewAccounts(db, meta)

	if err := accounts.Sync(context.Background(), "anilist", "", 11061, 148, 148); err != nil {
		t.Fatal(err)
	}
	if requests != 2 {
		t.Fatalf("got %d requests, want a progress lookup and mutation", requests)
	}
}

func TestSyncDoesNotMoveMALProgressBackwards(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != http.MethodGet {
			t.Errorf("progress must not be overwritten: %s %s", r.Method, r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"my_list_status": map[string]any{"status": "watching", "num_episodes_watched": 12}})
	}))
	defer server.Close()
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "mal", Token{Access: "access-token"}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	accounts := NewAccounts(db, meta)
	accounts.Client.HTTP = server.Client()
	accounts.MALAPIBase = server.URL + "/v2"
	accounts.MALGate.Interval = 0
	if err := accounts.Sync(context.Background(), "mal", "public-client", 21, 7, 24); err != nil {
		t.Fatal(err)
	}
	if requests != 1 {
		t.Fatalf("got %d requests, want a lookup only", requests)
	}
}

func TestMALTokenExchangeUsesBasicClientAuthentication(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		want := "Basic " + base64.StdEncoding.EncodeToString([]byte("client-id:client-secret"))
		if got := r.Header.Get("Authorization"); got != want {
			t.Errorf("Authorization = %q, want %q", got, want)
		}
		body, _ := io.ReadAll(r.Body)
		form, err := url.ParseQuery(string(body))
		if err != nil {
			t.Errorf("invalid token form: %v", err)
		}
		if form.Get("client_id") != "client-id" || form.Get("code_verifier") != "pkce-verifier" || form.Get("grant_type") != "authorization_code" {
			t.Errorf("token exchange form is incomplete: %v", form)
		}
		json.NewEncoder(w).Encode(map[string]any{"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})
	}))
	defer server.Close()
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	meta.Client.HTTP = server.Client()
	accounts := NewAccounts(db, meta)
	accounts.MALOAuthBase = server.URL
	if err := accounts.SetMALClientSecret("client-secret"); err != nil {
		t.Fatal(err)
	}
	if !accounts.MALClientSecretConfigured() {
		t.Fatal("stored MAL secret was not reported as configured")
	}
	token, err := accounts.exchange(context.Background(), url.Values{
		"client_id":     {"client-id"},
		"grant_type":    {"authorization_code"},
		"code":          {"authorization-code"},
		"code_verifier": {"pkce-verifier"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if token.Access != "access" || token.Refresh != "refresh" {
		t.Fatalf("unexpected token response: %+v", token)
	}
	if err := accounts.SetMALClientSecret(""); err != nil {
		t.Fatal(err)
	}
	if accounts.MALClientSecretConfigured() {
		t.Fatal("removed MAL secret still appears configured")
	}
}

func TestMALRefreshUsesBasicAuthenticationAndPreservesRefreshToken(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		want := "Basic " + base64.StdEncoding.EncodeToString([]byte("client-id:client-secret"))
		if got := r.Header.Get("Authorization"); got != want {
			t.Errorf("Authorization = %q, want %q", got, want)
		}
		body, _ := io.ReadAll(r.Body)
		form, err := url.ParseQuery(string(body))
		if err != nil {
			t.Errorf("invalid refresh form: %v", err)
		}
		if form.Get("client_id") != "client-id" || form.Get("grant_type") != "refresh_token" || form.Get("refresh_token") != "old-refresh" {
			t.Errorf("refresh form is incomplete: %v", form)
		}
		json.NewEncoder(w).Encode(map[string]any{"access_token": "new-access", "expires_in": 3600})
	}))
	defer server.Close()
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "mal", Token{Access: "old-access", Refresh: "old-refresh", Expires: 1}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	meta.Client.HTTP = server.Client()
	accounts := NewAccounts(db, meta)
	accounts.MALOAuthBase = server.URL
	accounts.MALGate.Interval = 0
	if err := accounts.SetMALClientSecret("client-secret"); err != nil {
		t.Fatal(err)
	}

	token, err := accounts.token(context.Background(), "mal", "client-id")
	if err != nil {
		t.Fatal(err)
	}
	if token.Access != "new-access" || token.Refresh != "old-refresh" {
		t.Fatalf("unexpected refreshed token: %+v", token)
	}
}
