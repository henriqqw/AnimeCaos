package integrations

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/henriqqw/animecaos/internal/netx"
	"github.com/henriqqw/animecaos/internal/platform"
	"github.com/henriqqw/animecaos/internal/store"
)

const MALClientID = "62b4b2a8de68653e14c06d37e3a43fda"
const AniListClientID = "39400"
const defaultMALOAuthBase = "https://myanimelist.net/v1/oauth2"
const defaultMALAPIBase = "https://api.myanimelist.net/v2"
const malClientSecretKey = "mal-client-secret"

type Token struct {
	Access  string `json:"accessToken"`
	Refresh string `json:"refreshToken"`
	Expires int64  `json:"expiresAt"`
}
type Account struct {
	Provider   string `json:"provider"`
	Connected  bool   `json:"connected"`
	ID         int    `json:"id"`
	Name       string `json:"name"`
	Avatar     string `json:"avatar"`
	AnimeCount int    `json:"animeCount"`
	Episodes   int    `json:"episodes"`
	Minutes    int    `json:"minutes"`
	Error      string `json:"error"`
}
type Accounts struct {
	Store        *store.Store
	Meta         *Metadata
	Client       *netx.Client
	MALGate      *netx.Gate
	MALOAuthBase string
	MALAPIBase   string
	login        sync.Mutex
	refresh      sync.Mutex
	syncMu       sync.Mutex
	Open         func(string) error
}

func NewAccounts(s *store.Store, m *Metadata) *Accounts {
	return &Accounts{Store: s, Meta: m, Client: m.Client, MALGate: &netx.Gate{Interval: time.Second}, MALOAuthBase: defaultMALOAuthBase, MALAPIBase: defaultMALAPIBase, Open: platform.Open}
}

func (a *Accounts) malOAuthBase() string {
	if base := strings.TrimRight(a.MALOAuthBase, "/"); base != "" {
		return base
	}
	return defaultMALOAuthBase
}

func (a *Accounts) malAPIBase() string {
	if base := strings.TrimRight(a.MALAPIBase, "/"); base != "" {
		return base
	}
	return defaultMALAPIBase
}

func (a *Accounts) MALClientSecretConfigured() bool {
	var secret string
	return a.Store.Get("auth", malClientSecretKey, &secret) == nil && secret != ""
}

func (a *Accounts) SetMALClientSecret(secret string) error {
	secret = strings.TrimSpace(secret)
	if len(secret) > 4096 {
		return fmt.Errorf("Client Secret do MyAnimeList excede o limite permitido")
	}
	if secret == "" {
		return a.Store.Delete("auth", malClientSecretKey)
	}
	return a.Store.Put("auth", malClientSecretKey, secret)
}

