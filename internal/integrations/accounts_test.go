package integrations

import (
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/securestore"
	"github.com/henriqqw/animecaos/internal/store"
)

type testCredentials struct {
	mu     sync.Mutex
	values map[string]string
	getErr error
	setErr error
}

func newTestCredentials() *testCredentials {
	return &testCredentials{values: map[string]string{}}
}

func (c *testCredentials) Get(key string) (string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.getErr != nil {
		return "", c.getErr
	}
	value, ok := c.values[key]
	if !ok {
		return "", securestore.ErrNotFound
	}
	return value, nil
}

func (c *testCredentials) Set(key, value string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.setErr != nil {
		return c.setErr
	}
	c.values[key] = value
	return nil
}

func (c *testCredentials) Delete(key string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, ok := c.values[key]; !ok {
		return securestore.ErrNotFound
	}
	delete(c.values, key)
	return nil
}

func newTestAccounts(db *store.Store, meta *Metadata) *Accounts {
	return NewAccountsWithCredentials(db, meta, newTestCredentials())
}

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
	accounts := newTestAccounts(db, meta)
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
	accounts := newTestAccounts(db, meta)

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
	accounts := newTestAccounts(db, meta)
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
	accounts := newTestAccounts(db, meta)
	accounts.MALOAuthBase = server.URL
	if err := accounts.SetMALClientSecret("client-secret"); err != nil {
		t.Fatal(err)
	}
	configured, err := accounts.MALClientSecretConfigured()
	if err != nil || !configured {
		t.Fatal("stored MAL secret was not reported as configured")
	}
	var plainSecret string
	if err := db.Get("auth", malClientSecretKey, &plainSecret); !errors.Is(err, sql.ErrNoRows) {
		t.Fatal("MAL secret was written to SQLite instead of the credential vault")
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
	configured, err = accounts.MALClientSecretConfigured()
	if err != nil || configured {
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
	accounts := newTestAccounts(db, meta)
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

func TestLegacyAccountCredentialsMigrateToVault(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	legacyToken := Token{Access: "migration-access", Refresh: "migration-refresh", Expires: 12345}
	if err := db.Put("auth", "mal", legacyToken); err != nil {
		t.Fatal(err)
	}
	if err := db.Put("auth", malClientSecretKey, "migration-secret"); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	vault := newTestCredentials()
	accounts := NewAccountsWithCredentials(db, meta, vault)

	profiles := accounts.Profiles()
	if len(profiles) != 3 || !profiles[1].Connected {
		t.Fatalf("legacy MAL token was not migrated: %+v", profiles)
	}
	configured, err := accounts.MALClientSecretConfigured()
	if err != nil || !configured {
		t.Fatalf("legacy MAL secret migration status = %v, %v", configured, err)
	}
	var got Token
	if err := accounts.readCredential("oauth:mal", "mal", &got); err != nil || got != legacyToken {
		t.Fatalf("vault token = %+v, err=%v", got, err)
	}
	var storedSecret string
	if err := accounts.readCredential("mal-client-secret", malClientSecretKey, &storedSecret); err != nil || storedSecret != "migration-secret" {
		t.Fatalf("vault secret migration failed: configured value missing")
	}
	for _, key := range []string{"mal", malClientSecretKey} {
		var value json.RawMessage
		if err := db.Get("auth", key, &value); !errors.Is(err, sql.ErrNoRows) {
			t.Errorf("legacy credential %q remains in SQLite: %v", key, err)
		}
	}
}

func TestDiscordLoginUsesPKCEAndStoresProfile(t *testing.T) {
	var tokenRequests int
	var expectedChallenge atomic.Value
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/oauth2/token":
			tokenRequests++
			if err := r.ParseForm(); err != nil {
				t.Errorf("parse token form: %v", err)
			}
			if r.Form.Get("grant_type") != "authorization_code" || r.Form.Get("client_id") != DiscordClientID || r.Form.Get("code") != "discord-code" {
				t.Errorf("unexpected Discord token request: %v", r.Form)
			}
			challenge, _ := expectedChallenge.Load().(string)
			if r.Form.Get("code_verifier") == "" || pkceChallenge(r.Form.Get("code_verifier")) != challenge {
				t.Errorf("Discord token exchange did not prove the PKCE verifier")
			}
			json.NewEncoder(w).Encode(map[string]any{"access_token": "discord-access", "refresh_token": "discord-refresh", "expires_in": 3600})
		case r.Method == http.MethodGet && r.URL.Path == "/api/v10/users/@me":
			if r.Header.Get("Authorization") != "Bearer discord-access" {
				t.Errorf("Discord profile authorization = %q", r.Header.Get("Authorization"))
			}
			json.NewEncoder(w).Encode(map[string]any{"id": "123456789012345678", "username": "caosdev", "global_name": "Caos Dev", "avatar": "avatar-hash"})
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	addrProbe, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := addrProbe.Addr().(*net.TCPAddr).Port
	addrProbe.Close()
	redirect := fmt.Sprintf("http://127.0.0.1:%d/", port)

	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	accounts := newTestAccounts(db, meta)
	accounts.Client.HTTP = server.Client()
	accounts.DiscordOAuthBase = server.URL + "/oauth2"
	accounts.DiscordAuthorizeURL = server.URL + "/authorize"
	accounts.DiscordAPIBase = server.URL + "/api/v10"
	accounts.DiscordListenAddr = fmt.Sprintf("127.0.0.1:%d", port)
	accounts.DiscordRedirectURI = redirect
	accounts.Open = func(raw string) error {
		authorize, parseErr := url.Parse(raw)
		if parseErr != nil {
			return parseErr
		}
		query := authorize.Query()
		if query.Get("client_id") != DiscordClientID || query.Get("scope") != "identify" || query.Get("response_type") != "code" || query.Get("redirect_uri") != redirect || query.Get("code_challenge_method") != "S256" {
			t.Errorf("unexpected Discord authorization URL: %s", raw)
		}
		if len(query.Get("code_challenge")) != 43 {
			t.Errorf("invalid PKCE challenge length: %q", query.Get("code_challenge"))
		}
		expectedChallenge.Store(query.Get("code_challenge"))
		go func() {
			callback := redirect + "?" + url.Values{"code": {"discord-code"}, "state": {query.Get("state")}, "iss": {"https://discord.com"}}.Encode()
			client := &http.Client{Timeout: 5 * time.Second}
			response, requestErr := client.Get(callback)
			if requestErr != nil {
				t.Errorf("Discord callback request failed: %v", requestErr)
				return
			}
			response.Body.Close()
		}()
		return nil
	}

	profile, err := func() (Account, error) {
		err := accounts.Login(context.Background(), "discord", "")
		if err != nil {
			return Account{}, err
		}
		return accounts.Profile(context.Background(), "discord", "")
	}()
	if err != nil {
		t.Fatal(err)
	}
	if tokenRequests != 1 || !profile.Connected || profile.ExternalID != "123456789012345678" || profile.Name != "Caos Dev" {
		t.Fatalf("Discord login/profile = %+v; token requests=%d", profile, tokenRequests)
	}
	if profile.Avatar != "https://cdn.discordapp.com/avatars/123456789012345678/avatar-hash.png?size=128" {
		t.Fatalf("Discord avatar = %q", profile.Avatar)
	}
	var stored Token
	if err := accounts.readCredential("oauth:discord", "discord", &stored); err != nil || stored.Access != "discord-access" || stored.Refresh != "discord-refresh" {
		t.Fatalf("Discord credential was not saved securely: %+v, %v", stored, err)
	}
}

func TestDiscordLoginReturnsPromptlyWhenUserDenies(t *testing.T) {
	probe, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := probe.Addr().(*net.TCPAddr).Port
	probe.Close()
	redirect := fmt.Sprintf("http://127.0.0.1:%d/", port)

	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	accounts := newTestAccounts(db, meta)
	accounts.DiscordListenAddr = fmt.Sprintf("127.0.0.1:%d", port)
	accounts.DiscordRedirectURI = redirect
	accounts.Open = func(raw string) error {
		authorize, parseErr := url.Parse(raw)
		if parseErr != nil {
			return parseErr
		}
		query := authorize.Query()
		go func() {
			callback := redirect + "?" + url.Values{
				"error": {"access_denied"},
				"state": {query.Get("state")},
				"iss":   {"https://discord.com"},
			}.Encode()
			response, requestErr := (&http.Client{Timeout: time.Second}).Get(callback)
			if requestErr == nil {
				response.Body.Close()
			}
		}()
		return nil
	}

	started := time.Now()
	err = accounts.Login(context.Background(), "discord", "")
	if err == nil || !strings.Contains(err.Error(), "cancelado pelo usuário") {
		t.Fatalf("denied Discord login error = %v", err)
	}
	if elapsed := time.Since(started); elapsed > time.Second {
		t.Fatalf("denied Discord login took %s; expected prompt completion", elapsed)
	}
}

func TestCredentialVaultFailurePreservesLegacyDataAndSurfacesError(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "anilist", Token{Access: "still-in-db"}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	vault := newTestCredentials()
	vault.setErr = errors.New("vault locked")
	accounts := NewAccountsWithCredentials(db, meta, vault)

	profiles := accounts.Profiles()
	if profiles[0].Connected || profiles[0].Error == "" {
		t.Fatalf("vault migration failure was not shown to the user: %+v", profiles[0])
	}
	var legacy Token
	if err := db.Get("auth", "anilist", &legacy); err != nil || legacy.Access != "still-in-db" {
		t.Fatalf("legacy token was lost after vault failure: %+v, %v", legacy, err)
	}
}

func TestCredentialReadDoesNotFallbackWhenVaultIsUnavailable(t *testing.T) {
	db, err := store.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if err := db.Put("auth", "anilist", Token{Access: "plaintext-must-not-be-used"}); err != nil {
		t.Fatal(err)
	}
	meta := NewMetadata(netx.New(), db)
	defer meta.Close()
	vault := newTestCredentials()
	vault.getErr = errors.New("credential service unavailable")
	accounts := NewAccountsWithCredentials(db, meta, vault)

	profiles := accounts.Profiles()
	if profiles[0].Connected || profiles[0].Error == "" {
		t.Fatalf("vault outage was silently treated as a valid connection: %+v", profiles[0])
	}
	if _, err := accounts.token(context.Background(), "anilist", ""); err == nil {
		t.Fatal("token lookup fell back to plaintext SQLite while the vault was unavailable")
	}
}