func (a *Accounts) malClientSecret() string {
	var secret string
	_ = a.Store.Get("auth", malClientSecretKey, &secret)
	return secret
}
func random() string {
	var b [48]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return base64.RawURLEncoding.EncodeToString(b[:])
}
func (a *Accounts) Login(ctx context.Context, provider, malID string) (resultErr error) {
	if !a.login.TryLock() {
		return fmt.Errorf("já existe um login em andamento")
	}
	defer a.login.Unlock()
	if provider != "anilist" && provider != "mal" {
		return fmt.Errorf("integração desconhecida")
	}
	port := "9742"
	redirect := "http://localhost:9742"
	if provider == "mal" {
		port = "9743"
		redirect = "http://localhost:9743/"
		if malID == "" {
			return fmt.Errorf("configure o Client ID do MyAnimeList")
		}
	}
	listener, e := net.Listen("tcp4", "127.0.0.1:"+port)
	if e != nil {
		return fmt.Errorf("não foi possível iniciar retorno do login na porta %s: %w", port, e)
	}
	ctx, cancel := context.WithTimeout(ctx, 2*time.Minute)
	defer cancel()
	state := random()
	verifier := random()
	received := make(chan string, 1)
	finished := make(chan struct{})
	complete := func(w http.ResponseWriter, r *http.Request) bool {
		select {
		case <-finished:
			if resultErr != nil {
				http.Error(w, "Não foi possível conectar: "+resultErr.Error(), http.StatusBadRequest)
				return false
			}
			return true
		case <-r.Context().Done():
			return false
		case <-ctx.Done():
			http.Error(w, "Login cancelado ou expirado. Volte ao AnimeCaos.", http.StatusRequestTimeout)
			return false
		}
	}
	handler := http.NewServeMux()
	handler.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Referrer-Policy", "no-referrer")
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		if provider == "anilist" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			io.WriteString(w, `<!doctype html><meta charset="utf-8"><title>AnimeCaos</title><p id="message">Conectando…</p><script>const p=new URLSearchParams(location.hash.slice(1));history.replaceState(null,'','/');fetch('/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:p.toString()}).then(r=>{document.getElementById('message').textContent=r.ok?'Conectado! Você pode voltar ao AnimeCaos.':'Login inválido. Volte ao aplicativo e tente novamente.'})</script>`)
			return
		}
		if subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("state")), []byte(state)) != 1 {
			http.Error(w, "retorno de login inválido", 400)
			return
		}
		code := r.URL.Query().Get("code")
		if code == "" {
			http.Error(w, "autorização não concedida", 400)
			return
		}
		select {
		case received <- code:
		default:
		}
		if complete(w, r) {
			io.WriteString(w, "Conectado. Volte ao AnimeCaos.")
		}
	})
	handler.HandleFunc("/token", func(w http.ResponseWriter, r *http.Request) {
		if provider != "anilist" || r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 16384)
		if r.ParseForm() != nil || subtle.ConstantTimeCompare([]byte(r.Form.Get("state")), []byte(state)) != 1 {
			http.Error(w, "estado inválido", 400)
			return
		}
		token := r.Form.Get("access_token")
		if token == "" {
			http.Error(w, "sem token", 400)
			return
		}
		select {
		case received <- token:
		default:
		}
		if complete(w, r) {
			w.WriteHeader(204)
		}
	})
	server := http.Server{Handler: handler, ReadHeaderTimeout: 5 * time.Second}
	defer func() {
		shutdown, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		server.Shutdown(shutdown)
	}()
	defer close(finished)
	go server.Serve(listener)
	u := "https://anilist.co/api/v2/oauth/authorize?" + url.Values{"client_id": {AniListClientID}, "response_type": {"token"}, "redirect_uri": {redirect}, "state": {state}}.Encode()
	if provider == "mal" {
		u = "https://myanimelist.net/v1/oauth2/authorize?" + url.Values{"client_id": {malID}, "response_type": {"code"}, "redirect_uri": {redirect}, "state": {state}, "code_challenge": {verifier}, "code_challenge_method": {"plain"}}.Encode()
	}
	if e = a.Open(u); e != nil {
		return e
	}
	var token Token
	select {
	case <-ctx.Done():
		return fmt.Errorf("login cancelado ou expirado")
	case value := <-received:
		if provider == "anilist" {
			token = Token{Access: value, Expires: time.Now().Add(365 * 24 * time.Hour).Unix()}
		} else {
			token, e = a.exchange(ctx, url.Values{"client_id": {malID}, "grant_type": {"authorization_code"}, "code": {value}, "code_verifier": {verifier}, "redirect_uri": {redirect}})
			if e != nil {
				return e
			}
		}
	}
	if e = a.Store.Put("auth", provider, token); e != nil {
		return e
	}
	_, e = a.Profile(ctx, provider, malID)
	return e
}
func (a *Accounts) exchange(ctx context.Context, form url.Values) (Token, error) {
	clientID := form.Get("client_id")
	if clientID == "" {
		return Token{}, fmt.Errorf("configure o Client ID do MyAnimeList")
	}
	basic := base64.StdEncoding.EncodeToString([]byte(clientID + ":" + a.malClientSecret()))
	r, e := a.Client.Do(ctx, "POST", a.malOAuthBase()+"/token", []byte(form.Encode()), map[string]string{"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded"})
	if e != nil {
		return Token{}, fmt.Errorf("MyAnimeList: troca de token: %w", e)
	}
	defer r.Body.Close()
	var t struct {
		Access  string `json:"access_token"`
		Refresh string `json:"refresh_token"`
		Expires int64  `json:"expires_in"`
	}
	if e = json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&t); e != nil {
		return Token{}, e
	}
	if t.Access == "" {
		return Token{}, fmt.Errorf("MyAnimeList não retornou token")
	}
	return Token{Access: t.Access, Refresh: t.Refresh, Expires: time.Now().Unix() + t.Expires}, nil
}
func (a *Accounts) token(ctx context.Context, p, id string) (Token, error) {
	a.refresh.Lock()
	defer a.refresh.Unlock()
	var t Token
	if a.Store.Get("auth", p, &t) != nil || t.Access == "" {
		return t, fmt.Errorf("conta não conectada")
	}
	if p == "mal" && t.Refresh != "" && time.Now().Unix() >= t.Expires-120 {
		n, e := a.exchange(ctx, url.Values{"client_id": {id}, "grant_type": {"refresh_token"}, "refresh_token": {t.Refresh}})
		if e != nil {
			return t, e
		}
		if n.Refresh == "" {
			n.Refresh = t.Refresh
		}
		t = n
		a.Store.Put("auth", p, t)
	}
	return t, nil
}
func (a *Accounts) Logout(p string) error {
	a.Store.Delete("accounts", p)
	return a.Store.Delete("auth", p)
}
func (a *Accounts) Profiles() []Account {
	out := []Account{}
	for _, p := range []string{"anilist", "mal"} {
		var v Account
		a.Store.Get("accounts", p, &v)
		v.Provider = p
		var t Token
		v.Connected = a.Store.Get("auth", p, &t) == nil && t.Access != ""
		out = append(out, v)
	}
	return out
}
func (a *Accounts) Profile(ctx context.Context, p, id string) (Account, error) {
	out := Account{Provider: p}
	t, e := a.token(ctx, p, id)
	if e != nil {
		return out, e
	}
	out.Connected = true
	if p == "anilist" {
		var r struct {
			Viewer struct {
				ID     int    `json:"id"`
				Name   string `json:"name"`
				Avatar struct {
					Large string `json:"large"`
				} `json:"avatar"`
				Statistics struct {
					Anime struct {
						Count    int `json:"count"`
						Episodes int `json:"episodesWatched"`
						Minutes  int `json:"minutesWatched"`
					} `json:"anime"`
				} `json:"statistics"`
			} `json:"Viewer"`
		}
		e = a.Meta.Query(ctx, `query {Viewer {id name avatar {large} statistics {anime {count episodesWatched minutesWatched}}}}`, nil, t.Access, &r)
		out.ID = r.Viewer.ID
		out.Name = r.Viewer.Name
		out.Avatar = r.Viewer.Avatar.Large
		out.AnimeCount = r.Viewer.Statistics.Anime.Count
		out.Episodes = r.Viewer.Statistics.Anime.Episodes
		out.Minutes = r.Viewer.Statistics.Anime.Minutes
	} else {
		if e = a.MALGate.Wait(ctx); e != nil {
			return out, e
		}
		var r struct {
			ID      int    `json:"id"`
			Name    string `json:"name"`
			Picture string `json:"picture"`
			Stats   struct {
				Count    int     `json:"num_items"`
				Episodes int     `json:"num_episodes"`
				Days     float64 `json:"num_days_watched"`
			} `json:"anime_statistics"`
		}
		e = a.Client.JSON(ctx, "GET", a.malAPIBase()+"/users/@me?fields=anime_statistics,picture", nil, map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": id}, &r)
		out.ID = r.ID
		out.Name = r.Name
		out.Avatar = r.Picture
		out.AnimeCount = r.Stats.Count
		out.Episodes = r.Stats.Episodes
		out.Minutes = int(r.Stats.Days * 1440)
	}
	if e != nil {
		return out, e
	}
	var cached Account
	if a.Store.Get("accounts", p, &cached) == nil && out.AnimeCount == 0 && out.Episodes == 0 && cached.AnimeCount > 0 {
		out.AnimeCount = cached.AnimeCount
		out.Episodes = cached.Episodes
		out.Minutes = cached.Minutes
	}
	return out, a.Store.Put("accounts", p, out)
}
func (a *Accounts) Sync(ctx context.Context, p, clientID string, mediaID, episode, total int) error {
	if p != "anilist" && p != "mal" {
		return fmt.Errorf("integração desconhecida")
	}
	if mediaID <= 0 {
		return fmt.Errorf("anime sem correspondência no tracker")
	}
	if episode <= 0 {
		return fmt.Errorf("número de episódio inválido para sincronização")
	}
	// A read-before-write prevents an older/replayed episode from moving a
	// user's remote list backwards. Serialize updates so concurrent player
	// events cannot race between that read and the mutation.
	a.syncMu.Lock()
	defer a.syncMu.Unlock()
	t, e := a.token(ctx, p, clientID)
	if e != nil {
		return e
	}
	status := "CURRENT"
	if total > 0 && episode >= total {
		status = "COMPLETED"
	}
	if p == "anilist" {
		var current struct {
			Media struct {
				Entry *struct {
					Progress int    `json:"progress"`
					Status   string `json:"status"`
				} `json:"mediaListEntry"`
			} `json:"Media"`
		}
		if e := a.Meta.Query(ctx, `query($id:Int){Media(id:$id){mediaListEntry{progress status}}}`, map[string]any{"id": mediaID}, t.Access, &current); e != nil {
			return fmt.Errorf("AniList: leitura do progresso atual: %w", e)
		}
		if entry := current.Media.Entry; entry != nil {
			if entry.Status == "COMPLETED" || entry.Progress > episode || (entry.Progress == episode && entry.Status == status) {
				return nil
			}
		}
		var result any
		return a.Meta.Query(ctx, `mutation($id:Int,$ep:Int,$status:MediaListStatus){SaveMediaListEntry(mediaId:$id,progress:$ep,status:$status){id progress}}`, map[string]any{"id": mediaID, "ep": episode, "status": status}, t.Access, &result)
	}
	if status == "CURRENT" {
		status = "watching"
	} else {
		status = "completed"
	}
	if e = a.MALGate.Wait(ctx); e != nil {
		return e
	}
	var current struct {
		ListStatus *struct {
			Status   string `json:"status"`
			Episodes int    `json:"num_episodes_watched"`
		} `json:"my_list_status"`
	}
	if e = a.Client.JSON(ctx, "GET", fmt.Sprintf("%s/anime/%d?fields=my_list_status", a.malAPIBase(), mediaID), nil, map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": clientID}, &current); e != nil {
		return fmt.Errorf("MyAnimeList: leitura do progresso atual: %w", e)
	}
	if entry := current.ListStatus; entry != nil {
		if entry.Status == "completed" || entry.Episodes > episode || (entry.Episodes == episode && entry.Status == status) {
			return nil
		}
	}
	if e = a.MALGate.Wait(ctx); e != nil {
		return e
	}
	r, e := a.Client.Do(ctx, "PATCH", fmt.Sprintf("%s/anime/%d/my_list_status", a.malAPIBase(), mediaID), []byte(url.Values{"status": {strings.ToLower(status)}, "num_watched_episodes": {fmt.Sprint(episode)}}.Encode()), map[string]string{"Authorization": "Bearer " + t.Access, "X-MAL-CLIENT-ID": clientID, "Content-Type": "application/x-www-form-urlencoded"})
	if r != nil {
		r.Body.Close()
	}
	return e
}
